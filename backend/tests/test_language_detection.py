"""
Tests for CLR-012 — Language detection service and endpoint.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from app.services.language_detection import (
    DetectionConfidence,
    LanguageDetectionResult,
    SUPPORTED_LANGUAGES,
    _normalise,
    detect_language,
)


# ── _normalise ────────────────────────────────────────────────────────────────

class TestNormalise:
    def test_base_code_passthrough(self):
        assert _normalise("en") == "en"

    def test_strips_region_suffix(self):
        assert _normalise("pt-BR") == "pt"

    def test_zh_cn(self):
        assert _normalise("zh-cn") == "zh-cn"

    def test_zh_tw(self):
        assert _normalise("zh-tw") == "zh-tw"

    def test_case_insensitive(self):
        assert _normalise("EN") == "en"
        assert _normalise("FR") == "fr"


# ── detect_language ───────────────────────────────────────────────────────────

class TestDetectLanguage:
    def test_english_text_detected(self):
        text = (
            "This Lease Agreement is entered into between the Landlord and the Tenant. "
            "The monthly rent shall be due on the first day of each month. "
            "The security deposit equals two months rent."
        ) * 3
        result = detect_language(text)
        assert result.detected_code == "en"
        assert result.confidence in (DetectionConfidence.HIGH, DetectionConfidence.LOW)

    def test_spanish_text_detected(self):
        text = (
            "Este contrato de arrendamiento se celebra entre el arrendador y el arrendatario. "
            "El alquiler mensual vence el primer día de cada mes. "
            "El depósito de seguridad equivale a dos meses de renta."
        ) * 3
        result = detect_language(text)
        assert result.detected_code == "es"

    def test_german_text_detected(self):
        text = (
            "Dieser Mietvertrag wird zwischen dem Vermieter und dem Mieter geschlossen. "
            "Die monatliche Miete ist am ersten Tag jedes Monats fällig. "
            "Die Kaution beträgt zwei Monatsmieten."
        ) * 3
        result = detect_language(text)
        assert result.detected_code == "de"

    def test_french_text_detected(self):
        text = (
            "Ce contrat de bail est conclu entre le bailleur et le locataire. "
            "Le loyer mensuel est dû le premier jour de chaque mois. "
            "Le dépôt de garantie équivaut à deux mois de loyer."
        ) * 3
        result = detect_language(text)
        assert result.detected_code == "fr"

    def test_insufficient_text_returns_insufficient(self):
        result = detect_language("Hi")
        assert result.confidence == DetectionConfidence.INSUFFICIENT
        assert result.detected_code is None
        assert result.mismatch is False

    def test_empty_text_returns_insufficient(self):
        result = detect_language("")
        assert result.confidence == DetectionConfidence.INSUFFICIENT

    def test_mismatch_true_when_differs(self):
        text = (
            "This employment contract is made between the employer and the employee. "
            "The position shall commence on the start date specified herein. "
            "The annual salary shall be paid in equal monthly installments."
        ) * 3
        result = detect_language(text, user_selected_code="de")
        # English text vs German selected — expect mismatch if high confidence
        if result.confidence == DetectionConfidence.HIGH:
            assert result.mismatch is True
            assert result.user_selected_code == "de"

    def test_no_mismatch_when_matches(self):
        text = (
            "This employment contract is entered into by and between the parties. "
            "The employee agrees to the terms and conditions set forth herein. "
            "Compensation shall be reviewed annually by the employer."
        ) * 3
        result = detect_language(text, user_selected_code="en")
        # Detected=en, selected=en → no mismatch
        if result.confidence == DetectionConfidence.HIGH and result.detected_code == "en":
            assert result.mismatch is False

    def test_no_mismatch_when_confidence_low(self):
        """Low-confidence detections should not trigger mismatch."""
        # Manufacture a low-confidence result via mocking
        from langdetect.language import Language
        mock_lang = Language("de", 0.60)
        with patch("app.services.language_detection.detect_langs", return_value=[mock_lang]):
            text = "a" * 100  # enough content chars to pass length check
            result = detect_language(text, user_selected_code="en")
        assert result.mismatch is False

    def test_no_mismatch_when_no_user_selection(self):
        text = (
            "This service agreement is entered into as of the date signed below. "
            "The service provider agrees to render the specified services diligently."
        ) * 3
        result = detect_language(text, user_selected_code=None)
        assert result.mismatch is False

    def test_result_fields_populated(self):
        text = (
            "This lease agreement is binding on both parties. "
            "The tenant shall maintain the property in good condition throughout the tenancy."
        ) * 3
        result = detect_language(text, user_selected_code="en")
        assert result.probability >= 0.0
        assert result.probability <= 1.0
        assert result.user_selected_name == "English"

    def test_detected_name_from_supported_list(self):
        from langdetect.language import Language
        mock_lang = Language("fr", 0.99)
        with patch("app.services.language_detection.detect_langs", return_value=[mock_lang]):
            text = "a" * 100
            result = detect_language(text)
        assert result.detected_name == "French"

    def test_langdetect_exception_returns_insufficient(self):
        from langdetect import LangDetectException
        with patch("app.services.language_detection.detect_langs", side_effect=LangDetectException(0, "fail")):
            text = "a" * 100
            result = detect_language(text)
        assert result.confidence == DetectionConfidence.INSUFFICIENT
        assert result.mismatch is False


# ── POST /api/v1/detect-language ─────────────────────────────────────────────

@pytest.fixture
async def client():
    import app.core.redis as redis_module
    import app.middleware.rate_limit as rl_module
    from unittest.mock import patch, AsyncMock
    from httpx import ASGITransport, AsyncClient
    from app.core.rate_limit import RateLimitResult

    async def _mock_check_rate(*args, **kwargs):
        return RateLimitResult(allowed=True, limit=100, remaining=99, reset_in_seconds=3600)

    with patch.object(rl_module, "check_rate_limit", side_effect=_mock_check_rate):
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:
            yield c


class TestDetectLanguageEndpoint:
    ENGLISH_CONTRACT = (
        "This Lease Agreement is entered into between the Landlord and the Tenant. "
        "The monthly rent shall be due on the first day of each month. "
        "Security deposit equals two months rent and is refundable."
    ) * 4

    @pytest.mark.asyncio
    async def test_returns_200_with_valid_text(self, client):
        r = await client.post("/api/v1/detect-language", json={"text": self.ENGLISH_CONTRACT})
        assert r.status_code == 200
        body = r.json()
        assert "detected_code" in body
        assert "confidence" in body
        assert "mismatch" in body
        assert "supported_languages" in body

    @pytest.mark.asyncio
    async def test_includes_supported_languages_map(self, client):
        r = await client.post("/api/v1/detect-language", json={"text": self.ENGLISH_CONTRACT})
        assert r.status_code == 200
        langs = r.json()["supported_languages"]
        assert "en" in langs
        assert "hi" in langs
        assert langs["en"] == "English"

    @pytest.mark.asyncio
    async def test_mismatch_flagged_when_wrong_selection(self, client):
        r = await client.post(
            "/api/v1/detect-language",
            json={"text": self.ENGLISH_CONTRACT, "user_selected_code": "de"},
        )
        assert r.status_code == 200
        body = r.json()
        if body["confidence"] == "high":
            assert body["mismatch"] is True

    @pytest.mark.asyncio
    async def test_empty_text_returns_422(self, client):
        r = await client.post("/api/v1/detect-language", json={"text": ""})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_language_code_returns_422(self, client):
        r = await client.post(
            "/api/v1/detect-language",
            json={"text": self.ENGLISH_CONTRACT, "user_selected_code": "not-a-valid-bcp47-code-toolong"},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_no_user_selection_no_mismatch(self, client):
        r = await client.post("/api/v1/detect-language", json={"text": self.ENGLISH_CONTRACT})
        assert r.status_code == 200
        assert r.json()["mismatch"] is False
        assert r.json()["user_selected_code"] is None
