"""
后台任务软取消注册表

通过共享存储实现优雅取消：
- 删除操作时将 ID 加入黑名单
- 后台任务在每个关键步骤检查是否该取消
- 任务完成或取消后自动清理记录
"""
from typing import Set

from app.services.task_store import task_store


class CancellationRegistry:
    """任务取消注册表（内存缓存 + SQLite 持久化）。"""

    def __init__(self) -> None:
        self._cancelled: Set[str] = set()
        self._store = task_store

    def cancel(self, task_id: str) -> None:
        """标记任务为取消"""
        self._cancelled.add(task_id)
        self._store.mark_cancelled(task_id)
        self._store.maybe_cleanup_expired()

    def is_cancelled(self, task_id: str) -> bool:
        """检查任务是否已被取消"""
        if task_id in self._cancelled:
            return True
        persisted = self._store.is_cancelled(task_id)
        if persisted:
            self._cancelled.add(task_id)
        return persisted

    def clear(self, task_id: str) -> None:
        """任务结束后清除记录，避免泄漏"""
        self._cancelled.discard(task_id)
        self._store.clear_cancelled(task_id)


# 全局单例
cancellation_registry = CancellationRegistry()
