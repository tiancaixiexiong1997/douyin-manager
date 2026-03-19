import asyncio
from typing import Any

import pytest

from app.services.ai_analysis_service import AIAnalysisService
from app.services.prompt_templates import (
    ACCOUNT_PLAN_PROMPT_TEMPLATE,
    BLOGGER_VIRAL_PROFILE_PROMPT_TEMPLATE,
    CALENDAR_GAP_FILL_PROMPT_TEMPLATE,
    CONTENT_CALENDAR_PROMPT_TEMPLATE,
)


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


def test_resolve_ai_overall_timeout_prefers_heavy_calendar_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    monkeypatch.delenv("AI_TEXT_CALL_OVERALL_TIMEOUT_SECONDS", raising=False)

    timeout = service._resolve_ai_overall_timeout(scene_key="content_calendar", is_multimodal_video=False)

    assert timeout == 240


def test_content_calendar_prompt_uses_hard_structure_constraints() -> None:
    assert "每条必须同时包含：具体对象 + 具体场景 + 具体问题/动作/差异/结果 + 明确观看回报" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "允许优先生成的题型" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "好题示例：第一次卖旧空调，客户最容易误会的是哪一步" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "坏题示例：她们在这里短暂逃离家庭" in CONTENT_CALENDAR_PROMPT_TEMPLATE


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

    async def fake_call_ai(_system_prompt: str, user_prompt: str, scene_key: str | None = None) -> dict[str, Any]:
        assert scene_key == "blogger_viral_profile"
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

    async def fake_call_ai(_system_prompt: str, user_prompt: str, scene_key: str | None = None) -> dict[str, Any]:
        assert scene_key == "account_plan"
        captured["user_prompt"] = user_prompt
        return {"account_positioning": {}, "content_strategy": {}}

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


@pytest.mark.asyncio
async def test_generate_blogger_report_without_representative_analysis_degrades_film_and_marks_copywriting(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return ("约束:{analysis_constraints}", {})

    async def fake_call_ai(_system_prompt: str, user_prompt: str, scene_key: str | None = None) -> dict[str, Any]:
        assert scene_key == "blogger_report"
        captured["user_prompt"] = user_prompt
        return {
            "filming_signature": {
                "visual_style": "固定机位室内口播",
                "editing_signature": "快切",
                "production_level": "半专业",
                "unique_techniques": "字幕强调",
            },
            "copywriting_dna": {
                "tone_of_voice": "直接、口语化",
                "typical_hooks": ["先说一个扎心事实"],
                "cta_patterns": "结尾追问一句",
                "interaction_style": "会在评论区接话",
            },
        }

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "blogger_report"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    result = await service.generate_blogger_report(
        blogger_info={"nickname": "测试博主"},
        videos_text_data=[{"title": "标题样本", "description": "描述样本"}],
        videos_analysis=[],
    )

    assert "当前没有代表作深度多模态分析数据" in captured["user_prompt"]
    assert result["filming_signature"]["visual_style"] == "数据不足，无法判断"
    assert result["filming_signature"]["editing_signature"] == "数据不足，无法判断"
    assert result["copywriting_dna"]["tone_of_voice"].startswith("仅基于标题/描述样本推断：")
    assert result["copywriting_dna"]["typical_hooks"][0].startswith("仅基于标题/描述样本推断：")


@pytest.mark.asyncio
async def test_generate_blogger_report_with_representative_analysis_keeps_original_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return ("约束:{analysis_constraints}", {})

    async def fake_call_ai(_system_prompt: str, _user_prompt: str, scene_key: str | None = None) -> dict[str, Any]:
        assert scene_key == "blogger_report"
        return {
            "filming_signature": {
                "visual_style": "手持探店",
                "editing_signature": "高频快切",
                "production_level": "专业团队",
                "unique_techniques": "大广角运动镜头",
            },
            "copywriting_dna": {
                "tone_of_voice": "短句压缩信息",
            },
        }

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "blogger_report"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    result = await service.generate_blogger_report(
        blogger_info={"nickname": "测试博主"},
        videos_text_data=[{"title": "标题样本"}],
        videos_analysis=[{"content_summary": "真实代表作分析"}],
    )

    assert result["filming_signature"]["visual_style"] == "手持探店"
    assert result["copywriting_dna"]["tone_of_voice"] == "短句压缩信息"


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


def test_scene_result_validator_rejects_empty_account_plan() -> None:
    service = AIAnalysisService()

    assert service._is_scene_result_acceptable(
        "account_plan",
        {"account_positioning": {}, "content_strategy": {}},
    ) is False


def test_scene_result_validator_accepts_nonempty_account_plan() -> None:
    service = AIAnalysisService()

    assert service._is_scene_result_acceptable(
        "account_plan",
        {"account_positioning": {"core_identity": "同城探店账号"}, "content_strategy": {}},
    ) is True


def test_scene_result_validator_rejects_empty_calendar_gap_fill() -> None:
    service = AIAnalysisService()

    assert service._is_scene_result_acceptable(
        "calendar_gap_fill",
        {"items": []},
    ) is False


def test_account_and_calendar_prompts_require_staged_output_and_anti_self_indulgent_rules() -> None:
    assert "当前阶段只做账号定位和内容策略" in ACCOUNT_PLAN_PROMPT_TEMPLATE
    assert "不要输出 30 天日历" in ACCOUNT_PLAN_PROMPT_TEMPLATE
    assert "只做一次输出，不要补充备用题" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "肉香盖过班味" in ACCOUNT_PLAN_PROMPT_TEMPLATE
    assert "全是笑声" in CONTENT_CALENDAR_PROMPT_TEMPLATE


def test_calendar_gap_fill_prompt_template_can_be_formatted() -> None:
    rendered = CALENDAR_GAP_FILL_PROMPT_TEMPLATE.format(
        project_context="{}",
        account_plan_json="{}",
        existing_calendar_json="[]",
        blocked_topics_json="[]",
        missing_days="1、2",
    )

    assert '"items"' in rendered
    assert "{missing_days}" not in rendered
