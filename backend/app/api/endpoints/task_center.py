"""统一任务中心 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_session import get_db
from app.repository.task_center_repo import task_center_repo
from app.schemas.task_center import TaskCenterPagedResponse

router = APIRouter()


@router.get("", response_model=TaskCenterPagedResponse, summary="获取统一任务中心列表")
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    status: str | None = Query(None, description="queued/running/completed/failed/cancelled"),
    task_type: str | None = Query(None, description="blogger_collect/planning_generate/script_extraction ..."),
    entity_type: str | None = Query(None, description="blogger/planning_project/script_extraction"),
    db: AsyncSession = Depends(get_db),
):
    items = await task_center_repo.list_tasks(
        db,
        skip=skip,
        limit=limit,
        status=(status or "").strip() or None,
        task_type=(task_type or "").strip() or None,
        entity_type=(entity_type or "").strip() or None,
    )
    total = await task_center_repo.count_tasks(
        db,
        status=(status or "").strip() or None,
        task_type=(task_type or "").strip() or None,
        entity_type=(entity_type or "").strip() or None,
    )
    summary = await task_center_repo.status_summary(db)
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(items) < total,
        "summary": summary,
    }
