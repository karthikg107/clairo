"""Health check endpoints."""
import time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis import redis_ping

router = APIRouter()
logger = get_logger(__name__)

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
    """Readiness check — verifies Redis is reachable. DB wired in CLR-003 migration run."""
    checks: dict[str, str] = {
        "db": "pending",                                    # wired when DB is running
        "redis": "ok" if await redis_ping() else "error",
    }
    failed = [k for k, v in checks.items() if v == "error"]
    return ReadinessResponse(
        status="error" if failed else "ok",
        checks=checks,
    )
