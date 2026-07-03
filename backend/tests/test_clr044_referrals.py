"""
CLR-044 — Referral programme.

- Claiming records a pending referral; self-referral, unknown referrer,
  and double-claims are rejected.
- Completing the referred user's first analysis grants BOTH users
  1 bonus analysis; the referrer stops earning at 10 bonuses (the
  referred user's bonus is unconditional).
- Bonus analyses extend the free-tier lifetime quota limit.
- Stats endpoint returns the /ref/[userId] link and counts.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.models.referral import MAX_REFERRAL_BONUSES, Referral
from app.models.user import User
from app.services.quota import FREE_LIFETIME_LIMIT, _status_for_user
from app.services.referrals import (
    ReferralError,
    claim_referral,
    complete_pending_referral,
)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
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


def _make_user(bonus: int = 0, used: int = 0) -> User:
    u = User(
        id=uuid.uuid4(),
        clerk_id=f"user_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        free_analyses_used=used,
        bonus_analyses=bonus,
    )
    u.subscription = None
    return u


def _pending_referral(referrer: User, referred: User) -> Referral:
    return Referral(
        id=uuid.uuid4(),
        referrer_user_id=referrer.id,
        referred_user_id=referred.id,
        bonus_granted=False,
        completed_at=None,
    )


# ── claim_referral ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claim_creates_pending_referral():
    referrer = _make_user()
    referred = _make_user()
    session = FakeSession(referrer, None)  # referrer lookup, no existing claim

    referral = await claim_referral(
        session, referred_user=referred, referrer_user_id=referrer.id
    )

    assert referral.referrer_user_id == referrer.id
    assert referral.referred_user_id == referred.id
    assert referral.completed_at is None
    assert referral in session.added
    assert session.committed is True


@pytest.mark.asyncio
async def test_claim_rejects_self_referral():
    user = _make_user()
    session = FakeSession()

    with pytest.raises(ReferralError) as exc:
        await claim_referral(session, referred_user=user, referrer_user_id=user.id)
    assert exc.value.code == "self_referral"


@pytest.mark.asyncio
async def test_claim_rejects_unknown_referrer():
    referred = _make_user()
    session = FakeSession(None)

    with pytest.raises(ReferralError) as exc:
        await claim_referral(
            session, referred_user=referred, referrer_user_id=uuid.uuid4()
        )
    assert exc.value.code == "invalid_referrer"


@pytest.mark.asyncio
async def test_claim_rejects_double_claim():
    referrer = _make_user()
    referred = _make_user()
    existing = _pending_referral(referrer, referred)
    session = FakeSession(referrer, existing)

    with pytest.raises(ReferralError) as exc:
        await claim_referral(
            session, referred_user=referred, referrer_user_id=referrer.id
        )
    assert exc.value.code == "already_claimed"


# ── complete_pending_referral ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_completion_grants_both_users_a_bonus():
    referrer = _make_user()
    referred = _make_user()
    referral = _pending_referral(referrer, referred)
    # queue: referral lookup, referred user, referrer user, granted count
    session = FakeSession(referral, referred, referrer, _FakeResult(0))

    completed = await complete_pending_referral(session, referred_user_id=referred.id)

    assert completed is True
    assert referred.bonus_analyses == 1
    assert referrer.bonus_analyses == 1
    assert referral.bonus_granted is True
    assert referral.completed_at is not None
    assert session.committed is True


@pytest.mark.asyncio
async def test_completion_caps_referrer_at_max_bonuses():
    referrer = _make_user(bonus=MAX_REFERRAL_BONUSES)
    referred = _make_user()
    referral = _pending_referral(referrer, referred)
    session = FakeSession(referral, referred, referrer, _FakeResult(MAX_REFERRAL_BONUSES))

    completed = await complete_pending_referral(session, referred_user_id=referred.id)

    assert completed is True
    # Referred user still gets their bonus...
    assert referred.bonus_analyses == 1
    # ...but the referrer is capped.
    assert referrer.bonus_analyses == MAX_REFERRAL_BONUSES
    assert referral.bonus_granted is False
    assert referral.completed_at is not None


@pytest.mark.asyncio
async def test_completion_noop_without_pending_referral():
    session = FakeSession(None)

    completed = await complete_pending_referral(
        session, referred_user_id=uuid.uuid4()
    )

    assert completed is False
    assert session.committed is False


@pytest.mark.asyncio
async def test_completion_only_fires_once():
    """An already-completed referral is not matched by the pending query."""
    referrer = _make_user(bonus=1)
    referred = _make_user(bonus=1)
    referral = _pending_referral(referrer, referred)
    referral.completed_at = datetime.now(UTC)
    # The service queries WHERE completed_at IS NULL — a completed row is
    # invisible to it, so the session returns None.
    session = FakeSession(None)

    completed = await complete_pending_referral(session, referred_user_id=referred.id)

    assert completed is False
    assert referred.bonus_analyses == 1  # unchanged


# ── quota integration ──────────────────────────────────────────────────────────

def test_bonus_analyses_extend_free_tier_limit():
    user = _make_user(bonus=3, used=2)

    status = _status_for_user(user)

    assert status.limit == FREE_LIFETIME_LIMIT + 3
    assert status.allowed is True
    assert status.remaining == 3


def test_zero_bonus_keeps_original_limit():
    user = _make_user(bonus=0, used=2)

    status = _status_for_user(user)

    assert status.limit == FREE_LIFETIME_LIMIT
    assert status.allowed is False


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
async def test_claim_endpoint_returns_204(client):
    referrer = _make_user()
    referred = _make_user()
    referred.clerk_id = "user_abc"
    # queue: require_user lookup, referrer lookup, existing-claim lookup
    _override_db(FakeSession(referred, referrer, None))

    r = await client.post(
        "/api/v1/referrals/claim",
        json={"referrer_user_id": str(referrer.id)},
        headers={"X-Clerk-User-Id": "user_abc"},
    )

    assert r.status_code == 204


@pytest.mark.asyncio
async def test_claim_endpoint_rejects_self_referral_with_400(client):
    referred = _make_user()
    referred.clerk_id = "user_abc"
    _override_db(FakeSession(referred))

    r = await client.post(
        "/api/v1/referrals/claim",
        json={"referrer_user_id": str(referred.id)},
        headers={"X-Clerk-User-Id": "user_abc"},
    )

    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "self_referral"


@pytest.mark.asyncio
async def test_stats_endpoint_returns_link_and_counts(client):
    user = _make_user(bonus=4)
    user.clerk_id = "user_abc"
    # queue: require_user, pending count, completed count, granted count
    _override_db(FakeSession(user, _FakeResult(2), _FakeResult(5), _FakeResult(4)))

    r = await client.get(
        "/api/v1/referrals/stats", headers={"X-Clerk-User-Id": "user_abc"}
    )

    assert r.status_code == 200
    body = r.json()
    assert body["referral_path"] == f"/ref/{user.id}"
    assert body["pending_count"] == 2
    assert body["completed_count"] == 5
    assert body["bonuses_earned"] == 4
    assert body["max_bonuses"] == 10
    assert body["bonus_analyses"] == 4
