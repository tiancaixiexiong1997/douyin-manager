from datetime import datetime

from app.services.planning_calendar_utils import normalize_content_calendar_item, normalize_content_type, normalize_text_list, safe_text


def normalize_performance_recap(raw: dict) -> dict:
    overall_summary = safe_text(
        raw.get("overall_summary")
        or raw.get("raw_analysis")
        or raw.get("error")
        or "AI 暂未生成结构化复盘，请稍后重试。"
    )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "overall_summary": overall_summary,
        "winning_patterns": normalize_text_list(raw.get("winning_patterns"), limit=5),
        "optimization_focus": normalize_text_list(raw.get("optimization_focus"), limit=5),
        "risk_alerts": normalize_text_list(raw.get("risk_alerts"), limit=4),
        "next_actions": normalize_text_list(raw.get("next_actions"), limit=5),
        "next_topic_angles": normalize_text_list(raw.get("next_topic_angles"), limit=5),
    }


def serialize_performance_rows(project, rows: list) -> list[dict]:
    content_item_map = {item.id: item for item in project.content_items or []}
    serialized_rows: list[dict] = []
    for row in rows:
        linked_item = content_item_map.get(row.content_item_id) if row.content_item_id else None
        serialized_rows.append(
            {
                "title": row.title,
                "publish_date": row.publish_date.isoformat() if row.publish_date else None,
                "views": row.views,
                "likes": row.likes,
                "comments": row.comments,
                "shares": row.shares,
                "conversions": row.conversions,
                "bounce_2s_rate": row.bounce_2s_rate,
                "completion_5s_rate": row.completion_5s_rate,
                "completion_rate": row.completion_rate,
                "notes": row.notes,
                "linked_content_item": (
                    {
                        "day_number": linked_item.day_number,
                        "title_direction": linked_item.title_direction,
                        "content_type": linked_item.content_type,
                    }
                    if linked_item
                    else None
                ),
            }
        )
    return serialized_rows


def serialize_existing_content_items(project) -> list[dict]:
    items = sorted(project.content_items or [], key=lambda item: item.day_number)
    return [
        {
            "day_number": item.day_number,
            "title_direction": item.title_direction,
            "content_type": item.content_type,
            "tags": item.tags or [],
        }
        for item in items
    ]


def normalize_next_topic_batch(raw: dict) -> dict:
    overall_strategy = safe_text(
        raw.get("overall_strategy")
        or raw.get("raw_analysis")
        or raw.get("error")
        or "AI 暂未生成下一批选题，请稍后重试。"
    )
    items: list[dict] = []
    if isinstance(raw.get("items"), list):
        for item in raw["items"]:
            if not isinstance(item, dict):
                continue
            title_direction = safe_text(item.get("title_direction"))
            if not title_direction:
                continue
            items.append(
                {
                    "title_direction": title_direction,
                    "content_type": normalize_content_type(item.get("content_type")),
                    "content_pillar": safe_text(item.get("content_pillar")) or None,
                    "hook_hint": safe_text(item.get("hook_hint")) or None,
                    "why_this_angle": safe_text(item.get("why_this_angle")) or None,
                    "imported_content_item_id": safe_text(item.get("imported_content_item_id")) or None,
                    "imported_day_number": item.get("imported_day_number") if isinstance(item.get("imported_day_number"), int) else None,
                    "imported_at": (
                        item.get("imported_at").isoformat()
                        if isinstance(item.get("imported_at"), datetime)
                        else (safe_text(item.get("imported_at")) or None)
                    ),
                }
            )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "overall_strategy": overall_strategy,
        "items": items[:10],
    }


def build_next_topic_calendar_item(batch_item: dict, next_day_number: int) -> dict:
    normalized_type = normalize_content_type(batch_item.get("content_type"))
    return normalize_content_calendar_item(
        {
            "day": next_day_number,
            "title_direction": batch_item.get("title_direction", ""),
            "content_type": normalized_type,
            "content_pillar": batch_item.get("content_pillar"),
            "key_message": batch_item.get("why_this_angle") or batch_item.get("hook_hint") or "",
            "tags": [batch_item.get("content_pillar")] if batch_item.get("content_pillar") else [],
            "priority": "P2-补充储备",
            "content_role": "补充试错",
            "is_main_validation": False,
            "is_batch_shootable": True,
            "batch_shoot_group": batch_item.get("batch_shoot_group"),
            "replacement_hint": batch_item.get("why_this_angle") or "",
        },
        day_fallback=next_day_number,
    )
