"""Health check endpoints."""
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis import redis_ping
from app.db.session import get_session_factory

router = APIRouter()
logger = get_logger(__name__)


async def _db_ping() -> bool:
    """True if a trivial query against the database succeeds. Never raises."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("readiness.db_ping_failed", error=str(exc))
        return False

_START_TIME = time.time()


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness check — returns 200 when the process is alive."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        env=settings.app_env,
        uptime_seconds=round(time.time() - _START_TIME, 1),
    )


@router.get("/ready", response_model=ReadinessResponse, tags=["ops"])
async def readiness() -> ReadinessResponse:
    """Readiness check — verifies the database and Redis are reachable."""
    checks: dict[str, str] = {
        "db": "ok" if await _db_ping() else "error",
        "redis": "ok" if await redis_ping() else "error",
    }
    failed = [k for k, v in checks.items() if v == "error"]
    return ReadinessResponse(
        status="error" if failed else "ok",
        checks=checks,
    )
