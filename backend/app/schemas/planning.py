"""
Pydantic 请求/响应 Schema：策划相关
"""
from pydantic import BaseModel, ConfigDict
from pydantic import Field
from typing import Optional, Literal
from datetime import datetime, date


class PlanningCreateRequest(BaseModel):
    """创建策划项目请求"""
    client_name: str
    industry: str
    target_audience: str
    unique_advantage: Optional[str] = None
    ip_requirements: str
    style_preference: Optional[str] = None
    business_goal: Optional[str] = None
    reference_blogger_ids: list[str] = Field(default_factory=list)  # 博主 UUID 列表
    account_homepage_url: Optional[str] = None  # 策划账号主页地址（可选）


class PlanningIntakeDraft(BaseModel):
    """互动式策划问诊草稿"""
    client_name: str = ""
    industry: str = ""
    target_audience: str = ""
    unique_advantage: str = ""
    ip_requirements: str = ""
    style_preference: str = ""
    business_goal: str = ""
    publishing_rhythm: str = ""
    time_windows: str = ""
    goal_target: str = ""
    iteration_rule: str = ""


class PlanningIntakeChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PlanningIntakeAssistantRequest(BaseModel):
    """互动问诊请求"""
    user_message: str
    draft: PlanningIntakeDraft = Field(default_factory=PlanningIntakeDraft)
    chat_history: list[PlanningIntakeChatMessage] = Field(default_factory=list)
    auto_complete: bool = True
    mode: Literal["normal", "fast"] = "normal"


class PlanningIntakeAssistantResponse(BaseModel):
    """互动问诊响应"""
    assistant_reply: str
    draft: PlanningIntakeDraft
    missing_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    ready_for_reference: bool = False
    ready_for_generate: bool = False
    confirmation_summary: Optional[str] = None
    suggested_questions: list[str] = Field(default_factory=list)


class AccountHomepageUpdateRequest(BaseModel):
    """补填/更新账号主页地址请求"""
    account_homepage_url: str


class PlanningUpdateRequest(BaseModel):
    """编辑策划项目基本信息请求"""
    client_name: Optional[str] = None
    industry: Optional[str] = None
    target_audience: Optional[str] = None
    unique_advantage: Optional[str] = None
    ip_requirements: Optional[str] = None
    style_preference: Optional[str] = None
    business_goal: Optional[str] = None
    account_plan: Optional[dict] = None  # 支持直接更新账号定位方案


class CalendarRegenerateRequest(BaseModel):
    """重新生成日历请求"""
    regenerate_day_numbers: list[int] = Field(default_factory=list)


class ContentItemResponse(BaseModel):
    """内容条目响应"""
    id: str
    day_number: int
    title_direction: str
    content_type: Optional[str]
    tags: Optional[list]
    full_script: Optional[dict]
    is_script_generated: bool

    model_config = ConfigDict(from_attributes=True)


class PlanningResponse(BaseModel):
    """策划项目响应"""
    id: str
    client_name: str
    industry: str
    target_audience: str
    unique_advantage: Optional[str]
    ip_requirements: str
    style_preference: Optional[str]
    business_goal: Optional[str]
    reference_blogger_ids: Optional[list]
    account_homepage_url: Optional[str]
    account_nickname: Optional[str]
    account_avatar_url: Optional[str]
    account_signature: Optional[str]
    account_follower_count: Optional[int]
    account_video_count: Optional[int]
    account_plan: Optional[dict]
    content_calendar: Optional[list]
    status: str
    content_items: list[ContentItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanningListResponse(BaseModel):
    """策划项目列表响应（不含 content_items，避免异步懒加载）"""
    id: str
    client_name: str
    industry: str
    target_audience: str
    status: str
    account_plan: Optional[dict] = None
    account_homepage_url: Optional[str] = None
    account_nickname: Optional[str] = None
    account_avatar_url: Optional[str] = None
    account_signature: Optional[str] = None
    account_follower_count: Optional[int] = None
    account_video_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanningPagedResponse(BaseModel):
    """策划项目分页响应"""
    items: list[PlanningListResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


class ScriptGenerateRequest(BaseModel):
    """单条脚本生成请求"""
    content_item_id: str
    reference_blogger_ids: Optional[list[str]] = Field(default_factory=list)  # 可选：额外指定参考博主


class ContentItemUpdateRequest(BaseModel):
    """更新内容条目请求（支持部分更新）"""
    title_direction: Optional[str] = None
    content_type: Optional[str] = None
    tags: Optional[list] = None
    full_script: Optional[dict] = None


class ContentPerformanceCreateRequest(BaseModel):
    """新增发布回流记录"""
    content_item_id: Optional[str] = None
    title: str
    platform: str = "douyin"
    publish_date: Optional[date] = None
    video_url: Optional[str] = None
    views: int = 0
    bounce_2s_rate: Optional[float] = None
    completion_5s_rate: Optional[float] = None
    completion_rate: Optional[float] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    conversions: int = 0
    notes: Optional[str] = None


class ContentPerformanceUpdateRequest(BaseModel):
    """编辑发布回流记录"""
    content_item_id: Optional[str] = None
    title: Optional[str] = None
    platform: Optional[str] = None
    publish_date: Optional[date] = None
    video_url: Optional[str] = None
    views: Optional[int] = None
    bounce_2s_rate: Optional[float] = None
    completion_5s_rate: Optional[float] = None
    completion_rate: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    conversions: Optional[int] = None
    notes: Optional[str] = None


class ContentPerformanceResponse(BaseModel):
    id: str
    project_id: str
    content_item_id: Optional[str]
    title: str
    platform: str
    publish_date: Optional[date]
    video_url: Optional[str]
    views: int
    bounce_2s_rate: Optional[float]
    completion_5s_rate: Optional[float]
    completion_rate: Optional[float]
    likes: int
    comments: int
    shares: int
    conversions: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentPerformanceInsightResponse(BaseModel):
    title: str
    body: str
    tone: Literal["good", "warn", "neutral"]


class PerformanceRecapResponse(BaseModel):
    generated_at: datetime
    overall_summary: str
    winning_patterns: list[str] = Field(default_factory=list)
    optimization_focus: list[str] = Field(default_factory=list)
    risk_alerts: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    next_topic_angles: list[str] = Field(default_factory=list)


class NextTopicBatchItemResponse(BaseModel):
    title_direction: str
    content_type: str
    content_pillar: Optional[str] = None
    hook_hint: Optional[str] = None
    why_this_angle: Optional[str] = None
    imported_content_item_id: Optional[str] = None
    imported_day_number: Optional[int] = None
    imported_at: Optional[datetime] = None


class NextTopicBatchResponse(BaseModel):
    generated_at: datetime
    overall_strategy: str
    items: list[NextTopicBatchItemResponse] = Field(default_factory=list)


class ContentPerformanceSummaryResponse(BaseModel):
    total_items: int
    planned_content_count: int
    coverage_rate: Optional[float]
    total_views: int
    avg_bounce_2s_rate: Optional[float]
    avg_completion_5s_rate: Optional[float]
    avg_completion_rate: Optional[float]
    avg_engagement_rate: Optional[float]
    avg_conversion_rate: Optional[float]
    total_likes: int
    total_comments: int
    total_shares: int
    total_conversions: int
    top_items: list[ContentPerformanceResponse]
    best_view_item: Optional[ContentPerformanceResponse]
    best_completion_item: Optional[ContentPerformanceResponse]
    best_engagement_item: Optional[ContentPerformanceResponse]
    best_conversion_item: Optional[ContentPerformanceResponse]
    insights: list[ContentPerformanceInsightResponse]
