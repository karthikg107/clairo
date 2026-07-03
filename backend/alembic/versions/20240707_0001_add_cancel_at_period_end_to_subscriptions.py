"""add cancel_at_period_end to subscriptions

Revision ID: 20240707_0001
Revises: 20240706_0001
Create Date: 2024-07-07 00:00:00.000000

CLR-029 — cancellation keeps access until the current billing period ends
(Stripe's cancel_at_period_end), rather than revoking access immediately.
This column mirrors that flag locally so the dashboard/billing UI can show
"cancels on <date>" and offer a reactivate action without a Stripe round
trip on every page load.
"""
import sqlalchemy as sa

from alembic import op

revision = "20240707_0001"
down_revision = "20240706_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "cancel_at_period_end")
