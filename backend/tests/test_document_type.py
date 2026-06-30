"""
Tests for CLR-013 — Document type detection.
All Claude API calls are mocked.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document_type import (
    DocumentType,
    PERMITTED_TYPES,
    PROHIBITED_TYPES,
    PROHIBITED_REFERRALS,
    _first_500_words,
    detect_document_type,
)


# ── Constants ─────────────────────────────────────────────────────────────────

class TestDocumentTypeEnum:
    def test_prohibited_set_complete(self):
        assert DocumentType.COURT_ORDER in PROHIBITED_TYPES
        assert DocumentType.IMMIGRATION in PROHIBITED_TYPES
        assert DocumentType.MEDICAL_CONSENT in PROHIBITED_TYPES
        assert DocumentType.FINANCIAL_INSTRUMENT in PROHIBITED_TYPES
        assert DocumentType.MINOR_INVOLVED in PROHIBITED_TYPES

    def test_permitted_set_complete(self):
        assert DocumentType.RENTAL in PERMITTED_TYPES
        assert DocumentType.EMPLOYMENT in PERMITTED_TYPES
        assert DocumentType.FREELANCE in PERMITTED_TYPES
        assert DocumentType.TOS in PERMITTED_TYPES
        assert DocumentType.OTHER_PERMITTED in PERMITTED_TYPES

    def test_prohibited_and_permitted_disjoint(self):
        assert PROHIBITED_TYPES.isdisjoint(PERMITTED_TYPES)

    def test_all_types_in_one_set(self):
        all_types = set(DocumentType)
        assert all_types == PROHIBITED_TYPES | PERMITTED_TYPES

    def test_referrals_cover_all_prohibited(self):
        for t in PROHIBITED_TYPES:
            assert t in PROHIBITED_REFERRALS, f"Missing referral for {t}"

    def test_referrals_have_required_fields(self):
        for t, ref in PROHIBITED_REFERRALS.items():
            assert "org" in ref
            assert "url" in ref
            assert "reason_key" in ref


# ── _first_500_words ──────────────────────────────────────────────────────────

class TestFirst500Words:
    def test_exact_count(self):
        text = " ".join(f"word{i}" for i in range(600))
        result = _first_500_words(text)
        assert len(result.split()) == 500

    def test_shorter_than_500(self):
        text = "hello world"
        assert _first_500_words(text) == text


# ── detect_document_type ──────────────────────────────────────────────────────

def _mock_claude_response(doc_type: str, confidence: float = 0.95) -> MagicMock:
    content = MagicMock()
    content.text = json.dumps({
        "document_type": doc_type,
        "confidence": confidence,
        "reasoning": "Test classification",
    })
    msg = MagicMock()
    msg.content = [content]
    return msg


@pytest.mark.asyncio
async def test_rental_classified():
    with patch("app.services.document_type.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=_mock_claude_response("rental"))

        result = await detect_document_type("This is a lease agreement.")

    assert result.document_type == DocumentType.RENTAL
    assert result.is_prohibited is False
    assert result.referral is None


@pytest.mark.asyncio
async def test_employment_classified():
    with patch("app.services.document_type.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=_mock_claude_response("employment"))
        result = await detect_document_type("This is an employment contract.")

    assert result.document_type == DocumentType.EMPLOYMENT
    assert result.is_prohibited is False


@pytest.mark.parametrize("prohibited_type,expected_referral_org", [
    ("court_order", "Legal Aid Society"),
    ("immigration", "UNHCR"),
    ("medical_consent", "Patient Advocate Foundation"),
    ("financial_instrument", "CFPB"),
    ("minor_involved", "Legal Aid Society"),
])
@pytest.mark.asyncio
async def test_prohibited_type_blocked(prohibited_type, expected_referral_org):
    with patch("app.services.document_type.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            return_value=_mock_claude_response(prohibited_type)
        )
        result = await detect_document_type("Some document text here.")

    assert result.is_prohibited is True
    assert result.referral is not None
    assert result.referral["org"] == expected_referral_org


@pytest.mark.asyncio
async def test_invalid_json_raises():
    bad_content = MagicMock()
    bad_content.text = "not json at all"
    bad_msg = MagicMock()
    bad_msg.content = [bad_content]

    with patch("app.services.document_type.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=bad_msg)

        with pytest.raises(ValueError, match="non-JSON"):
            await detect_document_type("Some text.")


@pytest.mark.asyncio
async def test_unknown_type_raises():
    with patch("app.services.document_type.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            return_value=_mock_claude_response("banana_contract")
        )

        with pytest.raises(ValueError, match="Unknown document type"):
            await detect_document_type("Some text.")


@pytest.mark.asyncio
async def test_prohibited_has_no_quota_decrement_marker():
    """
    Verify prohibited results carry is_prohibited=True so callers know
    NOT to decrement the quota. This is the contract the analysis
    endpoint must respect.
    """
    with patch("app.services.document_type.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(
            return_value=_mock_claude_response("court_order")
        )
        result = await detect_document_type("Court order text here.")

    # Callers check result.is_prohibited before decrementing quota
    assert result.is_prohibited is True
    # Confirm referral URL is safe (external, not internal)
    assert result.referral["url"].startswith("http")


# ── POST /api/v1/classify ─────────────────────────────────────────────────────

@pytest.fixture
async def client():
    from unittest.mock import patch
    from httpx import ASGITransport, AsyncClient
    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult

    async def _mock_check_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_check_rate):
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            yield c


@pytest.mark.asyncio
async def test_classify_endpoint_rental(client):
    with patch("app.api.v1.endpoints.classify.detect_document_type", new_callable=AsyncMock) as mock_dt:
        from app.services.document_type import DocumentTypeResult, DocumentType
        mock_dt.return_value = DocumentTypeResult(
            document_type=DocumentType.RENTAL,
            is_prohibited=False,
            confidence=0.97,
            reasoning="Lease agreement",
            referral=None,
        )
        r = await client.post("/api/v1/classify", json={"text": "This is a lease agreement " * 5})

    assert r.status_code == 200
    body = r.json()
    assert body["document_type"] == "rental"
    assert body["is_prohibited"] is False
    assert body["referral"] is None


@pytest.mark.asyncio
async def test_classify_endpoint_prohibited_returns_referral(client):
    with patch("app.api.v1.endpoints.classify.detect_document_type", new_callable=AsyncMock) as mock_dt:
        from app.services.document_type import DocumentTypeResult, DocumentType, PROHIBITED_REFERRALS
        mock_dt.return_value = DocumentTypeResult(
            document_type=DocumentType.IMMIGRATION,
            is_prohibited=True,
            confidence=0.91,
            reasoning="Immigration petition",
            referral=PROHIBITED_REFERRALS[DocumentType.IMMIGRATION],
        )
        r = await client.post("/api/v1/classify", json={"text": "Immigration petition text " * 5})

    assert r.status_code == 200
    body = r.json()
    assert body["is_prohibited"] is True
    assert body["referral"]["org"] == "UNHCR"
    assert body["referral"]["url"].startswith("http")


@pytest.mark.asyncio
async def test_classify_endpoint_short_text_422(client):
    r = await client.post("/api/v1/classify", json={"text": "hi"})
    assert r.status_code == 422
