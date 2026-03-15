"""
无水印下载 API 端点
"""
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.models.db_session import get_db
from app.models.database import User
from app.repository.operation_log_repo import operation_log_repo
from app.services.crawler_service import crawler_service
from app.services.download_proxy_service import build_proxy_download_response

router = APIRouter()


def _detect_platform_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "tiktok" in host:
        return "tiktok"
    if "bilibili" in host or "b23.tv" in host:
        return "bilibili"
    return "douyin"


@router.post("/parse", summary="解析单条视频链接")
async def parse_video_url(
    url: str = Query(..., description="抖音视频分享链接"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    根据给定的抖音或 TikTok 视频链接，调用爬虫微服务解析出视频元信息和无水印直链
    """
    video_data = await crawler_service.get_single_video_by_url(url)
    if not video_data:
        raise HTTPException(status_code=400, detail="解析视频失败，可能链接已失效或不支持该平台")

    result = {
        "video_id": video_data.get("video_id"),
        "title": video_data.get("title", ""),
        "cover_url": video_data.get("cover_url"),
        "video_url": video_data.get("video_url"),  # 无水印 CDN 地址
        "platform": _detect_platform_from_url(url),
        "published_at": video_data.get("published_at"),
        "view_count": int(video_data.get("view_count") or 0),
        "like_count": int(video_data.get("like_count") or 0),
        "comment_count": int(video_data.get("comment_count") or 0),
        "share_count": int(video_data.get("share_count") or 0),
    }
    await operation_log_repo.create(
        db,
        action="download.parse",
        entity_type="video",
        entity_id=result.get("video_id"),
        actor=current_user.username,
        detail="解析无水印视频链接",
        extra={
            "source_url": url,
            "title": result.get("title", ""),
            "has_video_url": bool(result.get("video_url")),
        },
    )
    return result


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
        detail="代理下载无水印视频",
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
