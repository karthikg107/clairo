"""Tests for file validation service — no ClamAV or disk needed."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.file_validation import (
    validate_file,
    _check_size,
    _check_mime,
    _check_magic,
    MAX_FILE_BYTES,
    AllowedMime,
)

# ── Magic bytes fixtures ──────────────────────────────────────────────────────

PDF_HEADER  = b"%PDF-1.4" + b"\x00" * 100
DOCX_HEADER = b"PK\x03\x04" + b"\x00" * 100
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG_HEADER  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
BAD_HEADER  = b"\x00\x01\x02\x03\x04\x05\x06\x07" + b"\x00" * 100


# ── Size checks ───────────────────────────────────────────────────────────────

def test_size_check_passes_within_limit():
    result = _check_size(b"x" * 1000)
    assert result.valid is True


def test_size_check_fails_over_25mb():
    result = _check_size(b"x" * (MAX_FILE_BYTES + 1))
    assert result.valid is False
    assert result.error_code == "FILE_TOO_LARGE"


def test_size_check_passes_exactly_at_limit():
    result = _check_size(b"x" * MAX_FILE_BYTES)
    assert result.valid is True


# ── MIME checks ───────────────────────────────────────────────────────────────

def test_mime_check_allows_pdf():
    assert _check_mime(AllowedMime.PDF.value).valid is True


def test_mime_check_allows_docx():
    assert _check_mime(AllowedMime.DOCX.value).valid is True


def test_mime_check_allows_jpeg():
    assert _check_mime(AllowedMime.JPEG.value).valid is True


def test_mime_check_rejects_exe():
    result = _check_mime("application/x-msdownload")
    assert result.valid is False
    assert result.error_code == "MIME_NOT_ALLOWED"


def test_mime_check_rejects_zip():
    result = _check_mime("application/zip")
    assert result.valid is False


def test_mime_check_rejects_html():
    result = _check_mime("text/html")
    assert result.valid is False


# ── Magic byte checks ─────────────────────────────────────────────────────────

def test_magic_pdf_valid():
    assert _check_magic(PDF_HEADER, AllowedMime.PDF.value).valid is True


def test_magic_docx_valid():
    assert _check_magic(DOCX_HEADER, AllowedMime.DOCX.value).valid is True


def test_magic_jpeg_valid():
    assert _check_magic(JPEG_HEADER, AllowedMime.JPEG.value).valid is True


def test_magic_png_valid():
    assert _check_magic(PNG_HEADER, AllowedMime.PNG.value).valid is True


def test_magic_mismatch_rejected():
    # Declare as PDF but provide JPEG header
    result = _check_magic(JPEG_HEADER, AllowedMime.PDF.value)
    assert result.valid is False
    assert result.error_code == "MAGIC_MISMATCH"


def test_magic_heic_skipped():
    # HEIC has no reliable magic — should pass magic check
    assert _check_magic(BAD_HEADER, AllowedMime.HEIC.value).valid is True


# ── Full pipeline ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_validation_passes_for_valid_pdf():
    mock_clamd = MagicMock()
    mock_clamd.instream.return_value = {"stream": ("OK", None)}

    with patch("app.services.file_validation.clamd.ClamdUnixSocket", return_value=mock_clamd):
        result = await validate_file(PDF_HEADER, AllowedMime.PDF.value, "contract.pdf")

    assert result.valid is True


@pytest.mark.asyncio
async def test_full_validation_rejects_virus():
    mock_clamd = MagicMock()
    mock_clamd.instream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}

    with patch("app.services.file_validation.clamd.ClamdUnixSocket", return_value=mock_clamd):
        result = await validate_file(PDF_HEADER, AllowedMime.PDF.value, "evil.pdf")

    assert result.valid is False
    assert result.error_code == "VIRUS_DETECTED"


@pytest.mark.asyncio
async def test_full_validation_rejects_wrong_mime():
    result = await validate_file(PDF_HEADER, "application/x-msdownload", "bad.exe")
    assert result.valid is False
    assert result.error_code == "MIME_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_clamav_unavailable_fails_closed():
    """SECURITY: if ClamAV is down, reject the file (fail closed, not open)."""
    import clamd
    with patch("app.services.file_validation.clamd.ClamdUnixSocket",
               side_effect=clamd.ConnectionError("unavailable")):
        result = await validate_file(PDF_HEADER, AllowedMime.PDF.value, "contract.pdf")

    assert result.valid is False
    assert result.error_code == "ANTIVIRUS_UNAVAILABLE"
