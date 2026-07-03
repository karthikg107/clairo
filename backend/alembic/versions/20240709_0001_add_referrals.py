"""add referrals table and users.bonus_analyses

Revision ID: 20240709_0001
Revises: 20240708_0001
Create Date: 2024-07-09 00:00:00.000000

CLR-044 — referral programme.

- users.bonus_analyses extends the free-tier lifetime limit
  (limit = 2 + bonus_analyses, see app/services/quota.py).
- referrals rows are created when a referred user claims a referral
  after sign-up (pending), and completed when they finish their first
  analysis — at which point both sides earn 1 bonus analysis, capped
  at 10 earned bonuses per referrer.
- referred_user_id is UNIQUE: a user can only ever be referred once.
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "20240709_0001"
down_revision = "20240708_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("bonus_analyses", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "referrals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "referrer_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "referred_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "bonus_granted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("referrals")
    op.drop_column("users", "bonus_analyses")
