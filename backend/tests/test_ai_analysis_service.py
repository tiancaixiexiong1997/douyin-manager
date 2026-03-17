import asyncio
from typing import Any

import pytest

from app.services.ai_analysis_service import AIAnalysisService
from app.services.prompt_templates import BLOGGER_VIRAL_PROFILE_PROMPT_TEMPLATE


def test_resolve_ffmpeg_timeout_uses_minimum_without_duration() -> None:
    service = AIAnalysisService()

    assert service._resolve_ffmpeg_timeout(None) == 120


def test_resolve_ffmpeg_timeout_scales_with_long_video() -> None:
    service = AIAnalysisService()

    timeout = service._resolve_ffmpeg_timeout(360)

    assert timeout > 120
    assert timeout == 390


def test_resolve_ffmpeg_timeout_has_upper_bound() -> None:
    service = AIAnalysisService()

    timeout = service._resolve_ffmpeg_timeout(2000)

    assert timeout == 900


def test_build_system_prompt_includes_fact_rules_for_all_scenes(monkeypatch) -> None:
    service = AIAnalysisService()

    async def fake_get_current_setting(key: str, default_value: str) -> str:
        if key == "GLOBAL_AI_FACT_RULES":
            return "FACT_RULES"
        if key == "GLOBAL_AI_WRITING_RULES":
            return "WRITING_RULES"
        return default_value

    monkeypatch.setattr(service, "_get_current_setting", fake_get_current_setting)

    prompt = asyncio.run(service._build_system_prompt(scene_key="blogger_report", base_prompt="BASE_PROMPT"))

    assert "BASE_PROMPT" in prompt
    assert "FACT_RULES" in prompt
    assert "WRITING_RULES" not in prompt


def test_build_system_prompt_adds_writing_rules_for_copy_scenes(monkeypatch) -> None:
    service = AIAnalysisService()

    async def fake_get_current_setting(key: str, default_value: str) -> str:
        if key == "GLOBAL_AI_FACT_RULES":
            return "FACT_RULES"
        if key == "GLOBAL_AI_WRITING_RULES":
            return "WRITING_RULES"
        return default_value

    monkeypatch.setattr(service, "_get_current_setting", fake_get_current_setting)

    prompt = asyncio.run(service._build_system_prompt(scene_key="video_script", base_prompt="BASE_PROMPT"))

    assert "BASE_PROMPT" in prompt
    assert "FACT_RULES" in prompt
    assert "WRITING_RULES" in prompt


@pytest.mark.asyncio
async def test_generate_blogger_viral_profile_sorts_videos_by_published_at(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return ("数据:{text_data_json}", {})

    async def fake_call_ai(_system_prompt: str, user_prompt: str) -> dict[str, Any]:
        captured["user_prompt"] = user_prompt
        return {"timeline_entries": []}

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "blogger_viral_profile"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    await service.generate_blogger_viral_profile(
        blogger_info={"nickname": "测试博主"},
        videos_text_data=[
            {"title": "较晚视频", "published_at": "2026-03-05T12:00:00"},
            {"title": "最早视频", "published_at": "2026-02-01T09:00:00"},
            {"title": "无日期视频", "published_at": None},
        ],
        videos_analysis=[],
    )

    user_prompt = captured["user_prompt"]
    assert user_prompt.index("最早视频") < user_prompt.index("较晚视频")
    assert user_prompt.index("较晚视频") < user_prompt.index("无日期视频")


@pytest.mark.asyncio
async def test_generate_account_plan_includes_timeline_fields_from_viral_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return ("参考:{bloggers_text}", {})

    async def fake_call_ai(_system_prompt: str, user_prompt: str) -> dict[str, Any]:
        captured["user_prompt"] = user_prompt
        return {"account_positioning": {}, "content_strategy": {}, "content_calendar": []}

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "account_plan"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    await service.generate_account_plan(
        client_info={"client_name": "测试客户"},
        reference_bloggers=[
            {
                "nickname": "参考博主A",
                "analysis_report": {
                    "viral_profile": {
                        "account_planning_logic": "先用低门槛痛点切入，再逐步放大。",
                        "timeline_overview": "2月先试探，3月出现第一条起量内容，之后连续放大同类选题。",
                        "timeline_entries": [
                            {
                                "date": "2026-02-10",
                                "title": "第一条试探内容",
                                "phase": "起号试探期",
                                "topic_pattern": "低门槛避坑",
                                "post_fire_role": "试探",
                                "why_it_mattered": "验证人群是否愿意停留。",
                            }
                        ],
                        "post_fire_arrangement": "爆点后连续做同类问题拆解，再补场景化延伸。",
                        "planning_takeaways": ["先用单点痛点破圈，再做场景延伸。"],
                    }
                },
            }
        ],
    )

    user_prompt = captured["user_prompt"]
    assert "timeline_overview" in user_prompt
    assert "2月先试探，3月出现第一条起量内容" in user_prompt
    assert "第一条试探内容" in user_prompt
    assert "先用单点痛点破圈，再做场景延伸" in user_prompt


def test_blogger_viral_profile_prompt_template_can_be_formatted_with_timeline_fields() -> None:
    rendered = BLOGGER_VIRAL_PROFILE_PROMPT_TEMPLATE.format(
        nickname="测试博主",
        platform="douyin",
        follower_count=1000,
        signature="简介",
        video_count=20,
        text_data_json="[]",
        analyses_json="[]",
    )

    assert '"timeline_entries"' in rendered
    assert '"date"' in rendered
    assert "{nickname}" not in rendered
