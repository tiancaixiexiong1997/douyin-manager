"""
AI 分析服务：通过关键帧或文本分析博主视频风格
"""
import os
import asyncio
import base64
import logging
import tempfile
import subprocess
import math
from typing import Any, Optional

import httpx

from app.config import settings
from app.services.prompt_templates import (
    ACCOUNT_PLAN_PROMPT_TEMPLATE,
    BLOGGER_REPORT_PROMPT_TEMPLATE,
    BLOGGER_VIRAL_PROFILE_PROMPT_TEMPLATE,
    CONTENT_CALENDAR_PROMPT_TEMPLATE,
    GLOBAL_AI_FACT_RULES_TEMPLATE,
    GLOBAL_AI_WRITING_RULES_TEMPLATE,
    NEXT_TOPIC_BATCH_PROMPT_TEMPLATE,
    PERFORMANCE_RECAP_PROMPT_TEMPLATE,
    PLANNING_INTAKE_PROMPT_TEMPLATE,
    SCRIPT_REMAKE_PROMPT_TEMPLATE,
    VIDEO_SCRIPT_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)

class AIAnalysisService:
    """AI 分析服务，下载并压缩视频后整体发送给多模态 AI（含音频）"""

    DEFAULT_GLOBAL_AI_FACT_RULES = GLOBAL_AI_FACT_RULES_TEMPLATE
    DEFAULT_GLOBAL_AI_WRITING_RULES = GLOBAL_AI_WRITING_RULES_TEMPLATE
    DEFAULT_BLOGGER_REPORT_PROMPT = BLOGGER_REPORT_PROMPT_TEMPLATE
    DEFAULT_BLOGGER_VIRAL_PROFILE_PROMPT = BLOGGER_VIRAL_PROFILE_PROMPT_TEMPLATE
    DEFAULT_ACCOUNT_PLAN_PROMPT = ACCOUNT_PLAN_PROMPT_TEMPLATE
    DEFAULT_CONTENT_CALENDAR_PROMPT = CONTENT_CALENDAR_PROMPT_TEMPLATE
    DEFAULT_NEXT_TOPIC_BATCH_PROMPT = NEXT_TOPIC_BATCH_PROMPT_TEMPLATE
    DEFAULT_PERFORMANCE_RECAP_PROMPT = PERFORMANCE_RECAP_PROMPT_TEMPLATE
    DEFAULT_PLANNING_INTAKE_PROMPT = PLANNING_INTAKE_PROMPT_TEMPLATE
    DEFAULT_VIDEO_SCRIPT_PROMPT = VIDEO_SCRIPT_PROMPT_TEMPLATE
    DEFAULT_SCRIPT_REMAKE_PROMPT = SCRIPT_REMAKE_PROMPT_TEMPLATE
    PROMPT_SCENE_SETTING_MAP = {
        "blogger_report": "BLOGGER_REPORT_PROMPT",
        "blogger_viral_profile": "BLOGGER_VIRAL_PROFILE_PROMPT",
        "account_plan": "ACCOUNT_PLAN_PROMPT",
        "content_calendar": "CONTENT_CALENDAR_PROMPT",
        "next_topic_batch": "NEXT_TOPIC_BATCH_PROMPT",
        "performance_recap": "PERFORMANCE_RECAP_PROMPT",
        "planning_intake": "PLANNING_INTAKE_PROMPT",
        "video_script": "VIDEO_SCRIPT_PROMPT",
        "script_remake": "SCRIPT_REMAKE_PROMPT",
    }
    WRITING_RULE_SCENES = {
        "blogger_viral_profile",
        "account_plan",
        "content_calendar",
        "performance_recap",
        "next_topic_batch",
        "planning_intake",
        "video_script",
        "script_remake",
    }

    def __init__(self):
        # 默认回退配置
        self.default_api_key = settings.AI_API_KEY
        self.default_base_url = settings.AI_BASE_URL
        self.default_model = settings.AI_MODEL
        self.default_failover_enabled = bool(settings.AI_FAILOVER_ENABLED)
        self.default_backup_api_key = settings.AI_API_KEY_BACKUP
        self.default_backup_base_url = settings.AI_BASE_URL_BACKUP
        self.default_backup_model = settings.AI_MODEL_BACKUP
        self.max_tokens = settings.AI_MAX_TOKENS
        self.temperature = settings.AI_TEMPERATURE
        
        # 缓存设置
        self._cached_settings = {}

    def _format_ffmpeg_error(self, stderr: bytes, stdout: bytes | None = None) -> str:
        raw = (stderr or b"").decode("utf-8", errors="ignore").strip()
        if not raw and stdout:
            raw = (stdout or b"").decode("utf-8", errors="ignore").strip()
        if not raw:
            return "未知 FFmpeg 错误"
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            return "未知 FFmpeg 错误"
        return " | ".join(lines[-4:])[:400]

    def _run_ffmpeg_with_fallback(self, commands: list[tuple[str, list[str]]], *, timeout: int = 120) -> tuple[bool, str]:
        last_error = "未知 FFmpeg 错误"
        for label, cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                last_error = f"FFmpeg 处理超时（>{timeout} 秒）"
                logger.warning("FFmpeg 压缩方案超时(label=%s timeout=%s)", label, timeout)
                continue
            if result.returncode == 0:
                if label != "primary":
                    logger.warning("FFmpeg 主压缩方案失败，已使用回退方案成功完成压缩")
                return True, ""
            last_error = self._format_ffmpeg_error(result.stderr, result.stdout)
            logger.warning("FFmpeg 压缩方案失败(label=%s): %s", label, last_error)
        return False, last_error

    def _probe_video_duration(self, file_path: str) -> Optional[float]:
        """读取视频时长（秒）；失败时返回 None。"""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    file_path,
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if result.returncode != 0:
                return None
            raw = (result.stdout or "").strip()
            if not raw:
                return None
            duration = float(raw)
            return duration if duration > 0 else None
        except Exception:
            return None

    def _resolve_ffmpeg_timeout(self, duration_seconds: Optional[float], *, minimum: int = 120) -> int:
        """按视频时长为 FFmpeg 分配更合理的超时时间。"""
        if not duration_seconds or duration_seconds <= 0:
            return minimum
        # 给低配 VPS 更宽松一点，避免 5-10 分钟素材在压缩阶段误判失败。
        estimated = int(math.ceil(duration_seconds * 0.75)) + 120
        return max(minimum, min(estimated, 900))
        
    async def reload_settings(self, db=None):
        """重新加载设置缓存"""
        if db is None:
            from app.models.db_session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                from app.repository.setting_repo import setting_repo
                self._cached_settings = await setting_repo.get_all(session)
        else:
            from app.repository.setting_repo import setting_repo
            self._cached_settings = await setting_repo.get_all(db)

    async def _get_current_setting(self, key: str, default_value):
        """获取当前设置，如果缓存为空则加载一次"""
        if not hasattr(self, '_settings_loaded') or not getattr(self, '_settings_loaded'):
            await self.reload_settings()
            self._settings_loaded = True
        return self._cached_settings.get(key, default_value)

    async def _resolve_prompt(
        self,
        *,
        scene_key: str,
        default_prompt: str,
        db: Optional[Any] = None,
    ) -> tuple[str, dict]:
        """解析当前场景应使用的提示词（固定使用当前设置，不再走版本实验链路）。"""
        setting_key = self.PROMPT_SCENE_SETTING_MAP.get(scene_key, "")
        fallback_prompt = await self._get_current_setting(setting_key, default_prompt)
        return fallback_prompt, {
            "prompt_version_id": None,
            "ab_experiment_id": None,
            "ab_branch": "BASE",
            "scene_key": scene_key,
        }

    async def _build_system_prompt(self, *, scene_key: str, base_prompt: str) -> str:
        factual_rules = str(
            await self._get_current_setting(
                "GLOBAL_AI_FACT_RULES",
                self.DEFAULT_GLOBAL_AI_FACT_RULES,
            )
        ).strip()
        writing_rules = str(
            await self._get_current_setting(
                "GLOBAL_AI_WRITING_RULES",
                self.DEFAULT_GLOBAL_AI_WRITING_RULES,
            )
        ).strip()

        sections = [base_prompt.strip()]
        if factual_rules:
            sections.append(factual_rules)
        if scene_key in self.WRITING_RULE_SCENES and writing_rules:
            sections.append(writing_rules)
        return "\n\n".join(section for section in sections if section)

    async def _record_prompt_run(
        self,
        *,
        scene_key: str,
        result: dict,
        prompt_meta: dict,
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> None:
        """实验链路已停用，保留空实现以兼容现有调用。"""
        return None

    async def _download_video_with_retry(
        self,
        video_url: str,
        temp_file_path: str,
        max_retries: int = 3,
        video_id: str = None,
    ) -> tuple[bool, str]:
        """带重试的视频下载，优先使用 httpx 流式下载并验证大小"""
        import asyncio
        import os
        import httpx
        import urllib.request
        
        # 获取 Douyin 核心配置中的 Cookie
        try:
            INTERNAL_CRAWLER_URL = os.environ.get("INTERNAL_CRAWLER_URL", "http://douyin-fetcher:8080")
            async with httpx.AsyncClient(timeout=10.0) as fetcher_client:
                res = await fetcher_client.get(f"{INTERNAL_CRAWLER_URL}/api/cookie")
                douyin_cookie = res.json().get("cookie", "") if res.status_code == 200 else ""
        except Exception as e:
            logger.warning(f"无法从爬虫微服务获取 Cookie: {e}")
            douyin_cookie = ""

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
            "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Range": "bytes=0-", # 提示服务器支持断点续传/完整流
            "Cookie": douyin_cookie
        }

        
        # 尝试 1：优先使用 httpx 流式下载 (针对大文件和抖音 CDN 更健壮)
        current_url = video_url
        last_error = ""
        for attempt in range(max_retries):
            try:
                logger.info(f"httpx 流式下载尝试 {attempt + 1}")
                async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                    req = client.build_request("GET", current_url, headers=headers)
                    response = await client.send(req, stream=True)
                    
                    if response.status_code == 403 and video_id:
                        try:
                            await response.aclose()
                        except Exception:
                            pass
                        from app.services.crawler_service import crawler_service
                        logger.info(f"下载大文件遇到 403，尝试使用 video_id {video_id} 重新获取视频信息")
                        fresh_video = await crawler_service.get_single_video_by_url(f"https://www.douyin.com/video/{video_id}")
                        if fresh_video and fresh_video.get("video_url"):
                            current_url = fresh_video["video_url"]
                            logger.info("已获取到新的视频 CDN 地址，重新尝试下载")
                            req = client.build_request("GET", current_url, headers=headers)
                            response = await client.send(req, stream=True)
                    
                    if response.status_code not in (200, 206):
                        try:
                            await response.aclose()
                        except Exception:
                            pass
                        raise Exception(f"HTTP {response.status_code}")
                        
                    try:
                        expected_size = int(response.headers.get("Content-Length", 0))
                        logger.info(f"预期文件大小: {expected_size / 1024 / 1024:.2f} MB")
                        
                        with open(temp_file_path, "wb") as f:
                            downloaded_size = 0
                            async for chunk in response.aiter_bytes(chunk_size=1024*1024): # 1MB chunk
                                f.write(chunk)
                                downloaded_size += len(chunk)
                        
                        # 验证完整性
                        if expected_size > 0 and downloaded_size < expected_size:
                            logger.warning(f"下载不完整: 实际 {downloaded_size} < 预期 {expected_size}，尝试删除并重试")
                            if os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
                            continue
                        
                        # 启发式校验：如果视频明明应该很大（时长久），下载却特别小，也视为失败
                        if downloaded_size < 512 * 1024: # 小于 512KB 几乎不可能是完整视频
                            logger.warning(f"下载文件过小 ({downloaded_size} bytes)，可能下载不完整")
                            # 此处先不直接中断，由 AI 后续处理
                            
                        logger.info(f"httpx 下载成功，大小: {downloaded_size / 1024 / 1024:.2f} MB")
                        return True, ""
                    finally:
                        try:
                            await response.aclose()
                        except Exception:
                            pass
            except Exception as e:
                last_error = str(e)
                logger.warning(f"httpx 下载尝试 {attempt + 1} 失败: {e}")
                if os.path.exists(temp_file_path):
                    try: os.unlink(temp_file_path)
                    except: pass
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
        
        # 尝试 2：使用 urllib 兜底
        try:
            logger.info("尝试使用 urllib 兜底下载...")
            def download_sync():
                req = urllib.request.Request(current_url, headers=headers)
                with urllib.request.urlopen(req, timeout=120) as response:
                    if response.getcode() not in (200, 206):
                        raise Exception(f"HTTP {response.getcode()}")
                    with open(temp_file_path, 'wb') as f:
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                return True
                
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download_sync)
            logger.info("urllib 成功完成下载兜底")
            return True, ""
        except Exception as e:
            logger.error(f"所有下载方式均失败: {e}")
            return False, str(e) or last_error or "未知下载错误"

    async def analyze_video_style(
        self,
        video_url: str,
        title: str,
        description: str,
        video_id: str = None,
        progress_task_id: str | None = None,
    ) -> dict:
        """
        分析单条视频的拍摄手法、音频风格和文案特点

        Args:
            video_url: 视频 URL
            title: 视频标题
            description: 视频描述

        Returns:
            结构化分析结果，失败时返回 {"error": "..."}
        """
        if not video_url:
            return {"error": "未提供视频 URL，无法进行分析"}
        return await self._analyze_by_video(
            video_url,
            title,
            description,
            video_id,
            progress_task_id=progress_task_id,
        )

    async def _analyze_by_video(
        self,
        video_url: str,
        title: str,
        description: str,
        video_id: str = None,
        progress_task_id: str | None = None,
    ) -> dict:
        """下载并压缩视频，整体发送给多模态 AI 分析（含音频）"""
        temp_original = None
        compressed_path = None

        def _set_progress(step: str, message: str | None = None) -> None:
            if not progress_task_id:
                return
            try:
                from app.services.progress import progress_registry

                progress_registry.set(progress_task_id, step, message)
            except Exception as progress_exc:
                logger.warning(
                    "更新任务进度失败(task_id=%s step=%s): %s",
                    progress_task_id,
                    step,
                    progress_exc,
                )

        try:
            # 1. 检查 ffmpeg
            check = subprocess.run(["which", "ffmpeg"], capture_output=True)
            if check.returncode != 0:
                return {"error": "ffmpeg 未安装，无法处理视频"}

            # 2. 下载视频
            _set_progress("downloading", "下载代表作视频中...")
            logger.info(f"开始下载视频: {video_url[:60]}...")
            temp_original = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            temp_original.close()  # Close it since _download_video_with_retry will handle writing
            try:
                download_ok, download_error = await self._download_video_with_retry(video_url, temp_original.name, video_id=video_id)
                if not download_ok or not os.path.exists(temp_original.name):
                    detail = f"（{download_error}）" if download_error else ""
                    error_message = f"视频下载失败：源文件未成功保存到本地，请稍后重试{detail}"
                    _set_progress("failed", error_message)
                    return {"error": error_message}
                size_mb = os.path.getsize(temp_original.name) / 1024 / 1024
                if size_mb <= 0:
                    error_message = "视频下载失败：下载结果为空文件，请稍后重试"
                    _set_progress("failed", error_message)
                    return {"error": error_message}
                logger.info(f"下载完成，本地文件大小: {size_mb:.1f}MB")
            except Exception as e:
                logger.error(f"视频下载失败: {e}")
                raise e

            duration_seconds = self._probe_video_duration(temp_original.name)
            ffmpeg_timeout = self._resolve_ffmpeg_timeout(duration_seconds)
            if duration_seconds:
                logger.info(
                    "代表作视频时长约 %.1f 秒，FFmpeg 超时设置为 %s 秒",
                    duration_seconds,
                    ffmpeg_timeout,
                )

            # 3. 压缩视频：480p / 15fps / CRF28 / 64kbps 单声道
            _set_progress("compressing", "压缩代表作视频中...")
            compressed_path = temp_original.name.replace(".mp4", "_c.mp4")
            ffmpeg_commands = [
                (
                    "primary",
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-i", temp_original.name,
                        "-vf", "scale=480:-2",
                        "-r", "15",
                        "-c:v", "libx264", "-crf", "30", "-preset", "veryfast",
                        "-c:a", "aac", "-b:a", "64k", "-ac", "1",
                        "-movflags", "+faststart",
                        "-y", compressed_path,
                    ],
                ),
                (
                    "fallback",
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-i", temp_original.name,
                        "-vf", "scale=480:-2",
                        "-r", "12",
                        "-c:v", "mpeg4", "-q:v", "8",
                        "-c:a", "aac", "-b:a", "64k", "-ac", "1",
                        "-movflags", "+faststart",
                        "-y", compressed_path,
                    ],
                ),
            ]
            success, ffmpeg_error = self._run_ffmpeg_with_fallback(ffmpeg_commands, timeout=ffmpeg_timeout)
            if not success:
                error_message = f"视频压缩失败: {ffmpeg_error}"
                _set_progress("failed", error_message)
                return {"error": error_message}

            compressed_size = os.path.getsize(compressed_path)
            logger.info(f"压缩完成，大小: {compressed_size / 1024 / 1024:.1f}MB")

            # 4. 读取并 base64 编码
            with open(compressed_path, "rb") as f:
                video_b64 = base64.b64encode(f.read()).decode("utf-8")

            # 5. 调用 AI
            _set_progress("ai_video", "AI 视频深度分析中...")
            return await self._call_ai_with_video(video_b64, title, description)

        except Exception as e:
            logger.error(f"视频分析失败: {e}")
            error_message = f"分析异常: {str(e)}"
            _set_progress("failed", error_message)
            return {"error": error_message}
        finally:
            for path in [
                temp_original.name if temp_original else None,
                compressed_path
            ]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

    async def generate_remake_script(
        self,
        video_url: str,
        title: str,
        description: str,
        user_prompt: str,
        account_plan_data: dict = None,
        video_id: str = None,
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """
        根据原始视频的画面、音频和用户提供的提示词/思路，
        多模态分析视频内容并提取亮点，进而生成对应风格的复刻脚本。
        """
        if not video_url:
            return {"error": "未提供视频 URL，无法进行分析"}
        return await self._analyze_remake_by_video(
            video_url,
            title,
            description,
            user_prompt,
            account_plan_data,
            video_id,
            run_context=run_context,
            db=db,
        )

    async def _analyze_remake_by_video(
        self,
        video_url: str,
        title: str,
        description: str,
        user_prompt: str,
        account_plan_data: dict = None,
        video_id: str = None,
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """下载压缩视频，发送给 AI (携带特制提示词) 拆解并生成复刻脚本"""
        temp_original = None
        compressed_path = None
        try:
            check = subprocess.run(["which", "ffmpeg"], capture_output=True)
            if check.returncode != 0:
                return {"error": "ffmpeg 未安装，无法处理视频"}

            logger.info(f"开始下载复刻原视频: {video_url[:60]}...")
            temp_original = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            temp_original.close()
            try:
                download_ok, download_error = await self._download_video_with_retry(video_url, temp_original.name, video_id=video_id)
                if not download_ok or not os.path.exists(temp_original.name):
                    detail = f"（{download_error}）" if download_error else ""
                    return {"error": f"视频下载失败：源文件未成功保存到本地，请稍后重试{detail}"}
                if os.path.getsize(temp_original.name) <= 0:
                    return {"error": "视频下载失败：下载结果为空文件，请稍后重试"}
            except Exception as e:
                logger.error(f"视频下载失败: {e}")
                raise e

            duration_seconds = self._probe_video_duration(temp_original.name)
            ffmpeg_timeout = self._resolve_ffmpeg_timeout(duration_seconds)

            compressed_path = temp_original.name.replace(".mp4", "_c.mp4")
            ffmpeg_commands = [
                (
                    "primary",
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-i", temp_original.name,
                        "-vf", "scale=360:-2", "-r", "10",
                        "-c:v", "libx264", "-crf", "33", "-preset", "veryfast",
                        "-c:a", "aac", "-b:a", "48k", "-ac", "1",
                        "-movflags", "+faststart", "-y", compressed_path,
                    ],
                ),
                (
                    "fallback",
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-i", temp_original.name,
                        "-vf", "scale=360:-2", "-r", "8",
                        "-c:v", "mpeg4", "-q:v", "9",
                        "-c:a", "aac", "-b:a", "48k", "-ac", "1",
                        "-movflags", "+faststart", "-y", compressed_path,
                    ],
                ),
            ]
            success, ffmpeg_error = self._run_ffmpeg_with_fallback(ffmpeg_commands, timeout=ffmpeg_timeout)
            if not success:
                return {"error": f"视频压缩失败: {ffmpeg_error}"}

            with open(compressed_path, "rb") as f:
                video_b64 = base64.b64encode(f.read()).decode("utf-8")
                
            logger.info(f"复刻提取压缩完成，Base64大小约: {len(video_b64) / 1024 / 1024:.1f}MB")

            # 构建 system_prompt：有账号策划时注入人设约束，无时使用通用高标准角色
            if account_plan_data:
                core_identity = account_plan_data.get('core_identity', '未知定位')
                target_audience = account_plan_data.get('target_audience', '未知受众')
                base_system_prompt = (
                    f"你现在是「{core_identity}」这个账号的首席内容编导。\n"
                    f"你的目标受众是：{target_audience}。\n"
                    "你的核心工作原则：\n"
                    "1. 从爆款视频中提取底层结构（情绪曲线、钩子机制、节奏节拍），而不是复制内容\n"
                    "2. 将提取的爆款结构完整移植到符合本账号人设和受众的全新主题上\n"
                    "3. 新脚本中不得出现原视频博主的任何个人痕迹（语气/品牌/人物）\n"
                    "4. 每一句台词都必须符合本账号的语言风格和目标受众的认知习惯\n"
                    "5. 宁可脚本简短有力，也不为凑时长输出低密度内容\n"
                    "6. 默认普通人单人可执行：优先口播主镜头+画中画补拍，或跟拍Vlog边做边说\n"
                    "7. 禁止设计依赖演技、多人对戏或复杂调度的情景剧拍法"
                )
            else:
                base_system_prompt = (
                    "你是一位顶级短视频内容编导，专注于爆款结构拆解与复刻移植。\n"
                    "你的核心能力：精准识别一条视频'为什么能火'的底层原因——"
                    "不是它讲了什么，而是它用了什么情绪结构、钩子机制和节奏节拍——"
                    "然后把这套爆款基因完整移植到全新主题上，生成可以直接开拍的脚本。\n"
                    "你坚持的标准：台词必须是真实的人能说出口的句子，"
                    "开头必须直接制造冲突或悬念，结尾必须留下让人想评论的钩子。\n"
                    "默认输出普通人单人拍法：口播+画中画，或跟拍Vlog；禁止情景剧式重表演脚本。"
                )

            system_prompt = await self._build_system_prompt(
                scene_key="script_remake",
                base_prompt=base_system_prompt,
            )

            # 兜底 user_prompt：基于账号定位动态生成，而非静态文本
            if user_prompt and user_prompt.strip():
                final_user_prompt = user_prompt.strip()
            elif account_plan_data:
                final_user_prompt = (
                    f"请以「{account_plan_data.get('core_identity', '本账号')}」的人设为核心，"
                    f"面向「{account_plan_data.get('target_audience', '目标受众')}」，"
                    "提取原视频的爆款结构和情绪钩子，生成一份完全匹配本账号风格的翻拍脚本。"
                    "脚本执行形式默认采用普通人友好路线：先口播再补拍画中画；若适配vlog则边做边说。"
                )
            else:
                final_user_prompt = (
                    "请提取原视频的爆款底层结构（情绪曲线+钩子机制+节奏节拍），"
                    "并基于这套结构生成一份主题创新、可直接开拍的复刻脚本。"
                    "优先普通人可执行方案：口播+画中画，或vlog边做边说，避免演技门槛。"
                )

            prompt_template, prompt_meta = await self._resolve_prompt(
                scene_key="script_remake",
                default_prompt=self.DEFAULT_SCRIPT_REMAKE_PROMPT,
                db=db,
            )
            prompt_text = prompt_template.format(
                title=title,
                description=description,
                user_prompt=final_user_prompt
            )
            content = [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:video/mp4;base64,{video_b64}"}}
            ]
            result = await self._call_ai(system_prompt, content)
            await self._record_prompt_run(
                scene_key="script_remake",
                result=result,
                prompt_meta=prompt_meta,
                run_context=run_context,
                db=db,
            )
            return result

        except Exception as e:
            logger.error(f"拆解复刻生成失败: {e}")
            return {"error": f"分析异常: {str(e)}"}
        finally:
            for path in [temp_original.name if temp_original else None, compressed_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

    async def _call_ai_with_video(self, video_b64: str, title: str, description: str) -> dict:
        """携带完整视频（含音频）调用 AI API 分析"""
        base_system_prompt = (
            "你是一位顶级短视频内容分析专家，专注于从视频的画面、音频和文案中提炼可复制的内容规律。\n"
            "你的分析标准：每个结论都必须能在视频中找到具体的画面或声音证据；"
            "描述风格特征时必须具体到操作层面（如'每5秒一次跳切'而非'节奏快'）；"
            "分析爆款因素时必须指出它触动了观众的哪种具体情绪，而不是笼统说'有吸引力'。\n"
            "你的分析目标：让另一个创作者读完报告后，能直接提炼出可复用的拍摄和文案方法论。"
        )
        system_prompt = await self._build_system_prompt(scene_key="video_analysis", base_prompt=base_system_prompt)
        user_prompt = (
            "请基于这段完整视频（含画面与音频），以及视频文字信息，对该视频进行深度分析：\n\n"
            f"视频标题：{title}\n"
            f"视频描述：{description}\n\n"
            "请按以下结构输出分析（JSON格式）：\n"
            "{{\n"
            '  "content_summary": "视频内容概述（2-3句话）",\n'
            '  "filming_style": {{\n'
            '    "shot_types": "镜头运用（近景/全景/特写等）",\n'
            '    "editing_pace": "剪辑节奏（快切/慢节奏/跳切等）",\n'
            '    "visual_style": "视觉风格（色调/构图/场景特点）",\n'
            '    "special_techniques": "特殊拍摄手法"\n'
            '  }},\n'
            '  "audio_style": {{\n'
            '    "bgm": "背景音乐风格与情绪（如：欢快流行/抒情钢琴/无音乐等）",\n'
            '    "sound_effects": "音效运用（如：转场音效/强调音效/无）",\n'
            '    "voice_style": "人声风格（如：口播/配音/无人声等）",\n'
            '    "audio_pacing": "音频节奏与画面的配合方式"\n'
            '  }},\n'
            '  "copywriting_style": {{\n'
            '    "hook_method": "开头吸引手法（问句/冲突/悬念等）",\n'
            '    "language_tone": "语言风格（口语/专业/搞笑/感性等）",\n'
            '    "structure": "文案结构（痛点-解决-CTA等）",\n'
            '    "cta_style": "结尾行动引导方式"\n'
            '  }},\n'
            '  "content_strategy": {{\n'
            '    "content_type": "内容类型（口播+画中画/跟拍Vlog/教程/测评/探店实拍等）",\n'
            '    "target_pain_points": "核心触达痛点或需求",\n'
            '    "engagement_tactics": "提升互动的策略"\n'
            '  }},\n'
            '  "viral_factors": ["爆款因素1", "爆款因素2", "爆款因素3"]\n'
            "}}\n\n"
            "请严格返回 JSON 格式。"
        )

        content = [
            {"type": "text", "text": user_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:video/mp4;base64,{video_b64}"}
            }
        ]

        return await self._call_ai(system_prompt, content)

    async def _call_ai(self, system_prompt: str, user_content) -> dict:
        """通用 AI API 调用"""
        try:
            import json
            import re

            def _to_bool(raw_value: Any) -> bool:
                if isinstance(raw_value, bool):
                    return raw_value
                if raw_value is None:
                    return False
                return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}

            api_key = str(await self._get_current_setting("AI_API_KEY", self.default_api_key) or "").strip()
            base_url = str(await self._get_current_setting("AI_BASE_URL", self.default_base_url) or "").strip().rstrip("/")
            model = str(await self._get_current_setting("AI_MODEL", self.default_model) or "").strip()
            failover_enabled = _to_bool(
                await self._get_current_setting("AI_FAILOVER_ENABLED", self.default_failover_enabled)
            )
            backup_api_key = str(
                await self._get_current_setting("AI_API_KEY_BACKUP", self.default_backup_api_key) or ""
            ).strip()
            backup_base_url = str(
                await self._get_current_setting("AI_BASE_URL_BACKUP", self.default_backup_base_url) or ""
            ).strip().rstrip("/")
            backup_model = str(
                await self._get_current_setting("AI_MODEL_BACKUP", self.default_backup_model) or ""
            ).strip()

            providers: list[dict[str, str]] = []
            if api_key and base_url and model:
                providers.append(
                    {"name": "primary", "api_key": api_key, "base_url": base_url, "model": model}
                )
            if failover_enabled:
                if backup_api_key and backup_base_url and backup_model:
                    if not (backup_api_key == api_key and backup_base_url == base_url and backup_model == model):
                        providers.append(
                            {
                                "name": "backup",
                                "api_key": backup_api_key,
                                "base_url": backup_base_url,
                                "model": backup_model,
                            }
                        )
                else:
                    logger.warning("AI_FAILOVER_ENABLED=true 但备用 AI 配置不完整，已忽略备用线路。")

            if not providers:
                return {"error": "AI 配置缺失：请检查主运营商或备用运营商配置"}
            
            is_multimodal_video = isinstance(user_content, list)
            overall_timeout_seconds = int(
                os.getenv(
                    "AI_MULTIMODAL_CALL_OVERALL_TIMEOUT_SECONDS" if is_multimodal_video else "AI_TEXT_CALL_OVERALL_TIMEOUT_SECONDS",
                    "180" if is_multimodal_video else "120",
                )
            )
            logger.info(
                "开始调用 AI API providers=%s multimodal=%s overall_timeout=%ss",
                [f"{p['name']}:{p['model']}" for p in providers],
                is_multimodal_video,
                overall_timeout_seconds,
            )
            loop = asyncio.get_running_loop()
            deadline = loop.time() + max(1, overall_timeout_seconds)
            errors: list[str] = []

            for index, provider in enumerate(providers):
                remaining_seconds = max(0.0, deadline - loop.time())
                if remaining_seconds <= 1:
                    errors.append("总超时预算耗尽")
                    break

                # 给备用线路留出时间，避免主线路耗尽全部预算。
                if index < len(providers) - 1:
                    per_provider_timeout = min(
                        remaining_seconds,
                        max(20.0, overall_timeout_seconds / max(1, len(providers))),
                    )
                else:
                    per_provider_timeout = remaining_seconds
                per_phase_timeout = int(min(max(15, per_provider_timeout), 180))
                request_timeout = httpx.Timeout(
                    connect=min(20, per_phase_timeout),
                    read=per_phase_timeout,
                    write=per_phase_timeout,
                    pool=30.0,
                )
                logger.info(
                    "开始调用 AI API provider=%s model=%s multimodal=%s timeout=%ss",
                    provider["name"],
                    provider["model"],
                    is_multimodal_video,
                    int(per_provider_timeout),
                )

                try:
                    async with httpx.AsyncClient(timeout=request_timeout) as client:
                        response = await asyncio.wait_for(
                            client.post(
                                f"{provider['base_url']}/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {provider['api_key']}",
                                    "Content-Type": "application/json",
                                },
                                json={
                                    "model": provider["model"],
                                    "messages": [
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": user_content},
                                    ],
                                    "max_tokens": self.max_tokens,
                                    "temperature": self.temperature,
                                    "response_format": {"type": "json_object"},
                                },
                            ),
                            timeout=max(1.0, per_provider_timeout),
                        )

                    if response.status_code == 200:
                        result = response.json()
                        content_str = result["choices"][0]["message"]["content"]

                        # 容错：清理可能包含的 Markdown 代码块或 <think> 标签
                        clean_str = content_str.strip()
                        clean_str = re.sub(r'<think>.*?</think>', '', clean_str, flags=re.DOTALL).strip()

                        # 提取 ```json ... ``` 中的内容
                        json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', clean_str, re.DOTALL)
                        if json_match:
                            clean_str = json_match.group(1)
                        else:
                            json_match = re.search(r'(\{.*\}|\[.*\])', clean_str, re.DOTALL)
                            if json_match:
                                clean_str = json_match.group(1)

                        clean_str = clean_str.strip()

                        try:
                            parsed = json.loads(clean_str)
                            logger.info(
                                "AI API 响应解析成功(provider=%s fields=%s)",
                                provider["name"],
                                list(parsed.keys()),
                            )
                            return parsed
                        except json.JSONDecodeError as exc:
                            logger.error(
                                "AI API JSON 解析失败(provider=%s): %s; 原始内容: %s",
                                provider["name"],
                                exc,
                                content_str[:500],
                            )
                            return {"raw_analysis": content_str}

                    error_text = f"HTTP {response.status_code}"
                    logger.error(
                        "AI API 调用失败(provider=%s): %s %s",
                        provider["name"],
                        error_text,
                        response.text[:200],
                    )
                    errors.append(f"{provider['name']} {error_text}")
                except asyncio.TimeoutError:
                    logger.error("AI API 调用超时(provider=%s)", provider["name"])
                    errors.append(f"{provider['name']} 超时")
                except Exception as exc:
                    logger.error(
                        "AI API 调用异常(provider=%s): %s: %s",
                        provider["name"],
                        exc.__class__.__name__,
                        exc,
                    )
                    errors.append(f"{provider['name']} 异常")

                if index < len(providers) - 1:
                    logger.warning(
                        "AI 主线路调用失败，自动切换到备用线路(next_provider=%s)",
                        providers[index + 1]["name"],
                    )

            if errors:
                return {"error": f"AI 调用失败: {' | '.join(errors)}"}
            return {"error": "AI 调用失败"}

        except asyncio.TimeoutError:
            logger.error("AI API 调用超时（达到总超时阈值）")
            return {"error": "AI 调用超时"}
        except Exception as e:
            logger.error("AI API 调用异常: %s: %s", e.__class__.__name__, e)
            return {"error": str(e)}

    async def generate_blogger_report(
        self, 
        blogger_info: dict, 
        videos_text_data: list[dict],
        videos_analysis: list[dict],
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """综合双轨数据生成报告"""
        import json
        base_system_prompt = (
            "你是一位顶级短视频 IP 拆解分析师，专注于从数据中提炼博主的底层内容基因。\n"
            "你的分析标准：每一个结论都必须能在数据中找到具体证据，"
            "每一个定位描述都必须具体到可以指导内容选题，"
            "绝不输出'内容优质''风格独特'等无法操作的空泛描述。\n"
            "你的分析目标不是描述这个博主是谁，而是提炼出'为什么是他/她，而不是别人'。"
        )
        system_prompt = await self._build_system_prompt(scene_key="blogger_report", base_prompt=base_system_prompt)

        text_data_json = json.dumps(videos_text_data, ensure_ascii=False, indent=2)
        analyses_json = json.dumps(videos_analysis, ensure_ascii=False, indent=2)

        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="blogger_report",
            default_prompt=self.DEFAULT_BLOGGER_REPORT_PROMPT,
            db=db,
        )
        user_prompt = prompt_template.format(
            nickname=blogger_info.get('nickname', ''),
            platform=blogger_info.get('platform', ''),
            follower_count=blogger_info.get('follower_count', 0),
            signature=blogger_info.get('signature', ''),
            video_count=blogger_info.get('video_count', 0),
            text_data_json=text_data_json[:15000],
            analyses_json=analyses_json[:5000]
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="blogger_report",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_blogger_viral_profile(
        self,
        blogger_info: dict,
        videos_text_data: list[dict],
        videos_analysis: list[dict],
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """生成“账号怎么策划 + 为什么火”的爆款归因报告。"""
        import json

        base_system_prompt = (
            "你是一位严谨的短视频增长复盘顾问。\n"
            "输出必须是可执行结论，直接服务于‘复用成功模型’与‘避开错误模仿’。\n"
            "如果证据不足，请明确写‘数据不足’，不要臆造。"
        )
        system_prompt = await self._build_system_prompt(scene_key="blogger_viral_profile", base_prompt=base_system_prompt)

        def _published_sort_key(item: dict) -> tuple[int, str]:
            published_at = str(item.get("published_at") or "").strip()
            if not published_at:
                return (1, "")
            return (0, published_at)

        sorted_videos_text_data = sorted(videos_text_data, key=_published_sort_key)
        text_data_json = json.dumps(sorted_videos_text_data, ensure_ascii=False, indent=2)
        analyses_json = json.dumps(videos_analysis, ensure_ascii=False, indent=2)

        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="blogger_viral_profile",
            default_prompt=self.DEFAULT_BLOGGER_VIRAL_PROFILE_PROMPT,
            db=db,
        )
        user_prompt = prompt_template.format(
            nickname=blogger_info.get("nickname", ""),
            platform=blogger_info.get("platform", ""),
            follower_count=blogger_info.get("follower_count", 0),
            signature=blogger_info.get("signature", ""),
            video_count=blogger_info.get("video_count", 0),
            text_data_json=text_data_json[:15000],
            analyses_json=analyses_json[:5000],
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="blogger_viral_profile",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_account_plan(
        self,
        client_info: dict,
        reference_bloggers: list[dict],
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """生成方案"""
        import json
        base_system_prompt = (
            "你是一位顶级短视频账号策划专家，核心能力是为客户找到在竞争中能真正站住脚的差异化支点。\n"
            "你的策划标准：定位必须具体到一句话让目标受众说'这说的就是我'，"
            "内容规划必须每条都有独立的选题价值而不是同类重复，"
            "所有建议必须考虑可持续执行性，不做只能红一次的噱头。\n"
            "你坚持的原则：宁可承认某个方向不适合客户，也不输出看起来完整但无法落地的空洞策划。"
        )
        system_prompt = await self._build_system_prompt(scene_key="account_plan", base_prompt=base_system_prompt)

        normalized_reference_bloggers: list[dict] = []
        for blogger in reference_bloggers:
            report = blogger.get("analysis_report") if isinstance(blogger.get("analysis_report"), dict) else {}
            viral_profile = blogger.get("viral_profile")
            if not isinstance(viral_profile, dict):
                viral_profile = report.get("viral_profile") if isinstance(report.get("viral_profile"), dict) else {}

            timeline_entries = viral_profile.get("timeline_entries", []) if isinstance(viral_profile, dict) else []
            if not isinstance(timeline_entries, list):
                timeline_entries = []
            normalized_timeline_entries: list[dict[str, str]] = []
            for item in timeline_entries[:8]:
                if not isinstance(item, dict):
                    continue
                normalized_timeline_entries.append(
                    {
                        "date": str(item.get("date", "") or "").strip(),
                        "title": str(item.get("title", "") or "").strip(),
                        "phase": str(item.get("phase", "") or "").strip(),
                        "performance_signal": str(item.get("performance_signal", "") or "").strip(),
                        "topic_pattern": str(item.get("topic_pattern", "") or "").strip(),
                        "post_fire_role": str(item.get("post_fire_role", "") or "").strip(),
                        "why_it_mattered": str(item.get("why_it_mattered", "") or "").strip(),
                    }
                )

            planning_takeaways = viral_profile.get("planning_takeaways", []) if isinstance(viral_profile, dict) else []
            if not isinstance(planning_takeaways, list):
                planning_takeaways = []

            normalized_viral_profile = {
                "account_planning_logic": str(viral_profile.get("account_planning_logic", "") or "").strip(),
                "why_it_went_viral": str(viral_profile.get("why_it_went_viral", "") or "").strip(),
                "content_playbook": [str(item).strip() for item in viral_profile.get("content_playbook", []) if str(item).strip()][:5]
                if isinstance(viral_profile, dict) and isinstance(viral_profile.get("content_playbook"), list)
                else [],
                "risk_warnings": [str(item).strip() for item in viral_profile.get("risk_warnings", []) if str(item).strip()][:4]
                if isinstance(viral_profile, dict) and isinstance(viral_profile.get("risk_warnings"), list)
                else [],
                "timeline_overview": str(viral_profile.get("timeline_overview", "") or "").strip(),
                "timeline_entries": normalized_timeline_entries,
                "post_fire_arrangement": str(viral_profile.get("post_fire_arrangement", "") or "").strip(),
                "planning_takeaways": [str(item).strip() for item in planning_takeaways if str(item).strip()][:5],
            }

            # 只保留对账号策划最有价值的字段，避免被截断时丢失关键信息。
            normalized_reference_bloggers.append(
                {
                    "nickname": blogger.get("nickname"),
                    "viral_profile": normalized_viral_profile,
                    "ip_positioning": report.get("ip_positioning", {}),
                    "content_strategy": report.get("content_strategy", {}),
                    "growth_insights": report.get("growth_insights", {}),
                    "reference_value": report.get("reference_value", {}),
                }
            )

        bloggers_text = json.dumps(
            normalized_reference_bloggers,
            ensure_ascii=False,
            indent=2,
        )[:7000]

        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="account_plan",
            default_prompt=self.DEFAULT_ACCOUNT_PLAN_PROMPT,
            db=db,
        )
        user_prompt = prompt_template.format(
            client_name=client_info.get('client_name', ''),
            industry=client_info.get('industry', ''),
            target_audience=client_info.get('target_audience', ''),
            unique_advantage=client_info.get('unique_advantage', '未指定'),
            ip_requirements=client_info.get('ip_requirements', ''),
            style_preference=client_info.get('style_preference', '未指定'),
            business_goal=client_info.get('business_goal', '未指定'),
            blogger_count=len(reference_bloggers),
            bloggers_text=bloggers_text
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="account_plan",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_content_calendar(
        self,
        client_info: dict,
        account_plan: dict,
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """根据当前账号策划重新生成 30 天内容日历"""
        import json
        
        pos = account_plan.get("account_positioning", {})
        strat = account_plan.get("content_strategy", {})
        recap = account_plan.get("performance_recap", {}) if isinstance(account_plan.get("performance_recap"), dict) else {}

        recap_summary = str(recap.get("overall_summary", "") or "").strip() or "暂无已生成复盘建议，请先基于当前定位正常生成。"
        winning_patterns = "；".join(
            [str(item).strip() for item in recap.get("winning_patterns", []) if str(item).strip()]
        ) or "暂无"
        optimization_focus = "；".join(
            [str(item).strip() for item in recap.get("optimization_focus", []) if str(item).strip()]
        ) or "暂无"
        next_topic_angles = "；".join(
            [str(item).strip() for item in recap.get("next_topic_angles", []) if str(item).strip()]
        ) or "暂无"
        
        base_system_prompt = (
            "你是一个深谙抖音流量密码的资深账号主理人。请你根据已经确定的账号定位，重新规划 30 天的内容日历。"
            "请直接返回 JSON 格式的规划方案，不要有任何多余文字或 markdown 包裹。"
        )
        system_prompt = await self._build_system_prompt(scene_key="content_calendar", base_prompt=base_system_prompt)
        
        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="content_calendar",
            default_prompt=CONTENT_CALENDAR_PROMPT_TEMPLATE,
            db=db,
        )

        user_prompt = prompt_template.format(
            client_name=client_info.get("client_name", "客户"),
            core_identity=pos.get("core_identity", ""),
            target_audience_detail=pos.get("target_audience_detail", ""),
            personality_tags="、".join(pos.get("personality_tags", [])),
            differentiation=pos.get("differentiation", ""),
            content_tone=strat.get("content_tone", ""),
            content_pillars=json.dumps(pos.get("content_pillars", []), ensure_ascii=False),
            performance_recap_summary=recap_summary,
            winning_patterns=winning_patterns,
            optimization_focus=optimization_focus,
            next_topic_angles=next_topic_angles,
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="content_calendar",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_performance_recap(
        self,
        *,
        project_context: dict,
        account_plan: dict,
        performance_summary: dict,
        performance_rows: list[dict],
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """基于回流数据生成下一轮内容复盘建议。"""
        import json

        base_system_prompt = (
            "你是一位顶级短视频增长复盘策略师。\n"
            "你的输出必须直接指导下一轮内容迭代，重点回答：什么值得继续放大、什么应该立刻优化、什么不要误判。\n"
            "如果样本量不够，请明确指出样本不足，但仍要给出谨慎、可执行的建议。"
        )
        system_prompt = await self._build_system_prompt(scene_key="performance_recap", base_prompt=base_system_prompt)

        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="performance_recap",
            default_prompt=self.DEFAULT_PERFORMANCE_RECAP_PROMPT,
            db=db,
        )
        user_prompt = prompt_template.format(
            project_context=json.dumps(project_context, ensure_ascii=False, indent=2)[:3000],
            account_plan_json=json.dumps(account_plan, ensure_ascii=False, indent=2)[:6000],
            performance_summary_json=json.dumps(performance_summary, ensure_ascii=False, indent=2)[:6000],
            performance_rows_json=json.dumps(performance_rows, ensure_ascii=False, indent=2)[:10000],
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="performance_recap",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_next_topic_batch(
        self,
        *,
        project_context: dict,
        account_plan: dict,
        performance_recap: dict,
        existing_content_items: list[dict],
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """基于复盘建议生成下一批 10 条可执行选题。"""
        import json

        base_system_prompt = (
            "你是一位顶级短视频选题策划总监。\n"
            "你要输出的是一批可以马上进入脚本阶段的高质量选题，而不是抽象方向。\n"
            "优先放大已经验证有效的模式，同时保证题目之间有足够区分度。"
        )
        system_prompt = await self._build_system_prompt(scene_key="next_topic_batch", base_prompt=base_system_prompt)

        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="next_topic_batch",
            default_prompt=self.DEFAULT_NEXT_TOPIC_BATCH_PROMPT,
            db=db,
        )
        user_prompt = prompt_template.format(
            project_context=json.dumps(project_context, ensure_ascii=False, indent=2)[:3000],
            account_plan_json=json.dumps(account_plan, ensure_ascii=False, indent=2)[:6000],
            performance_recap_json=json.dumps(performance_recap, ensure_ascii=False, indent=2)[:5000],
            existing_content_items_json=json.dumps(existing_content_items, ensure_ascii=False, indent=2)[:8000],
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="next_topic_batch",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_planning_intake_guidance(
        self,
        *,
        user_message: str,
        draft: dict,
        chat_history: list[dict],
        auto_complete: bool = True,
        mode: str = "normal",
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """互动问诊：从聊天中提取策划草稿并给出下一步追问。"""
        import json

        base_system_prompt = (
            "你是一位擅长抖音起号的策划顾问。"
            "你需要把用户的自然语言整理成结构化字段，并且只问最关键的问题。"
        )
        system_prompt = await self._build_system_prompt(scene_key="planning_intake", base_prompt=base_system_prompt)

        limited_history = chat_history[-12:] if chat_history else []
        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="planning_intake",
            default_prompt=self.DEFAULT_PLANNING_INTAKE_PROMPT,
            db=db,
        )
        user_prompt = (
            f"{prompt_template}\n\n"
            f"运行模式：mode={mode}，auto_complete={str(auto_complete).lower()}\n\n"
            f"当前结构化草稿：\n{json.dumps(draft, ensure_ascii=False)}\n\n"
            f"历史对话（最近若干条）：\n{json.dumps(limited_history, ensure_ascii=False)}\n\n"
            f"用户最新输入：\n{user_message}"
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="planning_intake",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result

    async def generate_video_script(
        self,
        content_item: dict,
        account_plan: dict,
        reference_bloggers: list[dict],
        run_context: Optional[dict] = None,
        db: Optional[Any] = None,
    ) -> dict:
        """生成视频脚本"""
        import json
        base_system_prompt = (
            "你是一位顶级短视频脚本写作专家，你写的每一条脚本都以情绪曲线为骨架：前3秒制造张力，中段持续兑现，结尾留下钩子。\n"
            "你的写作标准：台词必须是真实的人会说出口的句子，不是条目式大纲；"
            "每个分镜都要推进情绪或信息，没有低密度的过渡场景；"
            "开头绝不出现'大家好'，结尾绝不出现'点赞关注'。\n"
            "你坚持的原则：一条可以直接对着镜头拍的脚本，胜过十条漂亮的框架。\n"
            "执行约束：默认普通人单人拍摄，优先“口播主镜头+画中画补镜”，Vlog 场景采用“边做边说+必要补拍”；"
            "禁止输出依赖演技或多人表演的方案。"
        )
        system_prompt = await self._build_system_prompt(scene_key="video_script", base_prompt=base_system_prompt)

        prompt_template, prompt_meta = await self._resolve_prompt(
            scene_key="video_script",
            default_prompt=self.DEFAULT_VIDEO_SCRIPT_PROMPT,
            db=db,
        )
        user_prompt = prompt_template.format(
            title_direction=content_item.get('title_direction', ''),
            content_type=content_item.get('content_type', ''),
            key_message=content_item.get('key_message', ''),
            core_identity=account_plan.get('account_positioning', {}).get('core_identity', ''),
            content_tone=account_plan.get('content_strategy', {}).get('content_tone', ''),
            target_audience_detail=account_plan.get('account_positioning', {}).get('target_audience_detail', '')
        )

        result = await self._call_ai(system_prompt, user_prompt)
        await self._record_prompt_run(
            scene_key="video_script",
            result=result,
            prompt_meta=prompt_meta,
            run_context=run_context,
            db=db,
        )
        return result


# 全局单例
ai_analysis_service = AIAnalysisService()
