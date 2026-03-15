from types import SimpleNamespace

import pytest

import app.services.job_queue as job_queue


class _DummyQueue:
    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.connection = object()
        self.count = 0
        self._job = SimpleNamespace(id="job-123")
        self.last_enqueue_kwargs = {}

    def enqueue(self, *_args, **_kwargs):
        self.last_enqueue_kwargs = dict(_kwargs)
        return self._job


def test_enqueue_task_blocks_when_no_active_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _DummyQueue()
    monkeypatch.setattr(job_queue, "get_queue", lambda: queue)
    monkeypatch.setattr(job_queue.settings, "REQUIRE_ACTIVE_WORKER_ON_ENQUEUE", True)
    monkeypatch.setattr(
        job_queue,
        "get_queue_runtime_summary",
        lambda **_kwargs: {
            "status": "degraded",
            "queue_name": "default",
            "queued_jobs": 0,
            "worker_total": 0,
            "active_workers": 0,
            "stale_workers": 0,
            "worker_heartbeat_timeout_seconds": 120,
        },
    )

    with pytest.raises(RuntimeError, match="工作进程未就绪"):
        job_queue.enqueue_task("app.tasks.run_script_extraction", "ext-1", "url", "prompt")


def test_enqueue_task_returns_job_id_when_worker_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _DummyQueue()
    monkeypatch.setattr(job_queue, "get_queue", lambda: queue)
    monkeypatch.setattr(job_queue.settings, "REQUIRE_ACTIVE_WORKER_ON_ENQUEUE", True)
    monkeypatch.setattr(job_queue.settings, "JOB_QUEUE_RETRY_MAX", 1)
    monkeypatch.setattr(job_queue.settings, "JOB_QUEUE_RETRY_INTERVAL_SECONDS", 30)
    monkeypatch.setattr(
        job_queue,
        "get_queue_runtime_summary",
        lambda **_kwargs: {
            "status": "ok",
            "queue_name": "default",
            "queued_jobs": 1,
            "worker_total": 1,
            "active_workers": 1,
            "stale_workers": 0,
            "failed_jobs": 0,
            "started_jobs": 0,
            "scheduled_jobs": 0,
            "deferred_jobs": 0,
            "stuck_jobs": 0,
            "stuck_job_timeout_seconds": 1800,
            "worker_heartbeat_timeout_seconds": 120,
        },
    )

    job_id = job_queue.enqueue_task("app.tasks.run_script_extraction", "ext-1", "url", "prompt")
    assert job_id == "job-123"
    assert queue.last_enqueue_kwargs["result_ttl"] == 24 * 3600
    assert queue.last_enqueue_kwargs["failure_ttl"] == 7 * 24 * 3600
    if job_queue.Queue is not None:
        assert "retry" in queue.last_enqueue_kwargs


def test_resolve_worker_heartbeat_timeout_prefers_larger_worker_ttl() -> None:
    worker = SimpleNamespace(worker_ttl=420, default_worker_ttl=None)
    timeout = job_queue._resolve_worker_heartbeat_timeout(worker, 120)
    assert timeout == 420


def test_resolve_worker_heartbeat_timeout_uses_config_when_worker_ttl_missing() -> None:
    worker = SimpleNamespace(worker_ttl=None, default_worker_ttl=None)
    timeout = job_queue._resolve_worker_heartbeat_timeout(worker, 120)
    assert timeout == 120


def test_queue_runtime_summary_contains_registry_fields() -> None:
    queue = _DummyQueue()
    summary = job_queue.get_queue_runtime_summary(queue=queue)
    assert "failed_jobs" in summary
    assert "started_jobs" in summary
    assert "scheduled_jobs" in summary
    assert "deferred_jobs" in summary
    assert "stuck_jobs" in summary
