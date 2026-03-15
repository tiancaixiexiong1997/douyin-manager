"""日历排期相关 Schema。"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScheduleEntryCreateRequest(BaseModel):
    schedule_date: date
    title: str = Field(min_length=1, max_length=255)
    content_type: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = None
    done: bool = False


class ScheduleEntryUpdateRequest(BaseModel):
    schedule_date: Optional[date] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content_type: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = None
    done: Optional[bool] = None


class ScheduleEntryResponse(BaseModel):
    id: str
    schedule_date: date
    title: str
    content_type: Optional[str]
    notes: Optional[str]
    done: bool
    created_by_user_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

