"""队列任务入口（由 RQ Worker 调用）。"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

from app.api.endpoints.blogger import (
    _analyze_blogger_background,
    _generate_blogger_viral_profile_background,
    _analyze_single_rep_video,
    _update_blogger_report_background,
)
from app.api.endpoints.planning import (
    _generate_calendar_only_background,
    _generate_plan_background,
)
from app.api.endpoints.script import _process_extraction_background


def run_blogger_analyze(
    blogger_uuid: str,
    user_data: dict,
    sample_count: Optional[int],
    representative_video_url: Optional[str],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    refresh: bool = False,
    incremental_mode: bool = False,
    task_key: str | None = None,
) -> None:
    asyncio.run(
        _analyze_blogger_background(
            blogger_uuid,
            user_data,
            sample_count,
            representative_video_url,
            start_date,
            end_date,
            refresh,
            incremental_mode,
            task_key,
        )
    )


def run_blogger_rep_video_analyze(blogger_uuid: str, video_data: dict) -> None:
    asyncio.run(_analyze_single_rep_video(blogger_uuid, video_data))


def run_blogger_report_refresh(blogger_uuid: str) -> None:
    asyncio.run(_update_blogger_report_background(blogger_uuid))


def run_blogger_viral_profile_generate(blogger_uuid: str, task_key: str | None = None) -> None:
    asyncio.run(_generate_blogger_viral_profile_background(blogger_uuid, task_key))


def run_planning_generate(
    project_id: str,
    client_data: dict,
    blogger_ids: list,
    task_key: str | None = None,
    fallback_status: str | None = None,
) -> None:
    asyncio.run(_generate_plan_background(project_id, client_data, blogger_ids, task_key, fallback_status))


def run_planning_calendar_generate(
    project_id: str,
    client_data: dict,
    account_plan: dict,
    task_key: str | None = None,
) -> None:
    asyncio.run(_generate_calendar_only_background(project_id, client_data, account_plan, task_key))


def run_script_extraction(
    extraction_id: str,
    source_url: str,
    user_prompt: str,
    plan_id: str | None = None,
    task_key: str | None = None,
) -> None:
    asyncio.run(_process_extraction_background(extraction_id, source_url, user_prompt, plan_id, task_key))
