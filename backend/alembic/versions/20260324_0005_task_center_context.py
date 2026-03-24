"""task center context for pending planning state

Revision ID: 20260324_0005
Revises: 20260315_0004
Create Date: 2026-03-24 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260324_0005"
down_revision = "20260315_0004"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    column_names = _column_names(bind, "task_center_items")
    with op.batch_alter_table("task_center_items") as batch_op:
        if "context" not in column_names:
            batch_op.add_column(sa.Column("context", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    column_names = _column_names(bind, "task_center_items")
    with op.batch_alter_table("task_center_items") as batch_op:
        if "context" in column_names:
            batch_op.drop_column("context")
