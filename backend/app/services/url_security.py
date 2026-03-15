"""URL 安全校验工具。"""
from urllib.parse import urlparse


ALLOWED_MEDIA_DOMAINS = (
    "douyinvod.com",
    "douyin.com",
    "snssdk.com",
    "tiktokv.com",
    "tiktok.com",
    "bytedance.com",
    "douyinstatic.com",
    "byteimg.com",
    "zjcdn.com",
    "douyinpic.com",
    "iesdouyin.com",
    "amemv.com",
    "ixigua.com",
    "pstatp.com",
)


def is_allowed_media_url(url: str) -> bool:
    """严格校验下载地址，防止子串匹配绕过。"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        host = (parsed.hostname or "").lower().strip(".")
        if not host:
            return False

        return any(host == d or host.endswith(f".{d}") for d in ALLOWED_MEDIA_DOMAINS)
    except Exception:
        return False
