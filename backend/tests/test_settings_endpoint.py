from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps.auth import require_admin
from app.models.db_session import get_db
import app.api.endpoints.setting as setting_endpoint


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        async def commit(self) -> None:
            return None

    async def override_get_db() -> AsyncGenerator[Any, None]:
        yield DummyDB()

    async def override_admin() -> dict[str, str]:
        return {"role": "admin"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = override_admin
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_settings_masks_sensitive_fields(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_all(_db: Any) -> dict[str, str]:
        return {
            "AI_API_KEY": "sk-real-key",
            "AI_BASE_URL": "https://example.com/v1",
            "AI_MODEL": "test-model",
            "DOUYIN_COOKIE": "sessionid=real-cookie",
        }

    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)

    response = await client.get("/api/settings")
    assert response.status_code == 200

    settings = response.json()["settings"]
    assert settings["AI_API_KEY"] == "********"
    assert settings["AI_TEXT_API_KEY"] == "********"
    assert settings["AI_MULTIMODAL_API_KEY"] == "********"
    assert settings["DOUYIN_COOKIE"] == "********"
    assert settings["AI_BASE_URL"] == "https://example.com/v1"
    assert response.json()["defaults"]["AI_TEXT_MODEL"]


@pytest.mark.asyncio
async def test_get_settings_ignores_placeholder_cookie_from_fetcher(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_all(_db: Any) -> dict[str, str]:
        return {
            "AI_BASE_URL": "https://example.com/v1",
            "AI_MODEL": "test-model",
        }

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, str]:
            return {"cookie": "PLEASE_REPLACE_WITH_YOUR_OWN_COOKIE"}

    class FakeAsyncClient:
        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        async def get(self, _url: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)
    monkeypatch.setattr(setting_endpoint.app_settings, "ENABLE_LEGACY_COOKIE_FETCH_FALLBACK", True)
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=0: FakeAsyncClient())

    response = await client.get("/api/settings")
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["DOUYIN_COOKIE"] == ""


@pytest.mark.asyncio
async def test_get_settings_skips_legacy_cookie_fetch_by_default(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_all(_db: Any) -> dict[str, str]:
        return {}

    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)
    monkeypatch.setattr(setting_endpoint.app_settings, "ENABLE_LEGACY_COOKIE_FETCH_FALLBACK", False)

    def fail_async_client(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("legacy cookie fetch should stay disabled by default")

    monkeypatch.setattr("httpx.AsyncClient", fail_async_client)

    response = await client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["settings"]["DOUYIN_COOKIE"] == ""


@pytest.mark.asyncio
async def test_update_settings_keeps_sensitive_value_when_mask_sent(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def fake_get_all(_db: Any) -> dict[str, str]:
        return {
            "AI_API_KEY": "sk-existing",
            "AI_TEXT_API_KEY": "sk-text-existing",
            "DOUYIN_COOKIE": "cookie-existing",
        }

    async def fake_update_all(_db: Any, settings_dict: dict[str, str]) -> None:
        captured.update(settings_dict)

    async def fake_reload_settings(_db: Any = None) -> None:
        return None

    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)
    monkeypatch.setattr(setting_endpoint.setting_repo, "update_all", fake_update_all)
    monkeypatch.setattr(setting_endpoint.ai_analysis_service, "reload_settings", fake_reload_settings)

    response = await client.put(
        "/api/settings",
        json={
            "settings": {
                "AI_API_KEY": "********",
                "AI_TEXT_API_KEY": "********",
                "DOUYIN_COOKIE": "********",
                "AI_MODEL": "new-model",
            }
        },
    )

    assert response.status_code == 200
    assert captured["AI_API_KEY"] == "sk-existing"
    assert captured["AI_TEXT_API_KEY"] == "sk-text-existing"
    assert captured["DOUYIN_COOKIE"] == "cookie-existing"
    assert captured["AI_MODEL"] == "new-model"


@pytest.mark.asyncio
async def test_get_task_state_summary(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_summary() -> dict[str, Any]:
        return {
            "enabled": True,
            "storage": "sqlite",
            "retention_days": 14,
            "cleanup_interval_minutes": 60,
            "last_cleanup_at": "2026-03-13T00:00:00+00:00",
            "last_cleanup_deleted": {
                "task_cancellations": 2,
                "task_progress": 3,
            },
            "tables": {
                "task_cancellations": {
                    "count": 5,
                    "oldest_updated_at": "2026-03-12 12:00:00",
                    "newest_updated_at": "2026-03-13 12:00:00",
                },
                "task_progress": {
                    "count": 8,
                    "oldest_updated_at": "2026-03-12 11:00:00",
                    "newest_updated_at": "2026-03-13 12:00:00",
                },
            },
        }

    monkeypatch.setattr(setting_endpoint.task_store, "get_summary", fake_get_summary)

    response = await client.get("/api/settings/task-state")
    assert response.status_code == 200

    payload = response.json()
    assert payload["enabled"] is True
    assert payload["storage"] == "sqlite"
    assert payload["last_cleanup_deleted"]["task_cancellations"] == 2
    assert payload["tables"]["task_progress"]["count"] == 8


@pytest.mark.asyncio
async def test_get_cookie_extractor_status_generates_token(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {"DOUYIN_COOKIE": "sessionid=abc"}

    async def fake_get_all(_db: Any) -> dict[str, str]:
        return dict(store)

    async def fake_update_all(_db: Any, settings_dict: dict[str, str]) -> None:
        store.update(settings_dict)

    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)
    monkeypatch.setattr(setting_endpoint.setting_repo, "update_all", fake_update_all)

    response = await client.get("/api/settings/cookie-extractor")
    assert response.status_code == 200

    payload = response.json()
    assert payload["token"]
    assert payload["cookie_length"] == len("sessionid=abc")
    assert payload["login_url"] == "https://www.douyin.com/"
    assert payload["extension_path"] == "backend/douyin_api/chrome-cookie-sniffer"
    assert store["COOKIE_SNIFFER_WEBHOOK_TOKEN"] == payload["token"]


@pytest.mark.asyncio
async def test_cookie_extractor_webhook_updates_cookie_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {
        "COOKIE_SNIFFER_WEBHOOK_TOKEN": "token-123",
        "DOUYIN_COOKIE": "old-cookie",
    }

    class DummyDB:
        async def commit(self) -> None:
            return None

    class DummySessionContext:
        async def __aenter__(self) -> DummyDB:
            return DummyDB()

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    async def fake_get_all(_db: Any) -> dict[str, str]:
        return dict(store)

    async def fake_update_all(_db: Any, settings_dict: dict[str, str]) -> None:
        store.update(settings_dict)

    async def fake_reload_settings(_db: Any = None) -> None:
        return None

    monkeypatch.setattr(setting_endpoint, "AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)
    monkeypatch.setattr(setting_endpoint.setting_repo, "update_all", fake_update_all)
    monkeypatch.setattr(setting_endpoint.ai_analysis_service, "reload_settings", fake_reload_settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        response = await async_client.post(
            "/api/settings/cookie-extractor/webhook?token=token-123",
            json={
                "service": "douyin",
                "cookie": "sessionid=new-cookie; msToken=abc",
                "timestamp": "2026-03-16T00:00:00Z",
            },
        )

    assert response.status_code == 200
    assert store["DOUYIN_COOKIE"] == "sessionid=new-cookie; msToken=abc"
    assert store["COOKIE_SNIFFER_LAST_SERVICE"] == "douyin"
    assert store["COOKIE_SNIFFER_LAST_SYNC_AT"] == "2026-03-16T00:00:00Z"


@pytest.mark.asyncio
async def test_cookie_extractor_webhook_test_payload_does_not_override_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {
        "COOKIE_SNIFFER_WEBHOOK_TOKEN": "token-123",
        "DOUYIN_COOKIE": "keep-me",
    }

    class DummyDB:
        async def commit(self) -> None:
            return None

    class DummySessionContext:
        async def __aenter__(self) -> DummyDB:
            return DummyDB()

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    async def fake_get_all(_db: Any) -> dict[str, str]:
        return dict(store)

    async def fake_update_all(_db: Any, settings_dict: dict[str, str]) -> None:
        store.update(settings_dict)

    monkeypatch.setattr(setting_endpoint, "AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr(setting_endpoint.setting_repo, "get_all", fake_get_all)
    monkeypatch.setattr(setting_endpoint.setting_repo, "update_all", fake_update_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        response = await async_client.post(
            "/api/settings/cookie-extractor/webhook?token=token-123",
            json={
                "service": "douyin",
                "cookie": "ignore-me",
                "timestamp": "2026-03-16T00:00:00Z",
                "test": True,
                "message": "test hook ok",
            },
        )

    assert response.status_code == 200
    assert store["DOUYIN_COOKIE"] == "keep-me"
    assert store["COOKIE_SNIFFER_LAST_MESSAGE"] == "test hook ok"
