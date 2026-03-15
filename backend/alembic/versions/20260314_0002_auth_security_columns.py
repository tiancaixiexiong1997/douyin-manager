"""add auth security columns

Revision ID: 20260314_0002
Revises: 20260314_0001
Create Date: 2026-03-14 00:10:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260314_0002"
down_revision = "20260314_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users") as batch:
        if "failed_login_attempts" not in cols:
            batch.add_column(sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
        if "locked_until" not in cols:
            batch.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users") as batch:
        if "locked_until" in cols:
            batch.drop_column("locked_until")
        if "failed_login_attempts" in cols:
            batch.drop_column("failed_login_attempts")
