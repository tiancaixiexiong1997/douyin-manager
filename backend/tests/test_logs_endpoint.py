from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps.auth import require_admin
from app.models.db_session import get_db
import app.api.endpoints.log as log_endpoint


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        pass

    async def override_get_db() -> AsyncGenerator[Any, None]:
        yield DummyDB()

    async def override_admin() -> dict[str, str]:
        return {"role": "admin", "username": "tester"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = override_admin
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_logs_list_forwards_query_params(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_all(
        _db: Any,
        *,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        actor: str | None = None,
    ) -> list:
        captured["skip"] = skip
        captured["limit"] = limit
        captured["action"] = action
        captured["actor"] = actor
        return []

    monkeypatch.setattr(log_endpoint.operation_log_repo, "list_all", fake_list_all)

    response = await client.get("/api/logs?skip=10&limit=30&action=user.create&actor=admin")
    assert response.status_code == 200
    assert response.json() == []
    assert captured == {
        "skip": 10,
        "limit": 30,
        "action": "user.create",
        "actor": "admin",
    }


@pytest.mark.asyncio
async def test_logs_list_normalizes_filter_params(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_all(
        _db: Any,
        *,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        actor: str | None = None,
    ) -> list:
        captured["skip"] = skip
        captured["limit"] = limit
        captured["action"] = action
        captured["actor"] = actor
        return []

    monkeypatch.setattr(log_endpoint.operation_log_repo, "list_all", fake_list_all)

    response = await client.get("/api/logs?action=%20user.%20&actor=%20admin%20")
    assert response.status_code == 200
    assert response.json() == []
    assert captured == {
        "skip": 0,
        "limit": 50,
        "action": "user.",
        "actor": "admin",
    }


@pytest.mark.asyncio
async def test_logs_list_with_meta_returns_paged_payload(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_all(
        _db: Any,
        *,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        actor: str | None = None,
    ) -> list:
        _ = (skip, limit, action, actor)
        return [
            {
                "id": "l1",
                "action": "user.create",
                "entity_type": "user",
                "entity_id": "u1",
                "actor": "admin",
                "detail": "创建用户",
                "extra": {"role": "member"},
                "created_at": "2026-03-13T00:00:00",
            }
        ]

    async def fake_count_all(
        _db: Any,
        *,
        action: str | None = None,
        actor: str | None = None,
    ) -> int:
        _ = (action, actor)
        return 12

    monkeypatch.setattr(log_endpoint.operation_log_repo, "list_all", fake_list_all)
    monkeypatch.setattr(log_endpoint.operation_log_repo, "count_all", fake_count_all)

    response = await client.get("/api/logs?skip=0&limit=1&with_meta=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 12
    assert payload["skip"] == 0
    assert payload["limit"] == 1
    assert payload["has_more"] is True
    assert len(payload["items"]) == 1
