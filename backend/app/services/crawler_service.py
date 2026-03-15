"""
爬虫服务：通过 fetcher 微服务获取博主与视频数据
"""
import logging
import os
from datetime import date, datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================
# 初始化：使用 httpx 调用独立的 douyin-fetcher 微服务
# ============================================================
INTERNAL_CRAWLER_URL = os.environ.get("INTERNAL_CRAWLER_URL", "http://douyin-fetcher:8080")

COOKIE_PLACEHOLDER_MARKERS = (
    "PLEASE_REPLACE_WITH_YOUR_OWN_COOKIE",
    "YOUR_COOKIE",
    "put your cookie here",
)


class CrawlerServiceError(Exception):
    """爬虫服务可预期错误（用于向上层返回可读提示）"""



class CrawlerService:
    """统一封装 douyin_api 的爬虫调用"""

    @staticmethod
    def _clean_url(text: str) -> str:
        """从杂乱的分享文本中提取干净的 URL，直接使用精准正则"""
        if not text:
            return ""
        import re
        # 匹配 http/https 开头，只匹配合法的 URL 字符组合，自然排除中文、空格等边界
        match = re.search(r'https?://[a-zA-Z0-9./\-_=&?%]+', text)
        if match:
            return match.group(0)
        return text

    async def _get_dynamic_cookie(self) -> str:
        """从数据库读取动态配置的 Douyin Cookie"""
        from app.repository.setting_repo import setting_repo
        from app.models.db_session import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as db:
                settings_dict = await setting_repo.get_all(db)
                cookie = settings_dict.get("DOUYIN_COOKIE", "")
                if self._is_placeholder_cookie(cookie):
                    return ""
                return cookie
        except Exception as e:
            logger.error(f"获取动态 Cookie 失败: {e}")
            return ""

    @staticmethod
    def _is_placeholder_cookie(cookie: str) -> bool:
        value = (cookie or "").strip()
        if not value:
            return True
        lowered = value.lower()
        return any(marker.lower() in lowered for marker in COOKIE_PLACEHOLDER_MARKERS)

    @staticmethod
    def _extract_http_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
        except Exception:
            pass
        return (response.text or "").strip()

    def _build_user_facing_parse_error(self, status_code: int, detail_text: str) -> str:
        detail = (detail_text or "").strip()
        lowered = detail.lower()

        if "sec_user_id" in detail or "cannot extract sec_user_id" in lowered:
            return "无法识别博主主页链接，请粘贴账号主页链接后重试"
        if (
            "响应内容为空" in detail
            or "获取数据失败" in detail
            or "user profile not found" in lowered
            or status_code == 404
            or status_code >= 500
        ):
            return "抖音 Cookie 未配置或已失效，请到系统设置更新 DOUYIN_COOKIE 后重试"
        return "博主采集失败，请检查主页链接或稍后重试"

    # ========== URL 解析 ==========

    async def parse_user_url(self, url: str, *, strict: bool = False) -> Optional[dict]:
        """
        解析博主主页 URL，返回用户基本信息。
        支持格式:
          - https://www.douyin.com/user/MS4wLjAB...
          - https://v.douyin.com/xxxxxx/
        """
        try:
            clean_url = self._clean_url(url)
            if not clean_url:
                message = "请输入有效的博主主页链接"
                if strict:
                    raise CrawlerServiceError(message)
                logger.warning(message)
                return None

            cookie = await self._get_dynamic_cookie()
            if not cookie:
                message = "抖音 Cookie 未配置或已失效，请到系统设置更新 DOUYIN_COOKIE 后重试"
                if strict:
                    raise CrawlerServiceError(message)
                logger.warning(message)
                return None
            headers = {"X-Douyin-Cookie": cookie} if cookie else {}

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(f"{INTERNAL_CRAWLER_URL}/api/user", params={"url": clean_url}, headers=headers)
                if res.status_code != 200:
                    detail = self._extract_http_error_detail(res)
                    user_message = self._build_user_facing_parse_error(res.status_code, detail)
                    logger.error(f"调用爬虫微服务获取用户失败: status={res.status_code}, detail={detail}")
                    if strict:
                        raise CrawlerServiceError(user_message)
                    return None
                data = res.json()

            sec_user_id = data.get("sec_user_id")
            profile_data = data.get("profile")

            if not sec_user_id or not profile_data:
                logger.error(f"无法从服务获取 sec_user_id 或主页信息: {clean_url}")
                if strict:
                    raise CrawlerServiceError("采集结果异常，请稍后重试")
                return None

            logger.info(f"提取 sec_user_id 成功: {sec_user_id}")
            user_info = self._parse_user_profile(profile_data, sec_user_id)
            if strict and not user_info:
                raise CrawlerServiceError("无法解析博主主页数据，请稍后重试")
            return user_info

        except CrawlerServiceError:
            raise
        except Exception as e:
            logger.error(f"解析博主 URL 异常: {e}", exc_info=True)
            if strict:
                raise CrawlerServiceError("博主采集服务暂时不可用，请稍后重试")
            return None

    def _parse_user_profile(self, raw_data: dict, sec_user_id: str) -> Optional[dict]:
        """
        解析 douyin_api 返回的用户主页数据结构。
        注意：返回结构会随 API 版本变化，做多层容错处理。
        """
        try:
            # 尝试常见的几种数据路径
            user = None

            # 路径 1: {"user": {...}}
            if "user" in raw_data:
                user = raw_data["user"]
            # 路径 2: {"data": {"user": {...}}}
            elif "data" in raw_data and isinstance(raw_data["data"], dict):
                data = raw_data["data"]
                if "user" in data:
                    user = data["user"]
                elif "user_info" in data:
                    user = data["user_info"]
            # 路径 3: 直接是用户对象（含 uid 字段）
            elif "uid" in raw_data:
                user = raw_data

            if not user:
                logger.error(f"无法在返回数据中找到 user 对象，raw_data keys: {list(raw_data.keys())}")
                return None

            result = {
                "platform": "douyin",
                "blogger_id": user.get("sec_uid") or sec_user_id,
                "sec_user_id": user.get("sec_uid") or sec_user_id,
                "nickname": user.get("nickname") or "未知用户",
                "avatar_url": self._extract_avatar(user),
                "signature": user.get("signature") or "",
                "follower_count": user.get("follower_count", 0),
                "following_count": user.get("following_count", 0),
                "total_like_count": user.get("total_favorited") or user.get("total_like_count", 0),
                "video_count": user.get("aweme_count") or user.get("video_count", 0),
            }

            logger.info(f"解析用户信息成功: {result['nickname']}, 粉丝: {result['follower_count']}")
            return result

        except Exception as e:
            logger.error(f"解析用户 profile 数据失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _extract_avatar(user: dict) -> Optional[str]:
        """从用户数据中提取头像 URL"""
        # avatar_larger > avatar_medium > avatar_thumb
        for field in ["avatar_larger", "avatar_medium", "avatar_thumb"]:
            avatar = user.get(field)
            if avatar and isinstance(avatar, dict):
                url_list = avatar.get("url_list", [])
                if url_list:
                    return url_list[0]
        return None

    # ========== 视频详情获取 ==========

    async def get_single_video_by_url(self, url: str) -> Optional[dict]:
        """
        根据抖音单条视频 URL 获取视频详情
        支持 https://v.douyin.com/xxx 或 https://www.douyin.com/video/xxx
        """
        try:
            clean_url = self._clean_url(url)
            cookie = await self._get_dynamic_cookie()
            headers = {"X-Douyin-Cookie": cookie} if cookie else {}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.get(f"{INTERNAL_CRAWLER_URL}/api/video", params={"url": clean_url}, headers=headers)
                if res.status_code != 200:
                    logger.error(f"调用爬虫微服务获取单条视频失败: {res.text}")
                    return None
                data = res.json()

            aweme_detail = data.get("aweme_detail")
            if not aweme_detail:
                logger.error(f"获取视频详情失败, 返回数据中无 aweme_detail")
                return None

            return self._parse_video_item(aweme_detail)
        except Exception as e:
            logger.error(f"获取单条视频异常: {e}", exc_info=True)
            return None

    # ========== 视频列表采集 ==========

    async def get_user_videos(
        self,
        platform: str,
        user_id: str,
        sec_user_id: str,
        count: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        采集博主的发布视频列表。count=None 表示采集全部。
        返回 list[dict]，每个 dict 包含视频基本信息。
        """
        if platform == "douyin":
            return await self._get_douyin_videos(sec_user_id, count, start_date, end_date)
        else:
            logger.warning(f"暂不支持平台: {platform}")
            return []

    async def _get_douyin_videos(
        self,
        sec_user_id: str,
        count: Optional[int],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """采集抖音博主视频列表，count=None 表示采集全部（上限 5000）"""
        try:
            videos = []
            max_cursor = 0
            has_date_range = bool(start_date or end_date)
            fetch_all = count is None or has_date_range
            limit = count if not fetch_all else 5000  # 全部模式安全上限
            batch_size = min(20, limit)
            
            cookie = await self._get_dynamic_cookie()
            headers = {"X-Douyin-Cookie": cookie} if cookie else {}

            async with httpx.AsyncClient(timeout=60.0) as client:
                while len(videos) < limit:
                    res = await client.get(
                        f"{INTERNAL_CRAWLER_URL}/api/videos", 
                        params={"sec_user_id": sec_user_id, "max_cursor": max_cursor, "count": batch_size},
                        headers=headers
                    )
                    if res.status_code != 200:
                        logger.error(f"获取视频列表微服务失败: {res.text}")
                        break
                        
                    response_data = res.json()
                    data = response_data.get("data", {})
                    
                    if not data:
                        break

                    aweme_list = data.get("aweme_list", [])
                    if not aweme_list:
                        break

                    reached_older_than_start = False
                    for item in aweme_list:
                        video_info = self._parse_video_item(item)
                        if not video_info:
                            continue

                        published_at = video_info.get("published_at")
                        published_date = published_at.date() if published_at else None

                        # 指定发布时间区间时，不包含没有发布时间的视频。
                        if (start_date or end_date) and not published_date:
                            continue

                        if end_date and published_date and published_date > end_date:
                            continue

                        if start_date and published_date and published_date < start_date:
                            reached_older_than_start = True
                            continue

                        videos.append(video_info)
                        if not fetch_all and len(videos) >= limit:
                            break

                    has_more = data.get("has_more", False)
                    max_cursor = data.get("max_cursor", 0)

                    # 抖音返回按时间倒序，已进入开始日期之前可提前停止继续翻页。
                    if start_date and reached_older_than_start:
                        break
                    if not has_more:
                        break
                    if not fetch_all and len(videos) >= limit:
                        break

            logger.info(f"共采集 {len(videos)} 条视频")
            return videos if fetch_all else videos[:limit]

        except Exception as e:
            logger.error(f"采集视频列表失败: {e}", exc_info=True)
            return []

    @staticmethod
    def _parse_publish_time(raw_value) -> Optional[datetime]:
        """解析平台返回的发布时间（秒/毫秒时间戳）为 UTC naive datetime。"""
        if raw_value in (None, ""):
            return None
        try:
            ts = int(raw_value)
            if ts > 10_000_000_000:  # 毫秒时间戳
                ts = ts // 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _parse_video_item(item: dict) -> Optional[dict]:
        """解析单条视频数据"""
        try:
            video_node = item.get("video", {})

            # 封面图
            cover_url = None
            cover_data = video_node.get("cover") or video_node.get("dynamic_cover")
            if isinstance(cover_data, dict):
                url_list = cover_data.get("url_list", [])
                cover_url = url_list[0] if url_list else None

            # 视频播放地址 - 优先使用无水印高清 CDN 地址
            # NOTE: 核心逻辑与 douyin_api/hybrid_crawler.py 保持一致：
            #   play_addr.url_list[0] 是带水印的 CDN 地址（含 playwm），
            #   将 playwm 替换为 play 即可得到真正的无水印高清地址。
            #   uri 拼接方式只作为最后兜底，优先级最低。
            video_url = None
            play_addr = video_node.get("play_addr") or video_node.get("download_addr")
            if isinstance(play_addr, dict):
                url_list = play_addr.get("url_list", [])
                if url_list:
                    # 优先：取 CDN url_list[0]，将 playwm 替换为 play 得到无水印地址
                    raw_cdn_url = url_list[0]
                    video_url = raw_cdn_url.replace("playwm", "play")
                else:
                    # 兜底：使用 uri 拼接播放地址
                    uri = play_addr.get("uri", "")
                    if uri:
                        if uri.startswith("http"):
                            video_url = uri
                        else:
                            video_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"

            # 统计数据
            stats = item.get("statistics", {})

            return {
                "video_id": item.get("aweme_id", ""),
                "title": item.get("desc", ""),
                "description": item.get("desc", ""),
                "cover_url": cover_url,
                "video_url": video_url,
                "view_count": stats.get("play_count") or stats.get("play_cnt") or 0,
                "like_count": stats.get("digg_count", 0),
                "comment_count": stats.get("comment_count", 0),
                "share_count": stats.get("share_count", 0),
                "duration": video_node.get("duration", 0) // 1000,  # ms → s
                "published_at": CrawlerService._parse_publish_time(item.get("create_time")),
            }
        except Exception as e:
            logger.error(f"解析视频条目失败: {e}")
            return None


crawler_service = CrawlerService()
