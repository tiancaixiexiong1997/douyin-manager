import asyncio
from typing import Any

import pytest

from app.services.ai_analysis_service import AIAnalysisService
from app.services.prompt_templates import (
    ACCOUNT_PLAN_PROMPT_TEMPLATE,
    BLOGGER_VIRAL_PROFILE_PROMPT_TEMPLATE,
    CALENDAR_GAP_FILL_PROMPT_TEMPLATE,
    CONTENT_CALENDAR_PROMPT_TEMPLATE,
    NEXT_TOPIC_BATCH_PROMPT_TEMPLATE,
    PERFORMANCE_RECAP_PROMPT_TEMPLATE,
    SCRIPT_REMAKE_FROM_ANALYSIS_PROMPT_TEMPLATE,
    SCRIPT_REMAKE_PROMPT_TEMPLATE,
    VIDEO_SCRIPT_PROMPT_TEMPLATE,
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


def test_resolve_multimodal_video_base64_limit_prefers_scene_default(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    monkeypatch.delenv("AI_MULTIMODAL_MAX_VIDEO_BASE64_MB", raising=False)

    assert service._resolve_multimodal_video_base64_limit_mb("video_analysis") == 8.0
    assert service._resolve_multimodal_video_base64_limit_mb("script_remake") == 10.0


def test_build_video_compression_ladder_uses_more_aggressive_profiles_for_remake() -> None:
    service = AIAnalysisService()

    general = service._build_video_compression_ladder("video_analysis")
    remake = service._build_video_compression_ladder("script_remake")

    assert general[0]["scale"] == "480:-2"
    assert remake[0]["scale"] == "360:-2"
    assert remake[-1]["fps"] == "6"


def test_normalize_account_plan_result_can_overwrite_legacy_fields() -> None:
    service = AIAnalysisService()
    result = {
        "store_growth_plan": {
            "store_positioning": {
                "market_position": "柳州本地人下班会去的夜宵店",
                "primary_scene": "下班夜宵",
                "target_audience_detail": "附近上班族",
                "core_store_value": "不踩雷、上桌快",
                "differentiation": "老板判断很稳",
                "avoid_positioning": ["苦情创业"],
            },
            "decision_triggers": {
                "stop_scroll_triggers": ["下班后最馋这一口"],
                "visit_decision_factors": ["上桌快", "不踩雷", "味道稳"],
                "common_hesitations": ["怕排队"],
                "trust_builders": ["后厨现炒", "老板现场判断"],
            },
            "content_model": {
                "primary_formats": [{"name": "老板判断型", "fit_reason": "能立住懂行感", "ratio": "40%"}],
                "content_pillars": [
                    {"name": "点单建议", "description": "解决顾客不会点", "scene_source": "前厅"},
                    {"name": "后厨现场", "description": "证明锅气", "scene_source": "后厨"},
                    {"name": "夜宵场景", "description": "接住情绪", "scene_source": "门头"},
                ],
                "traffic_hooks": ["这口你半夜顶不住"],
                "interaction_triggers": ["你夜宵最先点什么"],
            },
            "on_camera_strategy": {
                "recommended_roles": [{"role": "老板", "responsibility": "做判断", "expression_style": "讲话直接"}],
                "light_persona": "嘴直但靠谱",
                "persona_boundaries": ["别演苦情"],
            },
            "conversion_path": {
                "traffic_to_trust": "先给判断，再给后厨证据",
                "trust_to_visit": "最后自然带到店",
                "soft_cta_templates": ["你们半夜最扛不住哪口"],
                "hard_sell_boundaries": ["开头不要直接推套餐"],
            },
            "execution_rules": {
                "posting_frequency": "每天1条",
                "best_posting_times": ["18:00", "21:00"],
                "batch_shoot_scenes": ["备菜", "高峰出餐"],
                "must_capture_elements": ["火", "烟", "翻锅"],
                "quality_checklist": ["有钩子", "有到店理由"],
            },
        },
        "account_positioning": {"core_identity": "旧定位"},
        "content_strategy": {"primary_format": "旧形式"},
    }

    normalized = service.normalize_account_plan_result(result, overwrite_legacy=True)

    assert normalized["account_positioning"]["core_identity"] == "柳州本地人下班会去的夜宵店"
    assert normalized["content_strategy"]["posting_frequency"] == "每天1条"


def test_resolve_ai_overall_timeout_prefers_heavy_calendar_scene(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    monkeypatch.delenv("AI_TEXT_CALL_OVERALL_TIMEOUT_SECONDS", raising=False)

    timeout = service._resolve_ai_overall_timeout(scene_key="content_calendar", is_multimodal_video=False)

    assert timeout == 240


def test_content_calendar_prompt_uses_hard_structure_constraints() -> None:
    assert "每条必须同时包含：具体对象 + 具体场景 + 具体问题/动作/差异/结果 + 明确观看回报" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "补齐编导排期标签：shoot_format / talent_requirement / shoot_scene / prep_requirement / schedule_group" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "允许优先生成的题型" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "好题示例：第一次卖旧空调，客户最容易误会的是哪一步" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "坏题示例：她们在这里短暂逃离家庭" in CONTENT_CALENDAR_PROMPT_TEMPLATE


def test_recap_and_next_topic_prompts_include_store_growth_fields() -> None:
    assert "{store_market_position}" in PERFORMANCE_RECAP_PROMPT_TEMPLATE
    assert "{store_growth_plan_json}" in PERFORMANCE_RECAP_PROMPT_TEMPLATE
    assert "{store_visit_decision_factors}" in NEXT_TOPIC_BATCH_PROMPT_TEMPLATE
    assert "{store_content_pillars}" in NEXT_TOPIC_BATCH_PROMPT_TEMPLATE


@pytest.mark.asyncio
async def test_call_ai_uses_text_provider_for_text_scenes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    values = {
        "AI_API_KEY": "sk-text",
        "AI_BASE_URL": "https://text.example.com/v1",
        "AI_MODEL": "text-model",
    }

    async def fake_get_current_setting(key: str, default_value: str) -> str:
        return values.get(key, default_value)

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"account_positioning": {"core_identity": "测试定位"}, "content_strategy": {"content_tone": "直接"}}'
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, timeout: Any = None) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(service, "_get_current_setting", fake_get_current_setting)
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    result = await service._call_ai("system", "hello", scene_key="account_plan")

    assert result["account_positioning"]["core_identity"] == "测试定位"
    assert result["content_strategy"]["content_tone"] == "直接"
    assert captured["url"] == "https://text.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-text"
    assert captured["json"]["model"] == "text-model"


@pytest.mark.asyncio
async def test_call_ai_uses_multimodal_provider_for_video_scenes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    values = {
        "AI_API_KEY": "sk-mm",
        "AI_BASE_URL": "https://mm.example.com/v1",
        "AI_MODEL": "mm-model",
    }

    async def fake_get_current_setting(key: str, default_value: str) -> str:
        return values.get(key, default_value)

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeAsyncClient:
        def __init__(self, timeout: Any = None) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(service, "_get_current_setting", fake_get_current_setting)
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    result = await service._call_ai(
        "system",
        [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {"url": "data:video/mp4;base64,abc"}}],
        scene_key="video_analysis",
    )

    assert result == {}
    assert captured["url"] == "https://mm.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-mm"
    assert captured["json"]["model"] == "mm-model"


@pytest.mark.asyncio
async def test_call_ai_surfaces_http_400_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()

    values = {
        "AI_API_KEY": "sk-mm",
        "AI_BASE_URL": "https://mm.example.com/v1",
        "AI_MODEL": "mm-model",
    }

    async def fake_get_current_setting(key: str, default_value: str) -> str:
        return values.get(key, default_value)

    class FakeResponse:
        status_code = 400
        text = '{"error":"payload too large"}'

        @staticmethod
        def json() -> dict[str, Any]:
            return {}

    class FakeAsyncClient:
        def __init__(self, timeout: Any = None) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(service, "_get_current_setting", fake_get_current_setting)
    monkeypatch.setattr("httpx.AsyncClient", FakeAsyncClient)

    result = await service._call_ai(
        "system",
        [{"type": "text", "text": "hello"}, {"type": "image_url", "image_url": {"url": "data:video/mp4;base64,abc"}}],
        scene_key="video_analysis",
    )

    assert result == {"error": 'AI 调用失败: primary HTTP 400（{"error":"payload too large"}）'}


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


def test_build_hook_reference_block_prioritizes_opening_segment() -> None:
    service = AIAnalysisService()

    block = service._build_hook_reference_block(
        {
            "copy_segment_breakdown": [
                {
                    "segment": "开场钩子",
                    "duration": "0-4秒",
                    "original_copy": "上班呢 你拍什么拍？我没拍。",
                    "copy_function": "钩子",
                    "emotion_goal": "先制造压迫感，再让人好奇后面发生什么",
                    "transition_role": "把观众带到后面的店铺广告段",
                }
            ]
        }
    )

    assert "上班呢 你拍什么拍？我没拍。" in block
    assert "先抓停留、再承接广告/卖点" in block
    assert "storyboard 的 scene 1 台词要与 opening_hook 一致或直接延展" in block


def test_script_remake_prompts_require_preserving_hook_before_ad_copy() -> None:
    assert "先用高流量钩子抓停留，再自然带出本店/产品/服务" in SCRIPT_REMAKE_PROMPT_TEMPLATE
    assert "优先复刻原视频已经验证有效的开场钩子机制" in SCRIPT_REMAKE_FROM_ANALYSIS_PROMPT_TEMPLATE
    assert "{hook_reference_block}" in SCRIPT_REMAKE_FROM_ANALYSIS_PROMPT_TEMPLATE


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
async def test_generate_performance_recap_includes_store_growth_context(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return (
            "定位:{store_market_position}\n场景:{store_primary_scene}\n决策:{store_visit_decision_factors}\n钩子:{store_traffic_hooks}\n支柱:{store_content_pillars}\n计划:{store_growth_plan_json}",
            {},
        )

    async def fake_call_ai(_system_prompt: str, user_prompt: str, scene_key: str | None = None) -> dict[str, Any]:
        assert scene_key == "performance_recap"
        captured["user_prompt"] = user_prompt
        return {"overall_summary": "ok", "winning_patterns": [], "optimization_focus": [], "risk_alerts": [], "next_actions": [], "next_topic_angles": []}

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "performance_recap"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    await service.generate_performance_recap(
        project_context={"client_name": "测试门店"},
        account_plan={
            "store_growth_plan": {
                "store_positioning": {"market_position": "社区刚需店", "primary_scene": "下班顺路来"},
                "decision_triggers": {"visit_decision_factors": ["方便", "值", "稳"]},
                "content_model": {
                    "traffic_hooks": ["第一次来最容易点错"],
                    "content_pillars": [{"name": "点单建议"}],
                },
                "on_camera_strategy": {"recommended_roles": [{"role": "老板"}]},
                "conversion_path": {"traffic_to_trust": "先给建议再给证据"},
                "execution_rules": {"posting_frequency": "每天1条"},
            }
        },
        performance_summary={"total_items": 1},
        performance_rows=[],
    )

    user_prompt = captured["user_prompt"]
    assert "社区刚需店" in user_prompt
    assert "下班顺路来" in user_prompt
    assert "方便；值；稳" in user_prompt
    assert "第一次来最容易点错" in user_prompt
    assert "点单建议" in user_prompt


@pytest.mark.asyncio
async def test_generate_next_topic_batch_includes_store_growth_context(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIAnalysisService()
    captured: dict[str, Any] = {}

    async def fake_resolve_prompt(**_kwargs: Any) -> tuple[str, dict[str, Any]]:
        return (
            "定位:{store_market_position}\n场景:{store_primary_scene}\n决策:{store_visit_decision_factors}\n钩子:{store_traffic_hooks}\n支柱:{store_content_pillars}\n计划:{store_growth_plan_json}",
            {},
        )

    async def fake_call_ai(_system_prompt: str, user_prompt: str, scene_key: str | None = None) -> dict[str, Any]:
        assert scene_key == "next_topic_batch"
        captured["user_prompt"] = user_prompt
        return {"overall_strategy": "ok", "items": []}

    async def fake_record_prompt_run(**_kwargs: Any) -> None:
        return None

    async def fake_build_system_prompt(*, scene_key: str, base_prompt: str) -> str:
        assert scene_key == "next_topic_batch"
        return base_prompt

    monkeypatch.setattr(service, "_resolve_prompt", fake_resolve_prompt)
    monkeypatch.setattr(service, "_build_system_prompt", fake_build_system_prompt)
    monkeypatch.setattr(service, "_call_ai", fake_call_ai)
    monkeypatch.setattr(service, "_record_prompt_run", fake_record_prompt_run)

    await service.generate_next_topic_batch(
        project_context={"client_name": "测试门店"},
        account_plan={
            "store_growth_plan": {
                "store_positioning": {"market_position": "社区刚需店", "primary_scene": "下班顺路来"},
                "decision_triggers": {"visit_decision_factors": ["方便", "值", "稳"]},
                "content_model": {
                    "traffic_hooks": ["第一次来最容易点错"],
                    "content_pillars": [{"name": "点单建议"}],
                },
                "on_camera_strategy": {"recommended_roles": [{"role": "老板"}]},
                "conversion_path": {"traffic_to_trust": "先给建议再给证据"},
                "execution_rules": {"posting_frequency": "每天1条"},
            }
        },
        performance_recap={"overall_summary": "ok"},
        existing_content_items=[],
    )

    user_prompt = captured["user_prompt"]
    assert "社区刚需店" in user_prompt
    assert "下班顺路来" in user_prompt
    assert "方便；值；稳" in user_prompt
    assert "第一次来最容易点错" in user_prompt
    assert "点单建议" in user_prompt


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
        {
            "store_growth_plan": {
                "store_positioning": {
                    "market_position": "柳州夜宵决策参考店",
                    "primary_scene": "下班后夜宵",
                    "target_audience_detail": "本地上班族",
                    "core_store_value": "点单不踩雷",
                    "differentiation": "老板会直接给判断",
                    "avoid_positioning": ["纯氛围感"],
                },
                "decision_triggers": {
                    "stop_scroll_triggers": ["第一口点什么", "几分钟上桌", "值不值来"],
                    "visit_decision_factors": ["上桌速度", "点单判断", "同城距离"],
                    "common_hesitations": ["怕踩雷", "怕等太久", "怕不值"],
                    "trust_builders": ["真实后厨", "老板出镜", "顾客加单"],
                },
                "content_model": {
                    "primary_formats": [{"name": "老板判断型", "fit_reason": "适合同城决策", "ratio": "40%"}],
                    "content_pillars": [
                        {"name": "点单建议", "description": "帮用户判断怎么点", "scene_source": "前厅"},
                        {"name": "后厨现场", "description": "证明出品稳定", "scene_source": "后厨"},
                        {"name": "夜宵场景", "description": "绑定消费时机", "scene_source": "门头"},
                    ],
                    "traffic_hooks": ["别乱点", "先看这口", "这个点来的人先问这个"],
                    "interaction_triggers": ["你会先点什么", "你最怕踩哪个雷", "你几点会来吃"],
                },
                "on_camera_strategy": {
                    "recommended_roles": [{"role": "老板", "responsibility": "做判断", "expression_style": "嘴直"}],
                    "light_persona": "讲话很直的老板",
                    "persona_boundaries": ["不演苦情创业"],
                },
                "conversion_path": {
                    "traffic_to_trust": "先讲判断，再给出店里真实画面",
                    "trust_to_visit": "再自然带出适合谁来",
                    "soft_cta_templates": ["你一般先点什么"],
                    "hard_sell_boundaries": ["开头别报店名"],
                },
                "execution_rules": {
                    "posting_frequency": "日更1条",
                    "best_posting_times": ["18:00", "22:00"],
                    "batch_shoot_scenes": ["后厨", "前厅", "门口"],
                    "must_capture_elements": ["出锅", "点单", "上桌"],
                    "quality_checklist": ["有停留点", "有决策理由", "有真实场景"],
                },
            }
        },
    ) is True


def test_scene_result_validator_rejects_incomplete_store_growth_plan() -> None:
    service = AIAnalysisService()

    assert service._is_scene_result_acceptable(
        "account_plan",
        {
            "store_growth_plan": {
                "store_positioning": {"market_position": "同城夜宵店"},
                "decision_triggers": {"visit_decision_factors": ["便宜"]},
                "content_model": {"content_pillars": [{"name": "点单建议"}], "traffic_hooks": ["先看这个"]},
                "on_camera_strategy": {"recommended_roles": []},
                "conversion_path": {"traffic_to_trust": ""},
                "execution_rules": {"posting_frequency": ""},
            }
        },
    ) is False


def test_scene_result_validator_rejects_empty_calendar_gap_fill() -> None:
    service = AIAnalysisService()

    assert service._is_scene_result_acceptable(
        "calendar_gap_fill",
        {"items": []},
    ) is False


def test_account_and_calendar_prompts_require_staged_output_and_anti_self_indulgent_rules() -> None:
    assert "先门店，后人设" in ACCOUNT_PLAN_PROMPT_TEMPLATE
    assert '"store_growth_plan"' in ACCOUNT_PLAN_PROMPT_TEMPLATE
    assert "不要输出 30 天逐日内容" in ACCOUNT_PLAN_PROMPT_TEMPLATE
    assert "只做一次输出，不要补充备用题" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "{store_growth_plan_json}" in CONTENT_CALENDAR_PROMPT_TEMPLATE
    assert "{traffic_hooks}" in VIDEO_SCRIPT_PROMPT_TEMPLATE
    assert "{recommended_roles}" in VIDEO_SCRIPT_PROMPT_TEMPLATE
    assert "全是笑声" in CONTENT_CALENDAR_PROMPT_TEMPLATE


def test_normalize_account_plan_result_maps_store_growth_plan_back_to_legacy() -> None:
    service = AIAnalysisService()

    result = service._normalize_account_plan_result(
        {
            "store_growth_plan": {
                "store_positioning": {
                    "market_position": "同城夜宵决策参考店",
                    "primary_scene": "下班后夜宵",
                    "target_audience_detail": "25-35岁本地上班族",
                    "core_store_value": "帮你少踩雷",
                    "differentiation": "老板直接给判断",
                    "avoid_positioning": ["纯氛围号"],
                },
                "decision_triggers": {
                    "stop_scroll_triggers": ["别乱点", "先看这个", "这口值不值"],
                    "visit_decision_factors": ["距离近", "上桌快", "味道稳"],
                    "common_hesitations": ["怕踩雷", "怕排队", "怕不值"],
                    "trust_builders": ["后厨实拍", "真实加单", "老板出镜"],
                },
                "content_model": {
                    "primary_formats": [{"name": "老板判断型", "fit_reason": "适合同城决策", "ratio": "40%"}],
                    "content_pillars": [
                        {"name": "点单建议", "description": "帮用户判断怎么点", "scene_source": "前厅"},
                        {"name": "后厨现场", "description": "证明出品稳定", "scene_source": "后厨"},
                        {"name": "夜宵场景", "description": "绑定消费时机", "scene_source": "门头"},
                    ],
                    "traffic_hooks": ["别乱点", "先看这口", "这个点来先问这个"],
                    "interaction_triggers": ["你会先点什么", "你最怕踩哪个雷", "你几点来吃"],
                },
                "on_camera_strategy": {
                    "recommended_roles": [{"role": "老板", "responsibility": "做判断", "expression_style": "嘴直"}],
                    "light_persona": "讲话很直的老板",
                    "persona_boundaries": ["不演苦情创业"],
                },
                "conversion_path": {
                    "traffic_to_trust": "先讲判断，再给真实画面",
                    "trust_to_visit": "再带出适合谁来",
                    "soft_cta_templates": ["你一般先点什么", "你更在意上桌快还是味道稳"],
                    "hard_sell_boundaries": ["别一开头报店名"],
                },
                "execution_rules": {
                    "posting_frequency": "日更1条",
                    "best_posting_times": ["18:00", "22:00"],
                    "batch_shoot_scenes": ["后厨", "前厅", "门头"],
                    "must_capture_elements": ["出锅", "点单", "上桌"],
                    "quality_checklist": ["有停留点", "有决策理由", "有真实场景"],
                },
            }
        }
    )

    assert result["account_positioning"]["core_identity"] == "同城夜宵决策参考店"
    assert result["account_positioning"]["content_pillars"][0]["name"] == "点单建议"
    assert result["content_strategy"]["primary_format"] == "老板判断型"
    assert "别乱点" in result["content_strategy"]["hook_template"]


def test_calendar_gap_fill_prompt_template_can_be_formatted() -> None:
    rendered = CALENDAR_GAP_FILL_PROMPT_TEMPLATE.format(
        project_context="{}",
        account_plan_json="{}",
        existing_calendar_json="[]",
        calendar_gap_brief="补足案例证明与承接转化",
        blocked_topics_json="[]",
        missing_days="1、2",
    )

    assert '"items"' in rendered
    assert "{missing_days}" not in rendered
