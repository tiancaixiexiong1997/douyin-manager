"""RQ 任务队列封装。"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from redis import Redis
    from rq import Queue
except Exception:  # pragma: no cover - 依赖缺失时降级报错提示
    Redis = None  # type: ignore[assignment]
    Queue = None  # type: ignore[assignment]


def _ensure_available() -> None:
    if Redis is None or Queue is None:
        raise RuntimeError("任务队列依赖缺失：请安装 redis 与 rq，并重建后端镜像。")


def get_redis_connection():
    _ensure_available()
    return Redis.from_url(settings.REDIS_URL)


def get_queue():
    _ensure_available()
    conn = get_redis_connection()
    return Queue(settings.JOB_QUEUE_NAME, connection=conn, default_timeout=3600)


def _extract_worker_queue_names(worker: Any) -> set[str]:
    try:
        names = worker.queue_names()
        if names:
            return {str(name) for name in names}
    except Exception:
        pass
    try:
        queues = getattr(worker, "queues", []) or []
        return {str(getattr(queue, "name", "")) for queue in queues if getattr(queue, "name", "")}
    except Exception:
        return set()


def _normalize_heartbeat(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _resolve_worker_heartbeat_timeout(worker: Any, default_timeout: int) -> int:
    timeout = int(default_timeout)
    for attr in ("worker_ttl", "default_worker_ttl"):
        raw = getattr(worker, attr, None)
        try:
            ttl = int(raw)
        except (TypeError, ValueError):
            continue
        if ttl > 0:
            timeout = max(timeout, ttl)
    return timeout


def get_queue_runtime_summary(*, queue: Any | None = None) -> dict[str, Any]:
    """获取队列运行摘要（排队数、活跃 worker 数）。"""
    queue_obj = queue or get_queue()
    active_workers = 0
    stale_workers = 0
    worker_total = 0
    failed_jobs = 0
    started_jobs = 0
    scheduled_jobs = 0
    deferred_jobs = 0
    stuck_jobs = 0
    now = datetime.utcnow()
    heartbeat_timeout = max(30, int(settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS))
    stuck_timeout = max(60, int(settings.JOB_QUEUE_STUCK_JOB_TIMEOUT_SECONDS))

    try:
        from rq import Worker

        workers = Worker.all(connection=queue_obj.connection)
        for worker in workers:
            queue_names = _extract_worker_queue_names(worker)
            if queue_names and queue_obj.name not in queue_names:
                continue
            worker_total += 1
            heartbeat = _normalize_heartbeat(getattr(worker, "last_heartbeat", None))
            if heartbeat is None:
                heartbeat = _normalize_heartbeat(getattr(worker, "birth_date", None))
            worker_timeout = _resolve_worker_heartbeat_timeout(worker, heartbeat_timeout)
            if heartbeat and (now - heartbeat).total_seconds() <= worker_timeout:
                active_workers += 1
            else:
                stale_workers += 1
    except Exception as exc:
        logger.warning("读取 worker 状态失败: %s", exc)

    queued_jobs = 0
    try:
        queued_jobs = int(queue_obj.count)
    except Exception as exc:
        logger.warning("读取队列长度失败(queue=%s): %s", getattr(queue_obj, "name", "unknown"), exc)

    try:
        from rq.job import Job
        from rq.registry import (
            DeferredJobRegistry,
            FailedJobRegistry,
            ScheduledJobRegistry,
            StartedJobRegistry,
        )

        failed_registry = FailedJobRegistry(name=queue_obj.name, connection=queue_obj.connection)
        started_registry = StartedJobRegistry(name=queue_obj.name, connection=queue_obj.connection)
        scheduled_registry = ScheduledJobRegistry(name=queue_obj.name, connection=queue_obj.connection)
        deferred_registry = DeferredJobRegistry(name=queue_obj.name, connection=queue_obj.connection)

        failed_jobs = int(getattr(failed_registry, "count", 0) or 0)
        started_jobs = int(getattr(started_registry, "count", 0) or 0)
        scheduled_jobs = int(getattr(scheduled_registry, "count", 0) or 0)
        deferred_jobs = int(getattr(deferred_registry, "count", 0) or 0)

        started_ids = started_registry.get_job_ids()
        if started_ids:
            jobs = Job.fetch_many(started_ids, connection=queue_obj.connection)
            for job in jobs:
                if not job:
                    continue
                started_at = _normalize_heartbeat(getattr(job, "started_at", None))
                if started_at and (now - started_at).total_seconds() > stuck_timeout:
                    stuck_jobs += 1
    except Exception as exc:
        logger.warning("读取队列注册表状态失败(queue=%s): %s", getattr(queue_obj, "name", "unknown"), exc)

    status = "ok" if active_workers > 0 and stuck_jobs == 0 else "degraded"
    return {
        "status": status,
        "queue_name": str(queue_obj.name),
        "queued_jobs": queued_jobs,
        "worker_total": worker_total,
        "active_workers": active_workers,
        "stale_workers": stale_workers,
        "failed_jobs": failed_jobs,
        "started_jobs": started_jobs,
        "scheduled_jobs": scheduled_jobs,
        "deferred_jobs": deferred_jobs,
        "stuck_jobs": stuck_jobs,
        "stuck_job_timeout_seconds": stuck_timeout,
        "worker_heartbeat_timeout_seconds": heartbeat_timeout,
    }


def get_started_job_ids(*, queue: Any | None = None) -> set[str]:
    """获取当前队列中处于 started registry 的任务 id 集合。"""
    queue_obj = queue or get_queue()
    try:
        from rq.registry import StartedJobRegistry

        registry = StartedJobRegistry(name=queue_obj.name, connection=queue_obj.connection)
        return {str(job_id) for job_id in registry.get_job_ids()}
    except Exception as exc:
        logger.warning(
            "读取 started 任务列表失败(queue=%s): %s",
            getattr(queue_obj, "name", "unknown"),
            exc,
        )
        return set()


def enqueue_task(
    func: str,
    *args: Any,
    job_id: str | None = None,
    description: str | None = None,
) -> str:
    """提交任务到 RQ 队列并返回 job_id。"""
    queue = get_queue()
    if settings.REQUIRE_ACTIVE_WORKER_ON_ENQUEUE:
        summary = get_queue_runtime_summary(queue=queue)
        if int(summary.get("active_workers", 0)) <= 0:
            logger.error(
                "任务入队前检测到无活跃 worker(queue=%s queued_jobs=%s)",
                summary.get("queue_name"),
                summary.get("queued_jobs"),
            )
            raise RuntimeError("任务工作进程未就绪，请稍后重试。")

    enqueue_kwargs: dict[str, Any] = {
        "job_id": job_id,
        "description": description,
        "result_ttl": 24 * 3600,
        "failure_ttl": 7 * 24 * 3600,
    }
    retry_max = max(0, int(settings.JOB_QUEUE_RETRY_MAX))
    if retry_max > 0:
        retry_interval = max(1, int(settings.JOB_QUEUE_RETRY_INTERVAL_SECONDS))
        try:
            from rq import Retry

            enqueue_kwargs["retry"] = Retry(max=retry_max, interval=retry_interval)
        except Exception as exc:
            logger.warning("任务重试策略未生效（Retry 不可用）: %s", exc)

    try:
        job = queue.enqueue(
            func,
            *args,
            **enqueue_kwargs,
        )
    except Exception as exc:
        logger.error("任务入队失败(func=%s): %s", func, exc, exc_info=True)
        raise RuntimeError("任务系统暂不可用，请稍后重试。") from exc
    return job.id


def purge_pending_jobs(*, queue: Any | None = None) -> dict[str, int]:
    """清理待执行任务（queued/scheduled/deferred），用于重建后避免自动续跑。"""
    queue_obj = queue or get_queue()
    removed = {"queued": 0, "scheduled": 0, "deferred": 0}

    try:
        removed["queued"] = int(queue_obj.count)
        if removed["queued"] > 0:
            queue_obj.empty()
    except Exception as exc:
        logger.warning("清理 queued 任务失败(queue=%s): %s", getattr(queue_obj, "name", "unknown"), exc)

    try:
        from rq.job import Job
        from rq.registry import DeferredJobRegistry, ScheduledJobRegistry

        for key, registry_cls in (
            ("scheduled", ScheduledJobRegistry),
            ("deferred", DeferredJobRegistry),
        ):
            registry = registry_cls(name=queue_obj.name, connection=queue_obj.connection)
            ids = registry.get_job_ids()
            removed[key] = len(ids)
            if not ids:
                continue
            jobs = Job.fetch_many(ids, connection=queue_obj.connection)
            with queue_obj.connection.pipeline() as pipe:
                for job in jobs:
                    if not job:
                        continue
                    registry.remove(job, pipeline=pipe, delete_job=False)
                pipe.execute()
    except Exception as exc:
        logger.warning("清理 scheduled/deferred 任务失败(queue=%s): %s", getattr(queue_obj, "name", "unknown"), exc)

    return removed


def purge_failed_jobs(
    *,
    queue: Any | None = None,
    abandoned_only: bool = True,
) -> dict[str, int]:
    """清理失败任务；默认只清理 AbandonedJobError 遗留任务。"""
    queue_obj = queue or get_queue()
    removed = {"failed": 0, "abandoned": 0}

    try:
        from rq.job import Job
        from rq.registry import FailedJobRegistry

        registry = FailedJobRegistry(name=queue_obj.name, connection=queue_obj.connection)
        ids = registry.get_job_ids()
        if not ids:
            return removed

        jobs = Job.fetch_many(ids, connection=queue_obj.connection)
        with queue_obj.connection.pipeline() as pipe:
            for job in jobs:
                if not job:
                    continue
                exc_info = str(getattr(job, "exc_info", "") or "")
                is_abandoned = "AbandonedJobError" in exc_info
                if abandoned_only and not is_abandoned:
                    continue
                registry.remove(job, pipeline=pipe, delete_job=True)
                removed["failed"] += 1
                if is_abandoned:
                    removed["abandoned"] += 1
            pipe.execute()
    except Exception as exc:
        logger.warning(
            "清理 failed 任务失败(queue=%s): %s",
            getattr(queue_obj, "name", "unknown"),
            exc,
        )

    return removed
