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
from app.services import planning_calendar_guardrails as calendar_guardrails_service
from app.services import planning_performance_utils as performance_utils_service
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
    CalendarRegenerateRequest,
)
from app.services.ai_analysis_service import ai_analysis_service
from app.services.cancellation import cancellation_registry
from app.services.planning_calendar_utils import (
    attach_normalized_content_calendar as _attach_normalized_content_calendar,
    build_calendar_task_context as _build_calendar_task_context,
    build_strategy_task_context as _build_strategy_task_context,
    has_meaningful_plan_result as _has_meaningful_plan_result,
    has_meaningful_strategy_result as _has_meaningful_strategy_result,
    normalize_calendar_generation_meta as _normalize_calendar_generation_meta,
    normalize_content_calendar as _normalize_content_calendar,
    normalize_content_calendar_item as _normalize_content_calendar_item,
    normalize_content_type as _normalize_content_type,
    normalize_text_list as _normalize_text_list,
    safe_text as _safe_text,
)
from app.services.crawler_service import crawler_service
from app.repository.planning_repo import planning_repository
from app.repository.blogger_repo import blogger_repository
from app.repository.performance_repo import performance_repo
from app.repository.operation_log_repo import operation_log_repo
from app.repository.task_center_repo import task_center_repo
from app.services.job_queue import enqueue_task

router = APIRouter()
logger = logging.getLogger(__name__)
_guardrails_collect_flags = calendar_guardrails_service.collect_calendar_quality_flags
_guardrails_build_gap_brief = calendar_guardrails_service._build_calendar_gap_brief
_guardrails_titles_too_similar = calendar_guardrails_service._calendar_titles_are_too_similar
_guardrails_apply_quality = calendar_guardrails_service.apply_calendar_quality_guardrails
_guardrails_regenerate_days = calendar_guardrails_service.regenerate_selected_calendar_days
_performance_normalize_recap = performance_utils_service.normalize_performance_recap
_performance_serialize_rows = performance_utils_service.serialize_performance_rows
_performance_serialize_existing_items = performance_utils_service.serialize_existing_content_items
_performance_normalize_batch = performance_utils_service.normalize_next_topic_batch
_performance_build_calendar_item = performance_utils_service.build_next_topic_calendar_item

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

def _collect_calendar_quality_flags(item: dict) -> list[str]:
    return _guardrails_collect_flags(item)


def _build_calendar_gap_brief(
    *,
    existing_calendar: list[dict],
    account_plan: dict,
    missing_days: list[int],
) -> str:
    return _guardrails_build_gap_brief(
        existing_calendar=existing_calendar,
        account_plan=account_plan,
        missing_days=missing_days,
    )


def _calendar_titles_are_too_similar(candidate: dict, existing_items: list[dict]) -> bool:
    return _guardrails_titles_too_similar(candidate, existing_items)


async def _apply_calendar_quality_guardrails(
    *,
    raw_calendar: list[dict],
    backup_pool: list[dict],
    client_data: dict,
    account_plan: dict,
    project_id: str,
    db: AsyncSession,
) -> tuple[list[dict], list[dict], dict, str]:
    calendar_guardrails_service._calendar_titles_are_too_similar = _calendar_titles_are_too_similar
    calendar_guardrails_service.collect_calendar_quality_flags = _collect_calendar_quality_flags
    calendar_guardrails_service._build_calendar_gap_brief = _build_calendar_gap_brief
    return await _guardrails_apply_quality(
        raw_calendar=raw_calendar,
        backup_pool=backup_pool,
        client_data=client_data,
        account_plan=account_plan,
        project_id=project_id,
        db=db,
    )


async def _regenerate_selected_calendar_days(
    *,
    project,
    client_data: dict,
    account_plan: dict,
    regenerate_days: list[int],
    project_id: str,
    db: AsyncSession,
) -> tuple[list[dict], dict, str]:
    calendar_guardrails_service._calendar_titles_are_too_similar = _calendar_titles_are_too_similar
    calendar_guardrails_service.collect_calendar_quality_flags = _collect_calendar_quality_flags
    calendar_guardrails_service._build_calendar_gap_brief = _build_calendar_gap_brief
    return await _guardrails_regenerate_days(
        project=project,
        client_data=client_data,
        account_plan=account_plan,
        regenerate_days=regenerate_days,
        project_id=project_id,
        db=db,
    )


async def _enqueue_strategy_generation(
    *,
    db: AsyncSession,
    project,
    current_user: User,
    client_data: dict,
    blogger_ids: list,
    task_key: str,
    action: str,
    detail: str,
) -> dict:
    previous_status = project.status
    project.status = "strategy_generating"
    cancellation_registry.clear(project.id)
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_generate",
        title=f"生成定位：{getattr(project, 'client_name', project.id)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message="定位生成任务已提交",
        context=_build_strategy_task_context(project),
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_generate",
            project.id,
            client_data,
            blogger_ids,
            task_key,
            previous_status,
            job_id=task_key,
            description=f"planning strategy {project.id}",
        )
    except RuntimeError as exc:
        project = await planning_repository.get_by_id(db, project.id)
        if project:
            project.status = previous_status
        await operation_log_repo.create(
            db,
            action="planning.enqueue_failed",
            entity_type="planning_project",
            entity_id=project.id,
            actor=current_user.username,
            detail="定位生成任务入队失败，状态已回退",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="定位生成任务入队失败",
            error_message=str(exc),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    await operation_log_repo.create(
        db,
        action=action,
        entity_type="planning_project",
        entity_id=project.id,
        actor=current_user.username,
        detail=detail,
        extra={"status": "strategy_generating"},
    )
    await db.commit()
    return {"message": "已开始生成账号定位方案", "status": "strategy_generating"}


def _normalize_draft(raw: dict) -> dict[str, str]:
    return {key: _safe_text(raw.get(key)) for key in INTAKE_DRAFT_KEYS}


PLACEHOLDER_PATTERNS = (
    "信息不足",
    "待确认",
    "后补充",
    "补齐",
    "无法判断",
    "暂无法",
    "待补充",
)


def _is_placeholder_value(value: str) -> bool:
    text = _safe_text(value)
    if not text:
        return True
    return any(pattern in text for pattern in PLACEHOLDER_PATTERNS)


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


def _normalize_performance_recap(raw: dict) -> dict:
    return _performance_normalize_recap(raw)


def _serialize_performance_rows(project, rows: list) -> list[dict]:
    return _performance_serialize_rows(project, rows)


def _serialize_existing_content_items(project) -> list[dict]:
    return _performance_serialize_existing_items(project)


def _normalize_next_topic_batch(raw: dict) -> dict:
    return _performance_normalize_batch(raw)


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
            if candidate and not _is_placeholder_value(candidate):
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

    required_missing = [key for key in INTAKE_REQUIRED_KEYS if _is_placeholder_value(merged_draft.get(key, ""))]
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
    1. 保存项目基本信息为草稿
    2. 由用户手动触发“生成账号定位方案”
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
        "status": "draft",
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

    return project


@router.post("/{project_id}/generate-strategy", summary="生成账号定位方案")
async def generate_strategy(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status in {"strategy_generating", "calendar_generating", "in_progress"}:
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")

    client_data = {
        "client_name": project.client_name,
        "industry": project.industry,
        "target_audience": project.target_audience,
        "unique_advantage": project.unique_advantage,
        "ip_requirements": project.ip_requirements,
        "style_preference": project.style_preference,
        "business_goal": project.business_goal,
        "reference_blogger_ids": project.reference_blogger_ids or [],
    }
    return await _enqueue_strategy_generation(
        db=db,
        project=project,
        current_user=current_user,
        client_data=client_data,
        blogger_ids=project.reference_blogger_ids or [],
        task_key=f"planning:{project.id}:generate-strategy",
        action="planning.generate_strategy",
        detail="生成账号定位方案",
    )


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
    return _attach_normalized_content_calendar(project)


@router.post("/{project_id}/retry", summary="重新生成账号定位方案")
async def retry_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """重新生成账号定位方案。"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if project.status in {"strategy_generating", "calendar_generating", "in_progress"}:
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")

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
    return await _enqueue_strategy_generation(
        db=db,
        project=project,
        current_user=current_user,
        client_data=client_data,
        blogger_ids=project.reference_blogger_ids or [],
        task_key=f"planning:{project.id}:retry",
        action="planning.retry",
        detail="重新生成账号定位方案",
    )


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
    return _attach_normalized_content_calendar(project)


@router.post("/{project_id}/regenerate-calendar", summary="基于当前定位生成或重生成30天内容日历")
async def regenerate_calendar(
    project_id: str,
    payload: CalendarRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    """基于当前账号定位，生成或重生成 30 天内容日历。"""
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status in {"strategy_generating", "calendar_generating", "in_progress"}:
        raise HTTPException(status_code=400, detail="生成中的项目正在排队，不可重复生成")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法单独生成日历")
    previous_status = project.status
    selected_days = sorted({day for day in payload.regenerate_day_numbers if isinstance(day, int) and 1 <= day <= 30})

    # 仅更新状态，避免入队失败时丢失已有结果。
    project.status = "calendar_generating"

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
    has_existing_calendar = bool(project.content_calendar) or bool(project.content_items)
    is_partial_regenerate = has_existing_calendar and bool(selected_days)
    calendar_task_title = "局部重生成日历" if is_partial_regenerate else ("重生成日历" if has_existing_calendar else "生成日历")
    queue_message = (
        f"已提交局部重生成任务，将重写 Day {', '.join(str(day) for day in selected_days)}"
        if is_partial_regenerate
        else "30天日历生成任务已提交，AI 将结合最新复盘建议优化选题"
        if has_performance_recap
        else "30天日历生成任务已提交"
    )
    await task_center_repo.upsert_task(
        db,
        task_key=task_key,
        task_type="planning_calendar",
        title=f"{calendar_task_title}：{getattr(project, 'client_name', project_id)}",
        entity_type="planning_project",
        entity_id=project.id,
        status=TaskStatus.QUEUED.value,
        progress_step="queued",
        message=queue_message,
        context=_build_calendar_task_context(project, selected_days),
    )
    await db.commit()

    try:
        enqueue_task(
            "app.tasks.run_planning_calendar_generate",
            project.id,
            client_data,
            project.account_plan,
            task_key,
            selected_days,
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
            detail="30天日历任务入队失败，状态已回退",
            extra={"error": str(exc)},
        )
        await task_center_repo.update_status(
            db,
            task_key,
            status=TaskStatus.FAILED.value,
            progress_step="enqueue_failed",
            message="30天日历任务入队失败",
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
        detail="生成30天内容日历" if not has_existing_calendar else "重新生成30天内容日历",
        extra={"status": "calendar_generating", "has_performance_recap": has_performance_recap},
    )

    return {"message": "已开始生成30天内容日历", "status": "calendar_generating"}


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
    return _attach_normalized_content_calendar(project)


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
    updated_calendar.append(_performance_build_calendar_item(batch_item, next_day_number))
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
            context=_build_strategy_task_context(project) if project else {
                "planning_state": "strategy_regenerating",
                "has_existing_strategy": False,
            },
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
                message="AI 正在生成账号定位方案",
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

            account_positioning = result.get("account_positioning", {})
            content_strategy = result.get("content_strategy", {})

            if not _has_meaningful_strategy_result(account_positioning, content_strategy):
                logger.error("项目 %s AI 返回空定位结果，拒绝覆盖原有内容", project_id)
                raise ValueError("AI 返回的定位结果为空，未覆盖原有内容")

            account_plan = {
                "account_positioning": account_positioning,
                "content_strategy": content_strategy,
            }

            # 更新项目
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="persist",
                message="正在写入账号定位结果",
            )
            await planning_repository.delete_content_items_by_project(db, project_id)
            await planning_repository.update_strategy_result(db, project_id, account_plan)

            await db.commit()
            logger.info(f"项目 {project_id} 定位方案生成完成")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message="账号定位方案生成完成，可继续生成 30 天日历",
            )
            await db.commit()

        except Exception as e:
            logger.error(f"项目 {project_id} 定位生成失败: {e}", exc_info=True)
            project = await planning_repository.get_by_id(db, project_id)
            if project:
                project.status = fallback_status or "draft"
                await db.commit()
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="账号定位方案生成失败",
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
    regenerate_day_numbers: list[int] | None = None,
):
    """后台任务：仅生成 30 天内容日历"""
    from app.models.db_session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or f"planning:{project_id}:calendar"
        project = await planning_repository.get_by_id(db, project_id)
        selected_days = sorted({day for day in (regenerate_day_numbers or []) if isinstance(day, int) and 1 <= day <= 30})
        has_existing_calendar = bool(project and (project.content_calendar or project.content_items))
        is_partial_regenerate = has_existing_calendar and bool(selected_days)
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="planning_calendar",
            title=f"{'局部重生成日历' if is_partial_regenerate else ('重生成日历' if has_existing_calendar else '生成日历')}：{project.client_name if project else project_id}",
            entity_type="planning_project",
            entity_id=project_id,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message=(
                f"开始重生成 Day {', '.join(str(day) for day in selected_days)}"
                if is_partial_regenerate
                else "开始生成30天内容日历"
            ),
            context=_build_calendar_task_context(project, selected_days) if project else {
                "planning_state": "calendar_regenerating",
                "regeneration_mode": "partial" if selected_days else "initial",
                "regenerate_day_numbers": selected_days,
                "calendar_snapshots": [],
            },
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

            logger.info(f"日历重构: 开始为项目 {project_id} 生成 30 天内容日历...")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="ai_generate",
                message=(
                    f"AI 正在重写 Day {', '.join(str(day) for day in selected_days)}"
                    if is_partial_regenerate
                    else
                    "AI 正在结合最新复盘建议生成新的 30 天日历"
                    if isinstance(account_plan, dict) and isinstance(account_plan.get("performance_recap"), dict)
                    else "AI 正在生成新的 30 天日历"
                ),
            )
            await db.commit()
            if is_partial_regenerate:
                content_calendar, calendar_meta, quality_notes = await _regenerate_selected_calendar_days(
                    project=project,
                    client_data=client_data,
                    account_plan=account_plan,
                    regenerate_days=selected_days,
                    project_id=project_id,
                    db=db,
                )
            else:
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

                content_calendar = _normalize_content_calendar(result.get("content_calendar", []))
                if len(content_calendar) != 30:
                    raise ValueError(f"内容日历输出数量异常，应为30条，实际 {len(content_calendar)} 条")
                calendar_meta = {
                    "blocked_count": 0,
                    "backup_used_count": 0,
                    "regeneration_count": 0,
                }
                quality_notes = ""

            if cancellation_registry.is_cancelled(project_id):
                return
            persisted_account_plan = dict(account_plan or {})
            persisted_account_plan["backup_topic_pool"] = []
            persisted_account_plan["calendar_generation_meta"] = calendar_meta
            persisted_account_plan["quality_notes"] = quality_notes

            # 更新项目的 content_calendar 和状态为 completed
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="persist",
                message="正在写入重生成结果",
            )
            await planning_repository.update_plan_result(db, project_id, persisted_account_plan, content_calendar)

            if is_partial_regenerate:
                await planning_repository.delete_content_items_by_days(db, project_id, selected_days)
                content_items_to_create = [item for item in content_calendar if item.get("day") in selected_days]
            else:
                await planning_repository.delete_content_items_by_project(db, project_id)
                content_items_to_create = content_calendar

            for item_data in content_items_to_create:
                await planning_repository.add_content_item(db, {
                    "project_id": project_id,
                    "day_number": item_data.get("day", 1),
                    "title_direction": item_data.get("title_direction", ""),
                    "content_type": _normalize_content_type(item_data.get("content_type")),
                    "tags": item_data.get("tags", []),
                })

            await db.commit()
            logger.info(f"日历重构: 项目 {project_id} 内容日历生成完成")
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message=(
                    f"已重生成 {len(selected_days)} 条内容，其余日历已保留"
                    if is_partial_regenerate
                    else f"30天日历生成完成，共 {len(content_calendar)} 条内容"
                ),
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
