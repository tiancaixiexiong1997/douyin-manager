import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


WEAK_AUTH_SECRET_KEYS = {
    "change-me-in-production",
    "local-dev-please-change-this-secret",
    "replace-this-with-a-long-random-string",
}

WEAK_ADMIN_PASSWORDS = {
    "admin",
    "admin123",
    "admin123456",
    "123456",
    "12345678",
    "password",
    "qwerty",
}


class Settings(BaseSettings):
    """应用配置，优先从环境变量读取"""

    # 应用基础配置
    APP_NAME: str = "抖音内容策划工作台"
    APP_VERSION: str = "1.0.0"
    APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "Asia/Shanghai")
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:80"
    AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "change-me-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 720))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))
    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    SECURITY_STRICT_MODE: bool = False
    MIN_AUTH_SECRET_KEY_LENGTH: int = 32
    MIN_ADMIN_PASSWORD_LENGTH: int = 12
    TASK_STATE_RETENTION_DAYS: int = 14
    TASK_STATE_CLEANUP_INTERVAL_MINUTES: int = 60
    TASK_STATE_CLEANUP_ON_STARTUP: bool = True
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_JSON: bool = os.getenv("LOG_JSON", "false").lower() in {"1", "true", "yes", "on"}
    RUN_ALEMBIC_ON_STARTUP: bool = os.getenv("RUN_ALEMBIC_ON_STARTUP", "true").lower() in {"1", "true", "yes", "on"}
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    JOB_QUEUE_NAME: str = os.getenv("JOB_QUEUE_NAME", "default")
    REQUIRE_ACTIVE_WORKER_ON_ENQUEUE: bool = os.getenv("REQUIRE_ACTIVE_WORKER_ON_ENQUEUE", "true").lower() in {"1", "true", "yes", "on"}
    WORKER_HEARTBEAT_TIMEOUT_SECONDS: int = int(os.getenv("WORKER_HEARTBEAT_TIMEOUT_SECONDS", 120))
    JOB_QUEUE_RETRY_MAX: int = int(os.getenv("JOB_QUEUE_RETRY_MAX", 1))
    JOB_QUEUE_RETRY_INTERVAL_SECONDS: int = int(os.getenv("JOB_QUEUE_RETRY_INTERVAL_SECONDS", 30))
    JOB_QUEUE_STUCK_JOB_TIMEOUT_SECONDS: int = int(os.getenv("JOB_QUEUE_STUCK_JOB_TIMEOUT_SECONDS", 1800))
    WORKER_PURGE_PENDING_ON_STARTUP: bool = os.getenv(
        "WORKER_PURGE_PENDING_ON_STARTUP", "false"
    ).lower() in {"1", "true", "yes", "on"}
    WORKER_PURGE_ABANDONED_FAILED_ON_STARTUP: bool = os.getenv(
        "WORKER_PURGE_ABANDONED_FAILED_ON_STARTUP", "true"
    ).lower() in {"1", "true", "yes", "on"}
    AUTO_REFRESH_REPORT_ON_REP_DELETE: bool = os.getenv(
        "AUTO_REFRESH_REPORT_ON_REP_DELETE", "false"
    ).lower() in {"1", "true", "yes", "on"}
    ENABLE_LEGACY_COOKIE_FETCH_FALLBACK: bool = os.getenv(
        "ENABLE_LEGACY_COOKIE_FETCH_FALLBACK", "false"
    ).lower() in {"1", "true", "yes", "on"}

    ACCESS_COOKIE_NAME: str = os.getenv("ACCESS_COOKIE_NAME", "access_token")
    REFRESH_COOKIE_NAME: str = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", "")

    AUTH_LOCK_MAX_ATTEMPTS: int = int(os.getenv("AUTH_LOCK_MAX_ATTEMPTS", 5))
    AUTH_LOCK_MINUTES: int = int(os.getenv("AUTH_LOCK_MINUTES", 15))
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", 300))
    AUTH_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", 20))
    DOWNLOAD_PROXY_CONNECT_TIMEOUT_SECONDS: int = int(
        os.getenv("DOWNLOAD_PROXY_CONNECT_TIMEOUT_SECONDS", 15)
    )
    DOWNLOAD_PROXY_READ_TIMEOUT_SECONDS: int = int(
        os.getenv("DOWNLOAD_PROXY_READ_TIMEOUT_SECONDS", 120)
    )
    DOWNLOAD_PROXY_FETCHER_TIMEOUT_SECONDS: int = int(
        os.getenv("DOWNLOAD_PROXY_FETCHER_TIMEOUT_SECONDS", 10)
    )
    DOWNLOAD_PROXY_CHUNK_SIZE_BYTES: int = int(
        os.getenv("DOWNLOAD_PROXY_CHUNK_SIZE_BYTES", 524288)
    )
    DOWNLOAD_PROXY_MAX_NETWORK_RETRIES: int = int(
        os.getenv("DOWNLOAD_PROXY_MAX_NETWORK_RETRIES", 1)
    )
    ENABLE_GZIP: bool = os.getenv("ENABLE_GZIP", "true").lower() in {"1", "true", "yes", "on"}
    GZIP_MINIMUM_SIZE: int = int(os.getenv("GZIP_MINIMUM_SIZE", 1024))
    GZIP_COMPRESS_LEVEL: int = int(os.getenv("GZIP_COMPRESS_LEVEL", 6))
    ENABLE_SECURITY_HEADERS: bool = os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() in {"1", "true", "yes", "on"}
    SECURITY_HSTS_SECONDS: int = int(os.getenv("SECURITY_HSTS_SECONDS", 31536000))

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/douyincehua.db"

    # douyin_api 路径（通过 Docker Volume 挂载或本地相对路径）
    DOUYIN_API_PATH: str = "/app/douyin_api"

    # AI 配置（复用 douyin_api 的 ai_config.yaml）
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "https://api.openai-hub.com/v1")
    AI_MODEL: str = os.getenv("AI_MODEL", "gemini-2.0-flash")
    AI_FAILOVER_ENABLED: bool = os.getenv("AI_FAILOVER_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    AI_API_KEY_BACKUP: str = os.getenv("AI_API_KEY_BACKUP", "")
    AI_BASE_URL_BACKUP: str = os.getenv("AI_BASE_URL_BACKUP", "")
    AI_MODEL_BACKUP: str = os.getenv("AI_MODEL_BACKUP", "")
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", 16384))
    AI_TEMPERATURE: float = 0.7

    # 博主分析默认配置
    DEFAULT_VIDEO_SAMPLE_COUNT: int = 10  # 默认采集视频数量

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def parse_cors_origins(raw: str) -> List[str]:
    """把逗号分隔的 CORS 配置解析为白名单数组。"""
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def security_warnings() -> list[str]:
    """返回当前配置的安全告警列表。"""
    warnings: list[str] = []

    secret = (settings.AUTH_SECRET_KEY or "").strip()
    if (
        len(secret) < settings.MIN_AUTH_SECRET_KEY_LENGTH
        or secret in WEAK_AUTH_SECRET_KEYS
    ):
        warnings.append(
            "AUTH_SECRET_KEY 强度不足：请使用至少 32 位随机字符串，并避免默认示例值。"
        )

    admin_password = (settings.DEFAULT_ADMIN_PASSWORD or "").strip()
    if admin_password:
        if (
            len(admin_password) < settings.MIN_ADMIN_PASSWORD_LENGTH
            or admin_password.lower() in WEAK_ADMIN_PASSWORDS
        ):
            warnings.append(
                "DEFAULT_ADMIN_PASSWORD 强度不足：请使用至少 12 位且包含大小写、数字、符号的强密码。"
            )

    cookie_samesite = (settings.COOKIE_SAMESITE or "").strip().lower()
    if cookie_samesite not in {"lax", "strict", "none"}:
        warnings.append("COOKIE_SAMESITE 配置无效：请使用 lax / strict / none 之一。")

    if not settings.DEBUG and not settings.COOKIE_SECURE:
        warnings.append(
            "COOKIE_SECURE=false：生产环境建议启用 HTTPS 并设置 COOKIE_SECURE=true，避免 Cookie 明文传输。"
        )

    if cookie_samesite == "none" and not settings.COOKIE_SECURE:
        warnings.append("COOKIE_SAMESITE=none 时必须启用 COOKIE_SECURE=true。")

    cors_origins = parse_cors_origins(settings.CORS_ORIGINS)
    if "*" in cors_origins:
        warnings.append("CORS_ORIGINS 不应包含 *：当前启用了凭据传递，需使用明确白名单域名。")

    return warnings
