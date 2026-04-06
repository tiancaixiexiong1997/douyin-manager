import re
from typing import Any


def safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_text_list(value, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [safe_text(item) for item in value]
    return [item for item in items if item][:limit]


def normalize_content_type(value: str | None) -> str:
    """统一内容类型，避免出现高表演门槛标签。"""
    raw = safe_text(value)
    if not raw:
        return "口播+画中画"

    compact = raw.lower().replace(" ", "")
    if any(token in compact for token in ("微剧情", "剧情", "情景剧", "短剧")):
        return "口播+画中画"
    if "口播" in compact or "画中画" in compact:
        return "口播+画中画"
    if "vlog" in compact or "跟拍" in raw or "记录" in raw:
        return "跟拍Vlog"
    if "评测" in raw or "测评" in raw:
        return "测评"
    if "教程" in raw or "教学" in raw:
        return "教程"
    if "探店" in raw:
        return "探店实拍"
    return "口播+画中画"


def normalize_calendar_priority(value) -> str | None:
    text = safe_text(value)
    if text.startswith("P0"):
        return "P0-主验证"
    if text.startswith("P2"):
        return "P2-补充储备"
    if text.startswith("P1"):
        return "P1-稳定输出"
    return None


def normalize_calendar_role(value) -> str:
    text = safe_text(value)
    allowed = {"主验证", "稳定输出", "流量放大", "信任建立", "承接转化", "补充试错"}
    return text if text in allowed else "稳定输出"


def normalize_shoot_format(value) -> str:
    text = safe_text(value)
    allowed = {"口播", "演示", "对谈", "情景化口播", "跟拍", "实拍讲解"}
    return text if text in allowed else ""


def normalize_talent_requirement(value) -> str:
    text = safe_text(value)
    allowed = {"IP单人出镜", "IP+客户", "IP配助理", "仅IP配音"}
    return text if text in allowed else ""


def normalize_estimated_duration(value) -> str:
    text = safe_text(value)
    allowed = {"5分钟内", "15分钟内", "30分钟内"}
    return text if text in allowed else ""


def normalize_prep_requirement(value) -> str:
    text = safe_text(value)
    allowed = {"无准备", "需提词器", "需案例素材", "需道具", "需现场配合", "需流程提纲"}
    return text if text in allowed else ""


def derive_batch_group(content_type: str) -> str:
    text = normalize_content_type(content_type)
    if "口播" in text or "画中画" in text:
        return "口播连拍"
    if "教程" in text:
        return "教程演示"
    if "测评" in text:
        return "测评连拍"
    if "探店" in text or "实拍" in text:
        return "外拍探店"
    if "Vlog" in text or "跟拍" in text:
        return "跟拍纪实"
    return "混合拍摄"


def derive_schedule_profile(content_type: str) -> dict[str, str]:
    text = normalize_content_type(content_type)
    if "口播" in text or "画中画" in text:
        return {
            "shoot_format": "口播",
            "talent_requirement": "IP单人出镜",
            "shoot_scene": "办公室",
            "estimated_duration": "15分钟内",
            "prep_requirement": "需提词器",
            "schedule_group": "办公室口播组",
        }
    if "教程" in text:
        return {
            "shoot_format": "演示",
            "talent_requirement": "IP单人出镜",
            "shoot_scene": "演示区",
            "estimated_duration": "15分钟内",
            "prep_requirement": "需道具",
            "schedule_group": "教程演示组",
        }
    if "测评" in text:
        return {
            "shoot_format": "演示",
            "talent_requirement": "IP单人出镜",
            "shoot_scene": "产品展示区",
            "estimated_duration": "15分钟内",
            "prep_requirement": "需道具",
            "schedule_group": "测评演示组",
        }
    if "探店" in text or "实拍" in text:
        return {
            "shoot_format": "实拍讲解",
            "talent_requirement": "IP单人出镜",
            "shoot_scene": "门店现场",
            "estimated_duration": "30分钟内",
            "prep_requirement": "需现场配合",
            "schedule_group": "门店实拍组",
        }
    if "Vlog" in text or "跟拍" in text:
        return {
            "shoot_format": "跟拍",
            "talent_requirement": "IP单人出镜",
            "shoot_scene": "门店现场",
            "estimated_duration": "30分钟内",
            "prep_requirement": "需流程提纲",
            "schedule_group": "门店跟拍组",
        }
    return {
        "shoot_format": "口播",
        "talent_requirement": "IP单人出镜",
        "shoot_scene": "办公室",
        "estimated_duration": "15分钟内",
        "prep_requirement": "需提词器",
        "schedule_group": "办公室口播组",
    }


def normalize_content_calendar_item(raw: dict, *, day_fallback: int) -> dict:
    day = raw.get("day") if isinstance(raw.get("day"), int) else day_fallback
    content_type = normalize_content_type(raw.get("content_type"))
    priority = normalize_calendar_priority(raw.get("priority"))
    is_main_validation_raw = raw.get("is_main_validation")
    is_main_validation = (
        bool(is_main_validation_raw)
        if isinstance(is_main_validation_raw, bool)
        else priority == "P0-主验证"
    )
    profile = derive_schedule_profile(content_type)
    is_batch_shootable_raw = raw.get("is_batch_shootable")
    is_batch_shootable = bool(is_batch_shootable_raw) if isinstance(is_batch_shootable_raw, bool) else True
    schedule_group = safe_text(raw.get("schedule_group")) or profile["schedule_group"] or safe_text(raw.get("batch_shoot_group"))
    batch_group = schedule_group or safe_text(raw.get("batch_shoot_group")) or derive_batch_group(content_type)
    shoot_format = normalize_shoot_format(raw.get("shoot_format")) or profile["shoot_format"]
    talent_requirement = normalize_talent_requirement(raw.get("talent_requirement")) or profile["talent_requirement"]
    shoot_scene = safe_text(raw.get("shoot_scene")) or profile["shoot_scene"]
    estimated_duration = normalize_estimated_duration(raw.get("estimated_duration")) or profile["estimated_duration"]
    prep_requirement = normalize_prep_requirement(raw.get("prep_requirement")) or profile["prep_requirement"]

    return {
        "day": day,
        "title_direction": safe_text(raw.get("title_direction")) or f"Day {day} 内容方向",
        "content_type": content_type,
        "content_pillar": safe_text(raw.get("content_pillar")) or None,
        "key_message": safe_text(raw.get("key_message")),
        "tags": normalize_text_list(raw.get("tags"), limit=6),
        "priority": "P0-主验证" if is_main_validation else priority,
        "content_role": normalize_calendar_role(raw.get("content_role")),
        "is_main_validation": is_main_validation,
        "shoot_format": shoot_format,
        "talent_requirement": talent_requirement,
        "shoot_scene": shoot_scene,
        "estimated_duration": estimated_duration,
        "prep_requirement": prep_requirement,
        "schedule_group": schedule_group,
        "is_batch_shootable": is_batch_shootable,
        "batch_shoot_group": batch_group if is_batch_shootable else (batch_group or "混合拍摄"),
        "replacement_hint": safe_text(raw.get("replacement_hint")),
        "replaced_from_backup": bool(raw.get("replaced_from_backup", False)),
        "replacement_source_index": raw.get("replacement_source_index"),
        "quality_flags": normalize_text_list(raw.get("quality_flags"), limit=8),
    }


def normalize_content_calendar(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items: list[dict] = []
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            continue
        items.append(normalize_content_calendar_item(raw, day_fallback=index))
    return items


def normalize_calendar_generation_meta(value) -> dict:
    raw = value if isinstance(value, dict) else {}
    return {
        "blocked_count": max(0, int(raw.get("blocked_count", 0) or 0)),
        "backup_used_count": max(0, int(raw.get("backup_used_count", 0) or 0)),
        "regeneration_count": max(0, int(raw.get("regeneration_count", 0) or 0)),
    }


def has_meaningful_plan_result(
    account_positioning: dict | None,
    content_strategy: dict | None,
    content_calendar: list | None,
) -> bool:
    positioning = account_positioning if isinstance(account_positioning, dict) else {}
    strategy = content_strategy if isinstance(content_strategy, dict) else {}
    calendar = content_calendar if isinstance(content_calendar, list) else []
    has_positioning = any(bool(safe_text(value)) for value in positioning.values())
    has_strategy = any(bool(safe_text(value)) for value in strategy.values())
    return has_positioning or has_strategy or bool(calendar)


def has_meaningful_strategy_result(
    account_positioning: dict | None,
    content_strategy: dict | None,
) -> bool:
    positioning = account_positioning if isinstance(account_positioning, dict) else {}
    strategy = content_strategy if isinstance(content_strategy, dict) else {}
    has_positioning = any(bool(safe_text(value)) for value in positioning.values())
    has_strategy = any(bool(safe_text(value)) for value in strategy.values())
    return has_positioning or has_strategy


def build_strategy_task_context(project) -> dict:
    account_plan = getattr(project, "account_plan", None)
    account_plan = account_plan if isinstance(account_plan, dict) else {}
    has_existing_strategy = has_meaningful_strategy_result(
        account_plan.get("account_positioning"),
        account_plan.get("content_strategy"),
    )
    return {
        "planning_state": "strategy_regenerating",
        "has_existing_strategy": has_existing_strategy,
    }


def serialize_calendar_snapshot_item(content_item, calendar_meta_by_day: dict[int, dict]) -> dict:
    calendar_meta = calendar_meta_by_day.get(getattr(content_item, "day_number", 0))
    return {
        "id": getattr(content_item, "id", ""),
        "day_number": getattr(content_item, "day_number", 0),
        "title_direction": getattr(content_item, "title_direction", ""),
        "content_type": normalize_content_type(getattr(content_item, "content_type", None)),
        "tags": normalize_text_list(getattr(content_item, "tags", None), limit=6),
        "is_script_generated": bool(getattr(content_item, "is_script_generated", False)),
        "calendar_meta": dict(calendar_meta) if isinstance(calendar_meta, dict) else None,
    }


def build_calendar_task_context(project, selected_days: list[int]) -> dict:
    normalized_calendar = normalize_content_calendar(project.content_calendar or [])
    calendar_meta_by_day = {
        item["day"]: item
        for item in normalized_calendar
        if isinstance(item, dict) and isinstance(item.get("day"), int)
    }
    content_items = list(project.content_items or [])
    available_days = sorted(
        {
            *(
                item.day_number
                for item in content_items
                if isinstance(getattr(item, "day_number", None), int)
            ),
            *(day for day in calendar_meta_by_day.keys() if isinstance(day, int)),
        }
    )
    has_existing_calendar = bool(normalized_calendar) or bool(content_items)
    is_partial_regenerate = has_existing_calendar and bool(selected_days)
    target_days = selected_days or available_days
    snapshots = [
        serialize_calendar_snapshot_item(item, calendar_meta_by_day)
        for item in sorted(content_items, key=lambda current: current.day_number)
        if item.day_number in target_days
    ]
    snapshot_days = {
        item.get("day_number")
        for item in snapshots
        if isinstance(item, dict) and isinstance(item.get("day_number"), int)
    }
    for day in target_days:
        if day in snapshot_days:
            continue
        calendar_meta = calendar_meta_by_day.get(day)
        if not calendar_meta:
            continue
        snapshots.append(
            {
                "id": f"pending-day-{day}",
                "day_number": day,
                "title_direction": safe_text(calendar_meta.get("title_direction")) or f"Day {day} 内容方向",
                "content_type": normalize_content_type(calendar_meta.get("content_type")),
                "tags": normalize_text_list(calendar_meta.get("tags"), limit=6),
                "is_script_generated": False,
                "calendar_meta": dict(calendar_meta),
            }
        )
    return {
        "planning_state": "calendar_regenerating",
        "regeneration_mode": "partial" if is_partial_regenerate else ("full" if has_existing_calendar else "initial"),
        "regenerate_day_numbers": target_days,
        "calendar_snapshots": snapshots,
    }


def attach_normalized_content_calendar(project):
    if not project or not hasattr(project, "content_calendar"):
        return project
    project.content_calendar = normalize_content_calendar(getattr(project, "content_calendar", None))
    return project
