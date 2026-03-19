import logging
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_session import get_db, AsyncSessionLocal
from app.schemas.setting import (
    BatchSettingsUpdateRequest,
    CookieExtractorRotateResponse,
    CookieExtractorStatusResponse,
    CookieExtractorWebhookRequest,
    SettingsResponse,
    TaskStateSummaryResponse,
)
from app.repository.setting_repo import setting_repo
from app.services.ai_analysis_service import ai_analysis_service
from app.services.task_store import task_store
from app.config import settings as app_settings

router = APIRouter()
public_router = APIRouter()
logger = logging.getLogger(__name__)

SENSITIVE_SETTING_KEYS = {"AI_API_KEY", "DOUYIN_COOKIE"}
SENSITIVE_MASK = "********"
COOKIE_PLACEHOLDER_MARKERS = {
    "please_replace_with_your_own_cookie",
    "your_cookie",
    "put your cookie here",
}
_legacy_cookie_fetch_attempted = False
_legacy_cookie_cache = ""
COOKIE_SNIFFER_TOKEN_KEY = "COOKIE_SNIFFER_WEBHOOK_TOKEN"
COOKIE_SNIFFER_LAST_SYNC_AT_KEY = "COOKIE_SNIFFER_LAST_SYNC_AT"
COOKIE_SNIFFER_LAST_SERVICE_KEY = "COOKIE_SNIFFER_LAST_SERVICE"
COOKIE_SNIFFER_LAST_MESSAGE_KEY = "COOKIE_SNIFFER_LAST_MESSAGE"
COOKIE_SNIFFER_LOGIN_URL = "https://www.douyin.com/"
COOKIE_SNIFFER_EXTENSION_PATH = "backend/douyin_api/chrome-cookie-sniffer"


def _mask_sensitive(key: str, value: str) -> str:
    if key in SENSITIVE_SETTING_KEYS and value:
        return SENSITIVE_MASK
    return value


def _is_placeholder_cookie(cookie: str) -> bool:
    value = (cookie or "").strip()
    if not value:
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in COOKIE_PLACEHOLDER_MARKERS)


async def _get_legacy_cookie_fallback() -> str:
    global _legacy_cookie_fetch_attempted, _legacy_cookie_cache

    if not app_settings.ENABLE_LEGACY_COOKIE_FETCH_FALLBACK:
        return ""
    if _legacy_cookie_fetch_attempted:
        return _legacy_cookie_cache

    _legacy_cookie_fetch_attempted = True
    try:
        import httpx
        import os

        internal_crawler_url = os.environ.get("INTERNAL_CRAWLER_URL", "http://douyin-fetcher:8080")
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{internal_crawler_url}/api/cookie")
            if res.status_code == 200:
                fallback_cookie = res.json().get("cookie", "")
                if not _is_placeholder_cookie(fallback_cookie):
                    _legacy_cookie_cache = fallback_cookie
    except Exception as exc:
        logger.warning("Failed to fetch legacy cookie from fetcher: %s", exc)
    return _legacy_cookie_cache


async def _ensure_cookie_sniffer_token(db: AsyncSession) -> str:
    settings_dict = await setting_repo.get_all(db)
    token = (settings_dict.get(COOKIE_SNIFFER_TOKEN_KEY) or "").strip()
    if token:
        return token

    token = secrets.token_urlsafe(24)
    await setting_repo.update_all(
        db,
        {
            COOKIE_SNIFFER_TOKEN_KEY: token,
            COOKIE_SNIFFER_LAST_MESSAGE_KEY: "Cookie 提取助手已初始化，可配置扩展回调。",
        },
    )
    await db.commit()
    return token


def _cookie_extractor_payload(settings_dict: dict[str, str], token: str) -> CookieExtractorStatusResponse:
    cookie = settings_dict.get("DOUYIN_COOKIE", "") or ""
    return CookieExtractorStatusResponse(
        token=token,
        login_url=COOKIE_SNIFFER_LOGIN_URL,
        extension_path=COOKIE_SNIFFER_EXTENSION_PATH,
        cookie_length=len(cookie),
        last_synced_at=settings_dict.get(COOKIE_SNIFFER_LAST_SYNC_AT_KEY) or None,
        last_service=settings_dict.get(COOKIE_SNIFFER_LAST_SERVICE_KEY) or None,
        last_message=settings_dict.get(COOKIE_SNIFFER_LAST_MESSAGE_KEY) or None,
    )

@router.get("", response_model=SettingsResponse, summary="获取系统设置")
async def get_settings(
    db: AsyncSession = Depends(get_db),
):
    """获取所有系统设置"""
    settings_dict = await setting_repo.get_all(db)
    defaults = {
        "AI_API_KEY": app_settings.AI_API_KEY,
        "AI_BASE_URL": app_settings.AI_BASE_URL,
        "AI_MODEL": app_settings.AI_MODEL,
        "GLOBAL_AI_FACT_RULES": ai_analysis_service.DEFAULT_GLOBAL_AI_FACT_RULES,
        "GLOBAL_AI_WRITING_RULES": ai_analysis_service.DEFAULT_GLOBAL_AI_WRITING_RULES,
        "BLOGGER_REPORT_PROMPT": ai_analysis_service.DEFAULT_BLOGGER_REPORT_PROMPT,
        "ACCOUNT_PLAN_PROMPT": ai_analysis_service.DEFAULT_ACCOUNT_PLAN_PROMPT,
        "CONTENT_CALENDAR_PROMPT": ai_analysis_service.DEFAULT_CONTENT_CALENDAR_PROMPT,
        "VIDEO_SCRIPT_PROMPT": ai_analysis_service.DEFAULT_VIDEO_SCRIPT_PROMPT,
        "SCRIPT_REMAKE_PROMPT": ai_analysis_service.DEFAULT_SCRIPT_REMAKE_PROMPT,
        "DOUYIN_COOKIE": "",
    }

    # 填充当前生效值，如果数据库中没有，则优先从默认配置中读取
    current_settings = {
        key: settings_dict.get(key, default_value)
        for key, default_value in defaults.items()
    }
    if _is_placeholder_cookie(current_settings["DOUYIN_COOKIE"]):
        current_settings["DOUYIN_COOKIE"] = ""
    
    if not current_settings["DOUYIN_COOKIE"]:
        current_settings["DOUYIN_COOKIE"] = await _get_legacy_cookie_fallback()

    masked_current_settings = {
        k: _mask_sensitive(k, v) if isinstance(v, str) else v
        for k, v in current_settings.items()
    }
    masked_defaults = {
        k: _mask_sensitive(k, v) if isinstance(v, str) else v
        for k, v in defaults.items()
    }
    return {"settings": masked_current_settings, "defaults": masked_defaults}


@router.put("", summary="批量更新系统设置")
async def update_settings(
    request: BatchSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新系统设置"""
    existing_settings = await setting_repo.get_all(db)
    cleaned_settings: dict[str, str] = {}
    for key, value in request.settings.items():
        # 前端未修改敏感字段时会回传掩码，保留原值
        if key in SENSITIVE_SETTING_KEYS and value == SENSITIVE_MASK:
            if key in existing_settings:
                cleaned_settings[key] = existing_settings[key]
            continue
        cleaned_settings[key] = value

    await setting_repo.update_all(db, cleaned_settings)
    await db.commit()
    
    # 同步更新 AIAnalysisService 里的设置
    await ai_analysis_service.reload_settings(db)
    
    return {"message": "设置更新成功"}


@router.get("/cookie-extractor", response_model=CookieExtractorStatusResponse, summary="获取 Cookie 提取助手状态")
async def get_cookie_extractor_status(
    db: AsyncSession = Depends(get_db),
):
    token = await _ensure_cookie_sniffer_token(db)
    settings_dict = await setting_repo.get_all(db)
    return _cookie_extractor_payload(settings_dict, token)


@router.post("/cookie-extractor/rotate-token", response_model=CookieExtractorRotateResponse, summary="重置 Cookie 提取助手 token")
async def rotate_cookie_extractor_token(
    db: AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(24)
    await setting_repo.update_all(
        db,
        {
            COOKIE_SNIFFER_TOKEN_KEY: token,
            COOKIE_SNIFFER_LAST_MESSAGE_KEY: "Cookie 提取 token 已重置，请更新扩展中的 Webhook 地址。",
        },
    )
    await db.commit()
    return CookieExtractorRotateResponse(token=token, message="Cookie 提取 token 已重置")


@router.get("/task-state", response_model=TaskStateSummaryResponse, summary="获取后台任务状态存储概览")
async def get_task_state_summary():
    """运维只读接口：查看任务状态积压与最近清理结果。"""
    return task_store.get_summary()


@public_router.post("/cookie-extractor/webhook", summary="接收 Cookie Sniffer 回调")
async def cookie_extractor_webhook(
    payload: CookieExtractorWebhookRequest,
    token: str = Query(..., description="Cookie 提取助手 token"),
):
    async with AsyncSessionLocal() as db:
        settings_dict = await setting_repo.get_all(db)
        expected_token = (settings_dict.get(COOKIE_SNIFFER_TOKEN_KEY) or "").strip()
        if not expected_token or token != expected_token:
            raise HTTPException(status_code=403, detail="无效的 Cookie 提取 token")

        service = (payload.service or "").strip().lower()
        if service != "douyin":
            raise HTTPException(status_code=400, detail="当前仅支持 Douyin Cookie 自动回写")

        timestamp = (payload.timestamp or "").strip() or datetime.utcnow().isoformat()
        message = (payload.message or "").strip()

        if payload.test:
            await setting_repo.update_all(
                db,
                {
                    COOKIE_SNIFFER_LAST_SYNC_AT_KEY: timestamp,
                    COOKIE_SNIFFER_LAST_SERVICE_KEY: service,
                    COOKIE_SNIFFER_LAST_MESSAGE_KEY: message or "收到测试回调，扩展与 Webhook 已连通。",
                },
            )
            await db.commit()
            return {"message": "测试回调成功", "test": True}

        cookie = (payload.cookie or "").strip()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie 内容为空")

        await setting_repo.update_all(
            db,
            {
                "DOUYIN_COOKIE": cookie,
                COOKIE_SNIFFER_LAST_SYNC_AT_KEY: timestamp,
                COOKIE_SNIFFER_LAST_SERVICE_KEY: service,
                COOKIE_SNIFFER_LAST_MESSAGE_KEY: message or f"已自动同步 Douyin Cookie（长度 {len(cookie)}）。",
            },
        )
        await db.commit()
        await ai_analysis_service.reload_settings(db)
        return {"message": "Douyin Cookie 已自动同步", "cookie_length": len(cookie)}
