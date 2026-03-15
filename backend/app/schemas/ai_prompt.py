"""AI 提示词能力升级相关 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PromptVersionCreateRequest(BaseModel):
    scene_key: str
    version_label: str
    template_text: str
    source_setting_key: Optional[str] = None
    is_active: bool = False


class PromptVersionResponse(BaseModel):
    id: str
    scene_key: str
    version_label: str
    template_text: str
    is_active: bool
    source_setting_key: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptExperimentCreateRequest(BaseModel):
    scene_key: str
    name: str
    version_a_id: str
    version_b_id: str
    traffic_ratio_a: int = Field(default=50, ge=0, le=100)
    is_active: bool = False


class PromptExperimentUpdateRequest(BaseModel):
    name: Optional[str] = None
    traffic_ratio_a: Optional[int] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None


class PromptExperimentResponse(BaseModel):
    id: str
    scene_key: str
    name: str
    version_a_id: str
    version_b_id: str
    traffic_ratio_a: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptRunResponse(BaseModel):
    id: str
    scene_key: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    status: str
    prompt_version_id: Optional[str]
    ab_experiment_id: Optional[str]
    ab_branch: Optional[str]
    score: Optional[float]
    feedback: Optional[str]
    output_preview: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptRunScoreRequest(BaseModel):
    score: float = Field(ge=0, le=10)
    feedback: Optional[str] = None


class PromptCompareResponse(BaseModel):
    version_a: dict
    version_b: dict
