"""schema guardrails: performance columns and uniqueness

Revision ID: 20260315_0004
Revises: 20260314_0003
Create Date: 2026-03-15 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260315_0004"
down_revision = "20260314_0003"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _deduplicate_bloggers(bind) -> None:
    duplicate_groups = bind.execute(
        sa.text(
            """
            SELECT platform, blogger_id
            FROM bloggers
            GROUP BY platform, blogger_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    for platform, blogger_id in duplicate_groups:
        rows = bind.execute(
            sa.text(
                """
                SELECT id
                FROM bloggers
                WHERE platform = :platform AND blogger_id = :blogger_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"platform": platform, "blogger_id": blogger_id},
        ).fetchall()
        if len(rows) <= 1:
            continue
        canonical_id = rows[0][0]
        duplicate_ids = [row[0] for row in rows[1:]]
        for duplicate_id in duplicate_ids:
            bind.execute(
                sa.text("UPDATE blogger_videos SET blogger_id = :canonical WHERE blogger_id = :duplicate"),
                {"canonical": canonical_id, "duplicate": duplicate_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE task_center_items
                    SET entity_id = :canonical
                    WHERE entity_type = 'blogger' AND entity_id = :duplicate
                    """
                ),
                {"canonical": canonical_id, "duplicate": duplicate_id},
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE operation_logs
                    SET entity_id = :canonical
                    WHERE entity_type = 'blogger' AND entity_id = :duplicate
                    """
                ),
                {"canonical": canonical_id, "duplicate": duplicate_id},
            )
            bind.execute(
                sa.text("DELETE FROM bloggers WHERE id = :duplicate"),
                {"duplicate": duplicate_id},
            )


def _deduplicate_blogger_videos(bind) -> None:
    duplicate_groups = bind.execute(
        sa.text(
            """
            SELECT blogger_id, video_id
            FROM blogger_videos
            GROUP BY blogger_id, video_id
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    for blogger_id, video_id in duplicate_groups:
        rows = bind.execute(
            sa.text(
                """
                SELECT id
                FROM blogger_videos
                WHERE blogger_id = :blogger_id AND video_id = :video_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"blogger_id": blogger_id, "video_id": video_id},
        ).fetchall()
        for duplicate_id in [row[0] for row in rows[1:]]:
            bind.execute(
                sa.text("DELETE FROM blogger_videos WHERE id = :duplicate"),
                {"duplicate": duplicate_id},
            )


def upgrade() -> None:
    bind = op.get_bind()

    content_performance_columns = _column_names(bind, "content_performances")
    with op.batch_alter_table("content_performances") as batch_op:
        if "bounce_2s_rate" not in content_performance_columns:
            batch_op.add_column(sa.Column("bounce_2s_rate", sa.Float(), nullable=True))
        if "completion_5s_rate" not in content_performance_columns:
            batch_op.add_column(sa.Column("completion_5s_rate", sa.Float(), nullable=True))

    _deduplicate_bloggers(bind)
    _deduplicate_blogger_videos(bind)

    blogger_indexes = _index_names(bind, "bloggers")
    if "uq_bloggers_platform_blogger_id" not in blogger_indexes:
        op.create_index(
            "uq_bloggers_platform_blogger_id",
            "bloggers",
            ["platform", "blogger_id"],
            unique=True,
        )

    video_indexes = _index_names(bind, "blogger_videos")
    if "uq_blogger_videos_blogger_id_video_id" not in video_indexes:
        op.create_index(
            "uq_blogger_videos_blogger_id_video_id",
            "blogger_videos",
            ["blogger_id", "video_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()

    blogger_indexes = _index_names(bind, "bloggers")
    if "uq_bloggers_platform_blogger_id" in blogger_indexes:
        op.drop_index("uq_bloggers_platform_blogger_id", table_name="bloggers")

    video_indexes = _index_names(bind, "blogger_videos")
    if "uq_blogger_videos_blogger_id_video_id" in video_indexes:
        op.drop_index("uq_blogger_videos_blogger_id_video_id", table_name="blogger_videos")

    content_performance_columns = _column_names(bind, "content_performances")
    with op.batch_alter_table("content_performances") as batch_op:
        if "completion_5s_rate" in content_performance_columns:
            batch_op.drop_column("completion_5s_rate")
        if "bounce_2s_rate" in content_performance_columns:
            batch_op.drop_column("bounce_2s_rate")
