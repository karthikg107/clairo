"""Tests for health check endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    # Use "http://localhost" so TrustedHostMiddleware accepts the host header
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as ac:
        yield ac


async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


async def test_health_response_shape(client: AsyncClient) -> None:
    data = (await client.get("/api/v1/health")).json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["env"] == "development"


async def test_ready_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200


async def test_ready_response_shape(client: AsyncClient) -> None:
    data = (await client.get("/api/v1/ready")).json()
    assert data["status"] in ("ok", "degraded", "error")
    assert "checks" in data


async def test_security_headers_present(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert "x-request-id" in response.headers


async def test_docs_disabled_in_production(client: AsyncClient) -> None:
    """OpenAPI docs must not be exposed outside development."""
    from app.core.config import get_settings
    settings = get_settings()
    if settings.is_production:
        r = await client.get("/docs")
        assert r.status_code == 404
