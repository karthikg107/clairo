"""
Central security-event logging (security hardening).

Writes structured security events to the append-only audit_log table
(best-effort, own session, never blocks the request) and raises Sentry
alerts for high-severity events.

PRIVACY: never logs document content or PII beyond what audit_log already
holds (user-agent, IP). Suspicious-pattern events record only the matched
pattern name and request path/query — never the request body.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.models.audit_log import AuditLog

logger = get_logger(__name__)

# audit_log.action values for security events
EVENT_RATE_LIMIT_HIT = "security.rate_limit_hit"
EVENT_UPLOAD_REJECTED = "security.upload_rejected"
EVENT_SUSPICIOUS_PATTERN = "security.suspicious_pattern"
EVENT_AUTH_FAILED = "security.auth_failed"
EVENT_AUTH_FAILURE_SPIKE = "security.auth_failure_spike"


def sentry_security_alert(message: str, extra: dict[str, Any]) -> None:
    """Fire a Sentry warning tagged as a security event. Never raises."""
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("category", "security")
            scope.set_extra("security_event", extra)
            sentry_sdk.capture_message(message, level="warning")
    except Exception:  # noqa: S110 — alerting must never raise into the request
        pass


async def log_security_event(
    *,
    action: str,
    request: Request | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    alert: bool = False,
    alert_message: str | None = None,
) -> None:
    """
    Record a security event to audit_log (best-effort) and optionally alert.

    Never raises — a logging/alerting failure must not affect the request.
    metadata MUST contain only safe fields (never document content).
    """
    md = dict(metadata or {})
    if request is not None:
        if ip is None:
            ip = request.client.host if request.client else None
        if user_agent is None:
            user_agent = request.headers.get("user-agent", "")[:200]

    try:
        factory = get_session_factory()
        async with factory() as session:
            session.add(
                AuditLog(
                    action=action,
                    metadata_json=md,
                    ip_address=ip,
                    user_agent=user_agent,
                )
            )
            await session.commit()
    except Exception as exc:
        # Fail-open: log a warning but never propagate (DB may be unreachable
        # in local dev). The Sentry alert below still fires.
        logger.warning("security_event.audit_failed", action=action, error=str(exc))

    if alert:
        sentry_security_alert(alert_message or action, {"action": action, "ip": ip, **md})
