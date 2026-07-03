"""
CLR-041 — Shareable analysis link generation.

- POST /share-links creates a link for the caller's own analysis
  (reusing an existing active one), 404 for someone else's analysis.
- GET /shared/{id} serves ONLY sanitized output — never original_text,
  numbers, OCR text, or any user identity.
- Unknown, expired, and revoked links return byte-identical 404 bodies
  (anti-enumeration).
- Revocation is instant; links auto-expire after 30 days.
- Per-link rate limit: 100 views/hour keyed by share id.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.models.analysis import Analysis, DocumentType
from app.models.share_link import SHARE_LINK_TTL_DAYS, ShareLink
from app.models.user import User
from app.services.sharing import (
    ShareLinkNotFoundError,
    SharingError,
    create_share_link,
    get_shared_analysis,
    revoke_share_link,
    sanitize_result_for_share,
)

RESULT_JSON = {
    "document_type": "rental",
    "summary": "A one-year lease with a high deposit.",
    "clauses": [
        {
            "id": "c1",
            "title": "Deposit",
            "original_text": "VERBATIM DOCUMENT EXCERPT — must never leave the DB",
            "explanation": "You pay three months upfront.",
            "frequency_pct": 60,
            "is_protective": False,
            "flag_level": "review",
            "numbers": [{"value": "€3000", "context": "deposit amount"}],
        }
    ],
    "protective_clause_count": 0,
    "review_clause_count": 1,
}


class _FakeResult:
    def __init__(self, value, *, many=False):
        self._value = value
        self._many = many

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return list(self._value or [])

    def first(self):
        return self._value


class FakeSession:
    def __init__(self, *results):
        self._results = list(results)
        self.added = []
        self.committed = False

    async def execute(self, *_args, **_kwargs):
        value = self._results.pop(0) if self._results else None
        return value if isinstance(value, _FakeResult) else _FakeResult(value)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def _make_user() -> User:
    return User(id=uuid.uuid4(), clerk_id="user_abc", email="test@example.com")


def _make_analysis(user: User) -> Analysis:
    a = Analysis(
        id=uuid.uuid4(),
        user_id=user.id,
        document_type=DocumentType.rental,
        doc_language="de",
        output_language="en",
        result_json=RESULT_JSON,
    )
    a.created_at = datetime(2026, 7, 1, tzinfo=UTC)
    return a


def _make_link(analysis: Analysis, **overrides) -> ShareLink:
    link = ShareLink(
        id=uuid.uuid4(),
        analysis_id=analysis.id,
        expires_at=datetime.now(UTC) + timedelta(days=SHARE_LINK_TTL_DAYS),
        is_revoked=False,
    )
    for k, v in overrides.items():
        setattr(link, k, v)
    return link


# ── sanitize_result_for_share ──────────────────────────────────────────────────

def test_sanitizer_strips_original_text_and_numbers():
    out = sanitize_result_for_share(RESULT_JSON)
    dumped = json.dumps(out)
    assert "VERBATIM" not in dumped
    assert "original_text" not in dumped
    assert "numbers" not in dumped
    assert "€3000" not in dumped
    # Safe fields survive
    assert out["summary"] == RESULT_JSON["summary"]
    assert out["clauses"][0]["explanation"] == "You pay three months upfront."
    assert out["clauses"][0]["frequency_pct"] == 60
    assert out["clauses"][0]["flag_level"] == "review"


def test_sanitizer_is_a_whitelist_unknown_keys_dropped():
    data = dict(RESULT_JSON)
    data["clauses"] = [dict(RESULT_JSON["clauses"][0], leaked_future_field="oops")]
    data["another_new_top_key"] = "oops"
    out = sanitize_result_for_share(data)
    dumped = json.dumps(out)
    assert "leaked_future_field" not in dumped
    assert "another_new_top_key" not in dumped


# ── create_share_link ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_link_for_own_analysis():
    user = _make_user()
    analysis = _make_analysis(user)
    session = FakeSession(analysis, _FakeResult([]))  # analysis lookup, no existing links

    link = await create_share_link(session, user=user, analysis_id=analysis.id)

    assert link.analysis_id == analysis.id
    assert session.committed is True
    assert link in session.added


@pytest.mark.asyncio
async def test_create_link_rejects_someone_elses_analysis():
    user = _make_user()
    other = _make_user()
    analysis = _make_analysis(other)  # belongs to someone else
    session = FakeSession(analysis)

    with pytest.raises(SharingError):
        await create_share_link(session, user=user, analysis_id=analysis.id)


@pytest.mark.asyncio
async def test_create_link_reuses_existing_active_link():
    user = _make_user()
    analysis = _make_analysis(user)
    existing = _make_link(analysis)
    session = FakeSession(analysis, _FakeResult([existing]))

    link = await create_share_link(session, user=user, analysis_id=analysis.id)

    assert link is existing
    assert session.added == []  # nothing new minted


@pytest.mark.asyncio
async def test_create_link_mints_new_when_existing_is_expired():
    user = _make_user()
    analysis = _make_analysis(user)
    expired = _make_link(analysis, expires_at=datetime.now(UTC) - timedelta(days=1))
    session = FakeSession(analysis, _FakeResult([expired]))

    link = await create_share_link(session, user=user, analysis_id=analysis.id)

    assert link is not expired
    assert link in session.added


# ── revoke_share_link ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_revoke_own_link():
    user = _make_user()
    analysis = _make_analysis(user)
    link = _make_link(analysis)
    session = FakeSession(_FakeResult((link, analysis)))

    await revoke_share_link(session, user=user, share_id=link.id)

    assert link.is_revoked is True
    assert session.committed is True


@pytest.mark.asyncio
async def test_revoke_rejects_someone_elses_link():
    user = _make_user()
    other = _make_user()
    analysis = _make_analysis(other)
    link = _make_link(analysis)
    session = FakeSession(_FakeResult((link, analysis)))

    with pytest.raises(SharingError):
        await revoke_share_link(session, user=user, share_id=link.id)
    assert link.is_revoked is False


# ── get_shared_analysis ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shared_payload_is_sanitized_and_has_metadata():
    user = _make_user()
    analysis = _make_analysis(user)
    link = _make_link(analysis)
    session = FakeSession(_FakeResult((link, analysis)))

    payload = await get_shared_analysis(session, share_id=link.id)

    dumped = json.dumps(payload)
    assert "VERBATIM" not in dumped
    assert "original_text" not in dumped
    assert "numbers" not in dumped
    # No user identity anywhere
    assert "user" not in dumped
    assert "clerk" not in dumped
    assert "email" not in dumped
    # Metadata the shared page needs (CLR-042)
    assert payload["document_type"] == "rental"
    assert payload["doc_language"] == "de"
    assert payload["output_language"] == "en"
    assert payload["analysed_at"].startswith("2026-07-01")
    assert "expires_at" in payload


@pytest.mark.asyncio
async def test_shared_unknown_expired_revoked_are_indistinguishable():
    user = _make_user()
    analysis = _make_analysis(user)
    expired = _make_link(analysis, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    revoked = _make_link(analysis, is_revoked=True)

    for session in (
        FakeSession(_FakeResult(None)),                    # unknown
        FakeSession(_FakeResult((expired, analysis))),     # expired
        FakeSession(_FakeResult((revoked, analysis))),     # revoked
    ):
        with pytest.raises(ShareLinkNotFoundError):
            await get_shared_analysis(session, share_id=uuid.uuid4())


# ── endpoints ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult
    from app.db.session import get_db

    async def _mock_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_rate):
        with patch.object(rl_module, "check_endpoint_rate_limit", side_effect=_mock_rate):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://localhost") as c:
                yield c
            app.dependency_overrides.pop(get_db, None)


def _override_db(session: FakeSession):
    from app.db.session import get_db
    from app.main import app

    async def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db


@pytest.mark.asyncio
async def test_create_endpoint_returns_share_path(client):
    user = _make_user()
    analysis = _make_analysis(user)
    _override_db(FakeSession(user, analysis, _FakeResult([])))

    r = await client.post(
        "/api/v1/share-links",
        json={"analysis_id": str(analysis.id)},
        headers={"X-Clerk-User-Id": "user_abc"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["share_path"] == f"/s/{body['share_id']}"
    assert body["ttl_days"] == 30
    # share_id parses as a UUID (unguessable link space)
    uuid.UUID(body["share_id"])


@pytest.mark.asyncio
async def test_create_endpoint_404_for_foreign_analysis(client):
    user = _make_user()
    other = _make_user()
    analysis = _make_analysis(other)
    _override_db(FakeSession(user, analysis))

    r = await client.post(
        "/api/v1/share-links",
        json={"analysis_id": str(analysis.id)},
        headers={"X-Clerk-User-Id": "user_abc"},
    )

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_shared_endpoint_serves_sanitized_payload(client):
    user = _make_user()
    analysis = _make_analysis(user)
    link = _make_link(analysis)
    _override_db(FakeSession(_FakeResult((link, analysis))))

    with patch(
        "app.api.v1.endpoints.share.check_endpoint_rate_limit"
    ) as mock_rate:
        from app.core.rate_limit import RateLimitResult
        mock_rate.return_value = RateLimitResult(
            allowed=True, limit=100, remaining=99, reset_in_seconds=3600
        )
        r = await client.get(f"/api/v1/shared/{link.id}")

    assert r.status_code == 200
    dumped = r.text
    assert "VERBATIM" not in dumped
    assert "original_text" not in dumped
    assert "numbers" not in dumped
    body = r.json()
    assert body["summary"] == RESULT_JSON["summary"]
    # Per-link rate limit keyed by the share id itself
    assert mock_rate.call_args.kwargs["identifier"] == str(link.id)
    assert mock_rate.call_args.kwargs["endpoint"] == "share_link"


@pytest.mark.asyncio
async def test_shared_endpoint_expired_and_revoked_and_unknown_identical(client):
    user = _make_user()
    analysis = _make_analysis(user)
    expired = _make_link(analysis, expires_at=datetime.now(UTC) - timedelta(days=1))
    revoked = _make_link(analysis, is_revoked=True)

    from app.core.rate_limit import RateLimitResult

    bodies = []
    for session in (
        FakeSession(_FakeResult(None)),
        FakeSession(_FakeResult((expired, analysis))),
        FakeSession(_FakeResult((revoked, analysis))),
    ):
        _override_db(session)
        with patch(
            "app.api.v1.endpoints.share.check_endpoint_rate_limit",
            return_value=RateLimitResult(
                allowed=True, limit=100, remaining=99, reset_in_seconds=3600
            ),
        ):
            r = await client.get(f"/api/v1/shared/{uuid.uuid4()}")
        assert r.status_code == 404
        bodies.append(r.text)

    # Anti-enumeration: byte-identical bodies
    assert bodies[0] == bodies[1] == bodies[2]


@pytest.mark.asyncio
async def test_shared_endpoint_rate_limited_returns_429(client):
    user = _make_user()
    analysis = _make_analysis(user)
    link = _make_link(analysis)
    _override_db(FakeSession(_FakeResult((link, analysis))))

    from app.core.rate_limit import RateLimitResult

    with patch(
        "app.api.v1.endpoints.share.check_endpoint_rate_limit",
        return_value=RateLimitResult(
            allowed=False, limit=100, remaining=0, reset_in_seconds=1200
        ),
    ):
        r = await client.get(f"/api/v1/shared/{link.id}")

    assert r.status_code == 429
    assert r.headers["Retry-After"] == "1200"


@pytest.mark.asyncio
async def test_revoke_endpoint(client):
    user = _make_user()
    analysis = _make_analysis(user)
    link = _make_link(analysis)
    _override_db(FakeSession(user, _FakeResult((link, analysis))))

    r = await client.post(
        f"/api/v1/share-links/{link.id}/revoke",
        headers={"X-Clerk-User-Id": "user_abc"},
    )

    assert r.status_code == 204
    assert link.is_revoked is True


def test_share_view_rate_limit_planes_configured():
    """The middleware plane and the per-link plane both exist at spec values."""
    from app.core.rate_limit import _ENDPOINT_HOURLY_LIMITS
    from app.middleware.rate_limit import _endpoint_key

    assert _ENDPOINT_HOURLY_LIMITS["share_link"] == (100, 100)
    assert "share_view" in _ENDPOINT_HOURLY_LIMITS
    assert _endpoint_key("/api/v1/shared/abc") == "share_view"


def test_shared_path_is_public_but_share_links_is_not():
    from app.middleware.jwt_auth import _is_public

    assert _is_public("/api/v1/shared/some-uuid") is True
    assert _is_public("/api/v1/share-links") is False
    assert _is_public("/api/v1/share-links/x/revoke") is False
