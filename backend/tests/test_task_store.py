import sqlite3
from pathlib import Path

from app.services.task_store import PersistentTaskStore


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path}"


def test_task_store_persists_cancellation_state(tmp_path: Path) -> None:
    db_path = tmp_path / "task_store_cancel.db"
    store1 = PersistentTaskStore(database_url=_sqlite_url(db_path))
    store1.mark_cancelled("task-1")
    assert store1.is_cancelled("task-1") is True

    # 模拟重启：新实例仍应读取到已持久化状态
    store2 = PersistentTaskStore(database_url=_sqlite_url(db_path))
    assert store2.is_cancelled("task-1") is True

    store2.clear_cancelled("task-1")
    assert store2.is_cancelled("task-1") is False


def test_task_store_persists_progress_state(tmp_path: Path) -> None:
    db_path = tmp_path / "task_store_progress.db"
    store1 = PersistentTaskStore(database_url=_sqlite_url(db_path))
    store1.set_progress("task-2", "ai_report")
    assert store1.get_progress("task-2") == "ai_report"

    # 模拟重启：新实例应能读取到进度
    store2 = PersistentTaskStore(database_url=_sqlite_url(db_path))
    assert store2.get_progress("task-2") == "ai_report"

    store2.clear_progress("task-2")
    assert store2.get_progress("task-2") is None


def test_task_store_cleanup_expired_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "task_store_cleanup.db"
    store = PersistentTaskStore(
        database_url=_sqlite_url(db_path),
        cleanup_retention_days=7,
        cleanup_interval_seconds=1,
    )
    store.mark_cancelled("cancel-old")
    store.set_progress("progress-old", "ai_report")
    store.mark_cancelled("cancel-new")
    store.set_progress("progress-new", "done")

    # 仅把 old 记录回写为过期时间
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE task_cancellations SET updated_at=datetime('now', '-10 days') WHERE task_id='cancel-old'"
        )
        conn.execute(
            "UPDATE task_progress SET updated_at=datetime('now', '-10 days') WHERE task_id='progress-old'"
        )
        conn.commit()

    deleted = store.cleanup_expired(retention_days=7)

    assert deleted["task_cancellations"] >= 1
    assert deleted["task_progress"] >= 1
    assert store.is_cancelled("cancel-old") is False
    assert store.get_progress("progress-old") is None
    assert store.is_cancelled("cancel-new") is True
    assert store.get_progress("progress-new") == "done"


def test_task_store_summary_contains_counts_and_cleanup_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "task_store_summary.db"
    store = PersistentTaskStore(
        database_url=_sqlite_url(db_path),
        cleanup_retention_days=7,
        cleanup_interval_seconds=1,
    )
    store.mark_cancelled("cancel-1")
    store.set_progress("progress-1", "crawling")
    store.maybe_cleanup_expired(force=True)

    summary = store.get_summary()

    assert summary["enabled"] is True
    assert summary["storage"] == "sqlite"
    assert summary["tables"]["task_cancellations"]["count"] >= 1
    assert summary["tables"]["task_progress"]["count"] >= 1
    assert summary["last_cleanup_at"] is not None
    assert "task_cancellations" in summary["last_cleanup_deleted"]
