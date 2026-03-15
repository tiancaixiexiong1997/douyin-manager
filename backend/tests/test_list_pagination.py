from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps.auth import require_member_or_admin
from app.models.db_session import get_db
from app.services.crawler_service import CrawlerServiceError
import app.api.endpoints.blogger as blogger_endpoint
import app.api.endpoints.planning as planning_endpoint


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
async def test_bloggers_list_forwards_pagination_params(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_all(
        _db: Any,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        platform: str | None = None,
    ) -> list:
        captured["skip"] = skip
        captured["limit"] = limit
        captured["keyword"] = keyword
        captured["platform"] = platform
        return []

    monkeypatch.setattr(blogger_endpoint.blogger_repository, "list_all", fake_list_all)

    response = await client.get("/api/bloggers?skip=5&limit=10")
    assert response.status_code == 200
    assert response.json() == []
    assert captured == {"skip": 5, "limit": 10, "keyword": None, "platform": None}


@pytest.mark.asyncio
async def test_planning_list_defaults_to_legacy_all_behavior(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_all(
        _db: Any,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list:
        captured["skip"] = skip
        captured["limit"] = limit
        captured["keyword"] = keyword
        captured["status"] = status
        return []

    monkeypatch.setattr(planning_endpoint.planning_repository, "list_all", fake_list_all)

    response = await client.get("/api/planning")
    assert response.status_code == 200
    assert response.json() == []
    assert captured == {"skip": 0, "limit": None, "keyword": None, "status": None}


@pytest.mark.asyncio
async def test_list_limit_validation(client: AsyncClient) -> None:
    response = await client.get("/api/bloggers?limit=500")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_blogger_returns_readable_cookie_error(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_parse_user_url(_url: str, *, strict: bool = False) -> dict:
        assert strict is True
        raise CrawlerServiceError("抖音 Cookie 未配置或已失效，请到系统设置更新 DOUYIN_COOKIE 后重试")

    monkeypatch.setattr(blogger_endpoint.crawler_service, "parse_user_url", fake_parse_user_url)

    response = await client.post(
        "/api/bloggers",
        json={
            "url": "https://www.douyin.com/user/test_user",
            "sample_count": 50,
            "incremental_mode": False,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "抖音 Cookie 未配置或已失效，请到系统设置更新 DOUYIN_COOKIE 后重试"


@pytest.mark.asyncio
async def test_bloggers_list_with_meta_returns_paged_payload(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_all(
        _db: Any,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        platform: str | None = None,
    ) -> list:
        _ = (skip, limit)
        assert keyword is None
        assert platform is None
        return [
            {
                "id": "b1",
                "platform": "douyin",
                "blogger_id": "u1",
                "nickname": "博主1",
                "avatar_url": None,
                "signature": None,
                "representative_video_url": None,
                "follower_count": 100,
                "video_count": 10,
                "is_analyzed": False,
                "created_at": "2026-03-13T00:00:00",
            },
            {
                "id": "b2",
                "platform": "douyin",
                "blogger_id": "u2",
                "nickname": "博主2",
                "avatar_url": None,
                "signature": None,
                "representative_video_url": None,
                "follower_count": 200,
                "video_count": 20,
                "is_analyzed": True,
                "created_at": "2026-03-13T00:00:01",
            },
        ]

    async def fake_count_all(
        _db: Any,
        keyword: str | None = None,
        platform: str | None = None,
    ) -> int:
        assert keyword is None
        assert platform is None
        return 5

    monkeypatch.setattr(blogger_endpoint.blogger_repository, "list_all", fake_list_all)
    monkeypatch.setattr(blogger_endpoint.blogger_repository, "count_all", fake_count_all)

    response = await client.get("/api/bloggers?skip=1&limit=2&with_meta=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert payload["skip"] == 1
    assert payload["limit"] == 2
    assert payload["has_more"] is True
    assert len(payload["items"]) == 2


@pytest.mark.asyncio
async def test_bloggers_list_with_filters_forwards_query_to_repo(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_all(
        _db: Any,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        platform: str | None = None,
    ) -> list:
        captured["skip"] = skip
        captured["limit"] = limit
        captured["keyword"] = keyword
        captured["platform"] = platform
        return []

    monkeypatch.setattr(blogger_endpoint.blogger_repository, "list_all", fake_list_all)

    response = await client.get("/api/bloggers?skip=2&limit=6&keyword=alice&platform=douyin")
    assert response.status_code == 200
    assert response.json() == []
    assert captured == {
        "skip": 2,
        "limit": 6,
        "keyword": "alice",
        "platform": "douyin",
    }


@pytest.mark.asyncio
async def test_planning_list_with_meta_returns_paged_payload(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_all(
        _db: Any,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list:
        _ = (skip, limit)
        assert keyword is None
        assert status is None
        return [
            {
                "id": "p1",
                "client_name": "客户A",
                "industry": "教育",
                "target_audience": "家长",
                "status": "completed",
                "created_at": "2026-03-13T00:00:00",
                "updated_at": "2026-03-13T00:00:00",
            }
        ]

    async def fake_count_all(
        _db: Any,
        keyword: str | None = None,
        status: str | None = None,
    ) -> int:
        assert keyword is None
        assert status is None
        return 1

    monkeypatch.setattr(planning_endpoint.planning_repository, "list_all", fake_list_all)
    monkeypatch.setattr(planning_endpoint.planning_repository, "count_all", fake_count_all)

    response = await client.get("/api/planning?with_meta=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["skip"] == 0
    assert payload["limit"] == 1
    assert payload["has_more"] is False
    assert len(payload["items"]) == 1


@pytest.mark.asyncio
async def test_planning_list_with_filters_forwards_query_to_repo(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list_all(
        _db: Any,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list:
        captured["skip"] = skip
        captured["limit"] = limit
        captured["keyword"] = keyword
        captured["status"] = status
        return []

    monkeypatch.setattr(planning_endpoint.planning_repository, "list_all", fake_list_all)

    response = await client.get("/api/planning?skip=3&limit=5&keyword=教育&status=completed")
    assert response.status_code == 200
    assert response.json() == []
    assert captured == {
        "skip": 3,
        "limit": 5,
        "keyword": "教育",
        "status": "completed",
    }
