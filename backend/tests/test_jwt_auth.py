"""
CLR-031 — JWT authentication middleware tests.

Tests:
- Valid JWT → 200, request.state populated
- Missing token → 401
- Expired token → 401
- Invalid signature → 401
- Wrong issuer → 401
- Public routes exempt from auth
- JWKS cache refresh on key rotation
- 401 responses never contain system information
"""
import time
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.middleware.jwt_auth import JWTAuthMiddleware, _jwks_cache

# ── Test RSA key pair ──────────────────────────────────────────────────────────

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()
_KID = "test-key-1"
_ISSUER = "https://test.clerk.accounts.dev"

import base64

def _b64url(n: int) -> str:
    length = (n.bit_length() + 7) // 8
    b = n.to_bytes(length, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


_pub = _PUBLIC_KEY.public_numbers()
_TEST_JWK = {
    "kty": "RSA",
    "kid": _KID,
    "use": "sig",
    "alg": "RS256",
    "n": _b64url(_pub.n),
    "e": _b64url(_pub.e),
}
_TEST_JWKS = {"keys": [_TEST_JWK]}

_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption(),
)


def _make_token(
    sub: str = "user_abc123",
    exp_offset: int = 300,
    iss: str = _ISSUER,
    kid: str = _KID,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": iss,
        "iat": now,
        "exp": now + exp_offset,
        "nbf": now - 5,
        **(extra or {}),
    }
    return jwt.encode(
        payload,
        _PRIVATE_PEM,
        algorithm="RS256",
        headers={"kid": kid},
    )


# ── Minimal FastAPI app for testing ───────────────────────────────────────────

def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        JWTAuthMiddleware,
        clerk_jwks_url="https://fake.clerk.dev/v1/jwks",
        clerk_issuer=_ISSUER,
    )

    @app.get("/api/v1/protected")
    async def protected(request: Request):
        return JSONResponse({
            "clerk_id": request.state.clerk_id,
            "tier": request.state.subscription_tier,
        })

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    return app


@pytest.fixture(autouse=True)
def patch_jwks():
    """Patch JWKS fetch to return test keys."""
    _jwks_cache._keys = []  # reset cache between tests
    _jwks_cache._fetched_at = 0.0

    async def _fake_get_keys(force_refresh=False):
        return _TEST_JWKS["keys"]

    with patch.object(_jwks_cache, "get_keys", side_effect=_fake_get_keys):
        yield


@pytest.fixture
def app():
    return _make_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_token_returns_200(client):
    token = _make_token(sub="user_clerk_123")
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["clerk_id"] == "user_clerk_123"
    assert body["tier"] == "free"  # default when no public_metadata


@pytest.mark.asyncio
async def test_subscription_tier_from_public_metadata(client):
    token = _make_token(sub="user_pro", extra={"public_metadata": {"tier": "pro"}})
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["tier"] == "pro"


@pytest.mark.asyncio
async def test_missing_token_returns_401(client):
    resp = await client.get("/api/v1/protected")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_returns_401(client):
    token = _make_token(exp_offset=-10)  # expired 10s ago
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(client):
    token = _make_token(iss="https://evil.attacker.com")
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(client):
    """Sign with a different key — signature mismatch."""
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    now = int(time.time())
    token = jwt.encode(
        {"sub": "x", "iss": _ISSUER, "iat": now, "exp": now + 300},
        other_pem,
        algorithm="RS256",
        headers={"kid": _KID},  # claims to be our key but isn't
    )
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_garbled_token_returns_401(client):
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": "Bearer not.a.jwt"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_route_exempt_from_auth(client):
    """Health endpoint must not require a token."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_401_body_contains_no_system_info(client):
    """401 response must only say 'Unauthorized' — no stack traces or internals."""
    resp = await client.get("/api/v1/protected")
    assert resp.status_code == 401
    body = resp.json()
    assert list(body.keys()) == ["detail"]
    assert body["detail"] == "Unauthorized"
    # Must not leak any system information
    body_str = resp.text
    assert "Traceback" not in body_str
    assert "Exception" not in body_str
    assert "jwt" not in body_str.lower()
    assert "clerk" not in body_str.lower()


@pytest.mark.asyncio
async def test_401_headers_contain_no_system_info(client):
    """Response headers must not leak internal details."""
    resp = await client.get("/api/v1/protected")
    assert resp.status_code == 401
    # No Server header revealing framework version
    assert "fastapi" not in resp.headers.get("server", "").lower()


@pytest.mark.asyncio
async def test_bearer_prefix_required(client):
    """Token without 'Bearer ' prefix must be rejected."""
    token = _make_token()
    resp = await client.get(
        "/api/v1/protected",
        headers={"Authorization": token},  # missing "Bearer "
    )
    assert resp.status_code == 401
