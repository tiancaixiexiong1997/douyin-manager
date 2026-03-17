import asyncio

from app.services.ai_analysis_service import AIAnalysisService


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
