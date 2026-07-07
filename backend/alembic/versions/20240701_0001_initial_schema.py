"""Initial schema — users, subscriptions, analyses, audit_log.

Revision ID: 0001
Revises: 
Create Date: 2024-07-01

SECURITY:
- NO document content columns exist anywhere in this schema
- audit_log: app user has INSERT only (enforced via REVOKE/GRANT below)
- GDPR: gdpr_delete_user() function performs immediate hard delete
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Self-healing bootstrap ────────────────────────────────────────────────
    # This is the initial migration (down_revision=None): Alembic only runs it
    # when NO revision is recorded yet, i.e. against an empty database or one
    # left half-built by an interrupted earlier run (which carries no real
    # data, since the migration never completed). Drop any leftover objects
    # first so a redeploy self-heals without a manual database reset.
    op.execute("DROP TABLE IF EXISTS audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS analyses CASCADE")
    op.execute("DROP TABLE IF EXISTS subscriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TYPE IF EXISTS document_type_enum")
    op.execute("DROP TYPE IF EXISTS subscription_status_enum")
    op.execute("DROP TYPE IF EXISTS subscription_tier_enum")

    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE subscription_tier_enum AS ENUM
            ('free', 'pro', 'enterprise')
    """)
    op.execute("""
        CREATE TYPE subscription_status_enum AS ENUM
            ('active', 'canceled', 'past_due', 'trialing', 'unpaid')
    """)
    op.execute("""
        CREATE TYPE document_type_enum AS ENUM
            ('rental', 'employment', 'freelance', 'tos', 'other_permitted')
    """)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clerk_id", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_users_clerk_id", "users", ["clerk_id"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"],
                    postgresql_where=sa.text("deleted_at IS NOT NULL"))

    # ── subscriptions ─────────────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "tier",
            postgresql.ENUM("free", "pro", "enterprise", name="subscription_tier_enum",
                            create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "canceled", "past_due", "trialing", "unpaid",
                            name="subscription_status_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions",
                    ["stripe_customer_id"])

    # ── analyses ──────────────────────────────────────────────────────────────
    # SECURITY: no document_content, raw_text, ocr_text, or extracted_text columns
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_type",
            postgresql.ENUM("rental", "employment", "freelance", "tos", "other_permitted",
                            name="document_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        # Structured JSON output only — flags, clauses, summary, risk_score
        sa.Column("result_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_analyses_user_id", "analyses", ["user_id"])
    op.create_index("ix_analyses_created_at", "analyses", ["created_at"])

    # ── audit_log (append-only) ───────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False, index=True
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(128), nullable=False, index=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])

    # ── SECURITY: restrict audit_log to INSERT-only for app user ──────────────
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'clairo_app') THEN
                REVOKE UPDATE, DELETE ON audit_log FROM clairo_app;
                GRANT INSERT, SELECT ON audit_log TO clairo_app;
            END IF;
        END$$
    """)

    # ── GDPR: immediate hard-delete function ──────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gdpr_delete_user(p_user_id UUID)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            -- Cascade deletes analyses and subscription (FK ON DELETE CASCADE)
            DELETE FROM users WHERE id = p_user_id;
            -- audit_log rows kept (SET NULL on user_id) for compliance
            INSERT INTO audit_log (id, action, metadata_json, user_id)
            VALUES (gen_random_uuid(), 'gdpr.user_deleted',
                    jsonb_build_object('deleted_user_id', p_user_id), NULL);
        END;
        $$
    """)

    # ── updated_at trigger ────────────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in ("users", "subscriptions", "analyses"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """)


def downgrade() -> None:
    for table in ("users", "subscriptions", "analyses"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS gdpr_delete_user(UUID)")
    op.drop_table("audit_log")
    op.drop_table("analyses")
    op.drop_table("subscriptions")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS document_type_enum")
    op.execute("DROP TYPE IF EXISTS subscription_status_enum")
    op.execute("DROP TYPE IF EXISTS subscription_tier_enum")
