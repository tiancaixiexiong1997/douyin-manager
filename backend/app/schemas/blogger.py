"""
Pydantic 请求/响应 Schema：博主相关
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date


class BloggerCreateRequest(BaseModel):
    """添加博主请求"""
    url: str  # 博主主页链接
    representative_video_url: Optional[str] = None  # 代表作视频（供深度析帧分析用）
    sample_count: Optional[int] = None  # None = 全部采集，否则指定条数
    start_date: Optional[date] = None  # 按发布时间过滤：开始日期（含）
    end_date: Optional[date] = None  # 按发布时间过滤：结束日期（含）
    incremental_mode: bool = False  # 增量采集模式（新增时通常无需开启）


class BloggerReanalyzeRequest(BaseModel):
    """重新采集请求（可选参数，不传则走默认策略）"""
    sample_count: Optional[int] = 100  # None = 全部采集；默认 100 条
    start_date: Optional[date] = None  # 按发布时间过滤：开始日期（含）
    end_date: Optional[date] = None  # 按发布时间过滤：结束日期（含）
    incremental_mode: bool = False  # 增量采集（仅拉取新视频）


class SetRepresentativeRequest(BaseModel):
    """将某条已采集视频设为代表作并触发深度解析"""
    video_url: str       # 无水印视频直链（直接用于 AI 析帧，无需重新下载）
    video_id: str        # 原始 video_id（用于生成 rep_ 记录）
    title: Optional[str] = ""   # 视频标题
    description: Optional[str] = ""  # 视频描述
    cover_url: Optional[str] = None
    like_count: Optional[int] = 0
    published_at: Optional[datetime] = None


class BloggerVideoResponse(BaseModel):
    """博主视频响应"""
    id: str
    video_id: str
    title: Optional[str]
    cover_url: Optional[str]
    video_url: Optional[str]
    like_count: int
    comment_count: int
    duration: int
    published_at: Optional[datetime]
    ai_analysis: Optional[dict]
    is_analyzed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerResponse(BaseModel):
    """博主响应"""
    id: str
    platform: str
    blogger_id: str
    nickname: str
    avatar_url: Optional[str]
    signature: Optional[str]
    representative_video_url: Optional[str]
    follower_count: int
    following_count: int
    total_like_count: int
    video_count: int
    analysis_report: Optional[dict]
    is_analyzed: bool
    incremental_enabled: bool = False
    last_collected_at: Optional[datetime] = None
    last_collected_published_at: Optional[datetime] = None
    videos: list[BloggerVideoResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerListResponse(BaseModel):
    """博主列表响应（不含 videos，避免异步懒加载）"""
    id: str
    platform: str
    blogger_id: str
    nickname: str
    avatar_url: Optional[str]
    signature: Optional[str]
    representative_video_url: Optional[str]
    follower_count: int
    video_count: int
    is_analyzed: bool
    incremental_enabled: bool = False
    last_collected_at: Optional[datetime] = None
    last_collected_published_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerPagedResponse(BaseModel):
    """博主分页响应"""
    items: list[BloggerListResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
