import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_analysis_service import ai_analysis_service
from app.services.planning_calendar_utils import (
    derive_batch_group,
    normalize_calendar_generation_meta,
    normalize_content_calendar,
    normalize_content_calendar_item,
    normalize_content_type,
    normalize_text_list,
    safe_text,
)

LOW_QUALITY_THRESHOLD = 2
POETIC_PHRASES = (
    "烟火气", "治愈", "回血", "翻篇", "全是笑声", "肉香盖过", "城市夜晚",
    "夜色里", "氛围感", "松弛感", "借着", "白噪音", "晚风", "情绪价值",
)
SELF_INDULGENT_PHRASES = (
    "我的店", "我店里", "今晚的店里", "晚上7点的第一把火", "周五晚上的店里",
    "借着肉香", "今天受的窝囊气", "肉香盖过班味", "全是笑声",
)
USER_VALUE_MARKERS = (
    "价格", "分量", "值不值", "划算", "避坑", "怎么选", "为什么", "差别", "省钱",
    "推荐", "适合", "攻略", "注意", "别点", "别踩", "真相", "内幕", "对比",
    "哪个", "哪种", "谁更", "值", "便宜", "实在", "复购",
)
CONFLICT_MARKERS = (
    "为什么", "结果", "居然", "到底", "差别", "别", "翻车", "踩雷", "对比",
    "冲突", "吵", "排队", "加单", "退款", "后悔", "劝退", "值不值", "谁",
    "怎么", "不是", "反而", "却", "但", "其实", "真相",
)
COMMENT_HOOK_MARKERS = (
    "你们", "你会", "你更", "会选", "值不值", "到底", "为什么", "哪种", "谁",
    "评论", "会不会", "是不是", "该不该", "有没有", "建议", "能不能",
)
USER_OBJECT_MARKERS = (
    "顾客", "客人", "用户", "打工人", "学生", "情侣", "社恐", "老板", "上班族",
    "回头客", "一个人", "女生", "男生", "本地人", "外地人", "新客", "老客",
)


def _normalize_topic_text(value: str | None) -> str:
    return re.sub(r"\s+", "", safe_text(value))


def _topic_signature(value: str | None) -> set[str]:
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", _normalize_topic_text(value))
    if not text:
        return set()
    if len(text) <= 2:
        return {text}
    return {text[index:index + 2] for index in range(len(text) - 1)}


def _topic_similarity(left: str | None, right: str | None) -> float:
    left_sig = _topic_signature(left)
    right_sig = _topic_signature(right)
    if not left_sig or not right_sig:
        return 0.0
    overlap = len(left_sig & right_sig)
    base = len(left_sig | right_sig)
    return overlap / base if base else 0.0


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def collect_calendar_quality_flags(item: dict) -> list[str]:
    title = _normalize_topic_text(item.get("title_direction"))
    key_message = _normalize_topic_text(item.get("key_message"))
    replacement_hint = _normalize_topic_text(item.get("replacement_hint"))
    text = " ".join(filter(None, [title, key_message, replacement_hint]))

    flags: list[str] = []
    if _contains_any(text, SELF_INDULGENT_PHRASES) or (
        _contains_any(text, POETIC_PHRASES) and not _contains_any(text, USER_OBJECT_MARKERS)
    ):
        flags.append("self_indulgent")
    if _contains_any(text, POETIC_PHRASES):
        flags.append("too_poetic")
    if not _contains_any(text, CONFLICT_MARKERS) and not re.search(r"[0-9一二三四五六七八九十]", text):
        flags.append("no_conflict")
    if not _contains_any(text, USER_VALUE_MARKERS):
        flags.append("no_user_value")
    if not _contains_any(text, COMMENT_HOOK_MARKERS):
        flags.append("no_comment_hook")

    deduped: list[str] = []
    for flag in flags:
        if flag not in deduped:
            deduped.append(flag)
    return deduped


def _normalize_backup_topic_pool_item(raw: dict, *, fallback_index: int) -> dict:
    content_type = normalize_content_type(raw.get("content_type"))
    return {
        "title_direction": safe_text(raw.get("title_direction")) or f"备用题 {fallback_index}",
        "content_type": content_type,
        "content_pillar": safe_text(raw.get("content_pillar")) or None,
        "key_message": safe_text(raw.get("key_message")),
        "tags": normalize_text_list(raw.get("tags"), limit=6),
        "shoot_format": safe_text(raw.get("shoot_format")),
        "talent_requirement": safe_text(raw.get("talent_requirement")),
        "shoot_scene": safe_text(raw.get("shoot_scene")),
        "estimated_duration": safe_text(raw.get("estimated_duration")),
        "prep_requirement": safe_text(raw.get("prep_requirement")),
        "schedule_group": safe_text(raw.get("schedule_group")),
        "batch_shoot_group": safe_text(raw.get("batch_shoot_group")) or derive_batch_group(content_type),
        "replacement_hint": safe_text(raw.get("replacement_hint")),
    }


def normalize_backup_topic_pool(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items: list[dict] = []
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            continue
        items.append(_normalize_backup_topic_pool_item(raw, fallback_index=index))
    return items


def _extract_ratio_value(value) -> float:
    text = safe_text(value).replace("%", "")
    if not text:
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    try:
        return float(match.group(0))
    except ValueError:
        return 0.0


def _build_calendar_gap_brief(
    *,
    existing_calendar: list[dict],
    account_plan: dict,
    missing_days: list[int],
) -> str:
    if not existing_calendar:
        return "当前没有保留条目，请直接围绕账号定位补出完整的高传播题，并尽量拉开内容支柱与拍摄分组。"

    lines: list[str] = []
    lines.append(f"当前已保留 {len(existing_calendar)} 条，待补 Day {', '.join(str(day) for day in missing_days)}。")

    pillar_entries = []
    positioning = account_plan.get("account_positioning") if isinstance(account_plan, dict) else {}
    if isinstance(positioning, dict):
        pillar_entries = positioning.get("content_pillars") if isinstance(positioning.get("content_pillars"), list) else []

    if pillar_entries:
        total_ratio = sum(_extract_ratio_value(item.get("ratio")) for item in pillar_entries if isinstance(item, dict))
        existing_pillar_counts: dict[str, int] = {}
        for item in existing_calendar:
            pillar = safe_text(item.get("content_pillar"))
            if pillar:
                existing_pillar_counts[pillar] = existing_pillar_counts.get(pillar, 0) + 1

        pillar_gaps: list[str] = []
        for pillar in pillar_entries:
            if not isinstance(pillar, dict):
                continue
            name = safe_text(pillar.get("name"))
            if not name:
                continue
            ratio_value = _extract_ratio_value(pillar.get("ratio"))
            target_count = round((ratio_value / total_ratio) * 30) if total_ratio > 0 else 0
            current_count = existing_pillar_counts.get(name, 0)
            gap = max(0, target_count - current_count)
            if gap > 0:
                pillar_gaps.append(f"{name} 还差约 {gap} 条（当前 {current_count} / 目标约 {target_count}）")
        if pillar_gaps:
            lines.append("优先补足的内容支柱：" + "；".join(pillar_gaps[:4]) + "。")

    schedule_counts: dict[str, int] = {}
    for item in existing_calendar:
        group = safe_text(item.get("schedule_group") or item.get("batch_shoot_group"))
        if group:
            schedule_counts[group] = schedule_counts.get(group, 0) + 1
    if schedule_counts:
        sorted_groups = sorted(schedule_counts.items(), key=lambda item: item[1])
        scarce_groups = [f"{group}（当前 {count} 条）" for group, count in sorted_groups[:3]]
        dominant_group, dominant_count = max(schedule_counts.items(), key=lambda item: item[1])
        lines.append("拍摄排期上优先补这些分组：" + "、".join(scarce_groups) + "。")
        if dominant_count >= max(6, len(existing_calendar) // 3):
            lines.append(f"注意避免继续堆在 {dominant_group}，它当前已占 {dominant_count} 条。")

    recent_items = sorted(existing_calendar, key=lambda item: int(item.get("day", 0)))[-5:]
    if recent_items:
        recent_titles = "；".join(
            safe_text(item.get("title_direction"))
            for item in recent_items
            if safe_text(item.get("title_direction"))
        )
        if recent_titles:
            lines.append(f"最近保留的条目有：{recent_titles}。新题要尽量拉开切入角度、不要只做近义改写。")

    return "\n".join(lines)


def _calendar_titles_are_too_similar(candidate: dict, existing_items: list[dict]) -> bool:
    title = candidate.get("title_direction")
    for item in existing_items:
        similarity = _topic_similarity(title, item.get("title_direction"))
        if similarity >= 0.55:
            return True
    return False


def _candidate_replacement_score(candidate: dict, target: dict) -> int:
    score = 0
    if candidate.get("content_type") == target.get("content_type"):
        score += 3
    if candidate.get("content_pillar") and candidate.get("content_pillar") == target.get("content_pillar"):
        score += 2
    if candidate.get("batch_shoot_group") == target.get("batch_shoot_group"):
        score += 1
    quality_flags = collect_calendar_quality_flags(candidate)
    score -= len(quality_flags) * 2
    return score


def _convert_backup_topic_to_calendar_item(backup_item: dict, target_item: dict) -> dict:
    merged = {
        **target_item,
        "title_direction": backup_item.get("title_direction", ""),
        "content_type": backup_item.get("content_type", target_item.get("content_type")),
        "content_pillar": backup_item.get("content_pillar") or target_item.get("content_pillar"),
        "key_message": backup_item.get("key_message") or target_item.get("key_message"),
        "tags": backup_item.get("tags") or target_item.get("tags"),
        "shoot_format": backup_item.get("shoot_format") or target_item.get("shoot_format"),
        "talent_requirement": backup_item.get("talent_requirement") or target_item.get("talent_requirement"),
        "shoot_scene": backup_item.get("shoot_scene") or target_item.get("shoot_scene"),
        "estimated_duration": backup_item.get("estimated_duration") or target_item.get("estimated_duration"),
        "prep_requirement": backup_item.get("prep_requirement") or target_item.get("prep_requirement"),
        "schedule_group": backup_item.get("schedule_group") or target_item.get("schedule_group"),
        "batch_shoot_group": backup_item.get("batch_shoot_group") or target_item.get("batch_shoot_group"),
        "replacement_hint": backup_item.get("replacement_hint") or target_item.get("replacement_hint"),
        "replaced_from_backup": True,
        "quality_flags": [],
    }
    if "replacement_source_index" not in merged:
        merged["replacement_source_index"] = None
    return normalize_content_calendar_item(merged, day_fallback=target_item.get("day", 1))


def _pick_backup_replacement(
    target_item: dict,
    backup_pool: list[dict],
    kept_items: list[dict],
) -> tuple[dict | None, int | None]:
    ranked: list[tuple[int, int, dict]] = []
    for index, candidate in enumerate(backup_pool):
        if len(collect_calendar_quality_flags(candidate)) >= LOW_QUALITY_THRESHOLD:
            continue
        if _calendar_titles_are_too_similar(candidate, kept_items):
            continue
        ranked.append((_candidate_replacement_score(candidate, target_item), index, candidate))
    if not ranked:
        return None, None
    ranked.sort(key=lambda item: item[0], reverse=True)
    _, index, candidate = ranked[0]
    return candidate, index


def _finalize_calendar_days(items: list[dict]) -> list[dict]:
    finalized: list[dict] = []
    for day, item in enumerate(items, start=1):
        normalized = normalize_content_calendar_item({**item, "day": day}, day_fallback=day)
        finalized.append(normalized)
    return finalized


def _derive_local_topic_subject(client_data: dict, account_plan: dict) -> str:
    text = " ".join(
        filter(
            None,
            [
                safe_text(client_data.get("client_name")),
                safe_text(client_data.get("industry")),
                safe_text(client_data.get("ip_requirements")),
                safe_text((account_plan.get("account_positioning") or {}).get("core_identity") if isinstance(account_plan, dict) else ""),
            ],
        )
    )
    lowered = text.lower()
    if "回收" in text or "废旧" in text or "废品" in text:
        return "旧家电和废品处理"
    if "烧烤" in text or "餐饮" in text or "美食" in text:
        return "夜宵和点单选择"
    if "健身" in text or "减脂" in text:
        return "减脂训练和饮食执行"
    if "护肤" in text or "美妆" in text:
        return "护肤和选品决策"
    if "本地" in text or "同城" in text or "门店" in text:
        return "同城消费和到店决策"
    if "education" in lowered or "学习" in text or "教育" in text:
        return "学习选择和提分执行"
    return safe_text(client_data.get("industry")) or "同城真实需求"


def _derive_local_audience_label(client_data: dict, account_plan: dict) -> str:
    target = safe_text((account_plan.get("account_positioning") or {}).get("target_audience_detail") if isinstance(account_plan, dict) else "")
    if not target:
        target = safe_text(client_data.get("target_audience"))
    if "上班" in target or "职场" in target or "打工" in target:
        return "上班族"
    if "学生" in target:
        return "学生党"
    if "老板" in target:
        return "老板"
    if "家庭" in target or "宝妈" in target or "父母" in target:
        return "家庭用户"
    return "同城用户"


def _build_local_calendar_fallback_pool(
    *,
    client_data: dict,
    account_plan: dict,
    existing_items: list[dict],
    missing_count: int,
) -> list[dict]:
    subject = _derive_local_topic_subject(client_data, account_plan)
    audience = _derive_local_audience_label(client_data, account_plan)
    positioning = account_plan.get("account_positioning", {}) if isinstance(account_plan, dict) else {}
    strategy = account_plan.get("content_strategy", {}) if isinstance(account_plan, dict) else {}
    content_type = normalize_content_type(strategy.get("primary_format"))
    pillars = positioning.get("content_pillars", []) if isinstance(positioning.get("content_pillars"), list) else []
    pillar_names = [
        safe_text(item.get("name"))
        for item in pillars
        if isinstance(item, dict) and safe_text(item.get("name"))
    ] or ["真实问题", "避坑决策", "同城需求"]

    title_templates = [
        "{audience}处理{subject}时，最先问的不是价格，而是能不能今天上门",
        "为什么很多人处理{subject}，最后卡在搬运费和楼层",
        "{subject}到底先问价格，还是先问能不能当天拉走",
        "同城做{subject}时，最容易被一句“马上到”拖住",
        "{audience}第一次问{subject}，最容易漏掉哪3句关键信息",
        "{subject}想少踩坑，提前确认哪一步最省时间",
        "{subject}值不值当场定，关键看哪两个细节",
        "同样是做{subject}，为什么有人半小时解决，有人拖两天",
        "{audience}处理{subject}，最怕临时加价还是上门太慢",
        "{subject}怎么问才不被来回拉扯，你会怎么选",
    ]
    key_templates = [
        "这条围绕{pillar}，把真实决策点讲清楚，评论区也更容易接话：你会怎么选。",
        "这条围绕{pillar}，直接回答用户最在意的时间、价格和执行成本。",
        "这条围绕{pillar}，用具体问题替代空泛氛围，用户看完知道下一步该怎么问。",
    ]

    candidates: list[dict] = []
    title_index = 0
    while len(candidates) < max(12, missing_count * 4):
        template = title_templates[title_index % len(title_templates)]
        pillar = pillar_names[title_index % len(pillar_names)]
        title = template.format(audience=audience, subject=subject, pillar=pillar)
        if len(pillar_names) > 1:
            title = f"{title}：{pillar}"
        candidate = {
            "title_direction": title,
            "content_type": content_type,
            "content_pillar": pillar,
            "key_message": key_templates[title_index % len(key_templates)].format(pillar=pillar),
            "tags": normalize_text_list([safe_text(client_data.get("industry")), pillar, audience], limit=6),
            "batch_shoot_group": derive_batch_group(content_type),
            "replacement_hint": "如果前面验证效果一般，就优先换成这种具体问题题，而不是空泛感受题；你会怎么选？",
        }
        if not _calendar_titles_are_too_similar(candidate, existing_items + candidates):
            candidates.append(candidate)
        title_index += 1
        if title_index > 60:
            break

    return candidates


async def apply_calendar_quality_guardrails(
    *,
    raw_calendar: list[dict],
    backup_pool: list[dict],
    client_data: dict,
    account_plan: dict,
    project_id: str,
    db: AsyncSession,
) -> tuple[list[dict], list[dict], dict, str]:
    kept_items: list[dict] = []
    blocked_items: list[dict] = []
    available_backup_pool = [dict(item) for item in backup_pool]
    meta = normalize_calendar_generation_meta({})
    quality_notes_parts: list[str] = []
    local_fallback_used = False

    for raw_item in raw_calendar[:30]:
        item = normalize_content_calendar_item(raw_item, day_fallback=len(kept_items) + 1)
        quality_flags = collect_calendar_quality_flags(item)
        is_duplicate_angle = _calendar_titles_are_too_similar(item, kept_items)
        if len(quality_flags) < LOW_QUALITY_THRESHOLD and not is_duplicate_angle:
            item["quality_flags"] = quality_flags
            item["replaced_from_backup"] = False
            item["replacement_source_index"] = None
            kept_items.append(item)
            continue
        if is_duplicate_angle and "duplicate_angle" not in quality_flags:
            quality_flags.append("duplicate_angle")

        blocked_items.append(
            {
                "day": item.get("day"),
                "title_direction": item.get("title_direction"),
                "content_type": item.get("content_type"),
                "content_pillar": item.get("content_pillar"),
                "quality_flags": quality_flags,
            }
        )
        meta["blocked_count"] += 1
        replacement, replacement_index = _pick_backup_replacement(item, available_backup_pool, kept_items)
        if replacement is None:
            continue
        chosen_replacement = available_backup_pool.pop(replacement_index)
        normalized_replacement = _convert_backup_topic_to_calendar_item(
            {**chosen_replacement, "replacement_source_index": replacement_index},
            item,
        )
        normalized_replacement["replacement_source_index"] = replacement_index
        normalized_replacement["quality_flags"] = collect_calendar_quality_flags(normalized_replacement)
        kept_items.append(normalized_replacement)
        meta["backup_used_count"] += 1

    missing_count = max(0, 30 - len(kept_items))
    if missing_count > 0:
        missing_days = list(range(len(kept_items) + 1, 31))
        gap_fill_result = await ai_analysis_service.generate_calendar_gap_fill(
            project_context={
                "client_name": client_data.get("client_name"),
                "industry": client_data.get("industry"),
                "target_audience": client_data.get("target_audience"),
                "ip_requirements": client_data.get("ip_requirements"),
            },
            account_plan=account_plan,
            existing_calendar=kept_items,
            calendar_gap_brief=_build_calendar_gap_brief(
                existing_calendar=kept_items,
                account_plan=account_plan,
                missing_days=missing_days,
            ),
            blocked_topics=blocked_items[-10:],
            missing_days=missing_days,
            run_context={"entity_type": "planning_project", "entity_id": project_id},
            db=db,
        )
        if isinstance(gap_fill_result, dict) and gap_fill_result.get("error"):
            raise ValueError(gap_fill_result["error"])
        refill_pool = normalize_backup_topic_pool(
            gap_fill_result.get("items", []) if isinstance(gap_fill_result, dict) else []
        )
        meta["regeneration_count"] += 1
        available_backup_pool.extend(refill_pool)

        while len(kept_items) < 30:
            target_day = len(kept_items) + 1
            placeholder = normalize_content_calendar_item({"day": target_day}, day_fallback=target_day)
            replacement, replacement_index = _pick_backup_replacement(
                placeholder,
                available_backup_pool,
                kept_items,
            )
            if replacement is None:
                break
            chosen_replacement = available_backup_pool.pop(replacement_index)
            normalized_replacement = _convert_backup_topic_to_calendar_item(
                {**chosen_replacement, "replacement_source_index": replacement_index},
                placeholder,
            )
            normalized_replacement["replacement_source_index"] = replacement_index
            normalized_replacement["quality_flags"] = collect_calendar_quality_flags(normalized_replacement)
            kept_items.append(normalized_replacement)
            meta["backup_used_count"] += 1

    if len(kept_items) < 30:
        local_fallback_used = True
        local_fallback_pool = _build_local_calendar_fallback_pool(
            client_data=client_data,
            account_plan=account_plan,
            existing_items=kept_items,
            missing_count=30 - len(kept_items),
        )
        available_backup_pool.extend(local_fallback_pool)

        while len(kept_items) < 30:
            target_day = len(kept_items) + 1
            placeholder = normalize_content_calendar_item({"day": target_day}, day_fallback=target_day)
            replacement, replacement_index = _pick_backup_replacement(
                placeholder,
                available_backup_pool,
                kept_items,
            )
            if replacement is None:
                break
            chosen_replacement = available_backup_pool.pop(replacement_index)
            normalized_replacement = _convert_backup_topic_to_calendar_item(
                {**chosen_replacement, "replacement_source_index": replacement_index},
                placeholder,
            )
            normalized_replacement["replacement_source_index"] = replacement_index
            normalized_replacement["quality_flags"] = collect_calendar_quality_flags(normalized_replacement)
            kept_items.append(normalized_replacement)
            meta["backup_used_count"] += 1

    finalized_items = _finalize_calendar_days(kept_items)
    if len(finalized_items) != 30:
        raise ValueError(f"内容日历质控补位后仍不足 30 条，当前仅 {len(finalized_items)} 条")

    if any(not safe_text(item.get("batch_shoot_group")) for item in finalized_items):
        raise ValueError("内容日历存在缺失拍摄分组的条目")

    if meta["blocked_count"] > 0:
        quality_notes_parts.append(f"已拦截 {meta['blocked_count']} 条低传播选题")
    if meta["backup_used_count"] > 0:
        quality_notes_parts.append(f"已使用 {meta['backup_used_count']} 条备用题补位")
    if meta["regeneration_count"] > 0:
        quality_notes_parts.append("已触发小范围补写兜底")
    if local_fallback_used:
        quality_notes_parts.append("已启用本地兜底补位，保证30天日历完整")

    return finalized_items, available_backup_pool, meta, "；".join(quality_notes_parts)


async def regenerate_selected_calendar_days(
    *,
    project,
    client_data: dict,
    account_plan: dict,
    regenerate_days: list[int],
    project_id: str,
    db: AsyncSession,
) -> tuple[list[dict], dict, str]:
    existing_calendar = normalize_content_calendar(project.content_calendar or [])
    if len(existing_calendar) != 30:
        raise ValueError("当前内容日历不足 30 条，暂不支持局部重生成，请先整批生成一次")

    selected_days = sorted({day for day in regenerate_days if isinstance(day, int) and 1 <= day <= 30})
    if not selected_days:
        return existing_calendar, normalize_calendar_generation_meta({}), ""

    preserved_items = [dict(item) for item in existing_calendar if item.get("day") not in selected_days]
    blocked_topics = [
        {
            "day": item.get("day"),
            "title_direction": item.get("title_direction"),
            "content_type": item.get("content_type"),
            "content_pillar": item.get("content_pillar"),
            "quality_flags": ["manual_regenerate"],
        }
        for item in existing_calendar
        if item.get("day") in selected_days
    ]

    gap_fill_result = await ai_analysis_service.generate_calendar_gap_fill(
        project_context={
            "client_name": client_data.get("client_name"),
            "industry": client_data.get("industry"),
            "target_audience": client_data.get("target_audience"),
            "ip_requirements": client_data.get("ip_requirements"),
        },
        account_plan=account_plan,
        existing_calendar=preserved_items,
        calendar_gap_brief=_build_calendar_gap_brief(
            existing_calendar=preserved_items,
            account_plan=account_plan,
            missing_days=selected_days,
        ),
        blocked_topics=blocked_topics[-10:],
        missing_days=selected_days,
        run_context={"entity_type": "planning_project", "entity_id": project_id},
        db=db,
    )
    if isinstance(gap_fill_result, dict) and gap_fill_result.get("error"):
        raise ValueError(gap_fill_result["error"])

    candidate_pool = normalize_backup_topic_pool(
        gap_fill_result.get("items", []) if isinstance(gap_fill_result, dict) else []
    )
    if len(candidate_pool) < len(selected_days):
        candidate_pool.extend(
            _build_local_calendar_fallback_pool(
                client_data=client_data,
                account_plan=account_plan,
                existing_items=preserved_items,
                missing_count=len(selected_days) - len(candidate_pool),
            )
        )

    regenerated_items: list[dict] = []
    for target_day in selected_days:
        placeholder = normalize_content_calendar_item({"day": target_day}, day_fallback=target_day)
        replacement, replacement_index = _pick_backup_replacement(
            placeholder,
            candidate_pool,
            preserved_items + regenerated_items,
        )
        if replacement is None:
            for index, candidate in enumerate(candidate_pool):
                if candidate.get("day") == target_day:
                    replacement = candidate
                    replacement_index = index
                    break
        if replacement is None and candidate_pool:
            replacement = candidate_pool[0]
            replacement_index = 0
        if replacement is None:
            raise ValueError(f"第 {target_day} 天未能生成可替换的新选题，请稍后重试")
        chosen_replacement = candidate_pool.pop(replacement_index)
        normalized_replacement = _convert_backup_topic_to_calendar_item(
            {**chosen_replacement, "replacement_source_index": replacement_index},
            placeholder,
        )
        normalized_replacement["replacement_source_index"] = replacement_index
        normalized_replacement["quality_flags"] = collect_calendar_quality_flags(normalized_replacement)
        regenerated_items.append(normalized_replacement)

    finalized_items = [
        normalize_content_calendar_item(item, day_fallback=item.get("day", index))
        for index, item in enumerate(
            sorted([*preserved_items, *regenerated_items], key=lambda item: int(item.get("day", 0))),
            start=1,
        )
    ]
    if len(finalized_items) != 30:
        raise ValueError(f"局部重生成后日历数量异常，当前 {len(finalized_items)} 条")

    meta = normalize_calendar_generation_meta(
        {
            "backup_used_count": len(regenerated_items),
            "regeneration_count": 1,
        }
    )
    note = f"已保留 {len(preserved_items)} 条原日历，仅重生成 {len(regenerated_items)} 条选中内容"
    return finalized_items, meta, note
