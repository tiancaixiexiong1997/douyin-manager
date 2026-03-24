from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps.auth import require_member_or_admin
from app.models.db_session import get_db
import app.api.endpoints.task_center as task_center_endpoint


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        pass

    async def override_get_db() -> AsyncGenerator[Any, None]:
        yield DummyDB()

    async def override_member() -> dict[str, str]:
        return {"role": "member", "username": "tester"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_member_or_admin] = override_member
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_task_center_list_forwards_entity_id_filter(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_tasks(
        _db: Any,
        *,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        task_type: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> list[dict]:
        captured["list"] = {
            "skip": skip,
            "limit": limit,
            "status": status,
            "task_type": task_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
        }
        return [
            {
                "id": "task-1",
                "task_key": "planning:proj-1:calendar",
                "task_type": "planning_calendar",
                "title": "重生成日历：测试账号",
                "entity_type": "planning_project",
                "entity_id": "proj-1",
                "status": "running",
                "progress_step": "ai_generate",
                "message": "AI 正在重写 Day 4",
                "error_message": None,
                "context": {
                    "planning_state": "calendar_regenerating",
                    "regenerate_day_numbers": [4],
                },
                "started_at": None,
                "finished_at": None,
                "created_at": "2026-03-24T00:00:00",
                "updated_at": "2026-03-24T00:00:00",
            }
        ]

    async def fake_count_tasks(_db: Any, **kwargs: Any) -> int:
        captured["count"] = kwargs
        return 1

    async def fake_status_summary(_db: Any, **kwargs: Any) -> dict[str, int]:
        captured["summary"] = kwargs
        return {"queued": 0, "running": 1, "completed": 0, "failed": 0, "cancelled": 0}

    monkeypatch.setattr(task_center_endpoint.task_center_repo, "list_tasks", fake_list_tasks)
    monkeypatch.setattr(task_center_endpoint.task_center_repo, "count_tasks", fake_count_tasks)
    monkeypatch.setattr(task_center_endpoint.task_center_repo, "status_summary", fake_status_summary)

    response = await client.get(
        "/api/tasks?entity_type=planning_project&entity_id=%20proj-1%20&task_type=planning_calendar"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["context"]["regenerate_day_numbers"] == [4]
    assert captured["list"]["entity_id"] == "proj-1"
    assert captured["count"]["entity_id"] == "proj-1"
    assert captured["summary"]["entity_id"] == "proj-1"
