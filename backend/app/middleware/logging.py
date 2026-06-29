"""Request/response logging middleware — structured JSON, no document content."""
import time
import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# Paths that should not be logged verbosely (health checks, etc.)
_SILENT_PATHS = {"/health", "/healthz", "/ready", "/metrics"}


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if request.url.path not in _SILENT_PATHS:
            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
                # NOTE: query params, headers, body — NEVER logged here.
                # Document content is processed in-memory and NEVER reaches logs.
            )

        response.headers["X-Request-ID"] = request_id
        return response
