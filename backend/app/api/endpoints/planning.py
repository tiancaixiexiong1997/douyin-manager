"""策划项目兼容出口。"""
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints import planning_compat, planning_content, planning_intake, planning_performance
from app.services import planning_calendar_guardrails as calendar_guardrails_service
from app.services import planning_generation_service

router = APIRouter()
router.include_router(planning_content.router)
router.include_router(planning_intake.router)
router.include_router(planning_performance.router)
# Compatibility aliases for tests and internal monkeypatching.
ai_analysis_service = planning_compat.ai_analysis_service
planning_generation = planning_compat.planning_generation
performance_repo = planning_compat.performance_repo
planning_repository = planning_compat.planning_repository
operation_log_repo = planning_compat.operation_log_repo
planning_intake_assistant = planning_compat.planning_intake_assistant
INTAKE_DRAFT_KEYS = planning_compat.INTAKE_DRAFT_KEYS
INTAKE_REQUIRED_KEYS = planning_compat.INTAKE_REQUIRED_KEYS
INTAKE_FIELD_LABELS = planning_compat.INTAKE_FIELD_LABELS
_attach_normalized_content_calendar = planning_compat._attach_normalized_content_calendar
_build_calendar_task_context = planning_compat._build_calendar_task_context
_has_meaningful_plan_result = planning_compat._has_meaningful_plan_result
_normalize_calendar_generation_meta = planning_compat._normalize_calendar_generation_meta
_normalize_content_calendar_item = planning_compat._normalize_content_calendar_item
_normalize_text_list = planning_compat._normalize_text_list
_safe_text = planning_compat._safe_text
_normalize_draft = planning_compat._normalize_draft
_is_placeholder_value = planning_compat._is_placeholder_value
_detect_industry = planning_compat._detect_industry
_build_default_ip_requirements = planning_compat._build_default_ip_requirements
_build_default_client_name = planning_compat._build_default_client_name
_auto_fill_intake_draft = planning_compat._auto_fill_intake_draft
_build_execution_preview = planning_compat._build_execution_preview
_normalize_performance_recap = planning_compat._normalize_performance_recap
_serialize_performance_rows = planning_compat._serialize_performance_rows
_serialize_existing_content_items = planning_compat._serialize_existing_content_items
_normalize_next_topic_batch = planning_compat._normalize_next_topic_batch
_performance_build_calendar_item = planning_compat._performance_build_calendar_item
_guardrails_collect_flags = calendar_guardrails_service.collect_calendar_quality_flags
_guardrails_build_gap_brief = calendar_guardrails_service._build_calendar_gap_brief
_guardrails_titles_too_similar = calendar_guardrails_service._calendar_titles_are_too_similar
_guardrails_apply_quality = calendar_guardrails_service.apply_calendar_quality_guardrails
_guardrails_regenerate_days = calendar_guardrails_service.regenerate_selected_calendar_days

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
    return planning_compat._normalize_draft(raw)


def _is_placeholder_value(value: str) -> bool:
    return planning_compat._is_placeholder_value(value)


def _detect_industry(user_message: str) -> str:
    return planning_compat._detect_industry(user_message)


def _build_default_ip_requirements(industry: str) -> str:
    return planning_compat._build_default_ip_requirements(industry)


def _build_default_client_name(industry: str, user_message: str) -> str:
    return planning_compat._build_default_client_name(industry, user_message)


def _auto_fill_intake_draft(draft: dict[str, str], user_message: str) -> list[str]:
    return planning_compat._auto_fill_intake_draft(draft, user_message)


def _build_execution_preview(draft: dict[str, str]) -> str:
    return planning_compat._build_execution_preview(draft)


def _normalize_performance_recap(raw: dict) -> dict:
    return planning_compat._normalize_performance_recap(raw)


def _serialize_performance_rows(project, rows: list) -> list[dict]:
    return planning_compat._serialize_performance_rows(project, rows)


def _serialize_existing_content_items(project) -> list[dict]:
    return planning_compat._serialize_existing_content_items(project)


def _normalize_next_topic_batch(raw: dict) -> dict:
    return planning_compat._normalize_next_topic_batch(raw)


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
