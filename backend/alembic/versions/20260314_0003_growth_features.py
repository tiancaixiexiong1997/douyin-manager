"""growth features: prompt versioning, task center, performance loop

Revision ID: 20260314_0003
Revises: 20260314_0002
Create Date: 2026-03-14 09:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260314_0003"
down_revision = "20260314_0002"
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _create_index_if_missing(bind, name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if name in _index_names(bind, table_name):
        return
    op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = _table_names(bind)

    blogger_columns = _column_names(bind, "bloggers")
    with op.batch_alter_table("bloggers") as batch_op:
        if "incremental_enabled" not in blogger_columns:
            batch_op.add_column(sa.Column("incremental_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        if "last_collected_at" not in blogger_columns:
            batch_op.add_column(sa.Column("last_collected_at", sa.DateTime(), nullable=True))
        if "last_collected_published_at" not in blogger_columns:
            batch_op.add_column(sa.Column("last_collected_published_at", sa.DateTime(), nullable=True))
    _create_index_if_missing(bind, "ix_bloggers_last_collected_at", "bloggers", ["last_collected_at"])
    _create_index_if_missing(bind, "ix_bloggers_last_collected_published_at", "bloggers", ["last_collected_published_at"])

    if "task_center_items" not in existing_tables:
        op.create_table(
            "task_center_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("task_key", sa.String(length=120), nullable=False),
            sa.Column("task_type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=False),
            sa.Column("entity_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
            sa.Column("progress_step", sa.String(length=80), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("task_center_items")
    _create_index_if_missing(bind, "ix_task_center_items_task_key", "task_center_items", ["task_key"], unique=True)
    _create_index_if_missing(bind, "ix_task_center_items_status", "task_center_items", ["status"])
    _create_index_if_missing(bind, "ix_task_center_items_task_type_status", "task_center_items", ["task_type", "status"])
    _create_index_if_missing(bind, "ix_task_center_items_entity_type_entity_id", "task_center_items", ["entity_type", "entity_id"])

    if "prompt_versions" not in existing_tables:
        op.create_table(
            "prompt_versions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scene_key", sa.String(length=60), nullable=False),
            sa.Column("version_label", sa.String(length=60), nullable=False),
            sa.Column("template_text", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("source_setting_key", sa.String(length=100), nullable=True),
            sa.Column("created_by", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("prompt_versions")
    _create_index_if_missing(bind, "ix_prompt_versions_scene_key", "prompt_versions", ["scene_key"])
    _create_index_if_missing(bind, "ix_prompt_versions_scene_key_created_at", "prompt_versions", ["scene_key", "created_at"])

    if "prompt_ab_experiments" not in existing_tables:
        op.create_table(
            "prompt_ab_experiments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scene_key", sa.String(length=60), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("version_a_id", sa.String(length=36), sa.ForeignKey("prompt_versions.id"), nullable=False),
            sa.Column("version_b_id", sa.String(length=36), sa.ForeignKey("prompt_versions.id"), nullable=False),
            sa.Column("traffic_ratio_a", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("prompt_ab_experiments")
    _create_index_if_missing(bind, "ix_prompt_ab_experiments_scene_key_is_active", "prompt_ab_experiments", ["scene_key", "is_active"])

    if "prompt_runs" not in existing_tables:
        op.create_table(
            "prompt_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scene_key", sa.String(length=60), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=True),
            sa.Column("entity_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
            sa.Column("prompt_version_id", sa.String(length=36), sa.ForeignKey("prompt_versions.id"), nullable=True),
            sa.Column("ab_experiment_id", sa.String(length=36), sa.ForeignKey("prompt_ab_experiments.id"), nullable=True),
            sa.Column("ab_branch", sa.String(length=8), nullable=True),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("output_preview", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        existing_tables.add("prompt_runs")
    _create_index_if_missing(bind, "ix_prompt_runs_scene_key_created_at", "prompt_runs", ["scene_key", "created_at"])
    _create_index_if_missing(bind, "ix_prompt_runs_prompt_version_id", "prompt_runs", ["prompt_version_id"])

    if "content_performances" not in existing_tables:
        op.create_table(
            "content_performances",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("planning_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content_item_id", sa.String(length=36), sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("platform", sa.String(length=30), nullable=False, server_default="douyin"),
            sa.Column("publish_date", sa.Date(), nullable=True),
            sa.Column("video_url", sa.Text(), nullable=True),
            sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("bounce_2s_rate", sa.Float(), nullable=True),
            sa.Column("completion_5s_rate", sa.Float(), nullable=True),
            sa.Column("completion_rate", sa.Float(), nullable=True),
            sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("comments", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("shares", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("conversions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    else:
        content_performance_columns = _column_names(bind, "content_performances")
        with op.batch_alter_table("content_performances") as batch_op:
            if "bounce_2s_rate" not in content_performance_columns:
                batch_op.add_column(sa.Column("bounce_2s_rate", sa.Float(), nullable=True))
            if "completion_5s_rate" not in content_performance_columns:
                batch_op.add_column(sa.Column("completion_5s_rate", sa.Float(), nullable=True))
    _create_index_if_missing(bind, "ix_content_performances_project_id", "content_performances", ["project_id"])
    _create_index_if_missing(bind, "ix_content_performances_project_id_publish_date", "content_performances", ["project_id", "publish_date"])
    _create_index_if_missing(bind, "ix_content_performances_content_item_id", "content_performances", ["content_item_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = _table_names(bind)

    for index_name, table_name in (
        ("ix_content_performances_content_item_id", "content_performances"),
        ("ix_content_performances_project_id_publish_date", "content_performances"),
        ("ix_content_performances_project_id", "content_performances"),
        ("ix_prompt_runs_prompt_version_id", "prompt_runs"),
        ("ix_prompt_runs_scene_key_created_at", "prompt_runs"),
        ("ix_prompt_ab_experiments_scene_key_is_active", "prompt_ab_experiments"),
        ("ix_prompt_versions_scene_key_created_at", "prompt_versions"),
        ("ix_prompt_versions_scene_key", "prompt_versions"),
        ("ix_task_center_items_entity_type_entity_id", "task_center_items"),
        ("ix_task_center_items_task_type_status", "task_center_items"),
        ("ix_task_center_items_status", "task_center_items"),
        ("ix_task_center_items_task_key", "task_center_items"),
        ("ix_bloggers_last_collected_published_at", "bloggers"),
        ("ix_bloggers_last_collected_at", "bloggers"),
    ):
        if table_name in existing_tables and index_name in _index_names(bind, table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in (
        "content_performances",
        "prompt_runs",
        "prompt_ab_experiments",
        "prompt_versions",
        "task_center_items",
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)

    blogger_columns = _column_names(bind, "bloggers")
    with op.batch_alter_table("bloggers") as batch_op:
        if "last_collected_published_at" in blogger_columns:
            batch_op.drop_column("last_collected_published_at")
        if "last_collected_at" in blogger_columns:
            batch_op.drop_column("last_collected_at")
        if "incremental_enabled" in blogger_columns:
            batch_op.drop_column("incremental_enabled")
