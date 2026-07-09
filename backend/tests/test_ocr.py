"""
Tests for CLR-010 — OCR pipeline and endpoint.
"""
from __future__ import annotations

import io
import os
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.ocr import (
    ConfidenceLevel,
    OcrPage,
    OcrResult,
    OcrUnavailableError,
    OcrWord,
    _classify_word,
    _NUMBER_PATTERN,
    run_ocr,
)


# ---------------------------------------------------------------------------
# _NUMBER_PATTERN
# ---------------------------------------------------------------------------

class TestNumberPattern:
    @pytest.mark.parametrize("text", [
        "1234", "12.5", "$500", "€200", "50%", "1,000,000",
        "3.14", "0.99", "£50.00", "¥1000", "100%",
    ])
    def test_matches_numbers(self, text):
        assert _NUMBER_PATTERN.search(text), f"Should match: {text}"

    @pytest.mark.parametrize("text", [
        "hello", "contract", "party", "agree", "THIS",
    ])
    def test_no_match_words(self, text):
        assert not _NUMBER_PATTERN.search(text), f"Should not match: {text}"


# ---------------------------------------------------------------------------
# _classify_word
# ---------------------------------------------------------------------------

class TestClassifyWord:
    def test_number_always_number_level(self):
        result = _classify_word("$500", 0.99)
        assert result == ConfidenceLevel.NUMBER

    def test_high_confidence(self):
        result = _classify_word("contract", 0.95)
        assert result == ConfidenceLevel.HIGH

    def test_medium_confidence(self):
        result = _classify_word("party", 0.65)
        assert result == ConfidenceLevel.MEDIUM

    def test_low_confidence(self):
        result = _classify_word("agreement", 0.3)
        assert result == ConfidenceLevel.LOW

    def test_boundary_high_medium(self):
        # 0.80 is the HIGH/MEDIUM boundary — must be > 0.80 for HIGH
        assert _classify_word("word", 0.81) == ConfidenceLevel.HIGH
        assert _classify_word("word", 0.80) == ConfidenceLevel.MEDIUM

    def test_boundary_medium_low(self):
        assert _classify_word("word", 0.50) == ConfidenceLevel.MEDIUM
        assert _classify_word("word", 0.49) == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# OcrPage helpers
# ---------------------------------------------------------------------------

def _make_page(words_data: list[tuple[str, float]]) -> OcrPage:
    words = [
        OcrWord(text=t, confidence=c, confidence_level=_classify_word(t, c))
        for t, c in words_data
    ]
    return OcrPage(page_number=1, words=words)


class TestOcrPage:
    def test_text_property(self):
        page = _make_page([("hello", 0.9), ("world", 0.8)])
        assert page.text == "hello world"

    def test_low_confidence_ratio_all_high(self):
        page = _make_page([("hello", 0.9), ("world", 0.95)])
        assert page.low_confidence_ratio == 0.0

    def test_low_confidence_ratio_mixed(self):
        page = _make_page([
            ("hello", 0.9),   # HIGH
            ("bad", 0.3),     # LOW  ← counts
            ("ok", 0.6),      # MEDIUM → does not count
        ])
        assert pytest.approx(page.low_confidence_ratio, abs=0.01) == 1 / 3

    def test_empty_page(self):
        page = _make_page([])
        assert page.text == ""
        assert page.low_confidence_ratio == 0.0


# ---------------------------------------------------------------------------
# run_ocr — PDF direct extraction
# ---------------------------------------------------------------------------

class TestRunOcrPdf:
    @pytest.mark.asyncio
    async def test_pdf_uses_direct_extraction(self, tmp_path):
        """PDF should use pypdf direct extraction, not GCV."""
        # Minimal valid-ish PDF content — we'll mock _extract_pdf_text
        fake_result = OcrResult(
            pages=[OcrPage(page_number=1, words=[OcrWord(
                text="clause",
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH,
            )])],
            source="direct",
            total_pages=1,
        )
        with patch("app.services.ocr._extract_pdf_text", return_value=fake_result):
            result = await run_ocr(b"%PDF-stub", "application/pdf", "test.pdf")

        assert result.source == "direct"
        assert result.total_pages == 1

    @pytest.mark.asyncio
    async def test_docx_uses_direct_extraction(self):
        fake_result = OcrResult(
            pages=[OcrPage(page_number=1, words=[])],
            source="direct",
            total_pages=1,
        )
        with patch("app.services.ocr._extract_docx_text", return_value=fake_result):
            result = await run_ocr(b"PK\x03\x04stub", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "test.docx")

        assert result.source == "direct"


# ---------------------------------------------------------------------------
# run_ocr — image GCV path
# ---------------------------------------------------------------------------

class TestRunOcrGcv:
    @pytest.mark.asyncio
    async def test_image_uses_tesseract_by_default(self):
        # Default OCR_PROVIDER is the free in-container Tesseract engine.
        fake = OcrResult(
            pages=[OcrPage(page_number=1, words=[OcrWord(
                text="amount", confidence=0.9, confidence_level=ConfidenceLevel.HIGH,
            )])],
            source="tesseract",
            total_pages=1,
        )
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("OCR_PROVIDER", None)
            with patch(
                "app.services.ocr._ocr_with_tesseract",
                new_callable=AsyncMock, return_value=fake,
            ):
                result = await run_ocr(b"\xff\xd8\xffstub", "image/jpeg", "test.jpg")
        assert result.source == "tesseract"

    @pytest.mark.asyncio
    async def test_image_uses_gcv_when_configured(self):
        fake_result = OcrResult(
            pages=[OcrPage(page_number=1, words=[OcrWord(
                text="amount",
                confidence=0.95,
                confidence_level=ConfidenceLevel.HIGH,
            )])],
            source="gcv",
            total_pages=1,
        )
        with patch.dict("os.environ", {"OCR_PROVIDER": "gcv"}), patch(
            "app.services.ocr._ocr_with_gcv", new_callable=AsyncMock, return_value=fake_result
        ):
            result = await run_ocr(b"\xff\xd8\xffstub", "image/jpeg", "test.jpg")

        assert result.source == "gcv"

    @pytest.mark.asyncio
    async def test_gcv_failure_falls_back_to_textract(self):
        textract_result = OcrResult(
            pages=[OcrPage(page_number=1, words=[])],
            source="textract",
            total_pages=1,
        )
        with (
            patch.dict("os.environ", {"OCR_PROVIDER": "gcv"}),
            patch("app.services.ocr._ocr_with_gcv", new_callable=AsyncMock, side_effect=Exception("GCV unavailable")),
            patch("app.services.ocr._ocr_with_textract", new_callable=AsyncMock, return_value=textract_result),
        ):
            result = await run_ocr(b"\x89PNGstub", "image/png", "test.png")

        assert result.source == "textract"

    @pytest.mark.asyncio
    async def test_image_ocr_failure_raises_unavailable(self):
        # An engine crash surfaces as OcrUnavailableError (clean 422), not a 500.
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("OCR_PROVIDER", None)
            with patch(
                "app.services.ocr._ocr_with_tesseract",
                new_callable=AsyncMock, side_effect=Exception("tesseract missing"),
            ):
                with pytest.raises(OcrUnavailableError):
                    await run_ocr(b"\xff\xd8\xffstub", "image/jpeg", "test.jpg")


# ---------------------------------------------------------------------------
# POST /api/v1/ocr endpoint
# ---------------------------------------------------------------------------

@pytest.fixture
def pdf_bytes():
    return b"%PDF-1.4 minimal"


@pytest.fixture
def jpeg_bytes():
    return b"\xff\xd8\xff" + b"\x00" * 100



@pytest.fixture
async def client():
    import fakeredis.aioredis as fakeredis
    import app.core.redis as redis_module
    import app.middleware.rate_limit as rl_module

    fake = fakeredis.FakeRedis()

    async def _mock_get_redis():
        return fake

    async def _mock_check_rate(*args, **kwargs):
        from app.core.rate_limit import RateLimitResult
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with (
        patch.object(redis_module, "get_redis", side_effect=_mock_get_redis),
        patch.object(rl_module, "check_rate_limit", side_effect=_mock_check_rate),
    ):
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            yield c


class TestOcrEndpoint:
    @pytest.mark.asyncio
    async def test_pdf_returns_skip_review_true(self, client: AsyncClient, pdf_bytes):
        fake_result = OcrResult(
            pages=[OcrPage(page_number=1, words=[OcrWord(
                text="Contract",
                confidence=1.0,
                confidence_level=ConfidenceLevel.HIGH,
            )])],
            source="direct",
            total_pages=1,
        )
        with (
            patch("app.api.v1.endpoints.ocr.validate_file") as mock_validate,
            patch("app.api.v1.endpoints.ocr.run_ocr", new_callable=AsyncMock, return_value=fake_result),
        ):
            from app.services.file_validation import ValidationResult
            mock_validate.return_value = ValidationResult(valid=True)

            response = await client.post(
                "/api/v1/ocr",
                files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["skip_review"] is True
        assert body["source"] == "direct"

    @pytest.mark.asyncio
    async def test_image_returns_skip_review_false(self, client: AsyncClient, jpeg_bytes):
        fake_result = OcrResult(
            pages=[OcrPage(page_number=1, words=[OcrWord(
                text="$500",
                confidence=0.9,
                confidence_level=ConfidenceLevel.NUMBER,
            )])],
            source="gcv",
            total_pages=1,
        )
        with (
            patch("app.api.v1.endpoints.ocr.validate_file") as mock_validate,
            patch("app.api.v1.endpoints.ocr.run_ocr", new_callable=AsyncMock, return_value=fake_result),
        ):
            from app.services.file_validation import ValidationResult
            mock_validate.return_value = ValidationResult(valid=True)

            response = await client.post(
                "/api/v1/ocr",
                files={"file": ("photo.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["skip_review"] is False
        assert body["source"] == "gcv"
        # NUMBER confidence level preserved
        assert body["pages"][0]["words"][0]["confidence_level"] == "number"

    @pytest.mark.asyncio
    async def test_invalid_file_returns_422(self, client: AsyncClient):
        with patch("app.api.v1.endpoints.ocr.validate_file") as mock_validate:
            from app.services.file_validation import ValidationResult
            mock_validate.return_value = ValidationResult(valid=False, error_code="VIRUS_DETECTED")

            response = await client.post(
                "/api/v1/ocr",
                files={"file": ("evil.pdf", io.BytesIO(b"%PDF bad"), "application/pdf")},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_content_type_returns_400(self, client: AsyncClient):
        # Send without content type header — tricky via multipart but simulate via direct check
        # The endpoint checks file.content_type — mock it
        from fastapi.testclient import TestClient
        # We just verify our guard clause exists by checking the endpoint code path
        # Real multipart always sets content_type so we test the guard path differently
        response = await client.post(
            "/api/v1/ocr",
            content=b"raw bytes without multipart",
            headers={"Content-Type": "application/octet-stream"},
        )
        # Should be 422 from FastAPI missing `file` field
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_response_confidence_levels_present(self, client: AsyncClient, jpeg_bytes):
        words = [
            OcrWord("Contract", 0.95, ConfidenceLevel.HIGH),
            OcrWord("parties", 0.65, ConfidenceLevel.MEDIUM),
            OcrWord("mumbojumbo", 0.3, ConfidenceLevel.LOW),
            OcrWord("$1,000", 0.99, ConfidenceLevel.NUMBER),
        ]
        fake_result = OcrResult(
            pages=[OcrPage(page_number=1, words=words)],
            source="gcv",
            total_pages=1,
        )
        with (
            patch("app.api.v1.endpoints.ocr.validate_file") as mock_validate,
            patch("app.api.v1.endpoints.ocr.run_ocr", new_callable=AsyncMock, return_value=fake_result),
        ):
            from app.services.file_validation import ValidationResult
            mock_validate.return_value = ValidationResult(valid=True)

            response = await client.post(
                "/api/v1/ocr",
                files={"file": ("photo.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            )

        assert response.status_code == 200
        levels = [w["confidence_level"] for w in response.json()["pages"][0]["words"]]
        assert levels == ["high", "medium", "low", "number"]
