"""统一封装视频代理下载能力，供多个 API 端点复用。"""
import os
import re
import urllib.parse
import logging
from typing import Optional, AsyncGenerator

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repository.setting_repo import setting_repo
from app.services.crawler_service import crawler_service
from app.services.url_security import is_allowed_media_url

logger = logging.getLogger(__name__)

_INVALID_FILENAME_CHARS = re.compile(r'[/\\:*?"<>|]')


def build_safe_filename(filename: str) -> str:
    """清洗文件名并保证 mp4 后缀，防止路径字符注入。"""
    safe_filename = _INVALID_FILENAME_CHARS.sub("_", (filename or "").strip())
    if not safe_filename:
        safe_filename = "video.mp4"
    if not safe_filename.lower().endswith(".mp4"):
        safe_filename += ".mp4"
    return safe_filename


def _normalized_positive(value: int, *, minimum: int, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, parsed)


def _build_http_timeout() -> httpx.Timeout:
    connect_timeout = _normalized_positive(
        settings.DOWNLOAD_PROXY_CONNECT_TIMEOUT_SECONDS,
        minimum=3,
        fallback=15,
    )
    read_timeout = _normalized_positive(
        settings.DOWNLOAD_PROXY_READ_TIMEOUT_SECONDS,
        minimum=10,
        fallback=120,
    )
    return httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=read_timeout,
        pool=connect_timeout,
    )


def _chunk_size_bytes() -> int:
    return _normalized_positive(
        settings.DOWNLOAD_PROXY_CHUNK_SIZE_BYTES,
        minimum=64 * 1024,
        fallback=512 * 1024,
    )


def _max_network_retries() -> int:
    retries = _normalized_positive(
        settings.DOWNLOAD_PROXY_MAX_NETWORK_RETRIES,
        minimum=0,
        fallback=1,
    )
    return min(retries, 3)


async def _get_douyin_cookie(db: AsyncSession) -> str:
    """优先从系统设置读取 Cookie；为空时回退 fetcher 端点。"""
    try:
        settings_dict = await setting_repo.get_all(db)
        douyin_cookie = settings_dict.get("DOUYIN_COOKIE", "")
        if douyin_cookie:
            return douyin_cookie

        internal_crawler_url = os.environ.get("INTERNAL_CRAWLER_URL", "http://douyin-fetcher:8080")
        fetcher_timeout = _normalized_positive(
            settings.DOWNLOAD_PROXY_FETCHER_TIMEOUT_SECONDS,
            minimum=2,
            fallback=10,
        )
        async with httpx.AsyncClient(timeout=fetcher_timeout) as fetcher_client:
            res = await fetcher_client.get(f"{internal_crawler_url}/api/cookie")
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, dict):
                    return data.get("cookie", "")
    except Exception as exc:
        logger.warning("获取 Douyin Cookie 失败，继续使用空 Cookie: %s", exc)
    return ""


def _build_download_headers(cookie: str) -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
        "Cookie": cookie,
    }


async def _video_stream(
    *,
    source_url: str,
    headers: dict[str, str],
    video_id: Optional[str],
) -> AsyncGenerator[bytes, None]:
    current_url = source_url
    retries_left = _max_network_retries()
    timeout = _build_http_timeout()

    while True:
        emitted_bytes = False
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                req = client.build_request("GET", current_url, headers=headers)
                resp = await client.send(req, stream=True)

                if resp.status_code == 403 and video_id:
                    try:
                        await resp.aclose()
                    except Exception:
                        pass

                    logger.info("代理下载遇到 403，尝试使用 video_id %s 重新获取视频信息", video_id)
                    fresh_video = await crawler_service.get_single_video_by_url(
                        f"https://www.douyin.com/video/{video_id}"
                    )
                    if fresh_video and fresh_video.get("video_url"):
                        current_url = fresh_video["video_url"]
                        req = client.build_request("GET", current_url, headers=headers)
                        resp = await client.send(req, stream=True)

                if resp.status_code not in (200, 206):
                    try:
                        await resp.aclose()
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"视频源请求失败 (HTTP {resp.status_code})",
                    )

                try:
                    async for chunk in resp.aiter_bytes(chunk_size=_chunk_size_bytes()):
                        if not chunk:
                            continue
                        emitted_bytes = True
                        yield chunk
                finally:
                    try:
                        await resp.aclose()
                    except Exception:
                        pass
                return
        except HTTPException:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            if emitted_bytes or retries_left <= 0:
                logger.error("代理下载失败，网络异常且无法继续重试: %s", exc)
                raise HTTPException(
                    status_code=502,
                    detail="下载源网络异常，请稍后重试。",
                ) from exc

            logger.warning(
                "代理下载网络异常，准备重试（剩余重试次数=%s）: %s",
                retries_left,
                exc,
            )
            retries_left -= 1


async def build_proxy_download_response(
    *,
    url: str,
    filename: str,
    video_id: Optional[str],
    db: AsyncSession,
) -> StreamingResponse:
    """构造统一的视频代理下载响应。"""
    if not is_allowed_media_url(url):
        raise HTTPException(status_code=400, detail="不支持的视频来源域名")

    douyin_cookie = await _get_douyin_cookie(db)
    headers = _build_download_headers(douyin_cookie)
    safe_filename = build_safe_filename(filename)
    encoded_filename = urllib.parse.quote(safe_filename)

    return StreamingResponse(
        _video_stream(source_url=url, headers=headers, video_id=video_id),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}",
            "Cache-Control": "no-cache",
        },
    )
