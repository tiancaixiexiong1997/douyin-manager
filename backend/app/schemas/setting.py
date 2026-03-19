from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class SettingBase(BaseModel):
    setting_key: str
    setting_value: Optional[str] = None
    description: Optional[str] = None

class SettingCreate(SettingBase):
    pass

class SettingUpdate(BaseModel):
    setting_value: Optional[str] = None

class SettingResponse(SettingBase):
    id: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BatchSettingsUpdateRequest(BaseModel):
    settings: dict[str, str]

class SettingsResponse(BaseModel):
    settings: dict[str, str]
    defaults: dict[str, str]


class CookieExtractorStatusResponse(BaseModel):
    token: str
    login_url: str
    extension_path: str
    cookie_length: int = 0
    last_synced_at: Optional[str] = None
    last_service: Optional[str] = None
    last_message: Optional[str] = None


class CookieExtractorRotateResponse(BaseModel):
    token: str
    message: str


class CookieExtractorWebhookRequest(BaseModel):
    service: str
    cookie: str = ""
    timestamp: Optional[str] = None
    test: bool = False
    message: Optional[str] = None


class TaskStateTableSummary(BaseModel):
    count: int = 0
    oldest_updated_at: Optional[str] = None
    newest_updated_at: Optional[str] = None


class TaskStateCleanupSummary(BaseModel):
    task_cancellations: int = 0
    task_progress: int = 0


class TaskStateTablesSummary(BaseModel):
    task_cancellations: TaskStateTableSummary
    task_progress: TaskStateTableSummary


class TaskStateSummaryResponse(BaseModel):
    enabled: bool
    storage: str
    retention_days: int
    cleanup_interval_minutes: int
    last_cleanup_at: Optional[str] = None
    last_cleanup_deleted: TaskStateCleanupSummary
    tables: TaskStateTablesSummary
