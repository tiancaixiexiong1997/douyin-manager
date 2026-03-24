"""
策划项目 API 端点
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.api.endpoints import planning_content, planning_performance
from app.models.database import User
from app.models.db_session import get_db
from app.services import planning_calendar_guardrails as calendar_guardrails_service
from app.services import planning_generation_service
from app.services import planning_intake_utils as intake_utils_service
from app.services import planning_performance_utils as performance_utils_service
from app.schemas.planning import (
    PlanningIntakeAssistantRequest,
    PlanningIntakeAssistantResponse,
)
from app.services.ai_analysis_service import ai_analysis_service
from app.services.planning_calendar_utils import (
    attach_normalized_content_calendar as _attach_normalized_content_calendar,
    build_calendar_task_context as _build_calendar_task_context,
    has_meaningful_plan_result as _has_meaningful_plan_result,
    normalize_calendar_generation_meta as _normalize_calendar_generation_meta,
    normalize_content_calendar_item as _normalize_content_calendar_item,
    normalize_text_list as _normalize_text_list,
    safe_text as _safe_text,
)
from app.repository.planning_repo import planning_repository
from app.repository.operation_log_repo import operation_log_repo

router = APIRouter()
router.include_router(planning_content.router)
router.include_router(planning_performance.router)
logger = logging.getLogger(__name__)
# Compatibility aliases for tests and internal monkeypatching.
planning_generation = planning_generation_service
performance_repo = planning_performance.performance_repo
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
INTAKE_DRAFT_KEYS = intake_utils_service.INTAKE_DRAFT_KEYS
INTAKE_REQUIRED_KEYS = intake_utils_service.INTAKE_REQUIRED_KEYS
INTAKE_FIELD_LABELS = intake_utils_service.INTAKE_FIELD_LABELS

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


def _normalize_draft(raw: dict) -> dict[str, str]:
    return intake_utils_service.normalize_draft(raw)


def _is_placeholder_value(value: str) -> bool:
    return intake_utils_service.is_placeholder_value(value)


def _detect_industry(user_message: str) -> str:
    return intake_utils_service.detect_industry(user_message)


def _build_default_ip_requirements(industry: str) -> str:
    return intake_utils_service.build_default_ip_requirements(industry)


def _build_default_client_name(industry: str, user_message: str) -> str:
    return intake_utils_service.build_default_client_name(industry, user_message)


def _auto_fill_intake_draft(draft: dict[str, str], user_message: str) -> list[str]:
    return intake_utils_service.auto_fill_intake_draft(draft, user_message)


def _build_execution_preview(draft: dict[str, str]) -> str:
    return intake_utils_service.build_execution_preview(draft)


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


async def _generate_plan_background(
    project_id: str,
    client_data: dict,
    blogger_ids: list,
    task_key: str | None = None,
    fallback_status: str | None = None,
):
    return await planning_generation_service.generate_plan_background(
        project_id=project_id,
        client_data=client_data,
        blogger_ids=blogger_ids,
        task_key=task_key,
        fallback_status=fallback_status,
    )

async def _generate_calendar_only_background(
    project_id: str,
    client_data: dict,
    account_plan: dict,
    task_key: str | None = None,
    regenerate_day_numbers: list[int] | None = None,
):
    return await planning_generation_service.generate_calendar_only_background(
        project_id=project_id,
        client_data=client_data,
        account_plan=account_plan,
        task_key=task_key,
        regenerate_day_numbers=regenerate_day_numbers,
    )
