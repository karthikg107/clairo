"""add share_links table

Revision ID: 20240708_0001
Revises: 20240707_0001
Create Date: 2024-07-08 00:00:00.000000

CLR-041 — shareable analysis links (/s/[uuid]).

The row id doubles as the public share id in the URL — a random UUIDv4,
so links are unguessable (122 bits of entropy; enumeration is infeasible).

ON DELETE CASCADE from analyses means share links die automatically when
the analysis is deleted — including via GDPR account deletion (CLR-024's
gdpr_delete_user deletes the user's analyses, which cascades here).
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "20240708_0001"
down_revision = "20240707_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
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
    op.drop_table("share_links")
