"""
视频脚本拆解复刻 API 端点
"""
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.models.db_session import get_db
from app.models.database import ExtractionStatus, TaskStatus, User
from app.schemas.script import (
    ExtractionCreateRequest,
    ExtractionDraftResponse,
    ExtractionDraftUpsertRequest,
    ExtractionResponse,
    ExtractionListResponse,
    ExtractionUpdateRequest,
)
from app.repository.script_repo import script_repo
from app.repository.script_draft_repo import script_draft_repo
from app.repository.operation_log_repo import operation_log_repo
from app.repository.task_center_repo import task_center_repo
from app.services.crawler_service import crawler_service
from app.services.ai_analysis_service import ai_analysis_service
from app.services.job_queue import enqueue_task

router = APIRouter()
logger = logging.getLogger(__name__)
DEFAULT_MAX_RETRIES = 1


def _is_transient_error(error_text: str) -> bool:
    text = (error_text or "").lower()
    transient_tokens = (
        "timeout", "timed out", "network", "connection", "temporarily", "temporarily unavailable",
        "429", "502", "503", "504", "rate limit", "超时", "网络", "连接", "繁忙", "网关",
    )
    return any(token in text for token in transient_tokens)


def _retry_backoff_seconds(retry_index: int) -> float:
    # retry_index: 1,2,3...
    return min(2.0 * retry_index, 6.0)


@router.post("/extract", response_model=ExtractionResponse, summary="提交脚本拆解复刻任务")
async def create_extraction_task(
    request: ExtractionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    接收用户视频链接和提示词：
    1. 立即返回一条 Pending 状态的记录。
    2. 后台开始爬取无水印视频、提取亮点并执行 AI 复刻脚本。
    """
    # 存入数据库
    record = await script_repo.create(db, {
        "source_video_url": request.source_video_url,
        "user_prompt": request.user_prompt,
        "plan_id": request.plan_id,
        "status": ExtractionStatus.PENDING,
        "retry_count": 0,
        "max_retries": DEFAULT_MAX_RETRIES,
    })
    await operation_log_repo.create(
        db,
        action="script.create",
        entity_type="script_extraction",
        entity_id=record.id,
        actor=current_user.username,
        detail="创建脚本拆解任务",
        extra={
            "source_video_url": request.source_video_url,
            "plan_id": request.plan_id,
            "max_retries": DEFAULT_MAX_RETRIES,
        },
    )
    await db.commit()

    task_key = f"script:{record.id}"
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="script_extraction",
        title=f"脚本拆解：{request.source_video_url[:40]}",
        entity_type="script_extraction",
        entity_id=record.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="任务已提交，等待执行",
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_script_extraction",
            record.id,
            request.source_video_url,
            request.user_prompt,
            request.plan_id,
            task_key,
            job_id=task_key,
            description=f"script extraction {record.id}",
        )
    except RuntimeError as exc:
        await script_repo.update_status(
            db,
            record.id,
            ExtractionStatus.FAILED,
            error_message=str(exc),
        )
        await operation_log_repo.create(
            db,
            action="script.enqueue_failed",
            entity_type="script_extraction",
            entity_id=record.id,
            actor="system",
            detail="脚本拆解任务入队失败",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="脚本拆解任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return record


@router.get("", response_model=list[ExtractionListResponse], summary="获取所有脚本拆解历史")
async def list_extractions(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """获取所有历史记录"""
    return await script_repo.list_all(db, skip=skip, limit=limit)


@router.get("/draft", response_model=ExtractionDraftResponse, summary="获取当前用户脚本草稿")
async def get_extraction_draft(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    draft = await script_draft_repo.get_by_user_id(db, current_user.id)
    if not draft:
        return ExtractionDraftResponse(source_video_url="", user_prompt="", plan_id=None, updated_at=None)
    return draft


@router.put("/draft", response_model=ExtractionDraftResponse, summary="保存当前用户脚本草稿")
async def upsert_extraction_draft(
    request: ExtractionDraftUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    draft = await script_draft_repo.upsert(
        db,
        user_id=current_user.id,
        source_video_url=request.source_video_url or "",
        user_prompt=request.user_prompt or "",
        plan_id=request.plan_id,
    )
    return draft


@router.get("/{extraction_id}", response_model=ExtractionResponse, summary="获取特定拆解结果与状态")
async def get_extraction(extraction_id: str, db: AsyncSession = Depends(get_db)):
    """前端轮询或查看特定记录详细内容"""
    record = await script_repo.get_by_id(db, extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@router.patch("/{extraction_id}", response_model=ExtractionResponse, summary="更新脚本拆解结果")
async def update_extraction(
    extraction_id: str,
    request: ExtractionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    record = await script_repo.get_by_id(db, extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    data = request.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="没有可更新的内容")

    record = await script_repo.update(db, extraction_id, data)
    await operation_log_repo.create(
        db,
        action="script.update",
        entity_type="script_extraction",
        entity_id=extraction_id,
        actor=current_user.username,
        detail="更新脚本拆解结果",
        extra={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{extraction_id}", summary="删除特定拆解记录")
async def delete_extraction(
    extraction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """删除记录"""
    record = await script_repo.get_by_id(db, extraction_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")

    success = await script_repo.delete(db, extraction_id)
    if not success:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    await operation_log_repo.create(
        db,
        action="script.delete",
        entity_type="script_extraction",
        entity_id=extraction_id,
        actor=current_user.username,
        detail="删除脚本拆解任务",
        extra={"status": record.status},
    )
    return {"message": "删除成功"}


async def _process_extraction_background(
    extraction_id: str,
    source_url: str,
    user_prompt: str,
    plan_id: str | None = None,
    task_key: str | None = None,
):
    """后台异步执行拆解和复刻流程"""
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or f"script:{extraction_id}"
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="script_extraction",
            title=f"脚本拆解任务：{extraction_id[:8]}",
            entity_type="script_extraction",
            entity_id=extraction_id,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message="任务开始执行",
        )
        await db.commit()

        record = await script_repo.get_by_id(db, extraction_id)
        max_retries = record.max_retries if record else DEFAULT_MAX_RETRIES

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.warning(
                        "[Script] 任务 %s 开始第 %s 次重试", extraction_id, attempt
                    )
                    await operation_log_repo.create(
                        db,
                        action="script.retry",
                        entity_type="script_extraction",
                        entity_id=extraction_id,
                        actor="system",
                        detail=f"脚本拆解任务第 {attempt} 次重试",
                        extra={"retry_count": attempt, "max_retries": max_retries},
                    )

                await _run_extraction_pipeline(
                    db=db,
                    extraction_id=extraction_id,
                    source_url=source_url,
                    user_prompt=user_prompt,
                    plan_id=plan_id,
                    task_key=resolved_task_key,
                )

                await script_repo.update(
                    db,
                    extraction_id,
                    {"status": ExtractionStatus.COMPLETED, "error_message": None},
                )
                await operation_log_repo.create(
                    db,
                    action="script.completed",
                    entity_type="script_extraction",
                    entity_id=extraction_id,
                    actor="system",
                    detail="脚本拆解任务完成",
                    extra={"retry_count": attempt, "max_retries": max_retries},
                )
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.COMPLETED.value,
                    progress_step="done",
                    message="脚本拆解已完成",
                )
                await db.commit()
                logger.info("[Script] 任务 %s 成功完成（重试次数: %s）", extraction_id, attempt)
                return

            except Exception as e:
                error_text = str(e)
                is_last_try = attempt >= max_retries
                can_retry = (not is_last_try) and _is_transient_error(error_text)
                logger.error(
                    "[Script] 任务 %s 第 %s 次执行失败: %s", extraction_id, attempt + 1, error_text
                )

                if can_retry:
                    retry_count = attempt + 1
                    await script_repo.mark_retry(db, extraction_id, retry_count=retry_count, error_message=error_text)
                    await operation_log_repo.create(
                        db,
                        action="script.retry.scheduled",
                        entity_type="script_extraction",
                        entity_id=extraction_id,
                        actor="system",
                        detail=f"检测到临时错误，准备第 {retry_count} 次重试",
                        extra={"error": error_text, "retry_count": retry_count, "max_retries": max_retries},
                    )
                    await task_center_repo.update_status(
                        db,
                        resolved_task_key,
                        status=TaskStatus.RUNNING.value,
                        progress_step=f"retry_{retry_count}",
                        message=f"临时错误，准备第 {retry_count} 次重试",
                        error_message=error_text,
                    )
                    await db.commit()
                    await asyncio.sleep(_retry_backoff_seconds(retry_count))
                    continue

                await script_repo.update_status(
                    db,
                    extraction_id,
                    ExtractionStatus.FAILED,
                    error_message=error_text,
                )
                await operation_log_repo.create(
                    db,
                    action="script.failed",
                    entity_type="script_extraction",
                    entity_id=extraction_id,
                    actor="system",
                    detail="脚本拆解任务失败",
                    extra={
                        "error": error_text,
                        "retry_count": attempt,
                        "max_retries": max_retries,
                    },
                )
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.FAILED.value,
                    progress_step="failed",
                    message="脚本拆解失败",
                    error_message=error_text,
                )
                await db.commit()
                return


async def _run_extraction_pipeline(
    *,
    db: AsyncSession,
    extraction_id: str,
    source_url: str,
    user_prompt: str,
    plan_id: str | None = None,
    task_key: str | None = None,
) -> None:
    resolved_task_key = task_key or f"script:{extraction_id}"
    # 1. 爬取视频真实直链
    await script_repo.update_status(db, extraction_id, ExtractionStatus.ANALYZING)
    await task_center_repo.update_status(
        db,
        resolved_task_key,
        status=TaskStatus.RUNNING.value,
        progress_step="analyzing",
        message="解析视频信息中",
    )

    logger.info("开始爬取复刻视频基础信息: %s", source_url)
    video_data = await crawler_service.get_single_video_by_url(source_url)

    if not video_data or not video_data.get("video_url"):
        error_msg = "爬虫未能提取到无水印视频链接（可能是视频链接有误、已被删除或遇到平台风控）。请提供有效的短链进行重试。"
        raise ValueError(error_msg)

    # 更新爬取到的基本信息
    await script_repo.update(
        db,
        extraction_id,
        {
            "parsed_video_url": video_data.get("video_url"),
            "title": video_data.get("title"),
            "description": video_data.get("description"),
            "cover_url": video_data.get("cover_url"),
            "status": ExtractionStatus.GENERATING,
        },
    )
    await task_center_repo.update_status(
        db,
        resolved_task_key,
        status=TaskStatus.RUNNING.value,
        progress_step="ai_generate",
        message="AI 正在生成复刻脚本",
    )
    await db.commit()

    # 2. 获取策划案的账号定位数据（如果绑定了策划）
    account_plan_data = None
    if plan_id:
        from app.repository.planning_repo import planning_repository

        project = await planning_repository.get_by_id(db, plan_id)
        if project and getattr(project, "account_plan", None):
            account_plan_data = {
                "target_audience": project.target_audience,
                "core_identity": project.account_plan.get("account_positioning", {}).get("core_identity", ""),
            }
            logger.info("读取到账号策划绑定: %s, 人设: %s", plan_id, account_plan_data["core_identity"])

    # 3. 调用 AI 进行多模态拆解和生成
    logger.info("[Script] 开始提取 %s 并生成复刻脚本...", extraction_id)
    result = await ai_analysis_service.generate_remake_script(
        video_url=video_data["video_url"],
        title=video_data.get("title", ""),
        description=video_data.get("description", ""),
        user_prompt=user_prompt,
        account_plan_data=account_plan_data,
        video_id=video_data.get("video_id"),
        run_context={"entity_type": "script_extraction", "entity_id": extraction_id},
        db=db,
    )

    if "error" in result:
        raise ValueError(result["error"])

    # 4. 结果入库
    await script_repo.update(
        db,
        extraction_id,
        {
            "highlight_analysis": result.get("highlight_analysis"),
            "generated_script": result.get("generated_script"),
        },
    )
    await db.commit()
