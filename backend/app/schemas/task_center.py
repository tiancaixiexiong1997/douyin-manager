"""统一任务中心 Schema。"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TaskCenterItemResponse(BaseModel):
    id: str
    task_key: str
    task_type: str
    title: str
    entity_type: str
    entity_id: str
    status: str
    progress_step: str | None
    message: str | None
    error_message: str | None
    context: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCenterPagedResponse(BaseModel):
    items: list[TaskCenterItemResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
    summary: dict[str, int]
