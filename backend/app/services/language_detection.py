"""
CLR-012 — Document language detection.

Detects the language of extracted OCR text and returns a structured result
the frontend uses to warn users when detected language differs from their selection.

SECURITY: Only operates on text strings — never receives raw document bytes.
          The caller (run_ocr) is responsible for purging the raw document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import structlog
from langdetect import DetectorFactory, LangDetectException, detect_langs

from app.core.logging import get_logger

# Make langdetect deterministic
DetectorFactory.seed = 0

logger = get_logger(__name__)

# ── Supported document languages ─────────────────────────────────────────────
# BCP-47 codes that Clairo accepts as document languages.
# Source: CLR-014 language selection screen spec (20+ languages).
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "de": "German",
    "es": "Spanish",
    "ar": "Arabic",
    "fr": "French",
    "pt": "Portuguese",
    "ur": "Urdu",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
}

# langdetect returns 'zh-cn'/'zh-tw' style codes; normalise them
_LANGDETECT_ALIAS: dict[str, str] = {
    "zh-cn": "zh-cn",
    "zh-tw": "zh-tw",
    "zh": "zh-cn",
    "id": "id",
    "ms": "ms",
}


def _normalise(code: str) -> str:
    """Normalise a langdetect BCP-47 code to a Clairo-supported code."""
    code = code.lower()
    if code in _LANGDETECT_ALIAS:
        return _LANGDETECT_ALIAS[code]
    # Strip region suffix (e.g. pt-br → pt)
    base = code.split("-")[0]
    if base in SUPPORTED_LANGUAGES:
        return base
    return code


# ── Confidence threshold ──────────────────────────────────────────────────────
# langdetect returns probability 0–1 per candidate.
HIGH_CONFIDENCE_THRESHOLD = 0.85
MIN_TEXT_LENGTH = 50  # characters; too short = unreliable


class DetectionConfidence(str, Enum):
    HIGH = "high"        # ≥ 85% probability
    LOW = "low"          # < 85% — warn but don't block
    INSUFFICIENT = "insufficient"  # text too short to detect reliably


@dataclass
class LanguageDetectionResult:
    detected_code: str | None         # BCP-47, None if detection failed
    detected_name: str | None
    confidence: DetectionConfidence
    probability: float                 # 0.0–1.0
    mismatch: bool                     # True when detected ≠ user_selected
    user_selected_code: str | None
    user_selected_name: str | None


def detect_language(
    text: str,
    user_selected_code: str | None = None,
) -> LanguageDetectionResult:
    """
    Detect the language of *text* and optionally compare against *user_selected_code*.

    Args:
        text: Extracted plain text (from OCR or direct extraction).
              SECURITY: caller must not pass raw document bytes.
        user_selected_code: BCP-47 code the user chose in CLR-014 UI (or None).

    Returns:
        LanguageDetectionResult with mismatch=True when detected ≠ selected.
    """
    log = logger.bind(text_length=len(text), user_selected=user_selected_code)

    # Guard: too-short text is unreliable
    # Strip whitespace/numbers to measure meaningful content
    content = re.sub(r"[\s\d\W]+", "", text)
    if len(content) < MIN_TEXT_LENGTH:
        log.info("language_detection.insufficient_text")
        return LanguageDetectionResult(
            detected_code=None,
            detected_name=None,
            confidence=DetectionConfidence.INSUFFICIENT,
            probability=0.0,
            mismatch=False,
            user_selected_code=user_selected_code,
            user_selected_name=SUPPORTED_LANGUAGES.get(user_selected_code or ""),
        )

    try:
        candidates = detect_langs(text)
    except LangDetectException as exc:
        log.warning("language_detection.failed", error=str(exc))
        return LanguageDetectionResult(
            detected_code=None,
            detected_name=None,
            confidence=DetectionConfidence.INSUFFICIENT,
            probability=0.0,
            mismatch=False,
            user_selected_code=user_selected_code,
            user_selected_name=SUPPORTED_LANGUAGES.get(user_selected_code or ""),
        )

    # Top candidate
    top = candidates[0]
    detected_code = _normalise(top.lang)
    probability = round(top.prob, 3)
    confidence = (
        DetectionConfidence.HIGH
        if probability >= HIGH_CONFIDENCE_THRESHOLD
        else DetectionConfidence.LOW
    )
    detected_name = SUPPORTED_LANGUAGES.get(detected_code, detected_code)

    # Mismatch check — only flag when BOTH codes are known and confidence is HIGH
    mismatch = False
    if (
        user_selected_code
        and detected_code
        and confidence == DetectionConfidence.HIGH
        and _normalise(user_selected_code) != detected_code
    ):
        mismatch = True

    log.info(
        "language_detection.complete",
        detected=detected_code,
        probability=probability,
        confidence=confidence.value,
        mismatch=mismatch,
    )

    return LanguageDetectionResult(
        detected_code=detected_code,
        detected_name=detected_name,
        confidence=confidence,
        probability=probability,
        mismatch=mismatch,
        user_selected_code=user_selected_code,
        user_selected_name=SUPPORTED_LANGUAGES.get(user_selected_code or ""),
    )
