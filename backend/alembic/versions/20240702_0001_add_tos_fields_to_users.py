"""add tos fields to users

Revision ID: 20240702_0001
Revises: 0001
Create Date: 2024-07-02 00:00:00.000000

Adds tos_accepted_at and tos_version to the users table (CLR-022).
"""
import sqlalchemy as sa

from alembic import op

revision = "20240702_0001"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tos_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("tos_version", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "tos_version")
    op.drop_column("users", "tos_accepted_at")
