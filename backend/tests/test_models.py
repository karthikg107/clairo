"""Tests for model definitions — no DB connection needed."""
import inspect
import pytest
from sqlalchemy import inspect as sa_inspect

from app.models import Base, User, Subscription, Analysis, AuditLog


def column_names(model) -> set[str]:
    return {c.key for c in sa_inspect(model).mapper.column_attrs}


def test_user_has_required_columns():
    cols = column_names(User)
    assert {"id", "clerk_id", "email", "created_at", "updated_at", "deleted_at"} <= cols


def test_user_has_free_analyses_used_column():
    """CLR-025 — lifetime free-tier quota counter."""
    cols = column_names(User)
    assert "free_analyses_used" in cols


def test_user_has_no_document_content_columns():
    """SECURITY: user table must never contain document content."""
    cols = column_names(User)
    forbidden = {"document_content", "raw_text", "ocr_text", "extracted_text", "content"}
    assert cols.isdisjoint(forbidden), f"Forbidden columns found: {cols & forbidden}"


def test_analysis_has_no_document_content_columns():
    """SECURITY: analyses table must never contain document content."""
    cols = column_names(Analysis)
    forbidden = {"document_content", "raw_text", "ocr_text", "extracted_text", "content"}
    assert cols.isdisjoint(forbidden), f"Forbidden columns found: {cols & forbidden}"


def test_analysis_has_language_pair_columns():
    """CLR-023 — dashboard history needs the full language pair, not one locale field."""
    cols = column_names(Analysis)
    assert {"doc_language", "output_language"} <= cols
    assert "locale" not in cols


def test_analysis_has_result_json():
    cols = column_names(Analysis)
    assert "result_json" in cols


def test_audit_log_has_no_updated_at():
    """audit_log is append-only — no updated_at column."""
    cols = column_names(AuditLog)
    assert "updated_at" not in cols


def test_audit_log_has_required_columns():
    cols = column_names(AuditLog)
    assert {"id", "created_at", "action", "metadata_json", "user_id"} <= cols


def test_subscription_tier_enum_values():
    """CLR-026 — the four real product tiers: Free, Starter, Pro, Team."""
    from app.models.subscription import SubscriptionTier
    assert set(SubscriptionTier) == {
        SubscriptionTier.free, SubscriptionTier.starter,
        SubscriptionTier.pro, SubscriptionTier.team,
    }


def test_billing_interval_enum_values():
    from app.models.subscription import BillingInterval
    assert set(BillingInterval) == {BillingInterval.monthly, BillingInterval.annual}


def test_subscription_has_billing_columns():
    cols = column_names(Subscription)
    assert {"billing_interval", "stripe_price_id", "stripe_customer_id",
            "stripe_subscription_id"} <= cols


def test_document_type_enum_excludes_prohibited():
    """Prohibited document types must never reach the DB."""
    from app.models.analysis import DocumentType
    values = {t.value for t in DocumentType}
    assert "prohibited" not in values
    assert "other_permitted" in values


def test_all_models_registered_in_metadata():
    tables = set(Base.metadata.tables.keys())
    assert {"users", "subscriptions", "analyses", "audit_log"} <= tables
