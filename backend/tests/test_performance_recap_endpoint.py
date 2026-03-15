from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.deps.auth import require_member_or_admin
from app.models.db_session import get_db
import app.api.endpoints.planning as planning_endpoint


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    class DummyDB:
        async def commit(self) -> None:
            return None

        async def refresh(self, _obj: Any) -> None:
            return None

    async def override_get_db() -> AsyncGenerator[Any, None]:
        yield DummyDB()

    async def override_member() -> Any:
        return SimpleNamespace(role="member", username="tester")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_member_or_admin] = override_member
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_performance_recap_persists_result(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        id="plan-1",
        client_name="测试账号",
        industry="本地生活",
        target_audience="本地年轻人",
        business_goal="提升到店转化",
        account_plan={
            "account_positioning": {"core_identity": "同城娱乐省钱指南"},
            "content_strategy": {"content_tone": "真实、直接"},
        },
        content_items=[SimpleNamespace(id="item-1", day_number=1, title_direction="自助KTV避坑", content_type="口播+画中画")],
    )
    performance_row = SimpleNamespace(
        title="自助KTV避坑",
        publish_date=None,
        views=12000,
        likes=500,
        comments=60,
        shares=30,
        conversions=12,
        bounce_2s_rate=30.0,
        completion_5s_rate=48.0,
        completion_rate=26.0,
        notes="评论区问价很多",
        content_item_id="item-1",
    )

    async def fake_get_by_id(_db: Any, _project_id: str) -> Any:
        return project

    async def fake_list_by_project(_db: Any, _project_id: str) -> list[Any]:
        return [performance_row]

    async def fake_summary_by_project(_db: Any, _project_id: str, planned_content_count: int = 0) -> dict[str, Any]:
        return {
            "total_items": 1,
            "planned_content_count": planned_content_count,
            "coverage_rate": 100.0,
            "total_views": 12000,
            "avg_completion_5s_rate": 48.0,
            "avg_completion_rate": 26.0,
            "avg_engagement_rate": 4.9,
            "avg_conversion_rate": 0.1,
            "total_likes": 500,
            "total_comments": 60,
            "total_shares": 30,
            "total_conversions": 12,
            "top_items": [],
            "best_view_item": None,
            "best_completion_item": None,
            "best_engagement_item": None,
            "best_conversion_item": None,
            "insights": [],
        }

    async def fake_generate_recap(**_kwargs: Any) -> dict[str, Any]:
        return {
            "overall_summary": "当前高播放内容已经出现，最值得继续放大到店决策前的避坑选题。",
            "winning_patterns": ["避坑类选题更容易出播放"],
            "optimization_focus": ["继续优化前3秒反差"],
            "risk_alerts": ["样本量仍然偏少"],
            "next_actions": ["本周补3条同类回流"],
            "next_topic_angles": ["同城娱乐价格透明化"],
        }

    async def fake_log(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(planning_endpoint.planning_repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(planning_endpoint.performance_repo, "list_by_project", fake_list_by_project)
    monkeypatch.setattr(planning_endpoint.performance_repo, "summary_by_project", fake_summary_by_project)
    monkeypatch.setattr(planning_endpoint.ai_analysis_service, "generate_performance_recap", fake_generate_recap)
    monkeypatch.setattr(planning_endpoint.operation_log_repo, "create", fake_log)

    response = await client.post("/api/planning/plan-1/performance-recap")
    assert response.status_code == 200

    body = response.json()
    assert body["overall_summary"].startswith("当前高播放内容已经出现")
    assert body["winning_patterns"] == ["避坑类选题更容易出播放"]
    assert project.account_plan["performance_recap"]["overall_summary"].startswith("当前高播放内容已经出现")


@pytest.mark.asyncio
async def test_generate_performance_recap_requires_rows(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        id="plan-1",
        client_name="测试账号",
        industry="本地生活",
        target_audience="本地年轻人",
        business_goal="提升到店转化",
        account_plan={"account_positioning": {"core_identity": "同城娱乐省钱指南"}},
        content_items=[],
    )

    async def fake_get_by_id(_db: Any, _project_id: str) -> Any:
        return project

    async def fake_list_by_project(_db: Any, _project_id: str) -> list[Any]:
        return []

    monkeypatch.setattr(planning_endpoint.planning_repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(planning_endpoint.performance_repo, "list_by_project", fake_list_by_project)

    response = await client.post("/api/planning/plan-1/performance-recap")
    assert response.status_code == 400
    assert response.json()["detail"] == "请先录入至少 1 条发布回流数据"


@pytest.mark.asyncio
async def test_generate_next_topic_batch_persists_result(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        id="plan-1",
        client_name="测试账号",
        industry="本地生活",
        target_audience="本地年轻人",
        business_goal="提升到店转化",
        account_plan={
            "account_positioning": {"core_identity": "同城娱乐省钱指南"},
            "content_strategy": {"content_tone": "真实、直接"},
            "performance_recap": {
                "overall_summary": "避坑类内容已经被验证过，值得继续放大。",
                "winning_patterns": ["避坑类选题更容易出播放"],
                "optimization_focus": ["继续优化前3秒反差"],
                "next_topic_angles": ["同城娱乐价格透明化"],
            },
        },
        content_items=[SimpleNamespace(day_number=1, title_direction="自助KTV避坑", content_type="口播+画中画", tags=["避坑"])],
    )

    async def fake_get_by_id(_db: Any, _project_id: str) -> Any:
        return project

    async def fake_generate_batch(**_kwargs: Any) -> dict[str, Any]:
        return {
            "overall_strategy": "这一批围绕同城娱乐决策前的关键疑问展开，优先放大已验证有效的避坑切口。",
            "items": [
                {
                    "title_direction": "自助KTV最容易多花钱的3个点",
                    "content_type": "口播+画中画",
                    "content_pillar": "场景痛点",
                    "hook_hint": "先抛一个高频误判",
                    "why_this_angle": "延续避坑类高播放模式。",
                }
            ],
        }

    async def fake_log(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(planning_endpoint.planning_repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(planning_endpoint.ai_analysis_service, "generate_next_topic_batch", fake_generate_batch)
    monkeypatch.setattr(planning_endpoint.operation_log_repo, "create", fake_log)

    response = await client.post("/api/planning/plan-1/next-topic-batch")
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["title_direction"] == "自助KTV最容易多花钱的3个点"
    assert project.account_plan["next_topic_batch"]["items"][0]["title_direction"] == "自助KTV最容易多花钱的3个点"


@pytest.mark.asyncio
async def test_generate_next_topic_batch_requires_recap(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        id="plan-1",
        client_name="测试账号",
        industry="本地生活",
        target_audience="本地年轻人",
        business_goal="提升到店转化",
        account_plan={"account_positioning": {"core_identity": "同城娱乐省钱指南"}},
        content_items=[],
    )

    async def fake_get_by_id(_db: Any, _project_id: str) -> Any:
        return project

    monkeypatch.setattr(planning_endpoint.planning_repository, "get_by_id", fake_get_by_id)

    response = await client.post("/api/planning/plan-1/next-topic-batch")
    assert response.status_code == 400
    assert response.json()["detail"] == "请先生成 AI 发布复盘"


@pytest.mark.asyncio
async def test_import_next_topic_batch_item_appends_content_calendar(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project = SimpleNamespace(
        id="plan-1",
        client_name="测试账号",
        industry="本地生活",
        target_audience="本地年轻人",
        business_goal="提升到店转化",
        account_plan={
            "next_topic_batch": {
                "generated_at": "2026-03-15T12:00:00",
                "overall_strategy": "放大避坑题材",
                "items": [
                    {
                        "title_direction": "自助KTV最容易多花钱的3个点",
                        "content_type": "口播+画中画",
                        "content_pillar": "场景痛点",
                        "hook_hint": "先抛一个常见误区",
                        "why_this_angle": "延续避坑类高播放模式。",
                    }
                ],
            }
        },
        content_items=[SimpleNamespace(id="item-1", day_number=30, title_direction="旧内容", content_type="口播+画中画")],
        content_calendar=[{"day": 30, "title_direction": "旧内容", "content_type": "口播+画中画"}],
    )
    created_item = SimpleNamespace(
        id="item-31",
        day_number=31,
        title_direction="自助KTV最容易多花钱的3个点",
        content_type="口播+画中画",
        tags=["场景痛点"],
        full_script=None,
        is_script_generated=False,
        created_at="2026-03-15T12:01:00",
        updated_at="2026-03-15T12:01:00",
    )

    async def fake_get_by_id(_db: Any, _project_id: str) -> Any:
        return project

    async def fake_add_content_item(_db: Any, data: dict[str, Any]) -> Any:
        assert data["day_number"] == 31
        return created_item

    async def fake_log(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(planning_endpoint.planning_repository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(planning_endpoint.planning_repository, "add_content_item", fake_add_content_item)
    monkeypatch.setattr(planning_endpoint.operation_log_repo, "create", fake_log)

    response = await client.post("/api/planning/plan-1/next-topic-batch/0/import")
    assert response.status_code == 200
    assert response.json()["day_number"] == 31
    assert project.content_calendar[-1]["day"] == 31
    assert project.account_plan["next_topic_batch"]["items"][0]["imported_day_number"] == 31


def test_normalizers_store_json_safe_timestamps() -> None:
    recap = planning_endpoint._normalize_performance_recap({"overall_summary": "测试"})
    batch = planning_endpoint._normalize_next_topic_batch(
        {"overall_strategy": "测试", "items": [{"title_direction": "题目", "content_type": "口播+画中画"}]}
    )

    assert isinstance(recap["generated_at"], str)
    assert isinstance(batch["generated_at"], str)
