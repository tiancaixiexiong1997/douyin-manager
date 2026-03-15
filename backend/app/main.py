"""
FastAPI 应用主程序入口
"""
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.models.db_session import init_db, AsyncSessionLocal, engine
from app.config import settings, parse_cors_origins, security_warnings
from app.services.auth_service import auth_service
from app.services.task_store import task_store
from app.services.job_queue import (
    get_redis_connection,
    get_queue_runtime_summary,
    get_started_job_ids,
)
from app.repository.task_center_repo import task_center_repo
from app.services.logging_setup import configure_logging

# 配置日志
configure_logging(log_level=settings.LOG_LEVEL, log_json=settings.LOG_JSON)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动初始化。"""
    warnings = security_warnings()
    if warnings:
        for item in warnings:
            logger.warning("🔐 安全告警: %s", item)
        if settings.SECURITY_STRICT_MODE:
            raise RuntimeError("SECURITY_STRICT_MODE=true 且存在安全告警，请修复配置后再启动。")

    if not (settings.AI_API_KEY or "").strip():
        logger.warning("⚙️ 启动告警: AI_API_KEY 未配置，账号策划与脚本生成等 AI 功能将不可用。")

    # 确保数据目录存在
    os.makedirs("./data", exist_ok=True)
    os.makedirs("./logs", exist_ok=True)

    # 初始化数据库表
    await init_db()
    try:
        active_task_keys = get_started_job_ids()
        stale_seconds = max(120, int(settings.JOB_QUEUE_STUCK_JOB_TIMEOUT_SECONDS))
        stale_before = datetime.utcnow() - timedelta(seconds=stale_seconds)
        async with AsyncSessionLocal() as db:
            reclaimed = await task_center_repo.reclaim_orphan_running_tasks(
                db,
                active_task_keys=active_task_keys,
                stale_before=stale_before,
            )
            if reclaimed > 0:
                await db.commit()
                logger.warning(
                    "🧹 任务中心已自动回收孤儿运行任务: reclaimed=%s cutoff_seconds=%s",
                    reclaimed,
                    stale_seconds,
                )
            else:
                await db.rollback()
    except Exception as exc:
        logger.warning("任务中心孤儿任务回收失败: %s", exc)

    cleanup_result = (
        task_store.maybe_cleanup_expired(force=True)
        if settings.TASK_STATE_CLEANUP_ON_STARTUP
        else None
    )
    if cleanup_result:
        total_deleted = cleanup_result["task_cancellations"] + cleanup_result["task_progress"]
        if total_deleted > 0:
            logger.info(
                "🧹 任务状态清理完成: cancellations=%s, progress=%s",
                cleanup_result["task_cancellations"],
                cleanup_result["task_progress"],
            )
    async with AsyncSessionLocal() as db:
        await auth_service.ensure_default_admin(db)
        bootstrap_warnings = await auth_service.get_bootstrap_warnings(db)
        await db.commit()
    for item in bootstrap_warnings:
        logger.warning("⚙️ 启动告警: %s", item)
    logger.info("✅ 数据库初始化完成")
    logger.info(f"🚀 {settings.APP_NAME} 启动成功")
    yield


# 创建 FastAPI 应用
app = FastAPI(
    title="抖音内容策划工作台 API",
    version=settings.APP_VERSION,
    description="""
## 抖音内容策划工作台

**核心功能：**
- 🎯 博主 IP 库管理（自动采集 + AI 深度分析）
- 📋 账号策划生成（一键输出定位 + 30天内容日历）
- 📝 单条视频脚本生成（分镜 + 台词 + 拍摄建议）
""",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 跨域配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.ENABLE_GZIP:
    app.add_middleware(
        GZipMiddleware,
        minimum_size=max(100, int(settings.GZIP_MINIMUM_SIZE)),
        compresslevel=max(1, min(9, int(settings.GZIP_COMPRESS_LEVEL))),
    )


@app.middleware("http")
async def request_trace_middleware(request: Request, call_next):
    """为每个请求附加 request_id，并记录耗时日志。"""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "请求异常 request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    if settings.ENABLE_SECURITY_HEADERS:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.COOKIE_SECURE and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={max(0, int(settings.SECURITY_HSTS_SECONDS))}; includeSubDomains"
            )
    logger.info(
        "请求完成 request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

# 注册 API 路由
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/health/ready")
async def readiness_check():
    """就绪检查：验证数据库与 Redis 连接。"""
    checks: dict[str, str] = {}
    healthy = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        healthy = False
        checks["database"] = f"error:{exc.__class__.__name__}"

    try:
        redis_conn = get_redis_connection()
        redis_conn.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        healthy = False
        checks["redis"] = f"error:{exc.__class__.__name__}"

    payload = {
        "status": "ok" if healthy else "degraded",
        "version": settings.APP_VERSION,
        "checks": checks,
    }
    return JSONResponse(status_code=200 if healthy else 503, content=payload)


@app.get("/health/queue")
async def queue_health_check():
    """队列健康检查：用于确认 worker 是否在线。"""
    try:
        summary = get_queue_runtime_summary()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "queue_name": settings.JOB_QUEUE_NAME,
                "error": f"{exc.__class__.__name__}: {exc}",
            },
        )

    status_code = 200 if summary.get("active_workers", 0) > 0 else 503
    return JSONResponse(status_code=status_code, content=summary)
