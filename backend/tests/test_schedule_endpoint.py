from collections.abc import AsyncGenerator
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.endpoints.schedule as schedule_endpoint
from app.api.deps.auth import require_member_or_admin
from app.main import app
from app.models.db_session import get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        async def commit(self) -> None:
            return None

    async def override_get_db() -> AsyncGenerator[DummyDB, None]:
        yield DummyDB()

    async def override_member() -> SimpleNamespace:
        return SimpleNamespace(id="u-schedule", username="scheduler", role="member")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_member_or_admin] = override_member
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_schedule_rejects_past_date(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"create": False}

    async def fake_create(*_args, **_kwargs):
        called["create"] = True
        return None

    monkeypatch.setattr(schedule_endpoint.schedule_repository, "create", fake_create)

    today = date.today()
    monkeypatch.setattr(schedule_endpoint, "_today_in_app_timezone", lambda: today)
    past_date = (today - timedelta(days=1)).isoformat()
    response = await client.post(
        "/api/schedules",
        json={"schedule_date": past_date, "title": "past task", "done": False},
    )

    assert response.status_code == 400
    assert called["create"] is False


@pytest.mark.asyncio
async def test_update_schedule_rejects_move_to_past(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"update": False}

    async def fake_update(*_args, **_kwargs):
        called["update"] = True
        return None

    monkeypatch.setattr(schedule_endpoint.schedule_repository, "update", fake_update)

    today = date.today()
    monkeypatch.setattr(schedule_endpoint, "_today_in_app_timezone", lambda: today)
    past_date = (today - timedelta(days=2)).isoformat()
    response = await client.patch(
        "/api/schedules/entry-1",
        json={"schedule_date": past_date},
    )

    assert response.status_code == 400
    assert called["update"] is False
