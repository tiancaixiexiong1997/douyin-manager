"""
博主 API 端点：博主 IP 库管理
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.config import settings
from app.models.db_session import get_db
from app.models.database import BloggerVideo, TaskStatus, User
from app.schemas.blogger import (
    BloggerCreateRequest,
    BloggerReanalyzeRequest,
    BloggerResponse,
    BloggerListResponse,
    BloggerPagedResponse,
    SetRepresentativeRequest,
)
from app.services.crawler_service import crawler_service, CrawlerServiceError
from app.services.ai_analysis_service import ai_analysis_service
from app.services.cancellation import cancellation_registry
from app.services.progress import progress_registry
from app.services.download_proxy_service import build_proxy_download_response
from app.services.job_queue import enqueue_task, get_queue
from app.repository.blogger_repo import blogger_repository
from app.repository.operation_log_repo import operation_log_repo
from app.repository.task_center_repo import task_center_repo

router = APIRouter()
logger = logging.getLogger(__name__)

ACTIVE_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}


def _is_blogger_related_job(blogger_id: str, job_id: str) -> bool:
    prefixes = (
        f"blogger:{blogger_id}:rep:",
        f"blogger:{blogger_id}:analyze",
        f"blogger:{blogger_id}:reanalyze",
        f"blogger:{blogger_id}:refresh-report",
        f"blogger:{blogger_id}:viral-profile",
    )
    return job_id.startswith(prefixes)


def _find_active_rep_pipeline_job(blogger_id: str) -> Optional[tuple[str, str]]:
    """
    检测同一博主是否已有代表作链路任务在执行/排队。
    代表作链路包含：
    - 代表作深度解析任务：blogger:{id}:rep:*
    - 代表作后续报告刷新：blogger:{id}:refresh-report
    """
    rep_prefix = f"blogger:{blogger_id}:rep:"
    refresh_job_id = f"blogger:{blogger_id}:refresh-report"
    try:
        from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

        queue = get_queue()

        started_ids = StartedJobRegistry(name=queue.name, connection=queue.connection).get_job_ids()
        for job_id in started_ids:
            if job_id.startswith(rep_prefix) or job_id == refresh_job_id:
                return job_id, "processing"

        queued_ids = list(queue.job_ids or [])
        scheduled_ids = ScheduledJobRegistry(name=queue.name, connection=queue.connection).get_job_ids()
        deferred_ids = DeferredJobRegistry(name=queue.name, connection=queue.connection).get_job_ids()
        for job_id in [*queued_ids, *scheduled_ids, *deferred_ids]:
            if job_id.startswith(rep_prefix) or job_id == refresh_job_id:
                return job_id, "queued"
    except Exception as exc:
        logger.warning("检测代表作链路任务失败(blogger=%s): %s", blogger_id, exc)
    return None


def _find_active_viral_profile_job(blogger_id: str) -> Optional[tuple[str, str]]:
    """检测同一博主是否已有爆款归因任务在执行/排队。"""
    job_id = f"blogger:{blogger_id}:viral-profile"
    try:
        queue = get_queue()
        existing = queue.fetch_job(job_id)
        if not existing:
            return None
        status = (existing.get_status() or "").lower()
        if status == "started":
            return job_id, "processing"
        if status in {"queued", "deferred", "scheduled"}:
            return job_id, "queued"
    except Exception as exc:
        logger.warning("检测爆款归因任务失败(blogger=%s): %s", blogger_id, exc)
    return None


def _get_blogger_queue_progress(blogger_id: str) -> Optional[dict]:
    """从 RQ 队列推断博主任务状态，避免前端出现“无反馈”。"""
    viral_prefix = f"blogger:{blogger_id}:viral-profile"
    try:
        from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

        queue = get_queue()
        started_ids = StartedJobRegistry(name=queue.name, connection=queue.connection).get_job_ids()
        for job_id in started_ids:
            if job_id.startswith(viral_prefix):
                return {"step": "viral_profile", "message": "爆款归因报告生成中..."}
            if _is_blogger_related_job(blogger_id, job_id):
                return {"step": "processing", "message": "任务执行中..."}

        queued_ids = list(queue.job_ids or [])
        scheduled_ids = ScheduledJobRegistry(name=queue.name, connection=queue.connection).get_job_ids()
        deferred_ids = DeferredJobRegistry(name=queue.name, connection=queue.connection).get_job_ids()
        for job_id in [*queued_ids, *scheduled_ids, *deferred_ids]:
            if job_id.startswith(viral_prefix):
                return {"step": "viral_profile_queued", "message": "爆款归因任务排队中..."}
            if _is_blogger_related_job(blogger_id, job_id):
                return {"step": "queued", "message": "任务排队中..."}
    except Exception as exc:
        logger.warning("读取博主队列进度失败(blogger=%s): %s", blogger_id, exc)
    return None


def _enqueue_report_refresh_if_needed(blogger_id: str) -> bool:
    """仅在刷新任务未运行时入队，避免同一 job_id 重复排队。"""
    refresh_job_id = f"blogger:{blogger_id}:refresh-report"
    try:
        queue = get_queue()
        existing = queue.fetch_job(refresh_job_id)
        if existing:
            status = (existing.get_status() or "").lower()
            if status in ACTIVE_JOB_STATUSES:
                return False
            try:
                existing.delete()
            except Exception:
                logger.warning(
                    "删除历史刷新任务失败(job_id=%s status=%s)，继续尝试入队",
                    refresh_job_id,
                    status,
                )
    except Exception as exc:
        logger.warning("检查刷新任务状态失败(blogger=%s): %s", blogger_id, exc)

    enqueue_task(
        "app.tasks.run_blogger_report_refresh",
        blogger_id,
        job_id=refresh_job_id,
        description=f"blogger report refresh {blogger_id}",
    )
    return True


@router.post("", response_model=BloggerListResponse, summary="添加博主到IP库")
async def add_blogger(
    request: BloggerCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    添加博主：
    1. 解析博主主页链接获取基本信息
    2. 存入数据库
    3. 后台异步采集视频 + AI 分析
    """
    # 解析博主信息
    if request.start_date and request.end_date and request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")

    try:
        user_data = await crawler_service.parse_user_url(request.url, strict=True)
    except CrawlerServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user_data:
        raise HTTPException(status_code=400, detail="无法解析博主主页，请检查链接是否正确")

    # 检查是否已存在
    existing = await blogger_repository.get_by_platform_id(
        db, user_data["platform"], user_data["blogger_id"]
    )
    if existing:
        raise HTTPException(status_code=409, detail="该博主已在IP库中")

    # 保存博主基本信息
    blogger = await blogger_repository.create(db, {
        "platform": user_data["platform"],
        "blogger_id": user_data["blogger_id"],
        "nickname": user_data["nickname"],
        "avatar_url": user_data.get("avatar_url"),
        "signature": user_data.get("signature"),
        "representative_video_url": request.representative_video_url,
        "follower_count": user_data.get("follower_count", 0),
        "following_count": user_data.get("following_count", 0),
        "total_like_count": user_data.get("total_like_count", 0),
        "video_count": user_data.get("video_count", 0),
        "incremental_enabled": request.incremental_mode,
    })
    # 先提交博主记录，避免队列任务先于事务提交执行导致脏读/找不到数据。
    await db.commit()
    await db.refresh(blogger)

    task_key = f"blogger:{blogger.id}:analyze"
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="blogger_collect",
        title=f"采集博主：{blogger.nickname}",
        entity_type="blogger",
        entity_id=blogger.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="任务已提交，等待执行",
    )
    await db.commit()

    try:
        effective_sample_count = None if (request.start_date or request.end_date) else request.sample_count
        enqueue_task(
            "app.tasks.run_blogger_analyze",
            blogger.id,
            user_data,
            effective_sample_count,
            request.representative_video_url,
            request.start_date,
            request.end_date,
            False,
            request.incremental_mode,
            task_key,
            job_id=task_key,
            description=f"blogger analyze {blogger.id}",
        )
    except RuntimeError as exc:
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="任务入队失败",
            error_message=str(exc),
        )
        await blogger_repository.delete(db, blogger.id)
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return blogger


@router.get("", response_model=list[BloggerListResponse] | BloggerPagedResponse, summary="获取博主IP库列表")
async def list_bloggers(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: Optional[int] = Query(None, ge=1, le=200, description="返回条数上限（不传则返回全部）"),
    keyword: Optional[str] = Query(None, description="关键词：匹配昵称/简介/平台ID"),
    platform: Optional[str] = Query(None, description="平台筛选：douyin/tiktok/bilibili"),
    with_meta: bool = Query(False, description="是否返回分页元信息（total/has_more）"),
    db: AsyncSession = Depends(get_db),
):
    """获取博主列表（支持分页）"""
    normalized_keyword = (keyword or "").strip() or None
    normalized_platform = (platform or "").strip() or None
    items = await blogger_repository.list_all(
        db,
        skip=skip,
        limit=limit,
        keyword=normalized_keyword,
        platform=normalized_platform,
    )
    if not with_meta:
        return items

    total = await blogger_repository.count_all(
        db,
        keyword=normalized_keyword,
        platform=normalized_platform,
    )
    effective_limit = limit if limit is not None else len(items)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": effective_limit,
        "has_more": skip + len(items) < total,
    }


@router.get("/proxy-download", summary="代理下载无水印视频（绕过浏览器跨域限制）")
async def proxy_download_video(
    url: str = Query(..., description="视频 CDN 地址"),
    filename: str = Query("video.mp4", description="下载文件名"),
    video_id: Optional[str] = Query(None, description="视频 ID，用于 URL 过期时重新获取"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """统一调用下载代理服务，复用安全校验与重试逻辑。"""
    await operation_log_repo.create(
        db,
        action="download.proxy",
        entity_type="video",
        entity_id=video_id,
        actor=current_user.username,
        detail="博主模块代理下载无水印视频",
        extra={
            "filename": filename,
            "video_id": video_id,
            "url_preview": url[:200],
        },
    )
    return await build_proxy_download_response(
        url=url,
        filename=filename,
        video_id=video_id,
        db=db,
    )


@router.get("/{blogger_id}", response_model=BloggerResponse, summary="获取博主详情")
async def get_blogger(blogger_id: str, db: AsyncSession = Depends(get_db)):
    """获取博主详情（含视频和分析报告）"""
    blogger = await blogger_repository.get_by_id(db, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")
    return blogger


@router.delete("/{blogger_id}", summary="删除博主")
async def delete_blogger(blogger_id: str, db: AsyncSession = Depends(get_db)):
    """从 IP 库删除博主（同时取消进行中的后台分析任务）"""
    # NOTE: 先发取消信号，后台任务检查到后会主动退出
    cancellation_registry.cancel(blogger_id)
    deleted = await blogger_repository.delete(db, blogger_id)
    if not deleted:
        # 清理取消信号（博主不存在，无需保留）
        cancellation_registry.clear(blogger_id)
        raise HTTPException(status_code=404, detail="博主不存在")
    return {"message": "删除成功"}


@router.get("/{blogger_id}/progress", summary="查询博主分析进度")
async def get_blogger_progress(
    blogger_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取博主后台分析任务当前进度"""
    progress = progress_registry.get(blogger_id)
    if progress and progress.get("step") in {"done", "failed"}:
        return JSONResponse(progress)

    queue_progress = _get_blogger_queue_progress(blogger_id)
    if queue_progress:
        return JSONResponse(queue_progress)

    # 队列里已无任务时，以任务中心最新终态为准，避免旧的 "queued" 进度残留。
    latest_task = await task_center_repo.get_latest_for_entity(
        db,
        entity_type="blogger",
        entity_id=blogger_id,
    )
    if latest_task:
        status = (latest_task.status or "").lower()
        if status in {TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value}:
            progress_registry.set(blogger_id, "done")
            return JSONResponse({
                "step": "done",
                "message": latest_task.message or "分析完成",
            })
        if status == TaskStatus.FAILED.value:
            progress_registry.set(blogger_id, "failed")
            return JSONResponse({
                "step": "failed",
                "message": latest_task.error_message or latest_task.message or "分析失败",
            })

    if not progress:
        return JSONResponse({"step": "idle", "message": "无进行中的任务"})
    return JSONResponse(progress)


@router.post("/{blogger_id}/generate-viral-profile", summary="生成博主爆款归因报告")
async def generate_blogger_viral_profile(
    blogger_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """触发后台任务：分析“这个账号怎么策划 + 为什么火 + 如何可复制”并写入 analysis_report。"""
    blogger = await blogger_repository.get_by_id(db, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")

    running_job = _find_active_viral_profile_job(blogger_id)
    if running_job:
        _, progress_step = running_job
        progress_registry.set(blogger_id, "viral_profile" if progress_step == "processing" else "viral_profile_queued")
        return {
            "message": "已有爆款归因任务执行中，请等待完成后再重试",
            "task_started": True,
            "task_enqueued": False,
        }

    task_key = f"blogger:{blogger_id}:viral-profile"
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="blogger_viral_profile",
        title=f"爆款归因：{blogger.nickname}",
        entity_type="blogger",
        entity_id=blogger_id,
        status=TaskStatus.QUEUED.value,
        progress_step="viral_profile_queued",
        message="爆款归因任务已提交",
    )
    await operation_log_repo.create(
        db,
        action="blogger.viral_profile.generate",
        entity_type="blogger",
        entity_id=blogger_id,
        actor=current_user.username,
        detail=f"触发博主爆款归因生成：{blogger.nickname}",
    )
    progress_registry.set(blogger_id, "viral_profile_queued")
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_blogger_viral_profile_generate",
            blogger_id,
            task_key,
            job_id=task_key,
            description=f"blogger viral profile {blogger_id}",
        )
    except RuntimeError as exc:
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="failed",
            message="爆款归因任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"message": "已开始生成爆款归因报告，请稍后查看", "task_started": True, "task_enqueued": True}


@router.post("/{blogger_id}/reanalyze", summary="重新采集并分析博主")
async def reanalyze_blogger(
    blogger_id: str,
    request: Optional[BloggerReanalyzeRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """重新采集博主最新视频数据并触发 AI 分析"""
    blogger = await blogger_repository.get_by_id(db, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")

    # 重新获取博主主页最新信息以拿到新的 sec_user_id
    logger.info(f"重新采集博主 {blogger.nickname}，重置分析状态")
    previous_is_analyzed = bool(blogger.is_analyzed)
    previous_report = blogger.analysis_report
    # 标记为分析中
    await blogger_repository.reset_analysis(db, blogger_id)
    await db.commit()

    if request and request.start_date and request.end_date and request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    sample_count = 100 if request is None else request.sample_count
    incremental_mode = False if request is None else bool(request.incremental_mode)

    user_data = {
        "platform": blogger.platform,
        "blogger_id": blogger.blogger_id,
        "nickname": blogger.nickname,
        "sec_user_id": blogger.blogger_id,
        "video_count": blogger.video_count,
    }
    # 尽量在重采集前刷新一次主页信息，确保作品总数/昵称等字段是最新值。
    if blogger.platform == "douyin":
        try:
            latest_user_data = await crawler_service.parse_user_url(
                f"https://www.douyin.com/user/{blogger.blogger_id}"
            )
            if latest_user_data:
                user_data.update({
                    "platform": latest_user_data.get("platform", blogger.platform),
                    "blogger_id": latest_user_data.get("blogger_id", blogger.blogger_id),
                    "nickname": latest_user_data.get("nickname", blogger.nickname),
                    "sec_user_id": latest_user_data.get("sec_user_id", blogger.blogger_id),
                    "video_count": latest_user_data.get("video_count", blogger.video_count),
                })
                blogger.nickname = latest_user_data.get("nickname") or blogger.nickname
                blogger.avatar_url = latest_user_data.get("avatar_url") or blogger.avatar_url
                blogger.signature = latest_user_data.get("signature") or blogger.signature
                blogger.follower_count = int(latest_user_data.get("follower_count") or blogger.follower_count or 0)
                blogger.following_count = int(latest_user_data.get("following_count") or blogger.following_count or 0)
                blogger.total_like_count = int(latest_user_data.get("total_like_count") or blogger.total_like_count or 0)
                latest_total = int(latest_user_data.get("video_count") or 0)
                if latest_total > 0:
                    blogger.video_count = latest_total
                await db.commit()
        except Exception as exc:
            logger.warning("重采集前刷新博主主页信息失败(blogger=%s): %s", blogger_id, exc)

    task_key = f"blogger:{blogger_id}:reanalyze"
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="blogger_collect",
        title=f"重新采集：{blogger.nickname}",
        entity_type="blogger",
        entity_id=blogger_id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="重采集任务已提交",
    )
    progress_registry.set(blogger_id, "queued", "重采集任务已提交")
    await db.commit()

    try:
        effective_sample_count = None if (request and (request.start_date or request.end_date)) else sample_count
        enqueue_task(
            "app.tasks.run_blogger_analyze",
            blogger_id,
            user_data,
            # NOTE: 重采集时删除旧视频以获得干净的新数据；默认 100，可通过请求覆盖
            effective_sample_count,
            blogger.representative_video_url,
            request.start_date if request else None,
            request.end_date if request else None,
            True,
            incremental_mode,
            task_key,
            job_id=task_key,
            description=f"blogger reanalyze {blogger_id}",
        )
    except RuntimeError as exc:
        blogger = await blogger_repository.get_by_id(db, blogger_id)
        if blogger:
            blogger.is_analyzed = previous_is_analyzed
            blogger.analysis_report = previous_report
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="重采集入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "已开始重新采集，请稍后查看进度"}


@router.post("/{blogger_id}/set-representative", summary="将指定视频设为代表作并深度解析")
async def set_representative(
    blogger_id: str,
    request: "SetRepresentativeRequest",
    db: AsyncSession = Depends(get_db)
):
    """
    将已采集列表中的某条视频设为代表作：
    1. 更新博主的 representative_video_url
    2. 删除旧的 rep_ 记录（若有）
    3. 后台对该视频 URL 异步执行 AI 深度析帧
    """
    blogger = await blogger_repository.get_by_id(db, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")

    # 同一博主同一时间仅允许一个代表作链路任务，避免并发触发多次重型 AI 调用。
    running_job = _find_active_rep_pipeline_job(blogger_id)
    if running_job:
        _, progress_step = running_job
        progress_registry.set(blogger_id, progress_step)
        return {
            "message": "已有代表作任务执行中，请等待当前任务完成后再设置新的代表作",
            "task_started": True,
            "task_enqueued": False,
        }

    rep_video_key = f"rep_{request.video_id}"
    existing_success_rep = next(
        (
            v
            for v in (blogger.videos or [])
            if (v.video_id or "") == rep_video_key
            and isinstance(v.ai_analysis, dict)
            and not v.ai_analysis.get("error")
            and not v.ai_analysis.get("raw_analysis")
        ),
        None,
    )
    if existing_success_rep:
        if blogger.representative_video_url != request.video_url:
            await blogger_repository.update_rep_url(db, blogger_id, request.video_url)
            await db.commit()
        progress_registry.set(blogger_id, "done")
        return {
            "message": "该视频已完成代表作解析，已直接复用现有结果",
            "task_started": False,
        }

    previous_rep_url = blogger.representative_video_url

    # 更新博主 representative_video_url 字段
    await blogger_repository.update_rep_url(db, blogger_id, request.video_url)
    await db.commit()

    # 统一使用固定 job_id，确保同一博主不出现并发代表作解析任务。
    job_id = f"blogger:{blogger_id}:rep:active"
    try:
        queue = get_queue()
        existing_job = queue.fetch_job(job_id)
        if existing_job:
            existing_status = (existing_job.get_status() or "").lower()
            if existing_status in ACTIVE_JOB_STATUSES:
                progress_registry.set(
                    blogger_id,
                    "processing" if existing_status == "started" else "queued",
                )
                return {
                    "message": "代表作任务正在处理中，请稍后在详情中查看结果",
                    "task_started": True,
                    "task_enqueued": False,
                }
            try:
                existing_job.delete()
            except Exception:
                logger.warning(
                    "删除历史代表作任务失败(job_id=%s status=%s)，继续尝试入队",
                    job_id,
                    existing_status,
                )
    except Exception as exc:
        logger.warning("检测代表作任务状态失败(job_id=%s): %s", job_id, exc)

    try:
        progress_registry.set(blogger_id, "queued")
        enqueue_task(
            "app.tasks.run_blogger_rep_video_analyze",
            blogger_id,
            {
                "video_url": request.video_url,
                "video_id": request.video_id,
                "title": request.title or "",
                "description": request.description or "",
                "cover_url": request.cover_url,
                "like_count": request.like_count or 0,
                "published_at": request.published_at,
            },
            job_id=job_id,
            description=f"blogger rep analyze {blogger_id}",
        )
    except RuntimeError as exc:
        blogger = await blogger_repository.get_by_id(db, blogger_id)
        if blogger:
            blogger.representative_video_url = previous_rep_url
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"message": "已开始深度解析，请稍后在详情中查看结果", "task_started": True, "task_enqueued": True}


@router.delete("/{blogger_id}/videos/{video_id}", summary="删除博主视频及分析记录")
async def delete_blogger_video(
    blogger_id: str,
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除博主指定的视频记录：
    1. 彻底从数据库删除
    2. 如果是代表作 (video_id 以 rep_ 开头)，触发后台任务重新生成该博主的综合分析报告
    """
    video = await db.get(BloggerVideo, video_id)
    if not video or video.blogger_id != blogger_id:
        raise HTTPException(status_code=404, detail="视频不存在")

    is_rep = video.video_id.startswith("rep_")
    should_refresh_report = bool(is_rep and settings.AUTO_REFRESH_REPORT_ON_REP_DELETE)
    await blogger_repository.delete_video_by_id(db, video_id)

    # 删除代表作时，如果它正好是当前指向的 representative_video_url，则顺便清空该字段。
    if is_rep:
        blogger = await blogger_repository.get_by_id(db, blogger_id)
        if blogger and (blogger.representative_video_url or "") == (video.video_url or ""):
            blogger.representative_video_url = None
    await db.commit()

    if should_refresh_report:
        # 仅在开启配置时，删除代表作后自动重算综合报告
        try:
            enqueued = _enqueue_report_refresh_if_needed(blogger_id)
            if enqueued:
                progress_registry.set(blogger_id, "refresh_queued")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    elif is_rep:
        logger.info("删除代表作后跳过综合报告重算（AUTO_REFRESH_REPORT_ON_REP_DELETE=false）")
        progress_registry.set(blogger_id, "done")

    return {
        "message": "删除成功",
        "is_rep_deleted": is_rep,
        "report_refresh_triggered": should_refresh_report,
    }


async def _update_blogger_report_background(blogger_uuid: str):
    """单独触发重新生成博主报告的后台任务"""
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            progress_registry.set(blogger_uuid, "ai_report")
            blogger = await blogger_repository.get_by_id(db, blogger_uuid)
            if blogger:
                all_videos = await blogger_repository.get_videos_by_blogger(db, blogger_uuid)
                # 提取参与分析的最新广度数据
                videos_text_data = [
                    {"title": v.title or "", "description": "", "like_count": v.like_count, "comment_count": v.comment_count}
                    for v in all_videos if not (v.video_id or "").startswith("rep_")
                ]
                # 搜集所有剩余的代表作深度分析结果
                all_rep_analyses = [
                    v.ai_analysis for v in all_videos
                    if (v.video_id or "").startswith("rep_") and v.ai_analysis
                ]
                
                report = await ai_analysis_service.generate_blogger_report(
                    blogger_info={
                        "nickname": blogger.nickname,
                        "platform": blogger.platform,
                        "follower_count": blogger.follower_count,
                        "signature": blogger.signature,
                        "video_count": blogger.video_count,
                    },
                    videos_text_data=videos_text_data,
                    videos_analysis=all_rep_analyses,
                    run_context={"entity_type": "blogger", "entity_id": blogger_uuid},
                    db=db,
                )
                await blogger_repository.update_analysis(db, blogger_uuid, report)
                await db.commit()
                logger.info(f"博主 {blogger_uuid} 报告在视频删除后已同步更新")
            
            progress_registry.set(blogger_uuid, "done")
        except Exception as e:
            logger.error(f"同步刷新博主报告失败: {e}", exc_info=True)
            progress_registry.set(blogger_uuid, "failed")


async def _generate_blogger_viral_profile_background(blogger_uuid: str, task_key: str | None = None):
    """后台生成博主爆款归因报告，并写入 analysis_report.viral_profile。"""
    from app.models.db_session import AsyncSessionLocal

    resolved_task_key = task_key or f"blogger:{blogger_uuid}:viral-profile"
    async with AsyncSessionLocal() as db:
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="blogger_viral_profile",
            title=f"爆款归因：{blogger_uuid}",
            entity_type="blogger",
            entity_id=blogger_uuid,
            status=TaskStatus.RUNNING.value,
            progress_step="viral_profile",
            message="正在生成爆款归因报告",
        )
        await db.commit()

        try:
            progress_registry.set(blogger_uuid, "viral_profile")
            blogger = await blogger_repository.get_by_id(db, blogger_uuid)
            if not blogger:
                raise RuntimeError("博主不存在")

            all_videos = await blogger_repository.get_videos_by_blogger(db, blogger_uuid)
            videos_text_data = [
                {
                    "title": v.title or "",
                    "description": v.description or "",
                    "like_count": v.like_count,
                    "comment_count": v.comment_count,
                    "share_count": v.share_count,
                    "published_at": v.published_at.isoformat() if isinstance(v.published_at, datetime) else None,
                }
                for v in all_videos
                if not (v.video_id or "").startswith("rep_")
            ]
            rep_analyses = [
                v.ai_analysis for v in all_videos
                if (v.video_id or "").startswith("rep_") and v.ai_analysis
            ]
            if not videos_text_data and not rep_analyses:
                raise RuntimeError("数据不足：请先完成博主采集或代表作解析")

            viral_profile = await ai_analysis_service.generate_blogger_viral_profile(
                blogger_info={
                    "nickname": blogger.nickname,
                    "platform": blogger.platform,
                    "follower_count": blogger.follower_count,
                    "signature": blogger.signature,
                    "video_count": blogger.video_count,
                },
                videos_text_data=videos_text_data,
                videos_analysis=rep_analyses,
                run_context={"entity_type": "blogger", "entity_id": blogger_uuid},
                db=db,
            )
            if not isinstance(viral_profile, dict):
                raise RuntimeError("AI 返回格式异常")
            if viral_profile.get("error"):
                raise RuntimeError(str(viral_profile.get("error")))
            if viral_profile.get("raw_analysis"):
                raise RuntimeError("AI 返回非结构化内容，请稍后重试")

            report = dict(blogger.analysis_report or {})
            report["viral_profile"] = viral_profile
            report["viral_profile_updated_at"] = datetime.utcnow().isoformat()
            await blogger_repository.update_analysis(db, blogger_uuid, report)
            await db.commit()

            progress_registry.set(blogger_uuid, "done")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message="爆款归因报告生成完成",
            )
            await db.commit()
        except Exception as exc:
            logger.error("生成博主爆款归因失败(blogger=%s): %s", blogger_uuid, exc, exc_info=True)
            progress_registry.set(blogger_uuid, "failed")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="爆款归因生成失败",
                error_message=str(exc),
            )
            await db.commit()


async def _analyze_single_rep_video(blogger_uuid: str, video_data: dict):
    """
    后台异步：对单条视频进行 AI 深度析帧并写入数据库
    同时将结果纳入博主综合报告重新生成（仅更新 AI 报告，不重新采集广度数据）
    """
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            progress_registry.set(blogger_uuid, "processing")

            # NOTE: 不删除旧代表作，直接追加——每条代表作都保留各自的深度分析
            # 对视频 URL 直接析帧（无需重新下载列表，直接用已有 video_url）
            logger.info(f"开始对代表作进行深度析帧: {video_data['video_url'][:60]}...")
            analysis = await ai_analysis_service.analyze_video_style(
                video_url=video_data["video_url"],
                title=video_data.get("title", ""),
                description=video_data.get("description", ""),
                video_id=video_data.get("video_id"),
                progress_task_id=blogger_uuid,
            )
            analysis_failed = (
                not isinstance(analysis, dict)
                or bool(analysis.get("error"))
                or bool(analysis.get("raw_analysis"))
            )
            if analysis_failed:
                logger.warning(
                    "代表作深度析帧未获得有效结构化结果(blogger=%s video=%s): %s",
                    blogger_uuid,
                    video_data.get("video_id"),
                    (analysis.get("error") if isinstance(analysis, dict) else "invalid-analysis"),
                )

            # 写入数据库（累加新代表作记录）
            await blogger_repository.upsert_video_by_blogger_video_id(
                db,
                blogger_id=blogger_uuid,
                video_id=f"rep_{video_data['video_id']}",
                data={
                    "title": f"[代表作] {video_data.get('title', '')}",
                    "description": video_data.get("description", ""),
                    "cover_url": video_data.get("cover_url"),
                    "video_url": video_data["video_url"],
                    "like_count": video_data.get("like_count", 0),
                    "published_at": video_data.get("published_at"),
                    "ai_analysis": analysis,
                    "is_analyzed": True,
                },
            )
            await db.commit()

            if analysis_failed:
                # 多模态分析失败时不触发综合报告，避免额外 AI 费用。
                failure_message = (
                    (analysis.get("error") if isinstance(analysis, dict) else None)
                    or "代表作深度析帧失败，请稍后重试"
                )
                progress_registry.set(blogger_uuid, "failed", failure_message)
                return

            logger.info("代表作深度析帧完成，提交综合报告刷新任务")
            try:
                enqueued = _enqueue_report_refresh_if_needed(blogger_uuid)
                if enqueued:
                    progress_registry.set(blogger_uuid, "refresh_queued")
                else:
                    progress_registry.set(blogger_uuid, "ai_report")
            except RuntimeError as refresh_exc:
                logger.error("代表作后续报告刷新入队失败(blogger=%s): %s", blogger_uuid, refresh_exc)
                progress_registry.set(blogger_uuid, "failed", f"综合报告刷新入队失败：{refresh_exc}")
                return

            logger.info(f"博主 {blogger_uuid} 代表作析帧完成")

        except Exception as e:
            logger.error(f"代表作深度解析失败: {e}", exc_info=True)
            progress_registry.set(blogger_uuid, "failed", f"代表作深度解析失败：{e}")


async def _analyze_blogger_background(
    blogger_uuid: str,
    user_data: dict,
    sample_count: Optional[int],
    representative_video_url: str | None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    refresh: bool = False,
    incremental_mode: bool = False,
    task_key: str | None = None,
):
    """
    后台异步任务：
    1. 广度：批量采集博主视频数据
    2. 深度：若有代表作，则下载并逐帧分析
    3. 生成博主综合报告
    """
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or (
            f"blogger:{blogger_uuid}:reanalyze" if refresh else f"blogger:{blogger_uuid}:analyze"
        )
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="blogger_collect",
            title=f"采集博主：{user_data.get('nickname', blogger_uuid)}",
            entity_type="blogger",
            entity_id=blogger_uuid,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message="任务开始执行",
        )
        await db.commit()

        try:
            # 采集前先检查取消
            if cancellation_registry.is_cancelled(blogger_uuid):
                logger.info(f"博主 {blogger_uuid} 任务已取消，跳过采集")
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.CANCELLED.value,
                    progress_step="cancelled",
                    message="任务已取消",
                )
                await db.commit()
                cancellation_registry.clear(blogger_uuid)
                return

            blogger = await blogger_repository.get_by_id(db, blogger_uuid)
            if not blogger:
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.FAILED.value,
                    progress_step="failed",
                    message="博主不存在",
                    error_message="未找到目标博主记录",
                )
                await db.commit()
                return

            # 1. 采集视频列表
            progress_registry.set(blogger_uuid, "crawling")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="crawling",
                message="正在拉取视频列表",
            )
            await db.commit()

            if refresh and not incremental_mode:
                logger.info(f"全量重采集：清空博主 {blogger_uuid} 旧视频数据")
                await blogger_repository.delete_all_videos(db, blogger_uuid)
                await db.commit()

            existing_video_ids = await blogger_repository.get_existing_video_ids(db, blogger_uuid) if incremental_mode else set()
            effective_start_date = start_date
            effective_end_date = end_date
            if incremental_mode and not effective_start_date and blogger.last_collected_published_at:
                effective_start_date = blogger.last_collected_published_at.date()

            effective_sample_count = sample_count
            if effective_start_date or effective_end_date:
                # 指定区间时采集全部区间视频，数量限制作废
                effective_sample_count = None

            logger.info(f"开始采集博主 {user_data['nickname']} 的视频...")
            videos = await crawler_service.get_user_videos(
                platform=user_data["platform"],
                user_id=user_data["blogger_id"],
                sec_user_id=user_data.get("sec_user_id", user_data["blogger_id"]),
                count=effective_sample_count,
                start_date=effective_start_date,
                end_date=effective_end_date,
            )

            # 2. 保存广度视频
            progress_registry.set(blogger_uuid, "saving")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="saving",
                message="正在入库采集结果",
            )
            await db.commit()

            pending_write_count = 0
            added_count = 0
            latest_published_at = blogger.last_collected_published_at
            for video_data in videos:
                if cancellation_registry.is_cancelled(blogger_uuid):
                    if pending_write_count > 0:
                        await db.commit()
                    logger.info(f"博主 {blogger_uuid} 广度分析任务被取消，提前退出")
                    await task_center_repo.update_status(
                        db,
                        resolved_task_key,
                        status=TaskStatus.CANCELLED.value,
                        progress_step="cancelled",
                        message="任务执行中被取消",
                    )
                    await db.commit()
                    cancellation_registry.clear(blogger_uuid)
                    return

                video_id = video_data.get("video_id")
                if not video_id:
                    continue
                if incremental_mode and video_id in existing_video_ids:
                    continue

                await blogger_repository.add_video(db, {
                    "blogger_id": blogger_uuid,
                    **{k: v for k, v in video_data.items() if k in [
                        "video_id", "title", "description", "cover_url",
                        "video_url", "like_count", "comment_count", "share_count", "duration", "published_at"
                    ]}
                })
                if incremental_mode:
                    existing_video_ids.add(video_id)
                published_at = video_data.get("published_at")
                if isinstance(published_at, datetime):
                    if latest_published_at is None or published_at > latest_published_at:
                        latest_published_at = published_at
                pending_write_count += 1
                added_count += 1
                if pending_write_count >= 20:
                    await db.commit()
                    pending_write_count = 0

            if pending_write_count > 0:
                await db.commit()

            normal_video_count = await blogger_repository.count_normal_videos(db, blogger_uuid)
            # video_count 表示作者主页总作品数，不应被“参与分析样本数”覆盖。
            # 当 user_data 携带最新总数时，更新为该总数；否则保留原值。
            try:
                parsed_total_video_count = int(user_data.get("video_count") or 0)
            except Exception:
                parsed_total_video_count = 0
            if parsed_total_video_count > 0:
                blogger.video_count = parsed_total_video_count
            await blogger_repository.update_collection_meta(
                db,
                blogger_uuid,
                incremental_enabled=incremental_mode,
                last_collected_published_at=latest_published_at,
            )
            await db.commit()
            logger.info(
                "博主 %s 视频入库完成，本次新增 %s 条，参与分析累计 %s 条，总作品数 %s",
                blogger_uuid,
                added_count,
                normal_video_count,
                blogger.video_count,
            )

            # 3. 深度析帧（仅限代表作）
            videos_analysis = []
            if representative_video_url:
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.RUNNING.value,
                    progress_step="representative",
                    message="正在分析代表作",
                )
                await db.commit()
                if refresh:
                    # NOTE: 重采集时优先复用数据库中已有的所有代表作分析（支持多条累加模式）
                    all_videos_now = await blogger_repository.get_videos_by_blogger(db, blogger_uuid)
                    existing_rep_analyses = [
                        v.ai_analysis for v in all_videos_now
                        if (v.video_id or "").startswith("rep_") and v.ai_analysis
                    ]
                    if existing_rep_analyses:
                        logger.info(f"检测到 {len(existing_rep_analyses)} 条代表作分析结果，直接复用，跳过重新下载")
                        videos_analysis.extend(existing_rep_analyses)
                    else:
                        # 没有历史分析结果，走完整流程
                        logger.info(f"准备下载并分析博主代表作（无历史记录）: {representative_video_url}")
                        progress_registry.set(blogger_uuid, "downloading")
                        rep_video_data = await crawler_service.get_single_video_by_url(representative_video_url)
                        if rep_video_data and rep_video_data.get("video_url"):
                            progress_registry.set(blogger_uuid, "ai_video")
                            analysis = await ai_analysis_service.analyze_video_style(
                                video_url=rep_video_data.get("video_url", ""),
                                title=rep_video_data.get("title", ""),
                                description=rep_video_data.get("description", ""),
                                video_id=rep_video_data.get("video_id"),
                                progress_task_id=blogger_uuid,
                            )
                            videos_analysis.append(analysis)
                            rep_video_id = f"rep_{rep_video_data.get('video_id', 'obj')}"
                            await blogger_repository.upsert_video_by_blogger_video_id(
                                db,
                                blogger_id=blogger_uuid,
                                video_id=rep_video_id,
                                data={
                                    "title": f"[代表作] {rep_video_data.get('title', '')}",
                                    "description": rep_video_data.get("description", ""),
                                    "cover_url": rep_video_data.get("cover_url", ""),
                                    "video_url": rep_video_data.get("video_url", ""),
                                    "like_count": rep_video_data.get("like_count", 0),
                                    "published_at": rep_video_data.get("published_at"),
                                    "ai_analysis": analysis,
                                    "is_analyzed": True,
                                },
                            )
                            await db.commit()
                            logger.info("代表作视频深度解析完成（新建）")
                        else:
                            logger.warning(f"代表作视频解析失败: {representative_video_url}")
                else:
                    # 首次分析：正常下载+AI析帧流程
                    progress_registry.set(blogger_uuid, "downloading")
                    logger.info(f"准备下载并分析博主代表作: {representative_video_url}")
                    rep_video_data = await crawler_service.get_single_video_by_url(representative_video_url)
                    if rep_video_data and rep_video_data.get("video_url"):
                        progress_registry.set(blogger_uuid, "ai_video")
                        analysis = await ai_analysis_service.analyze_video_style(
                            video_url=rep_video_data.get("video_url", ""),
                            title=rep_video_data.get("title", ""),
                            description=rep_video_data.get("description", ""),
                            video_id=rep_video_data.get("video_id"),
                            progress_task_id=blogger_uuid,
                        )
                        videos_analysis.append(analysis)
                        rep_video_id = f"rep_{rep_video_data.get('video_id', 'obj')}"
                        await blogger_repository.upsert_video_by_blogger_video_id(
                            db,
                            blogger_id=blogger_uuid,
                            video_id=rep_video_id,
                            data={
                                "title": f"[代表作] {rep_video_data.get('title', '')}",
                                "description": rep_video_data.get("description", ""),
                                "cover_url": rep_video_data.get("cover_url", ""),
                                "video_url": rep_video_data.get("video_url", ""),
                                "like_count": rep_video_data.get("like_count", 0),
                                "published_at": rep_video_data.get("published_at"),
                                "ai_analysis": analysis,
                                "is_analyzed": True,
                            },
                        )
                        await db.commit()
                        logger.info("代表作视频深度解析完成")
                    else:
                        logger.warning(f"代表作视频解析失败: {representative_video_url}")
            else:
                logger.info("用户未指定代表作，跳过深度多模态解析")

            # 生成报告前再次检查
            if cancellation_registry.is_cancelled(blogger_uuid):
                logger.info(f"博主 {blogger_uuid} 综合报告生成被取消")
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.CANCELLED.value,
                    progress_step="cancelled",
                    message="任务在报告生成前被取消",
                )
                await db.commit()
                cancellation_registry.clear(blogger_uuid)
                return

            # 4. 生成博主综合分析报告
            progress_registry.set(blogger_uuid, "ai_report")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="ai_report",
                message="正在生成博主综合报告",
            )
            await db.commit()
            blogger = await blogger_repository.get_by_id(db, blogger_uuid)
            if blogger:
                all_videos = await blogger_repository.get_videos_by_blogger(db, blogger_uuid)
                videos_text_data = [
                    {
                        "title": v.title or "",
                        "description": v.description or "",
                        "like_count": v.like_count,
                        "comment_count": v.comment_count,
                    }
                    for v in all_videos
                    if not (v.video_id or "").startswith("rep_")
                ]
                all_rep_analyses = [
                    v.ai_analysis for v in all_videos
                    if (v.video_id or "").startswith("rep_") and v.ai_analysis
                ]
                merged_analyses = [*all_rep_analyses, *videos_analysis]
                report = await ai_analysis_service.generate_blogger_report(
                    blogger_info={
                        "nickname": blogger.nickname,
                        "platform": blogger.platform,
                        "follower_count": blogger.follower_count,
                        "signature": blogger.signature,
                        "video_count": blogger.video_count,
                    },
                    videos_text_data=videos_text_data,
                    videos_analysis=merged_analyses,
                    run_context={"entity_type": "blogger", "entity_id": blogger_uuid},
                    db=db,
                )
                await blogger_repository.update_analysis(db, blogger_uuid, report)
                await db.commit()
                progress_registry.set(blogger_uuid, "done")
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.COMPLETED.value,
                    progress_step="done",
                    message=f"任务完成，新增 {added_count} 条视频",
                )
                await db.commit()
                logger.info(f"博主 {user_data['nickname']} 分析完成")

        except Exception as e:
            logger.error(f"博主 {blogger_uuid} 后台分析失败: {e}", exc_info=True)
            progress_registry.set(blogger_uuid, "failed", f"任务执行失败：{e}")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="任务执行失败",
                error_message=str(e),
            )
            await db.commit()
        finally:
            # 确保任务结束后清理取消标志
            cancellation_registry.clear(blogger_uuid)
