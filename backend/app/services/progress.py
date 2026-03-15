"""
后台任务进度注册表
存储每个博主分析任务的当前步骤，供前端轮询
"""
from typing import Dict, Optional

from app.services.task_store import task_store


class ProgressRegistry:
    """任务进度注册表（内存缓存 + SQLite 持久化）。"""

    # 步骤定义：(step_key, 展示文案)
    STEPS = {
        "queued":       "任务排队中...",
        "processing":   "任务执行中...",
        "viral_profile_queued": "爆款归因任务排队中...",
        "viral_profile": "生成博主爆款归因中...",
        "crawling":     "采集视频列表中...",
        "saving":       "保存视频数据中...",
        "downloading":  "下载代表作视频中...",
        "compressing":  "压缩视频中...",
        "ai_video":     "AI 视频深度分析中...",
        "refresh_queued": "代表作解析完成，等待刷新综合报告...",
        "ai_report":    "生成博主综合报告中...",
        "done":         "分析完成",
        "failed":       "分析失败",
    }

    def __init__(self) -> None:
        self._progress: Dict[str, str] = {}
        self._store = task_store

    def set(self, task_id: str, step: str) -> None:
        self._progress[task_id] = step
        self._store.set_progress(task_id, step)
        self._store.maybe_cleanup_expired()

    def get(self, task_id: str) -> Optional[dict]:
        step = self._progress.get(task_id)
        if not step:
            step = self._store.get_progress(task_id)
            if step:
                self._progress[task_id] = step
        if not step:
            return None
        return {"step": step, "message": self.STEPS.get(step, step)}

    def clear(self, task_id: str) -> None:
        self._progress.pop(task_id, None)
        self._store.clear_progress(task_id)


progress_registry = ProgressRegistry()
