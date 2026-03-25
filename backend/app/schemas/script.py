"""
Pydantic 请求/响应 Schema：视频脚本拆解复刻
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.database import ExtractionStatus

class ExtractionCreateRequest(BaseModel):
    """创建视频脚本拆解复刻任务的请求"""
    source_video_url: str
    user_prompt: str = ""
    plan_id: Optional[str] = None


class ExtractionDraftUpsertRequest(BaseModel):
    """保存脚本拆解页草稿请求"""
    source_video_url: str = ""
    user_prompt: str = ""
    plan_id: Optional[str] = None


class ExtractionDraftResponse(BaseModel):
    """脚本拆解页草稿响应"""
    source_video_url: str = ""
    user_prompt: str = ""
    plan_id: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExtractionUpdateRequest(BaseModel):
    """更新脚本拆解结果"""
    highlight_analysis: Optional[dict] = None
    generated_script: Optional[dict] = None


class ExtractionResponse(BaseModel):
    """视频脚本拆解复刻记录的响应"""
    id: str
    source_video_url: str
    user_prompt: str
    plan_id: Optional[str] = None
    
    parsed_video_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    
    highlight_analysis: Optional[dict] = None
    generated_script: Optional[dict] = None
    has_highlight_analysis: bool = False
    has_generated_script: bool = False
    
    status: ExtractionStatus
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 1
    
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractionListResponse(BaseModel):
    """提取历史列表项响应（简略信息）"""
    id: str
    source_video_url: str
    plan_id: Optional[str] = None
    title: Optional[str] = None
    cover_url: Optional[str] = None
    status: ExtractionStatus
    has_highlight_analysis: bool = False
    has_generated_script: bool = False
    retry_count: int = 0
    max_retries: int = 1
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
