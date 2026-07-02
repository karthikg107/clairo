"""update subscription tiers to four real tiers, add billing interval

Revision ID: 20240704_0001
Revises: 20240703_0001
Create Date: 2024-07-04 00:00:00.000000

CLR-026 — Stripe subscription billing.

Replaces the placeholder subscription_tier_enum (free/pro/enterprise)
with the real four product tiers (free/starter/pro/team). Existing
'enterprise' rows are migrated to 'team' — there are no production
subscribers at this stage of the project, but this keeps the migration
safe regardless.

Also adds billing_interval (monthly/annual, null for the free tier)
and stripe_price_id to subscriptions, needed to track which of the two
price variants a paid subscriber is on.
"""
from alembic import op
import sqlalchemy as sa

revision = "20240704_0001"
down_revision = "20240703_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Replace subscription_tier_enum: free/pro/enterprise -> free/starter/pro/team ──
    op.execute("CREATE TYPE subscription_tier_enum_new AS ENUM ('free', 'starter', 'pro', 'team')")
    op.execute("ALTER TABLE subscriptions ADD COLUMN tier_new subscription_tier_enum_new")
    op.execute("""
        UPDATE subscriptions
        SET tier_new = (CASE tier::text
            WHEN 'enterprise' THEN 'team'
            ELSE tier::text
        END)::subscription_tier_enum_new
    """)
    op.execute("ALTER TABLE subscriptions ALTER COLUMN tier_new SET NOT NULL")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN tier_new SET DEFAULT 'free'")
    op.execute("ALTER TABLE subscriptions DROP COLUMN tier")
    op.execute("ALTER TABLE subscriptions RENAME COLUMN tier_new TO tier")
    op.execute("DROP TYPE subscription_tier_enum")
    op.execute("ALTER TYPE subscription_tier_enum_new RENAME TO subscription_tier_enum")

    # ── New columns: billing interval + Stripe price id ───────────────────────
    op.execute("CREATE TYPE billing_interval_enum AS ENUM ('monthly', 'annual')")
    op.add_column(
        "subscriptions",
        sa.Column(
            "billing_interval",
            sa.Enum("monthly", "annual", name="billing_interval_enum", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "subscriptions",
        sa.Column("stripe_price_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "stripe_price_id")
    op.drop_column("subscriptions", "billing_interval")
    op.execute("DROP TYPE IF EXISTS billing_interval_enum")

    op.execute("CREATE TYPE subscription_tier_enum_old AS ENUM ('free', 'pro', 'enterprise')")
    op.execute("ALTER TABLE subscriptions ADD COLUMN tier_old subscription_tier_enum_old")
    op.execute("""
        UPDATE subscriptions
        SET tier_old = (CASE tier::text
            WHEN 'starter' THEN 'free'
            WHEN 'team' THEN 'enterprise'
            ELSE tier::text
        END)::subscription_tier_enum_old
    """)
    op.execute("ALTER TABLE subscriptions ALTER COLUMN tier_old SET NOT NULL")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN tier_old SET DEFAULT 'free'")
    op.execute("ALTER TABLE subscriptions DROP COLUMN tier")
    op.execute("ALTER TABLE subscriptions RENAME COLUMN tier_old TO tier")
    op.execute("DROP TYPE subscription_tier_enum")
    op.execute("ALTER TYPE subscription_tier_enum_old RENAME TO subscription_tier_enum")
