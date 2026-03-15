from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps.auth import require_authenticated
from app.models.db_session import get_db
import app.api.endpoints.auth as auth_endpoint


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        async def commit(self) -> None:
            return None

    async def override_get_db() -> AsyncGenerator[DummyDB, None]:
        yield DummyDB()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_endpoint.settings, "DEFAULT_ADMIN_PASSWORD", "configured-password")

    async def fake_authenticate_user_with_status(_db: object, username: str, password: str):
        if username == "admin" and password == "secret123":
            return SimpleNamespace(id="u1", role="admin", username="admin"), "ok"
        return None, "invalid_credentials"

    monkeypatch.setattr(auth_endpoint.auth_service, "authenticate_user_with_status", fake_authenticate_user_with_status)
    monkeypatch.setattr(auth_endpoint.auth_service, "create_access_token", lambda *_args, **_kwargs: "fake-token")
    monkeypatch.setattr(auth_endpoint.auth_service, "create_refresh_token", lambda *_args, **_kwargs: "fake-refresh-token")

    response = await client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "fake-token"
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_rejects_bad_password(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_endpoint.settings, "DEFAULT_ADMIN_PASSWORD", "configured-password")

    async def fake_authenticate_user_with_status(_db: object, _username: str, _password: str):
        return None, "invalid_credentials"

    monkeypatch.setattr(auth_endpoint.auth_service, "authenticate_user_with_status", fake_authenticate_user_with_status)

    response = await client.post("/api/auth/login", json={"username": "admin", "password": "wrongpass"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user_when_authorized(client: AsyncClient) -> None:
    async def override_admin() -> SimpleNamespace:
        return SimpleNamespace(id="u1", username="admin", role="admin")

    app.dependency_overrides[require_authenticated] = override_admin
    response = await client.get("/api/auth/me")
    app.dependency_overrides.pop(require_authenticated, None)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"
