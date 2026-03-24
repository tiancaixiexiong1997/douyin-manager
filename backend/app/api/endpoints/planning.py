"""
策划项目 API 端点
"""
import logging
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints import planning_content, planning_intake, planning_performance
from app.services import planning_calendar_guardrails as calendar_guardrails_service
from app.services import planning_generation_service
from app.services import planning_performance_utils as performance_utils_service
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
router.include_router(planning_intake.router)
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
planning_intake_assistant = planning_intake.planning_intake_assistant
INTAKE_DRAFT_KEYS = planning_intake.INTAKE_DRAFT_KEYS
INTAKE_REQUIRED_KEYS = planning_intake.INTAKE_REQUIRED_KEYS
INTAKE_FIELD_LABELS = planning_intake.INTAKE_FIELD_LABELS

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


def _normalize_performance_recap(raw: dict) -> dict:
    return _performance_normalize_recap(raw)


def _serialize_performance_rows(project, rows: list) -> list[dict]:
    return _performance_serialize_rows(project, rows)


def _serialize_existing_content_items(project) -> list[dict]:
    return _performance_serialize_existing_items(project)


def _normalize_next_topic_batch(raw: dict) -> dict:
    return _performance_normalize_batch(raw)


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
