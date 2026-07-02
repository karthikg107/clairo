"""add language preferences to users

Revision ID: 20240706_0001
Revises: 20240705_0001
Create Date: 2024-07-06 00:00:00.000000

CLR-024 — account settings needs somewhere to save a user's preferred
document/output language and country, so the upload flow (CLR-014) can
be pre-filled next time instead of asking every time.
"""
from alembic import op
import sqlalchemy as sa

revision = "20240706_0001"
down_revision = "20240705_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("doc_language", sa.String(10), nullable=True))
    op.add_column("users", sa.Column("output_language", sa.String(10), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(2), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "country")
    op.drop_column("users", "output_language")
    op.drop_column("users", "doc_language")
