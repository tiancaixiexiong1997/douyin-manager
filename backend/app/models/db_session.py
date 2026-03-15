"""
数据库连接和会话管理
"""
import asyncio
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.config import settings
from app.models.database import Base

logger = logging.getLogger(__name__)

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# 会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """初始化数据库，优先执行 Alembic 迁移，失败时回退 create_all。"""
    if settings.RUN_ALEMBIC_ON_STARTUP:
        migrated = await _run_alembic_upgrade()
        if migrated:
            return

    # Alembic 不可用时兜底，避免服务不可启动。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.DATABASE_URL:
            await _ensure_sqlite_schema(conn)


async def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _ensure_sqlite_schema(conn) -> None:
    """轻量 SQLite 补丁：只补历史列和索引，避免与 Alembic 定义重复漂移。"""
    user_cols_result = await conn.execute(text("PRAGMA table_info(users)"))
    user_cols = {row[1] for row in user_cols_result.fetchall()}
    if "failed_login_attempts" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0")
        )
    if "locked_until" not in user_cols:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN locked_until DATETIME")
        )

    result = await conn.execute(text("PRAGMA table_info(script_extractions)"))
    existing_cols = {row[1] for row in result.fetchall()}

    if "retry_count" not in existing_cols:
        await conn.execute(
            text("ALTER TABLE script_extractions ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
        )
    if "max_retries" not in existing_cols:
        await conn.execute(
            text("ALTER TABLE script_extractions ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 1")
        )

    video_cols_result = await conn.execute(text("PRAGMA table_info(blogger_videos)"))
    blogger_video_cols = {row[1] for row in video_cols_result.fetchall()}
    if "published_at" not in blogger_video_cols:
        await conn.execute(
            text("ALTER TABLE blogger_videos ADD COLUMN published_at DATETIME")
        )

    blogger_cols_result = await conn.execute(text("PRAGMA table_info(bloggers)"))
    blogger_cols = {row[1] for row in blogger_cols_result.fetchall()}
    if "incremental_enabled" not in blogger_cols:
        await conn.execute(
            text("ALTER TABLE bloggers ADD COLUMN incremental_enabled BOOLEAN NOT NULL DEFAULT 0")
        )
    if "last_collected_at" not in blogger_cols:
        await conn.execute(
            text("ALTER TABLE bloggers ADD COLUMN last_collected_at DATETIME")
        )
    if "last_collected_published_at" not in blogger_cols:
        await conn.execute(
            text("ALTER TABLE bloggers ADD COLUMN last_collected_published_at DATETIME")
        )

    performance_cols_result = await conn.execute(text("PRAGMA table_info(content_performances)"))
    performance_cols = {row[1] for row in performance_cols_result.fetchall()}
    if "bounce_2s_rate" not in performance_cols:
        await conn.execute(
            text("ALTER TABLE content_performances ADD COLUMN bounce_2s_rate FLOAT")
        )
    if "completion_5s_rate" not in performance_cols:
        await conn.execute(
            text("ALTER TABLE content_performances ADD COLUMN completion_5s_rate FLOAT")
        )

    # 为历史数据库补齐常用查询索引（新库会由 ORM index 创建，旧库兜底）。
    index_sql = (
        "CREATE INDEX IF NOT EXISTS ix_bloggers_created_at ON bloggers (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_bloggers_last_collected_at ON bloggers (last_collected_at)",
        "CREATE INDEX IF NOT EXISTS ix_bloggers_last_collected_published_at ON bloggers (last_collected_published_at)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_videos_blogger_id ON blogger_videos (blogger_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_videos_video_id ON blogger_videos (video_id)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_videos_created_at ON blogger_videos (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_videos_published_at ON blogger_videos (published_at)",
        "CREATE INDEX IF NOT EXISTS ix_blogger_videos_blogger_id_like_count ON blogger_videos (blogger_id, like_count)",
        "CREATE INDEX IF NOT EXISTS ix_planning_projects_created_at ON planning_projects (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_planning_projects_status ON planning_projects (status)",
        "CREATE INDEX IF NOT EXISTS ix_content_items_project_id ON content_items (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_content_items_created_at ON content_items (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_content_items_project_id_day_number ON content_items (project_id, day_number)",
        "CREATE INDEX IF NOT EXISTS ix_script_extractions_plan_id ON script_extractions (plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_script_extractions_status ON script_extractions (status)",
        "CREATE INDEX IF NOT EXISTS ix_script_extractions_created_at ON script_extractions (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_script_extraction_drafts_user_id ON script_extraction_drafts (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_script_extraction_drafts_plan_id ON script_extraction_drafts (plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_script_extraction_drafts_created_at ON script_extraction_drafts (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_script_extraction_drafts_updated_at ON script_extraction_drafts (updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_script_extraction_drafts_user_updated_at ON script_extraction_drafts (user_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_schedule_entries_schedule_date ON schedule_entries (schedule_date)",
        "CREATE INDEX IF NOT EXISTS ix_schedule_entries_done ON schedule_entries (done)",
        "CREATE INDEX IF NOT EXISTS ix_schedule_entries_created_by_user_id ON schedule_entries (created_by_user_id)",
        "CREATE INDEX IF NOT EXISTS ix_schedule_entries_created_at ON schedule_entries (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_schedule_entries_schedule_date_created_at ON schedule_entries (schedule_date, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_task_center_items_task_key ON task_center_items (task_key)",
        "CREATE INDEX IF NOT EXISTS ix_task_center_items_status ON task_center_items (status)",
        "CREATE INDEX IF NOT EXISTS ix_task_center_items_task_type_status ON task_center_items (task_type, status)",
        "CREATE INDEX IF NOT EXISTS ix_task_center_items_entity_type_entity_id ON task_center_items (entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS ix_prompt_versions_scene_key ON prompt_versions (scene_key)",
        "CREATE INDEX IF NOT EXISTS ix_prompt_versions_scene_key_created_at ON prompt_versions (scene_key, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_prompt_ab_experiments_scene_key_is_active ON prompt_ab_experiments (scene_key, is_active)",
        "CREATE INDEX IF NOT EXISTS ix_prompt_runs_scene_key_created_at ON prompt_runs (scene_key, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_prompt_runs_prompt_version_id ON prompt_runs (prompt_version_id)",
        "CREATE INDEX IF NOT EXISTS ix_content_performances_project_id ON content_performances (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_content_performances_project_id_publish_date ON content_performances (project_id, publish_date)",
        "CREATE INDEX IF NOT EXISTS ix_content_performances_content_item_id ON content_performances (content_item_id)",
    )
    for sql in index_sql:
        await conn.execute(text(sql))


def _run_alembic_upgrade_sync() -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parents[2]
    alembic_cfg_path = backend_root / "alembic.ini"
    alembic_cfg = Config(str(alembic_cfg_path))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(alembic_cfg, "head")


async def _run_alembic_upgrade() -> bool:
    try:
        await asyncio.to_thread(_run_alembic_upgrade_sync)
        logger.info("✅ Alembic migration 已升级到 head")
        return True
    except Exception as exc:
        logger.warning("Alembic migration 执行失败，回退到 SQLAlchemy create_all: %s", exc)
        return False
