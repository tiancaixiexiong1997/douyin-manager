"""add store profile json to planning projects

Revision ID: 20260402_0006
Revises: 20260324_0005
Create Date: 2026-04-02 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260402_0006"
down_revision = "20260324_0005"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    column_names = _column_names(bind, "planning_projects")
    with op.batch_alter_table("planning_projects") as batch_op:
        if "store_profile" not in column_names:
            batch_op.add_column(sa.Column("store_profile", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    column_names = _column_names(bind, "planning_projects")
    with op.batch_alter_table("planning_projects") as batch_op:
        if "store_profile" in column_names:
            batch_op.drop_column("store_profile")
