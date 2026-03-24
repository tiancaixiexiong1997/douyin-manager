from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.models.database import TaskStatus, User
from app.models.db_session import get_db
from app.repository.blogger_repo import blogger_repository
from app.repository.operation_log_repo import operation_log_repo
from app.repository.planning_repo import planning_repository
from app.repository.task_center_repo import task_center_repo
from app.schemas.planning import (
    AccountHomepageUpdateRequest,
    ContentItemResponse,
    ContentItemUpdateRequest,
    PlanningListResponse,
    ScriptGenerateRequest,
)
from app.services.ai_analysis_service import ai_analysis_service
from app.services.crawler_service import crawler_service
from app.services.planning_calendar_utils import (
    attach_normalized_content_calendar,
    normalize_content_type,
)

router = APIRouter()


@router.patch("/{project_id}/homepage", response_model=PlanningListResponse, summary="补填/更新账号主页地址")
async def update_account_homepage(
    project_id: str,
    request: AccountHomepageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    为策划项目补填或更新账号主页地址，自动抓取头像、昵称、简介。
    创建时未填写的可在此补上。
    """
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    user_info = await crawler_service.parse_user_url(request.account_homepage_url)
    project.account_homepage_url = request.account_homepage_url
    if user_info:
        project.account_nickname = user_info.get("nickname")
        project.account_avatar_url = user_info.get("avatar_url")
        project.account_signature = user_info.get("signature")
        project.account_follower_count = user_info.get("follower_count")
        project.account_video_count = user_info.get("video_count")
    await operation_log_repo.create(
        db,
        action="planning.update_homepage",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="更新策划账号主页信息",
        extra={"account_homepage_url": request.account_homepage_url},
    )
    await db.commit()
    await db.refresh(project)
    return attach_normalized_content_calendar(project)


@router.post("/script/generate", summary="为单条内容生成完整脚本")
async def generate_script(
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    为内容日历中的某一条生成完整视频脚本
    （含分镜、台词、拍摄建议、发布文案）
    """
    item = await planning_repository.get_content_item(db, request.content_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="内容条目不存在")

    project = await planning_repository.get_by_id(db, item.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    task_key = f"planning:content-item:{item.id}:script-generate"
    existing_task = await task_center_repo.get_by_task_key(db, task_key)
    if existing_task and existing_task.status in (TaskStatus.QUEUED.value, TaskStatus.RUNNING.value):
        started_at = existing_task.started_at or existing_task.updated_at
        if started_at and (datetime.utcnow() - started_at) > timedelta(minutes=30):
            await task_center_repo.update_status(
                db,
                task_key,
                status=TaskStatus.FAILED.value,
                progress_step="timeout",
                message="脚本生成任务超时，已自动标记失败，可重新发起",
                error_message="task_timeout",
            )
            await db.commit()
        else:
            raise HTTPException(status_code=409, detail="该条内容脚本正在生成中，请稍后刷新查看")

    try:
        await task_center_repo.upsert_task(
            db,
            task_key=task_key,
            task_type="planning_script_generate",
            title=f"生成脚本：Day {item.day_number}",
            entity_type="content_item",
            entity_id=item.id,
            status=TaskStatus.RUNNING.value,
            progress_step="generating",
            message="AI 正在生成脚本",
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="该条内容脚本正在生成中，请稍后刷新查看")

    blogger_ids = list(set((project.reference_blogger_ids or []) + (request.reference_blogger_ids or [])))

    reference_bloggers = []
    for bid in blogger_ids[:3]:
        blogger = await blogger_repository.get_by_id(db, bid)
        if blogger and blogger.analysis_report:
            reference_bloggers.append(
                {
                    "nickname": blogger.nickname,
                    "analysis_report": blogger.analysis_report,
                }
            )

    try:
        script = await ai_analysis_service.generate_video_script(
            content_item={
                "title_direction": item.title_direction,
                "content_type": item.content_type,
                "key_message": item.tags,
            },
            account_plan=project.account_plan or {},
            reference_bloggers=reference_bloggers,
            run_context={"entity_type": "content_item", "entity_id": item.id},
            db=db,
        )

        if script.get("error"):
            await task_center_repo.update_status(
                db,
                task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="脚本生成失败",
                error_message=str(script.get("error", "unknown_error")),
            )
            await db.commit()
            raise HTTPException(status_code=500, detail=f"脚本生成失败: {script['error']}")

        await planning_repository.update_script(db, item.id, script)
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.COMPLETED.value,
            progress_step="completed",
            message="脚本生成完成",
            error_message=None,
        )
        await operation_log_repo.create(
            db,
            action="planning.generate_script",
            entity_type="content_item",
            entity_id=item.id,
            actor=current_user.username,
            detail="为内容条目生成完整脚本",
            extra={"project_id": item.project_id},
        )
        await db.commit()

        return {
            "status": "success",
            "content_item_id": item.id,
            "script": script,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="failed",
            message="脚本生成异常终止",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=500, detail="脚本生成异常，请稍后重试") from exc


@router.patch("/content-items/{item_id}", response_model=ContentItemResponse, summary="更新内容条目")
async def update_content_item(
    item_id: str,
    request: ContentItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """部分更新内容条目（标题方向、内容类型、标签、脚本）"""
    data = request.model_dump(exclude_none=True)
    if "content_type" in data:
        data["content_type"] = normalize_content_type(data.get("content_type"))
    item = await planning_repository.update_content_item(db, item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="内容条目不存在")
    await operation_log_repo.create(
        db,
        action="planning.update_content_item",
        entity_type="content_item",
        entity_id=item_id,
        actor=current_user.username,
        detail="更新内容条目",
        extra={"fields": list(data.keys())},
    )
    await db.commit()
    return item
