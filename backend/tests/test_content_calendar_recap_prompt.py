from typing import Any

import pytest

from app.services.ai_analysis_service import AIAnalysisService


@pytest.mark.asyncio
async def test_generate_content_calendar_includes_performance_recap_context(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return (
            "复盘:{performance_recap_summary}\n"
            "放大:{winning_patterns}\n"
            "优化:{optimization_focus}\n"
            "选题:{next_topic_angles}",
            {},
        )

    async def fake_call_ai(_system_prompt: str, user_prompt: str) -> dict[str, Any]:
        captured["user_prompt"] = user_prompt
        return {"content_calendar": []}

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "content_calendar"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    await service.generate_content_calendar(
        client_info={"client_name": "测试项目"},
        account_plan={
            "account_positioning": {"core_identity": "同城娱乐省钱指南", "content_pillars": []},
            "content_strategy": {"content_tone": "真实直接"},
            "performance_recap": {
                "overall_summary": "避坑类内容已经验证过，有继续放大的价值。",
                "winning_patterns": ["避坑类选题更容易出播放"],
                "optimization_focus": ["继续优化前3秒反差"],
                "next_topic_angles": ["同城娱乐价格透明化"],
            },
        },
    )

    user_prompt = captured["user_prompt"]
    assert "避坑类内容已经验证过" in user_prompt
    assert "避坑类选题更容易出播放" in user_prompt
    assert "继续优化前3秒反差" in user_prompt
    assert "同城娱乐价格透明化" in user_prompt


@pytest.mark.asyncio
async def test_generate_content_calendar_handles_missing_performance_recap(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return ("复盘:{performance_recap_summary}", {})

    async def fake_call_ai(_system_prompt: str, user_prompt: str) -> dict[str, Any]:
        captured["user_prompt"] = user_prompt
        return {"content_calendar": []}

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "content_calendar"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    await service.generate_content_calendar(
        client_info={"client_name": "测试项目"},
        account_plan={
            "account_positioning": {"core_identity": "同城娱乐省钱指南", "content_pillars": []},
            "content_strategy": {"content_tone": "真实直接"},
        },
    )

    assert "暂无已生成复盘建议" in captured["user_prompt"]
