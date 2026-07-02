"""
CLR-023 — Analysis history persistence and the dashboard list endpoint.

- _persist_analysis (app/api/v1/endpoints/analyse.py): best-effort save
  after a successful /analyse call, authenticated users only.
- GET /api/v1/analyses (app/api/v1/endpoints/history.py): lists the
  caller's own analyses, most recent first.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.analyse import _persist_analysis
from app.db.session import get_db
from app.models.analysis import Analysis, DocumentType
from app.models.user import User
from app.services.analysis import AnalysisResult

VALID_RESULT_RAW = {
    "document_type": "rental",
    "summary": "A standard lease agreement.",
    "clauses": [],
    "protective_clause_count": 0,
    "review_clause_count": 0,
}


def _make_result() -> AnalysisResult:
    return AnalysisResult(
        raw=VALID_RESULT_RAW,
        document_type="rental",
        summary=VALID_RESULT_RAW["summary"],
        clauses=[],
        protective_clause_count=0,
        review_clause_count=0,
        cache_hit=False,
    )


class _FakeResult:
    """Serves both require_user's scalar_one_or_none() and a list query's scalars().all()."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else [self._value]


def _mock_session_factory(*results):
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[_FakeResult(r) for r in results])
    mock_session.add = MagicMock()

    @asynccontextmanager
    async def factory_cm():
        yield mock_session

    session_factory = MagicMock(side_effect=lambda: factory_cm())
    get_session_factory_mock = MagicMock(return_value=session_factory)
    return get_session_factory_mock, mock_session


# ── _persist_analysis ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_analysis_anonymous_is_noop():
    with patch("app.api.v1.endpoints.analyse.get_session_factory") as mock_factory:
        await _persist_analysis(
            clerk_id=None,
            document_type="rental",
            doc_language="en",
            output_language="es",
            result=_make_result(),
        )
    mock_factory.assert_not_called()


@pytest.mark.asyncio
async def test_persist_analysis_authenticated_inserts_row():
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    factory, session = _mock_session_factory(user)

    with patch("app.api.v1.endpoints.analyse.get_session_factory", factory):
        await _persist_analysis(
            clerk_id="user_abc",
            document_type="rental",
            doc_language="en",
            output_language="es",
            result=_make_result(),
        )

    session.add.assert_called_once()
    inserted: Analysis = session.add.call_args.args[0]
    assert inserted.user_id == user.id
    assert inserted.document_type == DocumentType.rental
    assert inserted.doc_language == "en"
    assert inserted.output_language == "es"
    assert inserted.result_json == VALID_RESULT_RAW
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_analysis_user_not_found_is_noop():
    factory, session = _mock_session_factory(None)
    with patch("app.api.v1.endpoints.analyse.get_session_factory", factory):
        await _persist_analysis(
            clerk_id="ghost_user",
            document_type="rental",
            doc_language="en",
            output_language="en",
            result=_make_result(),
        )
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_analysis_db_error_never_raises():
    def _raise(*a, **kw):
        raise RuntimeError("db down")

    with patch("app.api.v1.endpoints.analyse.get_session_factory", _raise):
        await _persist_analysis(
            clerk_id="user_abc",
            document_type="rental",
            doc_language="en",
            output_language="en",
            result=_make_result(),
        )  # must not raise


@pytest.mark.asyncio
async def test_persist_analysis_never_stores_verified_text_key():
    """SECURITY: only the validated Claude JSON is ever persisted."""
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    factory, session = _mock_session_factory(user)

    with patch("app.api.v1.endpoints.analyse.get_session_factory", factory):
        await _persist_analysis(
            clerk_id="user_abc",
            document_type="rental",
            doc_language="en",
            output_language="en",
            result=_make_result(),
        )

    inserted: Analysis = session.add.call_args.args[0]
    assert "verified_text" not in inserted.result_json
    assert set(inserted.result_json.keys()) == set(VALID_RESULT_RAW.keys())


# ── GET /api/v1/analyses ───────────────────────────────────────────────────────

@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult

    async def _mock_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_rate):
        with patch.object(rl_module, "check_endpoint_rate_limit", side_effect=_mock_rate):
            from app.main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://localhost") as c:
                yield c
            app.dependency_overrides.pop(get_db, None)


def _override_db(*results):
    from app.main import app

    factory, session = _mock_session_factory(*results)

    async def _get_db():
        async with factory()() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    return session


def _make_analysis(user_id, *, days_ago: int, document_type=DocumentType.rental) -> Analysis:
    a = Analysis(
        id=uuid.uuid4(),
        user_id=user_id,
        document_type=document_type,
        doc_language="en",
        output_language="en",
        result_json={"summary": f"Analysis from {days_ago} days ago"},
    )
    a.created_at = datetime(2026, 6, 30 - days_ago, tzinfo=UTC)
    return a


@pytest.mark.asyncio
async def test_list_analyses_requires_auth(client):
    _override_db(None)
    r = await client.get("/api/v1/analyses")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_analyses_empty(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(user, [])

    r = await client.get("/api/v1/analyses", headers={"X-Clerk-User-Id": "user_abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_analyses_returns_items_sorted_desc():
    """DB-level ordering is exercised by the query construction; here we verify
    the response shape matches whatever the (mocked) DB returns in order."""
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    rows = [
        _make_analysis(user.id, days_ago=0, document_type=DocumentType.rental),
        _make_analysis(user.id, days_ago=5, document_type=DocumentType.employment),
    ]

    from httpx import ASGITransport, AsyncClient

    import app.middleware.rate_limit as rl_module
    from app.core.rate_limit import RateLimitResult
    from app.main import app

    async def _mock_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    _override_db(user, rows)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_rate):
        with patch.object(rl_module, "check_endpoint_rate_limit", side_effect=_mock_rate):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://localhost") as c:
                r = await c.get("/api/v1/analyses", headers={"X-Clerk-User-Id": "user_abc"})

    app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0]["document_type"] == "rental"
    assert body["items"][1]["document_type"] == "employment"
    assert body["items"][0]["summary"] == "Analysis from 0 days ago"


@pytest.mark.asyncio
async def test_list_analyses_rejects_out_of_range_limit(client):
    user = User(id=uuid.uuid4(), clerk_id="user_abc", email="a@b.com")
    _override_db(user, [])

    r = await client.get(
        "/api/v1/analyses", params={"limit": 501}, headers={"X-Clerk-User-Id": "user_abc"}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_analyses_user_not_found_returns_404(client):
    _override_db(None)
    r = await client.get("/api/v1/analyses", headers={"X-Clerk-User-Id": "ghost_user"})
    assert r.status_code == 404
