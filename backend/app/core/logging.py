"""
Structured JSON logging for Clairo.

SECURITY: Document content MUST NEVER appear in log records.
Scrub all fields before passing to logger — use log_safe_* helpers.
"""
import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if sys.stderr.isatty():
        processors = [*shared_processors, structlog.dev.ConsoleRenderer()]
    else:
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


# ── Security helpers ─────────────────────────────────────────────────────────

def log_safe_filename(filename: str) -> str:
    import os
    return os.path.basename(filename)


def log_safe_file_meta(size_bytes: int, mime_type: str, filename: str) -> dict[str, Any]:
    return {
        "filename": log_safe_filename(filename),
        "size_bytes": size_bytes,
        "mime_type": mime_type,
    }
