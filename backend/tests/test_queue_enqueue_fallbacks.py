from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.endpoints.planning as planning_endpoint
import app.api.endpoints.script as script_endpoint
from app.api.deps.auth import require_member_or_admin
from app.main import app
from app.models.database import ExtractionStatus
from app.models.db_session import get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        async def commit(self) -> None:
            return None

    async def override_get_db() -> AsyncGenerator[DummyDB, None]:
        yield DummyDB()

    async def override_member() -> SimpleNamespace:
        return SimpleNamespace(id="u-test", username="tester", role="member")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_member_or_admin] = override_member
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_script_create_marks_failed_when_enqueue_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = SimpleNamespace(id="ext-1")
    status_calls: dict[str, str] = {}

    async def fake_create(_db: object, _data: dict) -> SimpleNamespace:
        return record

    async def fake_update_status(_db: object, extraction_id: str, status: ExtractionStatus, error_message: str | None = None) -> None:
        status_calls["id"] = extraction_id
        status_calls["status"] = status.value
        status_calls["error"] = error_message or ""

    async def fake_log(*_args, **_kwargs) -> None:
        return None

    def fake_enqueue(*_args, **_kwargs) -> None:
        raise RuntimeError("任务系统暂不可用")

    monkeypatch.setattr(script_endpoint.script_repo, "create", fake_create)
    monkeypatch.setattr(script_endpoint.script_repo, "update_status", fake_update_status)
    monkeypatch.setattr(script_endpoint.operation_log_repo, "create", fake_log)
    monkeypatch.setattr(script_endpoint, "enqueue_task", fake_enqueue)

    response = await client.post(
        "/api/script/extract",
        json={"source_video_url": "https://www.douyin.com/video/1", "user_prompt": "test"},
    )

    assert response.status_code == 503
    assert status_calls["id"] == "ext-1"
    assert status_calls["status"] == ExtractionStatus.FAILED.value
    assert "任务系统暂不可用" in status_calls["error"]


@pytest.mark.asyncio
async def test_generate_strategy_rolls_back_status_when_enqueue_fails(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = SimpleNamespace(
        id="proj-1",
        status="draft",
        client_name="client",
        industry="餐饮",
        target_audience="年轻用户",
        unique_advantage="",
        ip_requirements="真实",
        style_preference="",
        business_goal="",
        reference_blogger_ids=[],
    )

    async def fake_get_by_id(_db: object, _project_id: str) -> SimpleNamespace:
        return project

    async def fake_upsert_task(*_args, **_kwargs) -> None:
        return None

    async def fake_log(*_args, **_kwargs) -> None:
        return None

    def fake_enqueue(*_args, **_kwargs) -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(planning_endpoint.planning_repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(planning_endpoint.task_center_repo, "upsert_task", fake_upsert_task)
    monkeypatch.setattr(planning_endpoint.task_center_repo, "update_status", fake_upsert_task)
    monkeypatch.setattr(planning_endpoint.operation_log_repo, "create", fake_log)
    monkeypatch.setattr(planning_endpoint, "enqueue_task", fake_enqueue)

    response = await client.post("/api/planning/proj-1/generate-strategy")

    assert response.status_code == 503
    assert project.status == "draft"
