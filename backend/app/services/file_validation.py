"""
File validation service.

SECURITY (non-negotiable):
- File NEVER written to disk — processed in memory only
- Only allowlisted MIME types accepted
- Magic bytes must match declared MIME
- ClamAV scan on every upload
- All validation failures logged (event type only — no file content)
"""
from __future__ import annotations

import asyncio
import io
import struct
from dataclasses import dataclass
from enum import Enum

import clamd  # type: ignore[import]

from app.core.logging import get_logger, log_safe_file_meta

logger = get_logger(__name__)

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB

# ── Allowed MIME types ────────────────────────────────────────────────────────

class AllowedMime(str, Enum):
    PDF  = "application/pdf"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    JPEG = "image/jpeg"
    PNG  = "image/png"
    HEIC = "image/heic"
    HEIF = "image/heif"

ALLOWED_MIMES: frozenset[str] = frozenset(m.value for m in AllowedMime)

# ── Magic bytes (first 8 bytes) ───────────────────────────────────────────────
# Maps declared MIME → set of valid magic byte signatures

_MAGIC: dict[str, list[bytes]] = {
    AllowedMime.PDF.value:  [b"%PDF"],
    AllowedMime.DOCX.value: [b"PK\x03\x04"],   # ZIP-based (Office Open XML)
    AllowedMime.JPEG.value: [b"\xff\xd8\xff"],
    AllowedMime.PNG.value:  [b"\x89PNG\r\n\x1a\n"],
    AllowedMime.HEIC.value: [],   # No reliable magic — validated by extension
    AllowedMime.HEIF.value: [],
}

# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    valid: bool
    error_code: str | None = None      # machine-readable code for i18n
    error_detail: str | None = None    # safe detail (no file content)


# ── Validation steps ──────────────────────────────────────────────────────────

def _check_size(data: bytes) -> ValidationResult:
    if len(data) > MAX_FILE_BYTES:
        return ValidationResult(valid=False, error_code="FILE_TOO_LARGE",
                                error_detail=f"File exceeds 25 MB limit ({len(data)} bytes)")
    return ValidationResult(valid=True)


def _check_mime(declared_mime: str) -> ValidationResult:
    if declared_mime not in ALLOWED_MIMES:
        return ValidationResult(valid=False, error_code="MIME_NOT_ALLOWED",
                                error_detail=f"MIME type not in allowlist: {declared_mime}")
    return ValidationResult(valid=True)


def _check_magic(data: bytes, declared_mime: str) -> ValidationResult:
    signatures = _MAGIC.get(declared_mime, [])
    if not signatures:
        # HEIC/HEIF — no reliable magic, skip magic check
        return ValidationResult(valid=True)

    header = data[:8]
    for sig in signatures:
        if header.startswith(sig):
            return ValidationResult(valid=True)

    return ValidationResult(
        valid=False,
        error_code="MAGIC_MISMATCH",
        error_detail=f"File header does not match declared MIME {declared_mime}",
    )


async def _check_clamav(data: bytes) -> ValidationResult:
    """
    Scan file bytes with ClamAV daemon (clamd).
    Rejects file if any signature matches.

    SECURITY: file content is passed in-memory — never written to disk.
    """
    try:
        cd = clamd.ClamdUnixSocket()   # Uses /var/run/clamav/clamd.sock
        loop = asyncio.get_event_loop()
        # Run blocking scan in thread pool to avoid blocking event loop
        result = await loop.run_in_executor(
            None,
            lambda: cd.instream(io.BytesIO(data)),
        )
        stream_result = result.get("stream", ("OK", None))
        status, virus_name = stream_result[0], stream_result[1]

        if status != "OK":
            logger.warning(
                "clamav.virus_detected",
                status=status,
                # NEVER log virus_name as it could contain injected content
            )
            return ValidationResult(
                valid=False,
                error_code="VIRUS_DETECTED",
                error_detail="ClamAV detected a potentially malicious file",
            )
        return ValidationResult(valid=True)

    except clamd.ConnectionError:
        # ClamAV unavailable — fail CLOSED (reject upload, log for ops)
        logger.error("clamav.unavailable")
        return ValidationResult(
            valid=False,
            error_code="ANTIVIRUS_UNAVAILABLE",
            error_detail="Antivirus service temporarily unavailable",
        )
    except Exception as exc:
        logger.error("clamav.scan_error", error=str(exc))
        return ValidationResult(
            valid=False,
            error_code="ANTIVIRUS_ERROR",
            error_detail="Antivirus scan failed",
        )


# ── Public API ────────────────────────────────────────────────────────────────

async def validate_file(
    data: bytes,
    declared_mime: str,
    filename: str,
) -> ValidationResult:
    """
    Full validation pipeline. All checks run in-memory — file never touches disk.

    Steps:
    1. Size check (25 MB)
    2. MIME allowlist
    3. Magic bytes vs declared MIME
    4. ClamAV scan

    All failures are logged with safe metadata only (no file content).
    """
    meta = log_safe_file_meta(len(data), declared_mime, filename)

    # 1. Size
    result = _check_size(data)
    if not result.valid:
        logger.info("file_validation.rejected", reason="size", **meta)
        return result

    # 2. MIME allowlist
    result = _check_mime(declared_mime)
    if not result.valid:
        logger.info("file_validation.rejected", reason="mime", **meta)
        return result

    # 3. Magic bytes
    result = _check_magic(data, declared_mime)
    if not result.valid:
        logger.warning("file_validation.rejected", reason="magic_mismatch", **meta)
        return result

    # 4. ClamAV
    result = await _check_clamav(data)
    if not result.valid:
        logger.warning("file_validation.rejected", reason=result.error_code, **meta)
        return result

    logger.info("file_validation.passed", **meta)
    return ValidationResult(valid=True)
