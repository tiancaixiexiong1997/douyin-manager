from types import SimpleNamespace

import pytest

import app.services.auth_service as auth_module
from app.services.auth_service import auth_service


def test_password_hash_and_verify() -> None:
    plain = "MyP@ssw0rd"
    hashed = auth_service.hash_password(plain)

    assert hashed != plain
    assert auth_service.verify_password(plain, hashed) is True
    assert auth_service.verify_password("wrong", hashed) is False


def test_jwt_create_and_decode() -> None:
    token = auth_service.create_access_token("user-1", "admin", "admin")
    payload = auth_service.decode_access_token(token)

    assert payload is not None
    assert payload.get("sub") == "user-1"
    assert payload.get("role") == "admin"
    assert payload.get("username") == "admin"


@pytest.mark.asyncio
async def test_bootstrap_warnings_when_no_users_and_no_default_admin_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module.settings, "DEFAULT_ADMIN_PASSWORD", "")

    async def fake_count_all(_db):
        return 0

    monkeypatch.setattr(auth_module.user_repository, "count_all", fake_count_all)
    warnings = await auth_service.get_bootstrap_warnings(SimpleNamespace())
    assert any("未检测到任何用户" in item for item in warnings)


@pytest.mark.asyncio
async def test_bootstrap_warnings_empty_when_users_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module.settings, "DEFAULT_ADMIN_PASSWORD", "")

    async def fake_count_all(_db):
        return 1

    monkeypatch.setattr(auth_module.user_repository, "count_all", fake_count_all)
    warnings = await auth_service.get_bootstrap_warnings(SimpleNamespace())
    assert warnings == []
