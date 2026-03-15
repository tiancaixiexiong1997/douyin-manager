"""initial schema

Revision ID: 20260314_0001
Revises:
Create Date: 2026-03-14 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260314_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _create_index_if_missing(bind, name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if name in _index_names(bind, table_name):
        return
    op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = _table_names(bind)

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("username", sa.String(length=100), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("username", name="uq_users_username"),
        )
        existing_tables.add("users")
    _create_index_if_missing(bind, "ix_users_username", "users", ["username"], unique=True)

    if "bloggers" not in existing_tables:
        op.create_table(
            "bloggers",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("platform", sa.String(length=20), nullable=False),
            sa.Column("blogger_id", sa.String(length=100), nullable=False),
            sa.Column("nickname", sa.String(length=200), nullable=False),
            sa.Column("avatar_url", sa.Text(), nullable=True),
            sa.Column("signature", sa.Text(), nullable=True),
            sa.Column("representative_video_url", sa.Text(), nullable=True),
            sa.Column("follower_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("following_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_like_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("video_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("analysis_report", sa.JSON(), nullable=True),
            sa.Column("is_analyzed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("bloggers")
    _create_index_if_missing(bind, "ix_bloggers_blogger_id", "bloggers", ["blogger_id"])
    _create_index_if_missing(bind, "ix_bloggers_created_at", "bloggers", ["created_at"])

    if "planning_projects" not in existing_tables:
        op.create_table(
            "planning_projects",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("client_name", sa.String(length=200), nullable=False),
            sa.Column("industry", sa.String(length=100), nullable=False),
            sa.Column("target_audience", sa.Text(), nullable=False),
            sa.Column("unique_advantage", sa.Text(), nullable=True),
            sa.Column("ip_requirements", sa.Text(), nullable=False),
            sa.Column("style_preference", sa.Text(), nullable=True),
            sa.Column("business_goal", sa.Text(), nullable=True),
            sa.Column("reference_blogger_ids", sa.JSON(), nullable=True),
            sa.Column("account_homepage_url", sa.Text(), nullable=True),
            sa.Column("account_nickname", sa.String(length=200), nullable=True),
            sa.Column("account_avatar_url", sa.Text(), nullable=True),
            sa.Column("account_signature", sa.Text(), nullable=True),
            sa.Column("account_follower_count", sa.Integer(), nullable=True),
            sa.Column("account_video_count", sa.Integer(), nullable=True),
            sa.Column("account_plan", sa.JSON(), nullable=True),
            sa.Column("content_calendar", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("planning_projects")
    _create_index_if_missing(bind, "ix_planning_projects_status", "planning_projects", ["status"])
    _create_index_if_missing(bind, "ix_planning_projects_created_at", "planning_projects", ["created_at"])

    if "blogger_videos" not in existing_tables:
        op.create_table(
            "blogger_videos",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("blogger_id", sa.String(length=36), sa.ForeignKey("bloggers.id"), nullable=False),
            sa.Column("video_id", sa.String(length=100), nullable=False),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("cover_url", sa.Text(), nullable=True),
            sa.Column("video_url", sa.Text(), nullable=True),
            sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("comment_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("share_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("ai_analysis", sa.JSON(), nullable=True),
            sa.Column("is_analyzed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("blogger_videos")
    _create_index_if_missing(bind, "ix_blogger_videos_blogger_id", "blogger_videos", ["blogger_id"])
    _create_index_if_missing(bind, "ix_blogger_videos_video_id", "blogger_videos", ["video_id"])
    _create_index_if_missing(bind, "ix_blogger_videos_created_at", "blogger_videos", ["created_at"])
    _create_index_if_missing(bind, "ix_blogger_videos_published_at", "blogger_videos", ["published_at"])
    _create_index_if_missing(bind, "ix_blogger_videos_blogger_id_like_count", "blogger_videos", ["blogger_id", "like_count"])

    if "content_items" not in existing_tables:
        op.create_table(
            "content_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("planning_projects.id"), nullable=False),
            sa.Column("day_number", sa.Integer(), nullable=False),
            sa.Column("title_direction", sa.Text(), nullable=False),
            sa.Column("content_type", sa.String(length=50), nullable=True),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("full_script", sa.JSON(), nullable=True),
            sa.Column("is_script_generated", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("content_items")
    _create_index_if_missing(bind, "ix_content_items_project_id", "content_items", ["project_id"])
    _create_index_if_missing(bind, "ix_content_items_created_at", "content_items", ["created_at"])
    _create_index_if_missing(bind, "ix_content_items_project_id_day_number", "content_items", ["project_id", "day_number"])

    if "script_extractions" not in existing_tables:
        op.create_table(
            "script_extractions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("source_video_url", sa.Text(), nullable=False),
            sa.Column("user_prompt", sa.Text(), nullable=False, server_default=""),
            sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("planning_projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("parsed_video_url", sa.Text(), nullable=True),
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("cover_url", sa.Text(), nullable=True),
            sa.Column("highlight_analysis", sa.JSON(), nullable=True),
            sa.Column("generated_script", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("script_extractions")
    _create_index_if_missing(bind, "ix_script_extractions_plan_id", "script_extractions", ["plan_id"])
    _create_index_if_missing(bind, "ix_script_extractions_status", "script_extractions", ["status"])
    _create_index_if_missing(bind, "ix_script_extractions_created_at", "script_extractions", ["created_at"])

    if "script_extraction_drafts" not in existing_tables:
        op.create_table(
            "script_extraction_drafts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_video_url", sa.Text(), nullable=False, server_default=""),
            sa.Column("user_prompt", sa.Text(), nullable=False, server_default=""),
            sa.Column("plan_id", sa.String(length=36), sa.ForeignKey("planning_projects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", name="uq_script_extraction_drafts_user_id"),
        )
        existing_tables.add("script_extraction_drafts")
    _create_index_if_missing(bind, "ix_script_extraction_drafts_user_id", "script_extraction_drafts", ["user_id"], unique=True)
    _create_index_if_missing(bind, "ix_script_extraction_drafts_plan_id", "script_extraction_drafts", ["plan_id"])
    _create_index_if_missing(bind, "ix_script_extraction_drafts_created_at", "script_extraction_drafts", ["created_at"])
    _create_index_if_missing(bind, "ix_script_extraction_drafts_updated_at", "script_extraction_drafts", ["updated_at"])
    _create_index_if_missing(bind, "ix_script_extraction_drafts_user_updated_at", "script_extraction_drafts", ["user_id", "updated_at"])

    if "operation_logs" not in existing_tables:
        op.create_table(
            "operation_logs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("entity_type", sa.String(length=40), nullable=False),
            sa.Column("entity_id", sa.String(length=36), nullable=True),
            sa.Column("actor", sa.String(length=120), nullable=False, server_default="system"),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("extra", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("operation_logs")
    _create_index_if_missing(bind, "ix_operation_logs_action", "operation_logs", ["action"])
    _create_index_if_missing(bind, "ix_operation_logs_entity_type", "operation_logs", ["entity_type"])
    _create_index_if_missing(bind, "ix_operation_logs_entity_id", "operation_logs", ["entity_id"])
    _create_index_if_missing(bind, "ix_operation_logs_created_at", "operation_logs", ["created_at"])

    if "system_settings" not in existing_tables:
        op.create_table(
            "system_settings",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("setting_key", sa.String(length=100), nullable=False),
            sa.Column("setting_value", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("setting_key", name="uq_system_settings_setting_key"),
        )
        existing_tables.add("system_settings")
    _create_index_if_missing(bind, "ix_system_settings_setting_key", "system_settings", ["setting_key"], unique=True)

    if "schedule_entries" not in existing_tables:
        op.create_table(
            "schedule_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("schedule_date", sa.Date(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=80), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_by", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    _create_index_if_missing(bind, "ix_schedule_entries_schedule_date", "schedule_entries", ["schedule_date"])
    _create_index_if_missing(bind, "ix_schedule_entries_done", "schedule_entries", ["done"])
    _create_index_if_missing(bind, "ix_schedule_entries_created_by_user_id", "schedule_entries", ["created_by_user_id"])
    _create_index_if_missing(bind, "ix_schedule_entries_created_at", "schedule_entries", ["created_at"])
    _create_index_if_missing(bind, "ix_schedule_entries_schedule_date_created_at", "schedule_entries", ["schedule_date", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = _table_names(bind)

    for index_name, table_name in (
        ("ix_schedule_entries_schedule_date_created_at", "schedule_entries"),
        ("ix_schedule_entries_created_at", "schedule_entries"),
        ("ix_schedule_entries_created_by_user_id", "schedule_entries"),
        ("ix_schedule_entries_done", "schedule_entries"),
        ("ix_schedule_entries_schedule_date", "schedule_entries"),
        ("ix_system_settings_setting_key", "system_settings"),
        ("ix_operation_logs_created_at", "operation_logs"),
        ("ix_operation_logs_entity_id", "operation_logs"),
        ("ix_operation_logs_entity_type", "operation_logs"),
        ("ix_operation_logs_action", "operation_logs"),
        ("ix_script_extraction_drafts_user_updated_at", "script_extraction_drafts"),
        ("ix_script_extraction_drafts_updated_at", "script_extraction_drafts"),
        ("ix_script_extraction_drafts_created_at", "script_extraction_drafts"),
        ("ix_script_extraction_drafts_plan_id", "script_extraction_drafts"),
        ("ix_script_extraction_drafts_user_id", "script_extraction_drafts"),
        ("ix_script_extractions_created_at", "script_extractions"),
        ("ix_script_extractions_status", "script_extractions"),
        ("ix_script_extractions_plan_id", "script_extractions"),
        ("ix_content_items_project_id_day_number", "content_items"),
        ("ix_content_items_created_at", "content_items"),
        ("ix_content_items_project_id", "content_items"),
        ("ix_blogger_videos_blogger_id_like_count", "blogger_videos"),
        ("ix_blogger_videos_published_at", "blogger_videos"),
        ("ix_blogger_videos_created_at", "blogger_videos"),
        ("ix_blogger_videos_video_id", "blogger_videos"),
        ("ix_blogger_videos_blogger_id", "blogger_videos"),
        ("ix_planning_projects_created_at", "planning_projects"),
        ("ix_planning_projects_status", "planning_projects"),
        ("ix_bloggers_created_at", "bloggers"),
        ("ix_bloggers_blogger_id", "bloggers"),
        ("ix_users_username", "users"),
    ):
        if table_name in existing_tables and index_name in _index_names(bind, table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in (
        "schedule_entries",
        "system_settings",
        "operation_logs",
        "script_extraction_drafts",
        "script_extractions",
        "content_items",
        "blogger_videos",
        "planning_projects",
        "bloggers",
        "users",
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)
