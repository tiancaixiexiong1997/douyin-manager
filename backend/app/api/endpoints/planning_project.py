from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.models.database import TaskStatus, User
from app.models.db_session import get_db
from app.repository.operation_log_repo import operation_log_repo
from app.repository.planning_repo import planning_repository
from app.repository.task_center_repo import task_center_repo
from app.schemas.planning import (
    CalendarRegenerateRequest,
    PlanningCreateRequest,
    PlanningListResponse,
    PlanningPagedResponse,
    PlanningResponse,
    PlanningUpdateRequest,
)
from app.services.cancellation import cancellation_registry
from app.services.crawler_service import crawler_service
from app.services.job_queue import enqueue_task
from app.services.planning_calendar_utils import (
    attach_normalized_content_calendar,
    build_calendar_task_context,
    build_strategy_task_context,
)

router = APIRouter()


def _build_project_client_data(project) -> dict:
    return {
        "client_name": project.client_name,
        "industry": project.industry,
        "target_audience": project.target_audience,
        "unique_advantage": project.unique_advantage,
        "ip_requirements": project.ip_requirements,
        "style_preference": project.style_preference,
        "business_goal": project.business_goal,
        "reference_blogger_ids": project.reference_blogger_ids or [],
    }


async def _enqueue_strategy_generation(
    *,
    db: AsyncSession,
    project,
    current_user: User,
    client_data: dict,
    blogger_ids: list,
    task_key: str,
    action: str,
    detail: str,
) -> dict:
    previous_status = project.status
    project.status = "strategy_generating"
    cancellation_registry.clear(project.id)
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_generate",
        title=f"生成定位：{getattr(project, 'client_name', project.id)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="定位生成任务已提交",
        context=build_strategy_task_context(project),
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_generate",
            project.id,
            client_data,
            blogger_ids,
            task_key,
            previous_status,
            job_id=task_key,
            description=f"planning strategy {project.id}",
        )
    except RuntimeError as exc:
        project = await planning_repository.get_by_id(db, project.id)
        if project:
            project.status = previous_status
        await operation_log_repo.create(
            db,
            action="planning.enqueue_failed",
            entity_type="planning_project",
            entity_id=project.id,
            actor=current_user.username,
            detail="定位生成任务入队失败，状态已回退",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="定位生成任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await operation_log_repo.create(
        db,
        action=action,
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail=detail,
        extra={"status": "strategy_generating"},
    )
    await db.commit()
    return {"message": "已开始生成账号定位方案", "status": "strategy_generating"}


@router.post("", response_model=PlanningListResponse, summary="创建策划项目")
async def create_planning(
    request: PlanningCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """创建账号策划项目。"""
    account_info = {}
    if request.account_homepage_url:
        user_info = await crawler_service.parse_user_url(request.account_homepage_url)
        if user_info:
            account_info = {
                "account_homepage_url": request.account_homepage_url,
                "account_nickname": user_info.get("nickname"),
                "account_avatar_url": user_info.get("avatar_url"),
                "account_signature": user_info.get("signature"),
                "account_follower_count": user_info.get("follower_count"),
                "account_video_count": user_info.get("video_count"),
            }
        else:
            account_info = {"account_homepage_url": request.account_homepage_url}

    project = await planning_repository.create(
        db,
        {
            "client_name": request.client_name,
            "industry": request.industry,
            "target_audience": request.target_audience,
            "unique_advantage": request.unique_advantage,
            "ip_requirements": request.ip_requirements,
            "style_preference": request.style_preference,
            "business_goal": request.business_goal,
            "reference_blogger_ids": request.reference_blogger_ids,
            "status": "draft",
            **account_info,
        },
    )
    await operation_log_repo.create(
        db,
        action="planning.create",
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail="创建账号策划项目",
        extra={
            "client_name": request.client_name,
            "industry": request.industry,
            "reference_count": len(request.reference_blogger_ids or []),
        },
    )
    await db.commit()
    return project


@router.post("/{project_id}/generate-strategy", summary="生成账号定位方案")
async def generate_strategy(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status in {"strategy_generating", "calendar_generating", "in_progress"}:
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")

    return await _enqueue_strategy_generation(
        db=db,
        project=project,
        current_user=current_user,
        client_data=_build_project_client_data(project),
        blogger_ids=project.reference_blogger_ids or [],
        task_key=f"planning:{project.id}:generate-strategy",
        action="planning.generate_strategy",
        detail="生成账号定位方案",
    )


@router.get("", response_model=list[PlanningListResponse] | PlanningPagedResponse, summary="获取所有策划项目")
async def list_projects(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int | None = Query(None, ge=1, le=200, description="返回条数上限（不传则返回全部）"),
    keyword: str | None = Query(None, description="关键词：匹配客户名/行业/受众/账号昵称"),
    status: str | None = Query(None, description="状态筛选：draft/in_progress/completed"),
    with_meta: bool = Query(False, description="是否返回分页元信息（total/has_more）"),
    db: AsyncSession = Depends(get_db),
):
    """获取策划项目列表（支持分页）"""
    normalized_keyword = (keyword or "").strip() or None
    normalized_status = (status or "").strip() or None
    items = await planning_repository.list_all(
        db,
        skip=skip,
        limit=limit,
        keyword=normalized_keyword,
        status=normalized_status,
    )
    if not with_meta:
        return items

    total = await planning_repository.count_all(
        db,
        keyword=normalized_keyword,
        status=normalized_status,
    )
    effective_limit = limit if limit is not None else len(items)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": effective_limit,
        "has_more": skip + len(items) < total,
    }


@router.get("/{project_id}", response_model=PlanningResponse, summary="获取策划详情")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取策划项目详情（含账号定位、内容日历）"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return attach_normalized_content_calendar(project)


@router.post("/{project_id}/retry", summary="重新生成账号定位方案")
async def retry_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """重新生成账号定位方案。"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status in {"strategy_generating", "calendar_generating", "in_progress"}:
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")

    return await _enqueue_strategy_generation(
        db=db,
        project=project,
        current_user=current_user,
        client_data=_build_project_client_data(project),
        blogger_ids=project.reference_blogger_ids or [],
        task_key=f"planning:{project.id}:retry",
        action="planning.retry",
        detail="重新生成账号定位方案",
    )


@router.patch("/{project_id}", response_model=PlanningResponse, summary="编辑策划项目基本信息")
async def update_project(
    project_id: str,
    request: PlanningUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """部分更新策划项目的客户信息和IP需求字段"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = request.model_dump(exclude_none=True)
    project = await planning_repository.update_project_info(db, project_id, data)
    await operation_log_repo.create(
        db,
        action="planning.update",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="更新策划项目信息",
        extra={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(project)
    return attach_normalized_content_calendar(project)


@router.post("/{project_id}/regenerate-calendar", summary="基于当前定位生成或重生成30天内容日历")
async def regenerate_calendar(
    project_id: str,
    payload: CalendarRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """基于当前账号定位，生成或重生成 30 天内容日历。"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status in {"strategy_generating", "calendar_generating", "in_progress"}:
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法单独生成日历")
    previous_status = project.status
    selected_days = sorted({day for day in payload.regenerate_day_numbers if isinstance(day, int) and 1 <= day <= 30})

    project.status = "calendar_generating"
    cancellation_registry.clear(project_id)
    await db.commit()

    task_key = f"planning:{project.id}:calendar"
    has_performance_recap = bool(
        isinstance(project.account_plan, dict) and isinstance(project.account_plan.get("performance_recap"), dict)
    )
    has_existing_calendar = bool(project.content_calendar) or bool(project.content_items)
    is_partial_regenerate = has_existing_calendar and bool(selected_days)
    calendar_task_title = "局部重生成日历" if is_partial_regenerate else ("重生成日历" if has_existing_calendar else "生成日历")
    queue_message = (
        f"已提交局部重生成任务，将重写 Day {', '.join(str(day) for day in selected_days)}"
        if is_partial_regenerate
        else "30天日历生成任务已提交，AI 将结合最新复盘建议优化选题"
        if has_performance_recap
        else "30天日历生成任务已提交"
    )
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_calendar",
        title=f"{calendar_task_title}：{getattr(project, 'client_name', project_id)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message=queue_message,
        context=build_calendar_task_context(project, selected_days),
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_calendar_generate",
            project.id,
            _build_project_client_data(project),
            project.account_plan,
            task_key,
            selected_days,
            job_id=task_key,
            description=f"planning calendar {project.id}",
        )
    except RuntimeError as exc:
        project = await planning_repository.get_by_id(db, project_id)
        if project:
            project.status = previous_status
        await operation_log_repo.create(
            db,
            action="planning.enqueue_failed",
            entity_type="planning_project",
            entity_id=project_id,
            actor=current_user.username,
            detail="30天日历任务入队失败，状态已回退",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="30天日历任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await operation_log_repo.create(
        db,
        action="planning.regenerate_calendar",
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail="生成30天内容日历" if not has_existing_calendar else "重新生成30天内容日历",
        extra={"status": "calendar_generating", "has_performance_recap": has_performance_recap},
    )

    return {"message": "已开始生成30天内容日历", "status": "calendar_generating"}


@router.delete("/{project_id}", summary="删除策划项目")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """删除策划项目（同时取消进行中的后台生成任务）"""
    cancellation_registry.cancel(project_id)
    deleted = await planning_repository.delete(db, project_id)
    if not deleted:
        cancellation_registry.clear(project_id)
        raise HTTPException(status_code=404, detail="项目不存在")
    await operation_log_repo.create(
        db,
        action="planning.delete",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="删除策划项目",
    )
    return {"message": "删除成功"}
