"""
Request-hardening middleware (security hardening items 4, 5, 7, 8).

SecurityGuardMiddleware (runs before route handlers):
  - Global request body-size cap (25 MB) via Content-Length.
  - Suspicious-pattern firewall on the URL PATH + QUERY STRING only —
    NEVER the request body. The analysis body carries document text; we
    do not inspect it (privacy), and legitimate document content must
    never be able to trip a "SQLi/XSS" rule.
  - Origin verification on state-changing methods (the correct CSRF
    control for a stateless Bearer-token API — see module notes below).

RequestTimeoutMiddleware (wraps the handler):
  - Hard per-request timeout: 30 s default, 60 s for the analysis
    endpoint (its own LLM call is capped at 30 s + parsing/persistence).

CSRF note: Clairo's API authenticates with a Bearer JWT in the
Authorization header, not an ambient session cookie. Classic CSRF relies
on the browser auto-attaching cookies cross-site; it cannot forge an
Authorization header (and CORS blocks cross-origin reads). So per-form
CSRF tokens are not applicable to this API — Origin verification on
mutating requests is the appropriate defense-in-depth control.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from urllib.parse import unquote

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security_events import (
    EVENT_SUSPICIOUS_PATTERN,
    log_security_event,
)

logger = get_logger(__name__)

MAX_REQUEST_BYTES = 25 * 1024 * 1024  # 25 MB

_DEFAULT_TIMEOUT_SECONDS = 30.0
# The analysis endpoint's own LLM call is capped at 30 s; allow headroom
# for cache/persistence around it (also matches the E2E "under 60 s" bar).
_ROUTE_TIMEOUTS: list[tuple[str, float]] = [
    ("/api/v1/analyse", 60.0),
]

# State-changing methods that require an allowed Origin when one is sent.
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Server-to-server callers legitimately send no browser Origin — e.g. the
# Stripe webhook (verified by signature instead). These are never subject
# to the Origin check (which only triggers when an Origin header IS present).
_ORIGIN_EXEMPT_PREFIXES = ("/api/v1/billing/webhook",)

# Suspicious-pattern rules. Intentionally specific to avoid false positives
# on legitimate paths/queries (UUIDs, locale codes, numeric limits).
_SUSPICIOUS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("sqli_union", re.compile(r"(?i)\bunion\b\s+\bselect\b")),
    ("sqli_or_1", re.compile(r"(?i)('|\")?\s*\bor\b\s+1\s*=\s*1")),
    ("sqli_drop", re.compile(r"(?i);\s*\bdrop\b\s+\btable\b")),
    ("sqli_comment", re.compile(r"(?:--\s|/\*|\*/|#\s)")),
    ("sqli_exec", re.compile(r"(?i)\b(exec|execute)\b\s*\(")),
    ("xss_script", re.compile(r"(?i)<\s*script\b")),
    ("xss_js_uri", re.compile(r"(?i)javascript:")),
    ("xss_handler", re.compile(r"(?i)\bon(error|load|click|mouseover)\s*=")),
    ("xss_iframe", re.compile(r"(?i)<\s*iframe\b")),
    ("path_traversal", re.compile(r"(?:\.\./|\.\.\\|%2e%2e|/etc/passwd)")),
    ("null_byte", re.compile(r"(?:%00|\x00)")),
]


def _timeout_for(path: str) -> float:
    for prefix, seconds in _ROUTE_TIMEOUTS:
        if path.startswith(prefix):
            return seconds
    return _DEFAULT_TIMEOUT_SECONDS


def _first_suspicious(target: str) -> str | None:
    for name, pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(target):
            return name
    return None


class SecurityGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Body-size cap (defense-in-depth; the upload endpoint also checks).
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"error": "request_too_large"},
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"error": "bad_request"})

        # 2. Suspicious-pattern firewall — PATH + QUERY only, never the body.
        # URL-decode so encoded payloads (%27%20OR…) are matched too.
        target = request.url.path
        if request.url.query:
            target = f"{target}?{unquote(request.url.query)}"
        matched = _first_suspicious(target)
        if matched:
            await log_security_event(
                action=EVENT_SUSPICIOUS_PATTERN,
                request=request,
                metadata={"pattern": matched, "path": request.url.path},
                alert=True,
                alert_message=f"Suspicious request pattern detected: {matched}",
            )
            return JSONResponse(status_code=400, content={"error": "bad_request"})

        # 3. Origin verification on state-changing requests.
        if request.method in _MUTATING_METHODS:
            origin = request.headers.get("origin")
            path = request.url.path
            exempt = any(path.startswith(p) for p in _ORIGIN_EXEMPT_PREFIXES)
            if origin and not exempt:
                allowed = set(get_settings().cors_origins)
                if origin not in allowed:
                    return JSONResponse(
                        status_code=403,
                        content={"error": "origin_not_allowed"},
                    )

        return await call_next(request)


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        timeout = _timeout_for(request.url.path)
        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except TimeoutError:
            logger.warning("request.timeout", path=request.url.path, timeout=timeout)
            return JSONResponse(status_code=504, content={"error": "request_timeout"})
