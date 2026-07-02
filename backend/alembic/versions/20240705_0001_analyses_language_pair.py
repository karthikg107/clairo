"""replace locale with doc_language/output_language on analyses

Revision ID: 20240705_0001
Revises: 20240704_0001
Create Date: 2024-07-05 00:00:00.000000

CLR-023 — user dashboard needs the full language pair (document language
-> explanation language) for each past analysis, not just a single
"locale" field. The analyses table has never had a row written to it
(confirmed: no INSERT existed anywhere in the codebase before CLR-023),
so this is a safe structural change, not a lossy data migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "20240705_0001"
down_revision = "20240704_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("doc_language", sa.String(10), nullable=True))
    op.add_column("analyses", sa.Column("output_language", sa.String(10), nullable=True))
    op.execute("UPDATE analyses SET doc_language = locale, output_language = locale")
    op.alter_column("analyses", "doc_language", nullable=False)
    op.alter_column("analyses", "output_language", nullable=False)
    op.drop_column("analyses", "locale")


def downgrade() -> None:
    op.add_column("analyses", sa.Column("locale", sa.String(10), nullable=True))
    op.execute("UPDATE analyses SET locale = output_language")
    op.alter_column("analyses", "locale", nullable=False)
    op.drop_column("analyses", "output_language")
    op.drop_column("analyses", "doc_language")
