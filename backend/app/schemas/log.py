"""操作日志 Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OperationLogResponse(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    actor: str
    detail: Optional[str] = None
    extra: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationLogPagedResponse(BaseModel):
    items: list[OperationLogResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
