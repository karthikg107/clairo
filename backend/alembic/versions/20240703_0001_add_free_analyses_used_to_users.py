"""add free_analyses_used to users

Revision ID: 20240703_0001
Revises: 20240702_0001
Create Date: 2024-07-03 00:00:00.000000

Adds free_analyses_used to the users table (CLR-025) — tracks the
lifetime count of free-tier analyses an authenticated user has consumed.
"""
import sqlalchemy as sa

from alembic import op

revision = "20240703_0001"
down_revision = "20240702_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "free_analyses_used", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "free_analyses_used")
