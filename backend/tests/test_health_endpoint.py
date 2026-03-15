from httpx import ASGITransport, AsyncClient
import pytest

from app.main import app
import app.main as main_module


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert response.headers.get("X-Request-ID")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


class _DummyConnCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt):
        return None


@pytest.mark.asyncio
async def test_readiness_returns_ok_when_dependencies_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DummyEngine:
        def connect(self):
            return _DummyConnCtx()

    class _DummyRedis:
        def ping(self):
            return True

    monkeypatch.setattr(main_module, "engine", _DummyEngine())
    monkeypatch.setattr(main_module, "get_redis_connection", lambda: _DummyRedis())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_readiness_returns_503_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DummyEngine:
        def connect(self):
            return _DummyConnCtx()

    def _raise_redis_down():
        raise RuntimeError("redis down")

    monkeypatch.setattr(main_module, "engine", _DummyEngine())
    monkeypatch.setattr(main_module, "get_redis_connection", _raise_redis_down)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["redis"].startswith("error:")


@pytest.mark.asyncio
async def test_queue_health_returns_ok_when_worker_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module,
        "get_queue_runtime_summary",
        lambda: {
            "status": "ok",
            "queue_name": "default",
            "queued_jobs": 0,
            "worker_total": 1,
            "active_workers": 1,
            "stale_workers": 0,
            "worker_heartbeat_timeout_seconds": 120,
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/queue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["active_workers"] == 1


@pytest.mark.asyncio
async def test_queue_health_returns_503_when_no_active_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module,
        "get_queue_runtime_summary",
        lambda: {
            "status": "degraded",
            "queue_name": "default",
            "queued_jobs": 2,
            "worker_total": 0,
            "active_workers": 0,
            "stale_workers": 0,
            "worker_heartbeat_timeout_seconds": 120,
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/queue")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["active_workers"] == 0
