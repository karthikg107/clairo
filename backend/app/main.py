"""
Clairo FastAPI application entry point.

SECURITY checklist (enforced here):
- CORS: clairo.app and localhost:3000 only
- Security headers: X-Frame-Options DENY, HSTS, Permissions-Policy
- Structured JSON logging (never logs document content)
- JWT verification via Clerk JWKS (CLR-031)
- Rate limiting per user/IP via Redis
- Sentry error tracking
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis
from app.middleware.jwt_auth import JWTAuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app.startup", env=settings.app_env, version=settings.app_version)
    yield
    await close_redis()
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    # Middleware — Starlette applies in REVERSE add_middleware order,
    # so the last add_middleware() runs first on each request.
    #
    # Effective order (outermost → innermost):
    #   CORS → TrustedHost → SecurityHeaders → Logging → JWT → RateLimit → routes
    #
    # JWT must run before RateLimit so user_id is set for tier-aware limiting.

    app.add_middleware(RateLimitMiddleware)

    # Skip JWT middleware if clerk_issuer is not configured (dev without Clerk)
    if settings.clerk_issuer:
        app.add_middleware(
            JWTAuthMiddleware,
            clerk_jwks_url=settings.clerk_jwks_url,
            clerk_issuer=settings.clerk_issuer,
        )

    app.add_middleware(LoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Anonymous-Id"],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(v1_router)
    return app


app = create_app()
