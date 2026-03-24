from app.api.endpoints import planning_intake, planning_performance
from app.repository.operation_log_repo import operation_log_repo
from app.repository.planning_repo import planning_repository
from app.services import planning_generation_service
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
from app.services.planning_performance_utils import (
    build_next_topic_calendar_item as _performance_build_calendar_item,
    normalize_next_topic_batch as _normalize_next_topic_batch,
    normalize_performance_recap as _normalize_performance_recap,
    serialize_existing_content_items as _serialize_existing_content_items,
    serialize_performance_rows as _serialize_performance_rows,
)

planning_generation = planning_generation_service
performance_repo = planning_performance.performance_repo
planning_intake_assistant = planning_intake.planning_intake_assistant

INTAKE_DRAFT_KEYS = planning_intake.INTAKE_DRAFT_KEYS
INTAKE_REQUIRED_KEYS = planning_intake.INTAKE_REQUIRED_KEYS
INTAKE_FIELD_LABELS = planning_intake.INTAKE_FIELD_LABELS


def _normalize_draft(raw: dict) -> dict[str, str]:
    return planning_intake._normalize_draft(raw)


def _is_placeholder_value(value: str) -> bool:
    return planning_intake._is_placeholder_value(value)


def _detect_industry(user_message: str) -> str:
    return planning_intake._detect_industry(user_message)


def _build_default_ip_requirements(industry: str) -> str:
    return planning_intake._build_default_ip_requirements(industry)


def _build_default_client_name(industry: str, user_message: str) -> str:
    return planning_intake._build_default_client_name(industry, user_message)


def _auto_fill_intake_draft(draft: dict[str, str], user_message: str) -> list[str]:
    return planning_intake._auto_fill_intake_draft(draft, user_message)


def _build_execution_preview(draft: dict[str, str]) -> str:
    return planning_intake._build_execution_preview(draft)
