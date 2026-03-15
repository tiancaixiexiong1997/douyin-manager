"""
数据库模型定义
使用 SQLAlchemy 异步 ORM
"""
import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, Date, JSON, ForeignKey, Enum as SAEnum, Index, Float, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class Platform(str, enum.Enum):
    """平台枚举"""
    DOUYIN = "douyin"
    TIKTOK = "tiktok"
    BILIBILI = "bilibili"


class AnalysisMode(str, enum.Enum):
    """分析模式"""
    FRAME = "frame"       # 关键帧多模态分析（慢但准）
    TEXT = "text"         # 文本分析（快）


class PlanStatus(str, enum.Enum):
    """策划状态"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserRole(str, enum.Enum):
    """用户角色"""
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class User(Base):
    """后台用户模型（为多人协作预留）"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.MEMBER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Blogger(Base):
    """博主IP库模型"""
    __tablename__ = "bloggers"
    __table_args__ = (
        UniqueConstraint("platform", "blogger_id", name="uq_bloggers_platform_blogger_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    blogger_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    representative_video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    following_count: Mapped[int] = mapped_column(Integer, default=0)
    total_like_count: Mapped[int] = mapped_column(Integer, default=0)
    video_count: Mapped[int] = mapped_column(Integer, default=0)
    # AI 生成的博主整体分析报告
    analysis_report: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 采集状态
    is_analyzed: Mapped[bool] = mapped_column(default=False)
    incremental_enabled: Mapped[bool] = mapped_column(default=False)
    last_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    last_collected_published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联视频
    videos: Mapped[list["BloggerVideo"]] = relationship("BloggerVideo", back_populates="blogger", cascade="all, delete-orphan")


class BloggerVideo(Base):
    """博主视频样本模型"""
    __tablename__ = "blogger_videos"
    __table_args__ = (
        UniqueConstraint("blogger_id", "video_id", name="uq_blogger_videos_blogger_id_video_id"),
        Index("ix_blogger_videos_blogger_id_like_count", "blogger_id", "like_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    blogger_id: Mapped[str] = mapped_column(String(36), ForeignKey("bloggers.id"), nullable=False, index=True)
    video_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[int] = mapped_column(Integer, default=0)  # 秒
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    # AI 分析结果（拍摄手法、文案特点等）
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_analyzed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # 关联博主
    blogger: Mapped["Blogger"] = relationship("Blogger", back_populates="videos")


class PlanningProject(Base):
    """账号策划项目模型"""
    __tablename__ = "planning_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 客户信息
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    unique_advantage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 差异化优势
    # IP 需求
    ip_requirements: Mapped[str] = mapped_column(Text, nullable=False)
    style_preference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 参考博主（博主ID列表）
    reference_blogger_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # 策划账号主页信息（可选，后期可补填）
    account_homepage_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_nickname: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    account_avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_follower_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    account_video_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # AI 生成结果
    account_plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_calendar: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # 状态
    status: Mapped[str] = mapped_column(String(20), default=PlanStatus.DRAFT, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联内容条目
    content_items: Mapped[list["ContentItem"]] = relationship("ContentItem", back_populates="project", cascade="all, delete-orphan")


class ContentItem(Base):
    """单条内容策划条目"""
    __tablename__ = "content_items"
    __table_args__ = (
        Index("ix_content_items_project_id_day_number", "project_id", "day_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("planning_projects.id"), nullable=False, index=True)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 第几天
    title_direction: Mapped[str] = mapped_column(Text, nullable=False)  # 方向标题
    content_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 口播/剧情/教程
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # 完整脚本（按需生成）
    full_script: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_script_generated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    project: Mapped["PlanningProject"] = relationship("PlanningProject", back_populates="content_items")


class ExtractionStatus(str, enum.Enum):
    """脚本提取复刻状态"""
    PENDING = "pending"          # 等待处理
    ANALYZING = "analyzing"      # AI拆解原视频中
    GENERATING = "generating"    # AI生成新脚本中
    COMPLETED = "completed"      # 处理完成
    FAILED = "failed"            # 处理失败


class ScriptExtraction(Base):
    """视频脚本拆解复刻记录模型"""
    __tablename__ = "script_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 原始输入信息
    source_video_url: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("planning_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 视频解析结果
    parsed_video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # AI 结构化输出结果
    highlight_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 原视频亮点拆解
    generated_script: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)    # 结合灵感生成的新脚本
    
    # 状态与时间
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ExtractionStatus.PENDING, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScriptExtractionDraft(Base):
    """脚本拆解页草稿（按用户持久化）。"""
    __tablename__ = "script_extraction_drafts"
    __table_args__ = (
        Index("ix_script_extraction_drafts_user_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    source_video_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("planning_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class OperationLog(Base):
    """系统操作日志模型（最小审计能力）"""
    __tablename__ = "operation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class SystemSetting(Base):
    """系统设置模型"""
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    setting_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    setting_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduleEntry(Base):
    """日历排期条目（用户自定义）。"""
    __tablename__ = "schedule_entries"
    __table_args__ = (
        Index("ix_schedule_entries_schedule_date_created_at", "schedule_date", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    done: Mapped[bool] = mapped_column(default=False, index=True)

    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TaskStatus(str, enum.Enum):
    """统一任务中心状态"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCenterItem(Base):
    """统一任务中心条目"""
    __tablename__ = "task_center_items"
    __table_args__ = (
        Index("ix_task_center_items_task_type_status", "task_type", "status"),
        Index("ix_task_center_items_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.QUEUED.value, nullable=False, index=True)
    progress_step: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class PromptVersion(Base):
    """提示词版本管理"""
    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("ix_prompt_versions_scene_key_created_at", "scene_key", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scene_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(60), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    source_setting_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PromptABExperiment(Base):
    """提示词 A/B 实验"""
    __tablename__ = "prompt_ab_experiments"
    __table_args__ = (
        Index("ix_prompt_ab_experiments_scene_key_is_active", "scene_key", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scene_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version_a_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=False)
    version_b_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=False)
    traffic_ratio_a: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PromptRun(Base):
    """单次 AI 生成运行记录（用于评分和对比）"""
    __tablename__ = "prompt_runs"
    __table_args__ = (
        Index("ix_prompt_runs_scene_key_created_at", "scene_key", "created_at"),
        Index("ix_prompt_runs_prompt_version_id", "prompt_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scene_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    prompt_version_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=True)
    ab_experiment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("prompt_ab_experiments.id"), nullable=True)
    ab_branch: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # A/B/BASE
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContentPerformance(Base):
    """发布后数据回流记录"""
    __tablename__ = "content_performances"
    __table_args__ = (
        Index("ix_content_performances_project_id_publish_date", "project_id", "publish_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("planning_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    content_item_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), default="douyin", nullable=False)
    publish_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bounce_2s_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_5s_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
