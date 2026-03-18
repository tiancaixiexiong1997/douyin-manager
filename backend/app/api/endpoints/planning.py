"""
策划项目 API 端点
"""
import logging
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.api.deps.auth import require_member_or_admin
from app.models.database import TaskStatus, User
from app.models.db_session import get_db
from app.schemas.planning import (
    PlanningCreateRequest,
    PlanningResponse,
    PlanningListResponse,
    PlanningPagedResponse,
    PlanningIntakeAssistantRequest,
    PlanningIntakeAssistantResponse,
    ScriptGenerateRequest,
    ContentItemUpdateRequest,
    ContentItemResponse,
    AccountHomepageUpdateRequest,
    PlanningUpdateRequest,
    ContentPerformanceCreateRequest,
    ContentPerformanceUpdateRequest,
    ContentPerformanceResponse,
    ContentPerformanceSummaryResponse,
    NextTopicBatchResponse,
    PerformanceRecapResponse,
)
from app.services.ai_analysis_service import ai_analysis_service
from app.services.cancellation import cancellation_registry
from app.services.crawler_service import crawler_service
from app.repository.planning_repo import planning_repository
from app.repository.blogger_repo import blogger_repository
from app.repository.performance_repo import performance_repo
from app.repository.operation_log_repo import operation_log_repo
from app.repository.task_center_repo import task_center_repo
from app.services.job_queue import enqueue_task

router = APIRouter()
logger = logging.getLogger(__name__)

INTAKE_DRAFT_KEYS = (
    "client_name",
    "industry",
    "target_audience",
    "unique_advantage",
    "ip_requirements",
    "style_preference",
    "business_goal",
    "publishing_rhythm",
    "time_windows",
    "goal_target",
    "iteration_rule",
)
INTAKE_REQUIRED_KEYS = ("client_name", "industry", "target_audience", "ip_requirements")
INTAKE_FIELD_LABELS = {
    "client_name": "客户/品牌名称",
    "industry": "行业垂类",
    "target_audience": "目标受众画像",
    "ip_requirements": "账号定位与内容支柱",
}
INDUSTRY_KEYWORDS = {
    "美妆个护": ("美妆", "护肤", "化妆", "彩妆", "护发"),
    "餐饮美食": ("美食", "餐饮", "探店", "小吃", "咖啡", "烘焙"),
    "健身健康": ("健身", "减脂", "增肌", "养生", "瑜伽", "跑步"),
    "本地生活": ("同城", "本地", "门店", "团购", "生活服务"),
    "娱乐休闲": ("ktv", "k歌", "唱歌", "自助ktv", "自助k歌", "电玩城", "娱乐"),
    "教育知识": ("教育", "学习", "考研", "英语", "知识", "课程"),
    "电商带货": ("电商", "带货", "选品", "直播", "转化", "成交"),
    "家居家装": ("家居", "装修", "收纳", "软装"),
    "母婴亲子": ("母婴", "育儿", "亲子", "宝妈"),
}

INDUSTRY_AUDIENCE_DEFAULT = {
    "美妆个护": "20-35岁女性，关注护肤效率、妆容质感与高性价比产品选择。",
    "餐饮美食": "18-35岁城市用户，关注真实口味、价格透明和可复购餐饮选择。",
    "健身健康": "22-40岁上班族，关注减脂效率、时间友好和可持续健康习惯。",
    "本地生活": "18-40岁本地用户，关注同城优惠、实用服务与避坑信息。",
    "娱乐休闲": "18-35岁年轻用户，关注解压放松、朋友社交与高性价比娱乐体验。",
    "教育知识": "18-35岁学生与职场人，关注可落地的学习方法和提效路径。",
    "电商带货": "20-40岁有消费决策需求的用户，关注选购建议、真实测评和优惠信息。",
    "家居家装": "25-45岁家庭用户，关注实用收纳、装修避坑和预算优化。",
    "母婴亲子": "23-38岁新手父母，关注育儿效率、情绪支持和实操型经验。",
    "泛生活": "18-35岁泛兴趣用户，关注真实经验、实用建议和情绪价值内容。",
}

INDUSTRY_ADVANTAGE_DEFAULT = {
    "娱乐休闲": [
        "低门槛随时可玩，不用组局也能快速开唱",
        "高性价比，适合学生党和年轻人高频复购",
        "私密空间更友好，社恐和独处场景也成立",
    ],
    "餐饮美食": [
        "真实测评+价格透明，帮助用户快速做决策",
        "场景化推荐，覆盖工作餐/聚会/约会等真实需求",
        "高频更新本地新店与回头店，形成持续参考价值",
    ],
    "健身健康": [
        "低门槛动作方案，普通人也能坚持执行",
        "碎片时间友好，兼顾效率和可持续性",
        "持续复盘体感和数据，降低试错成本",
    ],
    "美妆个护": [
        "以成分和肤质场景做决策，不只讲感受",
        "高性价比和避坑导向，提升信任感",
        "对比测评和实拍反馈，内容可复用性高",
    ],
}

INDUSTRY_PILLARS_DEFAULT = {
    "娱乐休闲": [
        "场景种草：约会、聚会、下班解压、周末打卡",
        "情绪共鸣：社恐友好、情绪释放、深夜放松",
        "门店体验：环境、音质、曲库、收费、流程透明",
        "活动转化：新客福利、双人套餐、节日主题活动",
    ],
    "餐饮美食": [
        "场景推荐：工作餐、约会餐、聚会餐",
        "真实测评：口味、价格、份量、服务",
        "避坑清单：踩雷点与替代方案",
        "福利转化：套餐、团购、限时活动",
    ],
    "健身健康": [
        "痛点拆解：减脂焦虑、坚持困难、时间不足",
        "实操方案：10-20分钟训练与饮食策略",
        "跟练打卡：周计划+阶段复盘",
        "案例转化：真实前后变化与咨询引导",
    ],
}

INDUSTRY_TOPIC_TITLES = {
    "娱乐休闲": [
        "一个人想唱歌又不想社交，来这就够了",
        "情侣约会第二场，为什么越来越多人选自助KTV",
        "下班压力大，30分钟快速放空的方式",
        "学生党预算有限，也能实现唱歌自由",
        "商场里最容易被忽略的快乐角落",
        "社恐友好型娱乐空间到底是什么体验",
        "吃完饭不知道去哪？这套续摊方案直接抄",
        "同样是唱歌，自助KTV和传统KTV差在哪",
        "第一次来不会操作？从进门到点歌全流程",
        "本周福利怎么用最划算，一条视频讲清楚",
    ],
}

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
    return re.sub(r"\s+", "", _safe_text(value))


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


def _collect_calendar_quality_flags(item: dict) -> list[str]:
    title = _normalize_topic_text(item.get("title_direction"))
    key_message = _normalize_topic_text(item.get("key_message"))
    replacement_hint = _normalize_topic_text(item.get("replacement_hint"))
    text = " ".join(filter(None, [title, key_message, replacement_hint]))

    flags: list[str] = []

    if _contains_any(text, SELF_INDULGENT_PHRASES) or (_contains_any(text, POETIC_PHRASES) and not _contains_any(text, USER_OBJECT_MARKERS)):
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
    content_type = _normalize_content_type(raw.get("content_type"))
    return {
        "title_direction": _safe_text(raw.get("title_direction")) or f"备用题 {fallback_index}",
        "content_type": content_type,
        "content_pillar": _safe_text(raw.get("content_pillar")) or None,
        "key_message": _safe_text(raw.get("key_message")),
        "tags": _normalize_text_list(raw.get("tags"), limit=6),
        "batch_shoot_group": _safe_text(raw.get("batch_shoot_group")) or _derive_batch_group(content_type),
        "replacement_hint": _safe_text(raw.get("replacement_hint")),
    }


def _normalize_backup_topic_pool(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items: list[dict] = []
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            continue
        items.append(_normalize_backup_topic_pool_item(raw, fallback_index=index))
    return items


def _normalize_calendar_generation_meta(value) -> dict:
    raw = value if isinstance(value, dict) else {}
    return {
        "blocked_count": max(0, int(raw.get("blocked_count", 0) or 0)),
        "backup_used_count": max(0, int(raw.get("backup_used_count", 0) or 0)),
        "regeneration_count": max(0, int(raw.get("regeneration_count", 0) or 0)),
    }


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
    quality_flags = _collect_calendar_quality_flags(candidate)
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
        "batch_shoot_group": backup_item.get("batch_shoot_group") or target_item.get("batch_shoot_group"),
        "replacement_hint": backup_item.get("replacement_hint") or target_item.get("replacement_hint"),
        "replaced_from_backup": True,
        "quality_flags": [],
    }
    if "replacement_source_index" not in merged:
        merged["replacement_source_index"] = None
    return _normalize_content_calendar_item(merged, day_fallback=target_item.get("day", 1))


def _pick_backup_replacement(
    target_item: dict,
    backup_pool: list[dict],
    kept_items: list[dict],
) -> tuple[dict | None, int | None]:
    ranked: list[tuple[int, int, dict]] = []
    for index, candidate in enumerate(backup_pool):
        if len(_collect_calendar_quality_flags(candidate)) >= LOW_QUALITY_THRESHOLD:
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
        normalized = _normalize_content_calendar_item({**item, "day": day}, day_fallback=day)
        finalized.append(normalized)
    return finalized


async def _apply_calendar_quality_guardrails(
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
    meta = _normalize_calendar_generation_meta({})
    quality_notes_parts: list[str] = []

    for raw_item in raw_calendar[:30]:
        item = _normalize_content_calendar_item(raw_item, day_fallback=len(kept_items) + 1)
        quality_flags = _collect_calendar_quality_flags(item)
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
        normalized_replacement["quality_flags"] = _collect_calendar_quality_flags(normalized_replacement)
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
            blocked_topics=blocked_items[-10:],
            missing_days=missing_days,
            run_context={"entity_type": "planning_project", "entity_id": project_id},
            db=db,
        )
        if isinstance(gap_fill_result, dict) and gap_fill_result.get("error"):
            raise ValueError(gap_fill_result["error"])
        refill_pool = _normalize_backup_topic_pool(gap_fill_result.get("items", []) if isinstance(gap_fill_result, dict) else [])
        meta["regeneration_count"] += 1
        available_backup_pool.extend(refill_pool)

        while len(kept_items) < 30:
            target_day = len(kept_items) + 1
            placeholder = _normalize_content_calendar_item({"day": target_day}, day_fallback=target_day)
            replacement, replacement_index = _pick_backup_replacement(placeholder, available_backup_pool, kept_items)
            if replacement is None:
                break
            chosen_replacement = available_backup_pool.pop(replacement_index)
            normalized_replacement = _convert_backup_topic_to_calendar_item(
                {**chosen_replacement, "replacement_source_index": replacement_index},
                placeholder,
            )
            normalized_replacement["replacement_source_index"] = replacement_index
            normalized_replacement["quality_flags"] = _collect_calendar_quality_flags(normalized_replacement)
            kept_items.append(normalized_replacement)
            meta["backup_used_count"] += 1

    finalized_items = _finalize_calendar_days(kept_items)
    if len(finalized_items) != 30:
        raise ValueError(f"内容日历质控补位后仍不足 30 条，当前仅 {len(finalized_items)} 条")

    p0_count = sum(1 for item in finalized_items[:10] if item.get("is_main_validation"))
    if p0_count < min(10, len(finalized_items[:10])):
        raise ValueError("内容日历质控后前10条主验证题数量不足")
    if any(not _safe_text(item.get("batch_shoot_group")) for item in finalized_items):
        raise ValueError("内容日历存在缺失拍摄分组的条目")

    if meta["blocked_count"] > 0:
        quality_notes_parts.append(f"已拦截 {meta['blocked_count']} 条低传播选题")
    if meta["backup_used_count"] > 0:
        quality_notes_parts.append(f"已使用 {meta['backup_used_count']} 条备用题补位")
    if meta["regeneration_count"] > 0:
        quality_notes_parts.append("已触发小范围补写兜底")

    return finalized_items, available_backup_pool, meta, "；".join(quality_notes_parts)


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_content_type(value: str | None) -> str:
    """统一内容类型，避免出现高表演门槛标签。"""
    raw = _safe_text(value)
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


def _normalize_calendar_priority(value) -> str:
    text = _safe_text(value)
    if text.startswith("P0"):
        return "P0-主验证"
    if text.startswith("P2"):
        return "P2-补充储备"
    if text.startswith("P1"):
        return "P1-稳定输出"
    return "P1-稳定输出"


def _normalize_calendar_role(value) -> str:
    text = _safe_text(value)
    allowed = {"主验证", "稳定输出", "流量放大", "信任建立", "承接转化", "补充试错"}
    return text if text in allowed else "稳定输出"


def _derive_batch_group(content_type: str) -> str:
    text = _normalize_content_type(content_type)
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


def _derive_batch_shootable(content_type: str) -> bool:
    text = _normalize_content_type(content_type)
    return any(keyword in text for keyword in ("口播", "画中画", "教程", "测评"))


def _normalize_content_calendar_item(raw: dict, *, day_fallback: int) -> dict:
    day = raw.get("day") if isinstance(raw.get("day"), int) else day_fallback
    content_type = _normalize_content_type(raw.get("content_type"))
    priority = _normalize_calendar_priority(raw.get("priority"))
    is_main_validation_raw = raw.get("is_main_validation")
    is_main_validation = (
        bool(is_main_validation_raw)
        if isinstance(is_main_validation_raw, bool)
        else priority == "P0-主验证" or day <= 10
    )
    is_batch_shootable_raw = raw.get("is_batch_shootable")
    is_batch_shootable = (
        bool(is_batch_shootable_raw)
        if isinstance(is_batch_shootable_raw, bool)
        else _derive_batch_shootable(content_type)
    )
    batch_group = _safe_text(raw.get("batch_shoot_group")) or _derive_batch_group(content_type)

    return {
        "day": day,
        "title_direction": _safe_text(raw.get("title_direction")) or f"Day {day} 内容方向",
        "content_type": content_type,
        "content_pillar": _safe_text(raw.get("content_pillar")) or None,
        "key_message": _safe_text(raw.get("key_message")),
        "tags": _normalize_text_list(raw.get("tags"), limit=6),
        "priority": "P0-主验证" if is_main_validation else priority,
        "content_role": _normalize_calendar_role(raw.get("content_role")),
        "is_main_validation": is_main_validation,
        "is_batch_shootable": is_batch_shootable,
        "batch_shoot_group": batch_group if is_batch_shootable else (batch_group or "混合拍摄"),
        "replacement_hint": _safe_text(raw.get("replacement_hint")),
        "replaced_from_backup": bool(raw.get("replaced_from_backup", False)),
        "replacement_source_index": raw.get("replacement_source_index"),
        "quality_flags": _normalize_text_list(raw.get("quality_flags"), limit=8),
    }


def _normalize_content_calendar(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    items: list[dict] = []
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, dict):
            continue
        items.append(_normalize_content_calendar_item(raw, day_fallback=index))
    return items


def _has_meaningful_plan_result(account_positioning: dict | None, content_strategy: dict | None, content_calendar: list | None) -> bool:
    positioning = account_positioning if isinstance(account_positioning, dict) else {}
    strategy = content_strategy if isinstance(content_strategy, dict) else {}
    calendar = content_calendar if isinstance(content_calendar, list) else []
    has_positioning = any(bool(_safe_text(value)) for value in positioning.values())
    has_strategy = any(bool(_safe_text(value)) for value in strategy.values())
    return has_positioning or has_strategy or bool(calendar)


def _normalize_draft(raw: dict) -> dict[str, str]:
    return {key: _safe_text(raw.get(key)) for key in INTAKE_DRAFT_KEYS}


def _detect_industry(user_message: str) -> str:
    text = user_message.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return industry
    return "泛生活"


def _build_default_ip_requirements(industry: str) -> str:
    return (
        f"定位：{industry}实用派账号，强调真实经验与可执行建议。\n"
        "内容支柱：1) 场景痛点拆解 2) 实操解决方案 3) 对比评测与复盘。"
    )


def _build_default_client_name(industry: str, user_message: str) -> str:
    compact = re.sub(r"\s+", "", user_message)[:10]
    if compact:
        return f"{compact}账号"
    return f"{industry}策划账号"


def _auto_fill_intake_draft(draft: dict[str, str], user_message: str) -> list[str]:
    inferred_fields: list[str] = []
    industry = draft.get("industry") or _detect_industry(user_message)
    if not draft.get("industry"):
        draft["industry"] = industry
        inferred_fields.append("industry")

    if not draft.get("client_name"):
        draft["client_name"] = _build_default_client_name(industry, user_message)
        inferred_fields.append("client_name")

    if not draft.get("target_audience"):
        draft["target_audience"] = INDUSTRY_AUDIENCE_DEFAULT.get(industry, INDUSTRY_AUDIENCE_DEFAULT["泛生活"])
        inferred_fields.append("target_audience")

    if not draft.get("ip_requirements"):
        draft["ip_requirements"] = _build_default_ip_requirements(industry)
        inferred_fields.append("ip_requirements")

    if not draft.get("publishing_rhythm"):
        draft["publishing_rhythm"] = "每月10条（推荐，3天1条）"
        inferred_fields.append("publishing_rhythm")
    if not draft.get("time_windows"):
        draft["time_windows"] = "19:00、21:00"
        inferred_fields.append("time_windows")
    if not draft.get("goal_target"):
        draft["goal_target"] = "30天发布10条，至少跑出1-2条高潜内容"
        inferred_fields.append("goal_target")
    if not draft.get("iteration_rule"):
        draft["iteration_rule"] = "每周复盘1次，每次只调整1-2个变量（开头/标题/结构）"
        inferred_fields.append("iteration_rule")

    return inferred_fields


def _build_execution_preview(draft: dict[str, str]) -> str:
    """按“一句话即可执行”的风格输出可执行策划初稿。"""
    industry = draft.get("industry") or "泛生活"
    client_name = draft.get("client_name") or f"{industry}账号"
    target_audience = draft.get("target_audience") or INDUSTRY_AUDIENCE_DEFAULT.get(industry, INDUSTRY_AUDIENCE_DEFAULT["泛生活"])
    ip_requirements = draft.get("ip_requirements") or _build_default_ip_requirements(industry)
    business_goal = draft.get("business_goal") or "先完成30天稳定更新，跑出1-2条高潜内容并沉淀可复用模板。"
    rhythm = draft.get("publishing_rhythm") or "每月10条（推荐，3天1条）"
    time_windows = draft.get("time_windows") or "19:00、21:00"
    goal_target = draft.get("goal_target") or "30天发布10条，至少跑出1-2条高潜内容"
    iteration_rule = draft.get("iteration_rule") or "每周复盘1次，每次只调整1-2个变量（开头/标题/结构）"

    advantages = INDUSTRY_ADVANTAGE_DEFAULT.get(
        industry,
        [
            "低门槛、可持续执行，降低起号试错成本",
            "内容围绕真实场景，用户容易共鸣和转化",
            "结构化内容支柱明确，便于批量产出与复盘",
        ],
    )
    pillars = INDUSTRY_PILLARS_DEFAULT.get(
        industry,
        [
            "场景痛点：把用户真实问题讲清楚",
            "方法方案：提供可执行动作和流程",
            "对比复盘：展示选择逻辑与优化路径",
            "转化内容：结合活动/服务做行动引导",
        ],
    )
    topic_titles = INDUSTRY_TOPIC_TITLES.get(
        industry,
        [
            "这个场景下，为什么大多数人都会做错选择",
            "预算有限时，最值得优先做的3件事",
            "第一次尝试如何避免踩坑",
            "一周内可执行的基础版本方案",
            "同类选择对比：怎么选更稳",
            "真实案例复盘：从低效到高效的关键动作",
            "常见误区盘点：越努力越无效的点",
            "30天起号执行清单（可直接照做）",
            "新手最容易忽略但影响最大的细节",
            "本周行动建议：只改1个变量看结果",
        ],
    )

    advantages_text = "\n".join([f"- {item}" for item in advantages[:3]])
    pillars_text = "\n".join([f"- {item}" for item in pillars[:4]])
    topics_text = "\n".join([f"{idx + 1}. {title}" for idx, title in enumerate(topic_titles[:10])])

    return (
        f"## 可执行策划初稿（{client_name}）\n\n"
        "### 1) 目标受众\n"
        f"- {target_audience}\n\n"
        "### 2) 独特优势/亮点\n"
        f"{advantages_text}\n\n"
        "### 3) 账号定位与内容支柱\n"
        f"- 定位：{ip_requirements}\n"
        f"{pillars_text}\n\n"
        "### 4) 30天执行节奏\n"
        f"- 发布节奏：{rhythm}\n"
        f"- 发布时间窗口：{time_windows}\n"
        f"- 阶段目标：{goal_target}\n"
        f"- 迭代规则：{iteration_rule}\n"
        f"- 商业目标：{business_goal}\n\n"
        "### 5) 首批10条可拍选题\n"
        f"{topics_text}\n\n"
        "如果你愿意，我可以下一步直接把这份初稿转成“30天日历+每条脚本骨架”。"
    )


def _normalize_text_list(value, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_safe_text(item) for item in value]
    return [item for item in items if item][:limit]


def _normalize_performance_recap(raw: dict) -> dict:
    overall_summary = _safe_text(
        raw.get("overall_summary")
        or raw.get("raw_analysis")
        or raw.get("error")
        or "AI 暂未生成结构化复盘，请稍后重试。"
    )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "overall_summary": overall_summary,
        "winning_patterns": _normalize_text_list(raw.get("winning_patterns"), limit=5),
        "optimization_focus": _normalize_text_list(raw.get("optimization_focus"), limit=5),
        "risk_alerts": _normalize_text_list(raw.get("risk_alerts"), limit=4),
        "next_actions": _normalize_text_list(raw.get("next_actions"), limit=5),
        "next_topic_angles": _normalize_text_list(raw.get("next_topic_angles"), limit=5),
    }


def _serialize_performance_rows(project, rows: list) -> list[dict]:
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


def _serialize_existing_content_items(project) -> list[dict]:
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


def _normalize_next_topic_batch(raw: dict) -> dict:
    overall_strategy = _safe_text(
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
            title_direction = _safe_text(item.get("title_direction"))
            if not title_direction:
                continue
            items.append(
                {
                    "title_direction": title_direction,
                    "content_type": _normalize_content_type(item.get("content_type")),
                    "content_pillar": _safe_text(item.get("content_pillar")) or None,
                    "hook_hint": _safe_text(item.get("hook_hint")) or None,
                    "why_this_angle": _safe_text(item.get("why_this_angle")) or None,
                    "imported_content_item_id": _safe_text(item.get("imported_content_item_id")) or None,
                    "imported_day_number": item.get("imported_day_number") if isinstance(item.get("imported_day_number"), int) else None,
                    "imported_at": (
                        item.get("imported_at").isoformat()
                        if isinstance(item.get("imported_at"), datetime)
                        else (_safe_text(item.get("imported_at")) or None)
                    ),
                }
            )
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "overall_strategy": overall_strategy,
        "items": items[:10],
    }


@router.post("/intake-assistant", response_model=PlanningIntakeAssistantResponse, summary="互动问诊助手")
async def planning_intake_assistant(
    request: PlanningIntakeAssistantRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """账号策划创建前的互动问诊：提取结构化草稿并返回下一步追问。"""
    user_message = _safe_text(request.user_message)
    if not user_message:
        raise HTTPException(status_code=400, detail="请输入本次补充信息")

    current_draft = _normalize_draft(request.draft.model_dump())
    history_payload = [msg.model_dump() for msg in request.chat_history][-20:]
    ai_result = await ai_analysis_service.generate_planning_intake_guidance(
        user_message=user_message,
        draft=current_draft,
        chat_history=history_payload,
        auto_complete=request.auto_complete,
        mode=request.mode,
        run_context={"entity_type": "planning_intake", "entity_id": current_user.id},
        db=db,
    )

    ai_updated = ai_result.get("updated_draft", {}) if isinstance(ai_result, dict) else {}
    merged_draft = dict(current_draft)
    if isinstance(ai_updated, dict):
        for key in INTAKE_DRAFT_KEYS:
            candidate = _safe_text(ai_updated.get(key))
            if candidate:
                merged_draft[key] = candidate

    inferred_fields: list[str] = []
    raw_inferred = ai_result.get("inferred_fields", []) if isinstance(ai_result, dict) else []
    if isinstance(raw_inferred, list):
        for item in raw_inferred:
            key = _safe_text(item)
            if key in INTAKE_DRAFT_KEYS and key not in inferred_fields:
                inferred_fields.append(key)

    if request.auto_complete or request.mode == "fast":
        for key in _auto_fill_intake_draft(merged_draft, user_message):
            if key not in inferred_fields:
                inferred_fields.append(key)

    required_missing = [key for key in INTAKE_REQUIRED_KEYS if not merged_draft.get(key)]
    reported_missing = []
    raw_missing = ai_result.get("missing_fields", []) if isinstance(ai_result, dict) else []
    if isinstance(raw_missing, list):
        for item in raw_missing:
            key = _safe_text(item)
            if key in INTAKE_DRAFT_KEYS and key not in reported_missing:
                reported_missing.append(key)
    for key in required_missing:
        if key not in reported_missing:
            reported_missing.append(key)

    ready_for_reference = len(required_missing) == 0
    assistant_reply = _safe_text(ai_result.get("assistant_reply", "") if isinstance(ai_result, dict) else "")
    if not assistant_reply:
        if ready_for_reference:
            assistant_reply = "关键信息我已经整理好了，建议先确认无误，再进入“参考博主”步骤。"
        else:
            next_field = required_missing[0]
            assistant_reply = f"还差「{INTAKE_FIELD_LABELS.get(next_field, next_field)}」，你先补充这一项。"
    elif (request.auto_complete or request.mode == "fast") and inferred_fields:
        assistant_reply = (
            f"{assistant_reply}\n\n我已基于你的描述自动补齐可执行草稿，"
            f"其中推断字段：{', '.join(inferred_fields[:6])}。你可以直接生成，也可先微调。"
        )

    if request.mode == "fast":
        assistant_reply = _build_execution_preview(merged_draft)
        if inferred_fields:
            assistant_reply += (
                "\n\n推断字段："
                + "、".join(inferred_fields[:8])
                + "。如与你实际不一致，直接改字段后再生成即可。"
            )

    confirmation_summary = _safe_text(ai_result.get("confirmation_summary", "") if isinstance(ai_result, dict) else "")
    suggested_questions = []
    raw_questions = ai_result.get("suggested_questions", []) if isinstance(ai_result, dict) else []
    if isinstance(raw_questions, list):
        for q in raw_questions[:3]:
            text = _safe_text(q)
            if text:
                suggested_questions.append(text)

    return {
        "assistant_reply": assistant_reply,
        "draft": merged_draft,
        "missing_fields": reported_missing,
        "inferred_fields": inferred_fields,
        "ready_for_reference": ready_for_reference,
        "ready_for_generate": ready_for_reference,
        "confirmation_summary": confirmation_summary or None,
        "suggested_questions": suggested_questions,
    }


@router.post("", response_model=PlanningListResponse, summary="创建策划项目")
async def create_planning(
    request: PlanningCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    创建账号策划项目：
    1. 保存项目基本信息
    2. 后台异步生成账号定位和30天内容日历
    """
    # 如果填了主页地址，先抓取账号信息
    account_info = {}
    if request.account_homepage_url:
        user_info = await crawler_service.parse_user_url(request.account_homepage_url)
        if user_info:
            account_info = {
                "account_homepage_url": request.account_homepage_url,
                "account_nickname": user_info.get("nickname"),
                "account_avatar_url": user_info.get("avatar_url"),
                "account_signature": user_info.get("signature"),
                "account_follower_count": user_info.get("follower_count"),
                "account_video_count": user_info.get("video_count"),
            }
        else:
            account_info = {"account_homepage_url": request.account_homepage_url}

    # 保存项目
    project = await planning_repository.create(db, {
        "client_name": request.client_name,
        "industry": request.industry,
        "target_audience": request.target_audience,
        "unique_advantage": request.unique_advantage,
        "ip_requirements": request.ip_requirements,
        "style_preference": request.style_preference,
        "business_goal": request.business_goal,
        "reference_blogger_ids": request.reference_blogger_ids,
        "status": "in_progress",
        **account_info,
    })
    await operation_log_repo.create(
        db,
        action="planning.create",
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail="创建账号策划项目",
        extra={
            "client_name": request.client_name,
            "industry": request.industry,
            "reference_count": len(request.reference_blogger_ids or []),
        },
    )
    await db.commit()

    task_key = f"planning:{project.id}:generate"
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_generate",
        title=f"生成策划：{getattr(project, 'client_name', request.client_name)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="任务已提交，等待执行",
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_generate",
            project.id,
            request.model_dump(),
            request.reference_blogger_ids,
            task_key,
            "draft",
            job_id=task_key,
            description=f"planning generate {project.id}",
        )
    except RuntimeError as exc:
        project.status = "draft"
        await operation_log_repo.create(
            db,
            action="planning.enqueue_failed",
            entity_type="planning_project",
            entity_id=project.id,
            actor=current_user.username,
            detail="策划任务入队失败，状态已回退为草稿",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="策划任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return project


@router.get("", response_model=list[PlanningListResponse] | PlanningPagedResponse, summary="获取所有策划项目")
async def list_projects(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int | None = Query(None, ge=1, le=200, description="返回条数上限（不传则返回全部）"),
    keyword: str | None = Query(None, description="关键词：匹配客户名/行业/受众/账号昵称"),
    status: str | None = Query(None, description="状态筛选：draft/in_progress/completed"),
    with_meta: bool = Query(False, description="是否返回分页元信息（total/has_more）"),
    db: AsyncSession = Depends(get_db),
):
    """获取策划项目列表（支持分页）"""
    normalized_keyword = (keyword or "").strip() or None
    normalized_status = (status or "").strip() or None
    items = await planning_repository.list_all(
        db,
        skip=skip,
        limit=limit,
        keyword=normalized_keyword,
        status=normalized_status,
    )
    if not with_meta:
        return items

    total = await planning_repository.count_all(
        db,
        keyword=normalized_keyword,
        status=normalized_status,
    )
    effective_limit = limit if limit is not None else len(items)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": effective_limit,
        "has_more": skip + len(items) < total,
    }


@router.get("/{project_id}", response_model=PlanningResponse, summary="获取策划详情")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """获取策划项目详情（含账号定位、内容日历）"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.post("/{project_id}/retry", summary="重新生成失败的策划(草稿)")
async def retry_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """重新开始被网络中断变为草稿状态的项目"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if project.status == "in_progress":
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")
    previous_status = project.status

    # 标记为进行中。内容清理由后台任务落库前统一处理，避免入队失败导致数据丢失。
    project.status = "in_progress"

    from app.services.cancellation import cancellation_registry
    cancellation_registry.clear(project_id)
    await db.commit()

    # 提取重构参数
    client_data = {
        "client_name": project.client_name,
        "industry": project.industry,
        "target_audience": project.target_audience,
        "unique_advantage": project.unique_advantage,
        "ip_requirements": project.ip_requirements,
        "style_preference": project.style_preference,
        "business_goal": project.business_goal,
        "reference_blogger_ids": project.reference_blogger_ids or []
    }

    task_key = f"planning:{project.id}:retry"
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_generate",
        title=f"重新生成策划：{getattr(project, 'client_name', project_id)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="重试任务已提交",
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_generate",
            project.id,
            client_data,
            project.reference_blogger_ids or [],
            task_key,
            previous_status,
            job_id=task_key,
            description=f"planning retry {project.id}",
        )
    except RuntimeError as exc:
        project = await planning_repository.get_by_id(db, project_id)
        if project:
            project.status = previous_status
        await operation_log_repo.create(
            db,
            action="planning.enqueue_failed",
            entity_type="planning_project",
            entity_id=project_id,
            actor=current_user.username,
            detail="策划重试任务入队失败，状态已回退",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="策划重试任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await operation_log_repo.create(
        db,
        action="planning.retry",
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail="重新生成策划项目",
        extra={"status": "in_progress"},
    )

    return {"message": "已开始重新生成", "status": "in_progress"}


@router.patch("/{project_id}", response_model=PlanningResponse, summary="编辑策划项目基本信息")
async def update_project(
    project_id: str,
    request: PlanningUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """部分更新策划项目的客户信息和IP需求字段"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = request.model_dump(exclude_none=True)
    project = await planning_repository.update_project_info(db, project_id, data)
    await operation_log_repo.create(
        db,
        action="planning.update",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="更新策划项目信息",
        extra={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/regenerate-calendar", summary="单独重新生成内容日历")
async def regenerate_calendar(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """基于当前账号定位，单独重新生成 30 天内容日历"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status == "in_progress":
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法单独生成日历")
    previous_status = project.status

    # 仅更新状态，避免入队失败时丢失已有结果。
    project.status = "in_progress"

    from app.services.cancellation import cancellation_registry
    cancellation_registry.clear(project_id)
    await db.commit()

    # 提取重构参数
    client_data = {
        "client_name": project.client_name,
        "industry": project.industry,
        "target_audience": project.target_audience,
        "unique_advantage": project.unique_advantage,
        "ip_requirements": project.ip_requirements,
        "style_preference": project.style_preference,
        "business_goal": project.business_goal,
    }

    task_key = f"planning:{project.id}:calendar"
    has_performance_recap = bool(
        isinstance(project.account_plan, dict) and isinstance(project.account_plan.get("performance_recap"), dict)
    )
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_calendar",
        title=f"重生成日历：{getattr(project, 'client_name', project_id)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="日历重生成任务已提交，AI 将结合最新复盘建议优化选题" if has_performance_recap else "日历重生成任务已提交",
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_calendar_generate",
            project.id,
            client_data,
            project.account_plan,
            task_key,
            job_id=task_key,
            description=f"planning calendar {project.id}",
        )
    except RuntimeError as exc:
        project = await planning_repository.get_by_id(db, project_id)
        if project:
            project.status = previous_status
        await operation_log_repo.create(
            db,
            action="planning.enqueue_failed",
            entity_type="planning_project",
            entity_id=project_id,
            actor=current_user.username,
            detail="日历重生成任务入队失败，状态已回退",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="日历重生成任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await operation_log_repo.create(
        db,
        action="planning.regenerate_calendar",
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail="重新生成30天内容日历",
        extra={"status": "in_progress", "has_performance_recap": has_performance_recap},
    )

    return {"message": "已开始重新生成内容日历", "status": "in_progress"}


@router.delete("/{project_id}", summary="删除策划项目")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """删除策划项目（同时取消进行中的后台生成任务）"""
    cancellation_registry.cancel(project_id)
    deleted = await planning_repository.delete(db, project_id)
    if not deleted:
        cancellation_registry.clear(project_id)
        raise HTTPException(status_code=404, detail="项目不存在")
    await operation_log_repo.create(
        db,
        action="planning.delete",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="删除策划项目",
    )
    return {"message": "删除成功"}


@router.patch("/{project_id}/homepage", response_model=PlanningListResponse, summary="补填/更新账号主页地址")
async def update_account_homepage(
    project_id: str,
    request: AccountHomepageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    为策划项目补填或更新账号主页地址，自动抓取头像、昵称、简介。
    创建时未填写的可在此补上。
    """
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    user_info = await crawler_service.parse_user_url(request.account_homepage_url)
    project.account_homepage_url = request.account_homepage_url
    if user_info:
        project.account_nickname = user_info.get("nickname")
        project.account_avatar_url = user_info.get("avatar_url")
        project.account_signature = user_info.get("signature")
        project.account_follower_count = user_info.get("follower_count")
        project.account_video_count = user_info.get("video_count")
    await operation_log_repo.create(
        db,
        action="planning.update_homepage",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="更新策划账号主页信息",
        extra={"account_homepage_url": request.account_homepage_url},
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/script/generate", summary="为单条内容生成完整脚本")
async def generate_script(
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """
    为内容日历中的某一条生成完整视频脚本
    （含分镜、台词、拍摄建议、发布文案）
    """
    # 获取内容条目
    item = await planning_repository.get_content_item(db, request.content_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="内容条目不存在")

    # 获取所属项目
    project = await planning_repository.get_by_id(db, item.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    task_key = f"planning:content-item:{item.id}:script-generate"
    existing_task = await task_center_repo.get_by_task_key(db, task_key)
    if existing_task and existing_task.status in (TaskStatus.QUEUED.value, TaskStatus.RUNNING.value):
        # 兜底处理异常中断导致的僵尸任务（超过30分钟视为超时失败）
        started_at = existing_task.started_at or existing_task.updated_at
        if started_at and (datetime.utcnow() - started_at) > timedelta(minutes=30):
            await task_center_repo.update_status(
                db,
                task_key,
                status=TaskStatus.FAILED.value,
                progress_step="timeout",
                message="脚本生成任务超时，已自动标记失败，可重新发起",
                error_message="task_timeout",
            )
            await db.commit()
        else:
            raise HTTPException(status_code=409, detail="该条内容脚本正在生成中，请稍后刷新查看")

    try:
        await task_center_repo.upsert_task(
            db,
            task_key=task_key,
            task_type="planning_script_generate",
            title=f"生成脚本：Day {item.day_number}",
            entity_type="content_item",
            entity_id=item.id,
            status=TaskStatus.RUNNING.value,
            progress_step="generating",
            message="AI 正在生成脚本",
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="该条内容脚本正在生成中，请稍后刷新查看")

    # 获取参考博主信息（使用项目的+额外指定的）
    blogger_ids = list(set(
        (project.reference_blogger_ids or []) +
        (request.reference_blogger_ids or [])
    ))

    reference_bloggers = []
    for bid in blogger_ids[:3]:  # 最多取3个参考博主
        blogger = await blogger_repository.get_by_id(db, bid)
        if blogger and blogger.analysis_report:
            reference_bloggers.append({
                "nickname": blogger.nickname,
                "analysis_report": blogger.analysis_report
            })

    try:
        # 生成脚本
        script = await ai_analysis_service.generate_video_script(
            content_item={
                "title_direction": item.title_direction,
                "content_type": item.content_type,
                "key_message": item.tags,
            },
            account_plan=project.account_plan or {},
            reference_bloggers=reference_bloggers,
            run_context={"entity_type": "content_item", "entity_id": item.id},
            db=db,
        )

        if script.get("error"):
            await task_center_repo.update_status(
                db,
                task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="脚本生成失败",
                error_message=str(script.get("error", "unknown_error")),
            )
            await db.commit()
            raise HTTPException(status_code=500, detail=f"脚本生成失败: {script['error']}")

        # 保存脚本
        await planning_repository.update_script(db, item.id, script)
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.COMPLETED.value,
            progress_step="completed",
            message="脚本生成完成",
            error_message=None,
        )
        await operation_log_repo.create(
            db,
            action="planning.generate_script",
            entity_type="content_item",
            entity_id=item.id,
            actor=current_user.username,
            detail="为内容条目生成完整脚本",
            extra={"project_id": item.project_id},
        )
        await db.commit()

        return {
            "status": "success",
            "content_item_id": item.id,
            "script": script
        }
    except HTTPException:
        raise
    except Exception as exc:
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="failed",
            message="脚本生成异常终止",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=500, detail="脚本生成异常，请稍后重试") from exc


@router.patch("/content-items/{item_id}", response_model=ContentItemResponse, summary="更新内容条目")
async def update_content_item(
    item_id: str,
    request: ContentItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """部分更新内容条目（标题方向、内容类型、标签、脚本）"""
    data = request.model_dump(exclude_none=True)
    if "content_type" in data:
        data["content_type"] = _normalize_content_type(data.get("content_type"))
    item = await planning_repository.update_content_item(db, item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="内容条目不存在")
    await operation_log_repo.create(
        db,
        action="planning.update_content_item",
        entity_type="content_item",
        entity_id=item_id,
        actor=current_user.username,
        detail="更新内容条目",
        extra={"fields": list(data.keys())},
    )
    await db.commit()
    return item


@router.get("/{project_id}/performance", response_model=list[ContentPerformanceResponse], summary="获取发布回流数据")
async def list_project_performance(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return await performance_repo.list_by_project(db, project_id)


@router.post("/{project_id}/performance", response_model=ContentPerformanceResponse, summary="新增发布回流记录")
async def create_project_performance(
    project_id: str,
    request: ContentPerformanceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    record = await performance_repo.create(
        db,
        {
            "project_id": project_id,
            **request.model_dump(),
        },
    )
    await operation_log_repo.create(
        db,
        action="planning.performance.create",
        entity_type="content_performance",
        entity_id=record.id,
        actor=current_user.username,
        detail="新增发布回流记录",
        extra={"project_id": project_id},
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.patch("/{project_id}/performance/{performance_id}", response_model=ContentPerformanceResponse, summary="更新发布回流记录")
async def update_project_performance(
    project_id: str,
    performance_id: str,
    request: ContentPerformanceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = request.model_dump(exclude_none=True)
    record = await performance_repo.update(db, performance_id, data)
    if not record or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="回流记录不存在")
    await operation_log_repo.create(
        db,
        action="planning.performance.update",
        entity_type="content_performance",
        entity_id=record.id,
        actor=current_user.username,
        detail="更新发布回流记录",
        extra={"project_id": project_id, "fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{project_id}/performance/{performance_id}", summary="删除发布回流记录")
async def delete_project_performance(
    project_id: str,
    performance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    record = await performance_repo.get_by_id(db, performance_id)
    if not record or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="回流记录不存在")
    await performance_repo.delete(db, performance_id)
    await operation_log_repo.create(
        db,
        action="planning.performance.delete",
        entity_type="content_performance",
        entity_id=performance_id,
        actor=current_user.username,
        detail="删除发布回流记录",
        extra={"project_id": project_id},
    )
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{project_id}/performance-summary", response_model=ContentPerformanceSummaryResponse, summary="获取发布回流汇总")
async def get_project_performance_summary(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return await performance_repo.summary_by_project(
        db,
        project_id,
        planned_content_count=len(project.content_items or []),
    )


@router.post("/{project_id}/performance-recap", response_model=PerformanceRecapResponse, summary="生成 AI 发布复盘建议")
async def generate_project_performance_recap(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法做 AI 复盘")

    performance_rows = await performance_repo.list_by_project(db, project_id)
    if not performance_rows:
        raise HTTPException(status_code=400, detail="请先录入至少 1 条发布回流数据")

    performance_summary = await performance_repo.summary_by_project(
        db,
        project_id,
        planned_content_count=len(project.content_items or []),
    )
    ai_result = await ai_analysis_service.generate_performance_recap(
        project_context={
            "client_name": project.client_name,
            "industry": project.industry,
            "target_audience": project.target_audience,
            "business_goal": project.business_goal,
            "planned_content_count": len(project.content_items or []),
        },
        account_plan=project.account_plan or {},
        performance_summary=performance_summary,
        performance_rows=_serialize_performance_rows(project, performance_rows),
        run_context={"entity_type": "planning_project", "entity_id": project_id},
        db=db,
    )
    recap = _normalize_performance_recap(ai_result if isinstance(ai_result, dict) else {})

    account_plan = dict(project.account_plan or {})
    account_plan["performance_recap"] = recap
    project.account_plan = account_plan

    await operation_log_repo.create(
        db,
        action="planning.performance_recap.generate",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="生成 AI 发布复盘建议",
        extra={"performance_items": len(performance_rows)},
    )
    await db.commit()
    await db.refresh(project)
    return recap


@router.post("/{project_id}/next-topic-batch", response_model=NextTopicBatchResponse, summary="生成下一批10条选题")
async def generate_project_next_topic_batch(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法生成下一批选题")

    performance_recap = (
        project.account_plan.get("performance_recap")
        if isinstance(project.account_plan, dict)
        else None
    )
    if not isinstance(performance_recap, dict):
        raise HTTPException(status_code=400, detail="请先生成 AI 发布复盘")

    ai_result = await ai_analysis_service.generate_next_topic_batch(
        project_context={
            "client_name": project.client_name,
            "industry": project.industry,
            "target_audience": project.target_audience,
            "business_goal": project.business_goal,
        },
        account_plan=project.account_plan or {},
        performance_recap=performance_recap,
        existing_content_items=_serialize_existing_content_items(project),
        run_context={"entity_type": "planning_project", "entity_id": project_id},
        db=db,
    )
    next_topic_batch = _normalize_next_topic_batch(ai_result if isinstance(ai_result, dict) else {})

    account_plan = dict(project.account_plan or {})
    account_plan["next_topic_batch"] = next_topic_batch
    project.account_plan = account_plan

    await operation_log_repo.create(
        db,
        action="planning.next_topic_batch.generate",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="生成下一批10条选题",
        extra={"item_count": len(next_topic_batch["items"])},
    )
    await db.commit()
    await db.refresh(project)
    return next_topic_batch


@router.post("/{project_id}/next-topic-batch/{item_index}/import", response_model=ContentItemResponse, summary="将选题加入内容日历")
async def import_next_topic_batch_item(
    project_id: str,
    item_index: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not isinstance(project.account_plan, dict):
        raise HTTPException(status_code=400, detail="项目中暂无可导入的选题批次")

    next_topic_batch = project.account_plan.get("next_topic_batch")
    if not isinstance(next_topic_batch, dict) or not isinstance(next_topic_batch.get("items"), list):
        raise HTTPException(status_code=400, detail="请先生成下一批选题")

    items = [dict(item) for item in next_topic_batch.get("items", []) if isinstance(item, dict)]
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="选题不存在")

    batch_item = items[item_index]
    if batch_item.get("imported_content_item_id"):
        raise HTTPException(status_code=400, detail="这条选题已经加入内容日历")

    next_day_number = max((item.day_number for item in project.content_items or []), default=0) + 1
    content_item = await planning_repository.add_content_item(
        db,
        {
            "project_id": project_id,
            "day_number": next_day_number,
            "title_direction": batch_item.get("title_direction", ""),
            "content_type": _normalize_content_type(batch_item.get("content_type")),
            "tags": [batch_item.get("content_pillar")] if batch_item.get("content_pillar") else [],
        },
    )

    updated_calendar = list(project.content_calendar or [])
    updated_calendar.append(
        _normalize_content_calendar_item(
            {
                "day": next_day_number,
                "title_direction": batch_item.get("title_direction", ""),
                "content_type": _normalize_content_type(batch_item.get("content_type")),
                "content_pillar": batch_item.get("content_pillar"),
                "key_message": batch_item.get("why_this_angle") or batch_item.get("hook_hint") or "",
                "tags": [batch_item.get("content_pillar")] if batch_item.get("content_pillar") else [],
                "priority": "P2-补充储备",
                "content_role": "补充试错",
                "is_main_validation": False,
                "is_batch_shootable": _derive_batch_shootable(_normalize_content_type(batch_item.get("content_type"))),
                "batch_shoot_group": _derive_batch_group(_normalize_content_type(batch_item.get("content_type"))),
                "replacement_hint": batch_item.get("why_this_angle") or "",
            },
            day_fallback=next_day_number,
        )
    )
    project.content_calendar = updated_calendar

    batch_item["imported_content_item_id"] = content_item.id
    batch_item["imported_day_number"] = next_day_number
    batch_item["imported_at"] = datetime.utcnow().isoformat()
    items[item_index] = batch_item

    account_plan = dict(project.account_plan or {})
    account_plan["next_topic_batch"] = {
        **next_topic_batch,
        "items": items,
    }
    project.account_plan = account_plan

    await operation_log_repo.create(
        db,
        action="planning.next_topic_batch.import",
        entity_type="content_item",
        entity_id=content_item.id,
        actor=current_user.username,
        detail="将下一批选题加入内容日历",
        extra={"project_id": project_id, "item_index": item_index, "day_number": next_day_number},
    )
    await db.commit()
    await db.refresh(content_item)
    return content_item


async def _generate_plan_background(
    project_id: str,
    client_data: dict,
    blogger_ids: list,
    task_key: str | None = None,
    fallback_status: str | None = None,
):
    """后台任务：生成账号定位和内容日历（关键步骤均检查取消）"""
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or f"planning:{project_id}:generate"
        project = await planning_repository.get_by_id(db, project_id)
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="planning_generate",
            title=f"生成策划：{project.client_name if project else project_id}",
            entity_type="planning_project",
            entity_id=project_id,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message="开始生成账号策划",
        )
        await db.commit()
        try:
            if cancellation_registry.is_cancelled(project_id):
                logger.info(f"项目 {project_id} 已被取消，跳过生成")
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.CANCELLED.value,
                    progress_step="cancelled",
                    message="任务已取消",
                )
                await db.commit()
                return

            # 获取参考博主分析报告
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="collect_reference",
                message="收集参考博主分析数据",
            )
            await db.commit()
            reference_bloggers = []
            for bid in blogger_ids:
                blogger = await blogger_repository.get_by_id(db, bid)
                if blogger:
                    report = blogger.analysis_report if isinstance(blogger.analysis_report, dict) else {}
                    reference_bloggers.append({
                        "nickname": blogger.nickname,
                        "analysis_report": report,
                        "viral_profile": report.get("viral_profile"),
                    })

            # AI 生成账号策划
            logger.info(f"开始为项目 {project_id} 生成策划方案...")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="ai_generate",
                message="AI 正在生成账号定位和内容日历",
            )
            await db.commit()
            result = await ai_analysis_service.generate_account_plan(
                client_info=client_data,
                reference_bloggers=reference_bloggers,
                run_context={"entity_type": "planning_project", "entity_id": project_id},
                db=db,
            )

            if result.get("error"):
                logger.error(f"项目 {project_id} AI 分析返回 error: {result['error']}")
                raise Exception(result["error"])

            # 打印 AI 返回的完整 keys 供排查
            logger.info(f"项目 {project_id} AI 结果包含字段: {list(result.keys())}")
            if "raw_analysis" in result:
                logger.warning(f"由于解析失败，AI 直接返回了 raw_analysis (前500字符): {result['raw_analysis'][:500]}")

            # NOTE: AI 调用完成后再次检查，避免写入已删除项目的数据
            if cancellation_registry.is_cancelled(project_id):
                logger.info(f"项目 {project_id} 在 AI 完成后被取消，不写入数据库")
                return

            # 解析内容日历 (如果 key 不全，get() 返回默认空值，需要防止后续出错)
            account_positioning = result.get("account_positioning", {})
            content_strategy = result.get("content_strategy", {})
            raw_content_calendar = _normalize_content_calendar(result.get("content_calendar", []))
            backup_topic_pool = _normalize_backup_topic_pool(result.get("backup_topic_pool", []))
            generated_quality_notes = _safe_text(result.get("quality_notes"))

            if not _has_meaningful_plan_result(account_positioning, content_strategy, raw_content_calendar):
                logger.error("项目 %s AI 返回空策划结果，拒绝覆盖原有内容", project_id)
                raise ValueError("AI 返回的策划结果为空，未覆盖原有内容")

            draft_account_plan = {
                "account_positioning": account_positioning,
                "content_strategy": content_strategy,
            }
            content_calendar, backup_topic_pool, calendar_generation_meta, guardrail_quality_notes = await _apply_calendar_quality_guardrails(
                raw_calendar=raw_content_calendar,
                backup_pool=backup_topic_pool,
                client_data=client_data,
                account_plan=draft_account_plan,
                project_id=project_id,
                db=db,
            )

            account_plan = {
                "account_positioning": account_positioning,
                "content_strategy": content_strategy,
                "backup_topic_pool": backup_topic_pool,
                "calendar_generation_meta": calendar_generation_meta,
                "quality_notes": "；".join(filter(None, [generated_quality_notes, guardrail_quality_notes])),
            }

            # 更新项目
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="persist",
                message="正在写入策划结果",
            )
            await planning_repository.delete_content_items_by_project(db, project_id)
            await planning_repository.update_plan_result(db, project_id, account_plan, content_calendar)

            # 批量创建内容条目
            for item_data in content_calendar:
                await planning_repository.add_content_item(db, {
                    "project_id": project_id,
                    "day_number": item_data.get("day", 1),
                    "title_direction": item_data.get("title_direction", ""),
                    "content_type": _normalize_content_type(item_data.get("content_type")),
                    "tags": item_data.get("tags", []),
                })

            await db.commit()
            logger.info(f"项目 {project_id} 策划生成完成")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message=f"策划生成完成，共 {len(content_calendar)} 条内容",
            )
            await db.commit()

        except Exception as e:
            logger.error(f"项目 {project_id} 策划生成失败: {e}", exc_info=True)
            project = await planning_repository.get_by_id(db, project_id)
            if project:
                project.status = fallback_status or "draft"
                await db.commit()
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="策划生成失败",
                error_message=str(e),
            )
            await db.commit()
        finally:
            cancellation_registry.clear(project_id)

async def _generate_calendar_only_background(
    project_id: str,
    client_data: dict,
    account_plan: dict,
    task_key: str | None = None,
):
    """后台任务：仅生成 30 天内容日历"""
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or f"planning:{project_id}:calendar"
        project = await planning_repository.get_by_id(db, project_id)
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="planning_calendar",
            title=f"重生成日历：{project.client_name if project else project_id}",
            entity_type="planning_project",
            entity_id=project_id,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message="开始重生成内容日历",
        )
        await db.commit()
        try:
            if cancellation_registry.is_cancelled(project_id):
                logger.info(f"日历重构: 项目 {project_id} 已被取消，跳过生成")
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.CANCELLED.value,
                    progress_step="cancelled",
                    message="日历重生成任务已取消",
                )
                await db.commit()
                return

            logger.info(f"日历重构: 开始为项目 {project_id} 重新生成 30 天内容日历...")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="ai_generate",
                message=(
                    "AI 正在结合最新复盘建议生成新的 30 天日历"
                    if isinstance(account_plan, dict) and isinstance(account_plan.get("performance_recap"), dict)
                    else "AI 正在生成新的 30 天日历"
                ),
            )
            await db.commit()
            result = await ai_analysis_service.generate_content_calendar(
                client_info=client_data,
                account_plan=account_plan,
                run_context={"entity_type": "planning_project", "entity_id": project_id},
                db=db,
            )

            if result.get("error"):
                logger.error(f"日历重构: 项目 {project_id} AI 分析返回 error: {result['error']}")
                raise Exception(result["error"])

            if cancellation_registry.is_cancelled(project_id):
                return

            raw_content_calendar = _normalize_content_calendar(result.get("content_calendar", []))
            backup_topic_pool = _normalize_backup_topic_pool(result.get("backup_topic_pool", []))
            generated_quality_notes = _safe_text(result.get("quality_notes"))
            content_calendar, backup_topic_pool, calendar_generation_meta, guardrail_quality_notes = await _apply_calendar_quality_guardrails(
                raw_calendar=raw_content_calendar,
                backup_pool=backup_topic_pool,
                client_data=client_data,
                account_plan=account_plan,
                project_id=project_id,
                db=db,
            )
            persisted_account_plan = dict(account_plan or {})
            persisted_account_plan["backup_topic_pool"] = backup_topic_pool
            persisted_account_plan["calendar_generation_meta"] = calendar_generation_meta
            persisted_account_plan["quality_notes"] = "；".join(filter(None, [generated_quality_notes, guardrail_quality_notes]))

            # 更新项目的 content_calendar 和状态为 completed
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="persist",
                message="正在写入新日历内容",
            )
            await planning_repository.delete_content_items_by_project(db, project_id)
            await planning_repository.update_plan_result(db, project_id, persisted_account_plan, content_calendar)

            # 批量创建新的内容条目
            for item_data in content_calendar:
                await planning_repository.add_content_item(db, {
                    "project_id": project_id,
                    "day_number": item_data.get("day", 1),
                    "title_direction": item_data.get("title_direction", ""),
                    "content_type": _normalize_content_type(item_data.get("content_type")),
                    "tags": item_data.get("tags", []),
                })

            await db.commit()
            logger.info(f"日历重构: 项目 {project_id} 内容日历重新生成完成")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message=f"日历重生成完成，共 {len(content_calendar)} 条内容",
            )
            await db.commit()

        except Exception as e:
            logger.error(f"日历重构: 项目 {project_id} 重新生成失败: {e}", exc_info=True)
            project = await planning_repository.get_by_id(db, project_id)
            if project:
                project.status = "completed"  # 退回 completed 状态，至少策划还在
                await db.commit()
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="日历重生成失败",
                error_message=str(e),
            )
            await db.commit()
        finally:
            cancellation_registry.clear(project_id)
