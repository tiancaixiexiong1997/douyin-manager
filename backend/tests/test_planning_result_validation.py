import app.api.endpoints.planning as planning_endpoint
import pytest


def test_has_meaningful_plan_result_rejects_empty_payload() -> None:
    assert planning_endpoint._has_meaningful_plan_result({}, {}, []) is False


def test_has_meaningful_plan_result_accepts_structured_plan_content() -> None:
    assert planning_endpoint._has_meaningful_plan_result(
        {"core_identity": "同城探店账号"},
        {},
        [],
    ) is True


def test_has_meaningful_plan_result_accepts_calendar_only_result() -> None:
    assert planning_endpoint._has_meaningful_plan_result(
        {},
        {},
        [{"day": 1, "title_direction": "先拍一条验证题"}],
    ) is True


def test_collect_calendar_quality_flags_detects_low_quality_self_indulgent_topic() -> None:
    flags = planning_endpoint._collect_calendar_quality_flags(
        {
            "title_direction": "周五晚上的店里，全是笑声",
            "key_message": "隔壁写字楼灯刚暗下去，我店里的白噪音正好飙到80分贝。",
        }
    )

    assert "self_indulgent" in flags
    assert "too_poetic" in flags


def test_normalize_content_calendar_item_derives_schedule_labels_for_legacy_data() -> None:
    item = planning_endpoint._normalize_content_calendar_item(
        {
            "day": 1,
            "title_direction": "第一次来做体态的人，最容易紧张的是哪一步",
            "content_type": "口播+画中画",
        },
        day_fallback=1,
    )

    assert item["shoot_format"] == "口播"
    assert item["talent_requirement"] == "IP单人出镜"
    assert item["shoot_scene"] == "办公室"
    assert item["estimated_duration"] == "15分钟内"
    assert item["prep_requirement"] == "需提词器"
    assert item["schedule_group"] == "办公室口播组"
    assert item["is_batch_shootable"] is True
    assert item["batch_shoot_group"] == "办公室口播组"


@pytest.mark.asyncio
async def test_apply_calendar_quality_guardrails_uses_backup_pool_to_keep_30(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_calendar = [
        {"day": day, "title_direction": f"第{day}天顾客最常问的消费问题{day}", "content_type": "口播+画中画", "key_message": f"真实点单原因{day}"}
        for day in range(1, 31)
    ]
    raw_calendar[0] = {
        "day": 1,
        "title_direction": "周五晚上的店里，全是笑声",
        "content_type": "跟拍Vlog",
        "key_message": "今晚就想借着肉香回血",
    }
    backup_pool = [
        {
            "title_direction": "下班后来吃烧烤的人，第一轮最常加的不是肉",
            "content_type": "口播+画中画",
            "key_message": "真实加单顺序更能打动打工人",
            "batch_shoot_group": "口播连拍",
        }
    ]
    monkeypatch.setattr(planning_endpoint, "_calendar_titles_are_too_similar", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        planning_endpoint,
        "_collect_calendar_quality_flags",
        lambda item: ["self_indulgent", "too_poetic"] if "全是笑声" in item.get("title_direction", "") else [],
    )
    async def fake_gap_fill(**_kwargs):
        raise AssertionError("有备用池时不应该触发小范围补写")
    monkeypatch.setattr(planning_endpoint.ai_analysis_service, "generate_calendar_gap_fill", fake_gap_fill)

    calendar, remaining_backup, meta, notes = await planning_endpoint._apply_calendar_quality_guardrails(
        raw_calendar=raw_calendar,
        backup_pool=backup_pool,
        client_data={"client_name": "测试店", "industry": "餐饮美食"},
        account_plan={"account_positioning": {"core_identity": "同城烧烤避坑指南"}},
        project_id="project-1",
        db=None,
    )

    assert len(calendar) == 30
    assert calendar[0]["title_direction"] == "下班后来吃烧烤的人，第一轮最常加的不是肉"
    assert calendar[0]["replaced_from_backup"] is True
    assert remaining_backup == []
    assert meta["blocked_count"] == 1
    assert meta["backup_used_count"] == 1
    assert "已拦截 1 条低传播选题" in notes


@pytest.mark.asyncio
async def test_apply_calendar_quality_guardrails_uses_gap_fill_when_backup_is_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_calendar = [
        {"day": day, "title_direction": f"第{day}天顾客最常问的消费问题{day}", "content_type": "口播+画中画", "key_message": f"真实点单原因{day}"}
        for day in range(1, 31)
    ]
    raw_calendar[-1] = {
        "day": 30,
        "title_direction": "晚上7点的第一把火，肉香盖过班味",
        "content_type": "跟拍Vlog",
        "key_message": "今天受的窝囊气就算翻篇了",
    }

    async def fake_gap_fill(**_kwargs):
        return {
            "items": [
                {
                    "day": 30,
                    "title_direction": "凌晨还在营业的烧烤店，最后一桌一般都点什么",
                    "content_type": "口播+画中画",
                    "content_pillar": "真实测评",
                    "key_message": "夜宵高频点单能直接反映店里招牌",
                    "tags": ["夜宵", "烧烤"],
                    "batch_shoot_group": "口播连拍",
                    "replacement_hint": "替掉空泛氛围题，换成真实消费观察",
                }
            ]
        }

    monkeypatch.setattr(planning_endpoint.ai_analysis_service, "generate_calendar_gap_fill", fake_gap_fill)
    monkeypatch.setattr(planning_endpoint, "_calendar_titles_are_too_similar", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        planning_endpoint,
        "_collect_calendar_quality_flags",
        lambda item: ["self_indulgent", "too_poetic"] if "肉香盖过班味" in item.get("title_direction", "") else [],
    )

    calendar, _remaining_backup, meta, notes = await planning_endpoint._apply_calendar_quality_guardrails(
        raw_calendar=raw_calendar,
        backup_pool=[],
        client_data={"client_name": "测试店", "industry": "餐饮美食"},
        account_plan={"account_positioning": {"core_identity": "同城烧烤避坑指南"}},
        project_id="project-2",
        db=None,
    )

    assert len(calendar) == 30
    assert calendar[-1]["title_direction"] == "凌晨还在营业的烧烤店，最后一桌一般都点什么"
    assert meta["regeneration_count"] == 1
    assert meta["backup_used_count"] == 1
    assert "已触发小范围补写兜底" in notes


@pytest.mark.asyncio
async def test_apply_calendar_quality_guardrails_uses_local_fallback_when_ai_gap_fill_still_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_calendar = [
        {"day": day, "title_direction": f"第{day}天顾客最常问的消费问题{day}", "content_type": "口播+画中画", "key_message": f"真实点单原因{day}"}
        for day in range(1, 26)
    ]

    async def fake_gap_fill(**_kwargs):
        return {"items": []}

    monkeypatch.setattr(planning_endpoint.ai_analysis_service, "generate_calendar_gap_fill", fake_gap_fill)
    monkeypatch.setattr(planning_endpoint, "_calendar_titles_are_too_similar", lambda *_args, **_kwargs: False)

    calendar, _remaining_backup, meta, notes = await planning_endpoint._apply_calendar_quality_guardrails(
        raw_calendar=raw_calendar,
        backup_pool=[],
        client_data={"client_name": "本地废旧回收账号", "industry": "本地生活", "target_audience": "同城家庭用户"},
        account_plan={
            "account_positioning": {
                "core_identity": "同城废旧回收避坑指南",
                "content_pillars": [{"name": "上门回收避坑", "description": "讲清流程", "ratio": "50%"}],
                "target_audience_detail": "同城家庭用户",
            },
            "content_strategy": {"primary_format": "口播+画中画"},
        },
        project_id="project-3",
        db=None,
    )

    assert len(calendar) == 30
    assert meta["regeneration_count"] == 1
    assert any("回收" in item["title_direction"] or "废品" in item["title_direction"] for item in calendar[-5:])
    assert "已启用本地兜底补位，保证30天日历完整" in notes
