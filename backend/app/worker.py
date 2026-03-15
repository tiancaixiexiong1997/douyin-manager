"""RQ Worker 进程入口。"""
from __future__ import annotations

import logging

from app.config import settings
from app.services.job_queue import (
    get_redis_connection,
    get_queue,
    purge_failed_jobs,
    purge_pending_jobs,
)
from app.services.logging_setup import configure_logging

configure_logging(log_level=settings.LOG_LEVEL, log_json=settings.LOG_JSON)
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        from rq import Connection, Worker
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("RQ 依赖缺失，无法启动 worker。") from exc

    conn = get_redis_connection()
    queue = get_queue()
    logger.info("启动队列 Worker，queue=%s redis=%s", settings.JOB_QUEUE_NAME, settings.REDIS_URL)
    if settings.WORKER_PURGE_PENDING_ON_STARTUP:
        removed = purge_pending_jobs(queue=queue)
        logger.warning(
            "已按配置清理待执行任务(queue=%s): queued=%s scheduled=%s deferred=%s",
            settings.JOB_QUEUE_NAME,
            removed.get("queued", 0),
            removed.get("scheduled", 0),
            removed.get("deferred", 0),
        )
    if settings.WORKER_PURGE_ABANDONED_FAILED_ON_STARTUP:
        removed_failed = purge_failed_jobs(queue=queue, abandoned_only=True)
        if removed_failed.get("failed", 0) > 0:
            logger.warning(
                "已按配置清理失败遗留任务(queue=%s): failed=%s abandoned=%s",
                settings.JOB_QUEUE_NAME,
                removed_failed.get("failed", 0),
                removed_failed.get("abandoned", 0),
            )
    with Connection(conn):
        worker = Worker([settings.JOB_QUEUE_NAME])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
