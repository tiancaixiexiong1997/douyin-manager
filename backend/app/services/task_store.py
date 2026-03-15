"""后台任务状态持久化存储（基于 SQLite，可跨重启保留）。"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _resolve_sqlite_path(database_url: str) -> Optional[Path]:
    """从 SQLAlchemy URL 解析 SQLite 文件路径；非 SQLite 返回 None。"""
    sqlite_prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return None

    raw_path = database_url[len(sqlite_prefix):]
    if not raw_path:
        return None

    # 去掉查询参数，兼容 sqlite+aiosqlite:///./data/app.db?foo=bar
    raw_path = raw_path.split("?", 1)[0]
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


class PersistentTaskStore:
    """任务状态持久化存储。"""

    def __init__(
        self,
        database_url: Optional[str] = None,
        cleanup_retention_days: Optional[int] = None,
        cleanup_interval_seconds: Optional[float] = None,
    ):
        db_url = database_url or settings.DATABASE_URL
        self._db_path = _resolve_sqlite_path(db_url)
        self._enabled = self._db_path is not None
        self._lock = threading.Lock()
        self._retention_days = max(
            1,
            int(cleanup_retention_days if cleanup_retention_days is not None else settings.TASK_STATE_RETENTION_DAYS),
        )
        default_cleanup_seconds = settings.TASK_STATE_CLEANUP_INTERVAL_MINUTES * 60
        self._cleanup_interval_seconds = max(
            30.0,
            float(cleanup_interval_seconds if cleanup_interval_seconds is not None else default_cleanup_seconds),
        )
        self._last_cleanup_monotonic = 0.0
        self._last_cleanup_at: Optional[str] = None
        self._last_cleanup_deleted = {"task_cancellations": 0, "task_progress": 0}

        if not self._enabled:
            logger.warning("PersistentTaskStore 未启用：当前数据库非 SQLite。")
            return

        try:
            assert self._db_path is not None
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_schema()
        except Exception as exc:
            logger.warning("PersistentTaskStore 初始化失败，降级为内存模式: %s", exc)
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _connect(self) -> sqlite3.Connection:
        assert self._db_path is not None
        return sqlite3.connect(self._db_path, timeout=2.0)

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_cancellations (
                        task_id TEXT PRIMARY KEY,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_progress (
                        task_id TEXT PRIMARY KEY,
                        step TEXT NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()

    # -------- cancellation --------

    def mark_cancelled(self, task_id: str) -> None:
        if not self._enabled:
            return
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO task_cancellations(task_id, updated_at)
                        VALUES (?, CURRENT_TIMESTAMP)
                        ON CONFLICT(task_id) DO UPDATE SET updated_at=CURRENT_TIMESTAMP
                        """,
                        (task_id,),
                    )
                    conn.commit()
        except Exception as exc:
            logger.warning("持久化取消信号失败(task_id=%s): %s", task_id, exc)

    def is_cancelled(self, task_id: str) -> bool:
        if not self._enabled:
            return False
        try:
            with self._lock:
                with self._connect() as conn:
                    row = conn.execute(
                        "SELECT 1 FROM task_cancellations WHERE task_id = ? LIMIT 1",
                        (task_id,),
                    ).fetchone()
                    return row is not None
        except Exception as exc:
            logger.warning("读取取消信号失败(task_id=%s): %s", task_id, exc)
            return False

    def clear_cancelled(self, task_id: str) -> None:
        if not self._enabled:
            return
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("DELETE FROM task_cancellations WHERE task_id = ?", (task_id,))
                    conn.commit()
        except Exception as exc:
            logger.warning("清理取消信号失败(task_id=%s): %s", task_id, exc)

    # -------- progress --------

    def set_progress(self, task_id: str, step: str) -> None:
        if not self._enabled:
            return
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO task_progress(task_id, step, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(task_id) DO UPDATE SET
                            step=excluded.step,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (task_id, step),
                    )
                    conn.commit()
        except Exception as exc:
            logger.warning("持久化任务进度失败(task_id=%s): %s", task_id, exc)

    def get_progress(self, task_id: str) -> Optional[str]:
        if not self._enabled:
            return None
        try:
            with self._lock:
                with self._connect() as conn:
                    row = conn.execute(
                        "SELECT step FROM task_progress WHERE task_id = ? LIMIT 1",
                        (task_id,),
                    ).fetchone()
                    return str(row[0]) if row else None
        except Exception as exc:
            logger.warning("读取任务进度失败(task_id=%s): %s", task_id, exc)
            return None

    def clear_progress(self, task_id: str) -> None:
        if not self._enabled:
            return
        try:
            with self._lock:
                with self._connect() as conn:
                    conn.execute("DELETE FROM task_progress WHERE task_id = ?", (task_id,))
                    conn.commit()
        except Exception as exc:
            logger.warning("清理任务进度失败(task_id=%s): %s", task_id, exc)

    # -------- cleanup --------

    def cleanup_expired(self, retention_days: Optional[int] = None) -> dict[str, int]:
        """清理超期任务状态记录，返回各表删除数量。"""
        deleted = {"task_cancellations": 0, "task_progress": 0}
        if not self._enabled:
            return deleted

        days = max(1, int(retention_days if retention_days is not None else self._retention_days))
        threshold = f"-{days} days"
        try:
            with self._lock:
                with self._connect() as conn:
                    cur1 = conn.execute(
                        "DELETE FROM task_cancellations WHERE updated_at < datetime('now', ?)",
                        (threshold,),
                    )
                    cur2 = conn.execute(
                        "DELETE FROM task_progress WHERE updated_at < datetime('now', ?)",
                        (threshold,),
                    )
                    conn.commit()
                    deleted["task_cancellations"] = max(cur1.rowcount, 0)
                    deleted["task_progress"] = max(cur2.rowcount, 0)
        except Exception as exc:
            logger.warning("清理超期任务状态失败: %s", exc)
        return deleted

    def maybe_cleanup_expired(self, *, force: bool = False) -> Optional[dict[str, int]]:
        """按间隔触发清理；force=True 时无视间隔立即执行。"""
        if not self._enabled:
            return None
        now = time.monotonic()
        if not force and (now - self._last_cleanup_monotonic) < self._cleanup_interval_seconds:
            return None
        deleted = self.cleanup_expired()
        self._last_cleanup_monotonic = now
        self._last_cleanup_at = datetime.now(timezone.utc).isoformat()
        self._last_cleanup_deleted = deleted
        return deleted

    def get_summary(self) -> dict:
        """获取任务状态存储摘要信息（供运维观测）。"""
        summary = {
            "enabled": self._enabled,
            "storage": "sqlite" if self._enabled else "memory-only",
            "retention_days": self._retention_days,
            "cleanup_interval_minutes": max(1, int(round(self._cleanup_interval_seconds / 60))),
            "last_cleanup_at": self._last_cleanup_at,
            "last_cleanup_deleted": dict(self._last_cleanup_deleted),
            "tables": {
                "task_cancellations": {
                    "count": 0,
                    "oldest_updated_at": None,
                    "newest_updated_at": None,
                },
                "task_progress": {
                    "count": 0,
                    "oldest_updated_at": None,
                    "newest_updated_at": None,
                },
            },
        }
        if not self._enabled:
            return summary

        try:
            with self._lock:
                with self._connect() as conn:
                    for table in ("task_cancellations", "task_progress"):
                        row = conn.execute(
                            f"SELECT COUNT(*), MIN(updated_at), MAX(updated_at) FROM {table}"
                        ).fetchone()
                        if row:
                            summary["tables"][table]["count"] = int(row[0] or 0)
                            summary["tables"][table]["oldest_updated_at"] = row[1]
                            summary["tables"][table]["newest_updated_at"] = row[2]
        except Exception as exc:
            logger.warning("读取任务状态摘要失败: %s", exc)
        return summary


# 全局单例
task_store = PersistentTaskStore()
