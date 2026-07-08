"""
CLR-013 — Document type detection and prohibited type blocking.

Claude classifies document type from first 500 words.
Prohibited types are hard-blocked before any further processing.
Free analysis quota is NOT decremented for prohibited documents.

SECURITY:
- Only the first 500 words are sent to Claude (reduced attack surface).
- Document content passed as user message data — never system message.
- Result is validated as one of the known enum values before use.
"""
from __future__ import annotations

import json
import os
from enum import Enum

import anthropic
import structlog

from app.core.logging import get_logger
from app.core.secrets import get_secret

logger = get_logger(__name__)


async def _classify_raw(excerpt: str) -> str:
    """
    Send the excerpt to the configured LLM and return the raw JSON string.
    Mirrors the LLM_PROVIDER switch in app/services/analysis.py: OpenAI when
    LLM_PROVIDER=openai, otherwise Anthropic Claude (default / production).
    """
    user_content = f"Classify this document excerpt (respond with JSON):\n\n{excerpt}"

    if os.getenv("LLM_PROVIDER", "anthropic").strip().lower() == "openai":
        from openai import AsyncOpenAI

        api_key = get_secret("clairo/openai").get("api_key", "")
        client = AsyncOpenAI(api_key=api_key)
        resp = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            max_tokens=256,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        return (resp.choices[0].message.content or "").strip()

    api_key = get_secret("clairo/anthropic").get("api_key", "")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text.strip()

# ── Document types ────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    # Permitted types
    RENTAL          = "rental"
    EMPLOYMENT      = "employment"
    FREELANCE       = "freelance"
    TOS             = "tos"
    OTHER_PERMITTED = "other_permitted"

    # Prohibited types — hard block, no analysis, no quota decrement
    COURT_ORDER         = "court_order"
    IMMIGRATION         = "immigration"
    MEDICAL_CONSENT     = "medical_consent"
    FINANCIAL_INSTRUMENT = "financial_instrument"
    MINOR_INVOLVED      = "minor_involved"


PROHIBITED_TYPES: frozenset[DocumentType] = frozenset({
    DocumentType.COURT_ORDER,
    DocumentType.IMMIGRATION,
    DocumentType.MEDICAL_CONSENT,
    DocumentType.FINANCIAL_INSTRUMENT,
    DocumentType.MINOR_INVOLVED,
})

PERMITTED_TYPES: frozenset[DocumentType] = frozenset(
    t for t in DocumentType if t not in PROHIBITED_TYPES
)

# Referrals shown on the blocked screen (CLR-038)
PROHIBITED_REFERRALS: dict[DocumentType, dict[str, str]] = {
    DocumentType.COURT_ORDER: {
        "org": "Legal Aid Society",
        "url": "https://www.lsc.gov/about-lsc/what-legal-aid/get-legal-help",
        "reason_key": "court_order",
    },
    DocumentType.IMMIGRATION: {
        "org": "UNHCR",
        "url": "https://www.unhcr.org/get-help",
        "reason_key": "immigration",
    },
    DocumentType.MEDICAL_CONSENT: {
        "org": "Patient Advocate Foundation",
        "url": "https://www.patientadvocate.org",
        "reason_key": "medical_consent",
    },
    DocumentType.FINANCIAL_INSTRUMENT: {
        "org": "CFPB",
        "url": "https://www.consumerfinance.gov/ask-cfpb",
        "reason_key": "financial_instrument",
    },
    DocumentType.MINOR_INVOLVED: {
        "org": "Legal Aid Society",
        "url": "https://www.lsc.gov/about-lsc/what-legal-aid/get-legal-help",
        "reason_key": "minor_involved",
    },
}

# ── Classification prompt ─────────────────────────────────────────────────────

_MAX_WORDS = 500

_SYSTEM_PROMPT = """\
You are a document classifier. Your only job is to classify legal documents
into one of these types and return a JSON object.

PERMITTED document types:
- rental: lease agreements, rental contracts, tenancy agreements
- employment: job contracts, offer letters, employment agreements
- freelance: service agreements, independent contractor contracts, SOWs
- tos: terms of service, terms and conditions, user agreements, privacy policies
- other_permitted: NDAs, partnership agreements, simple purchase orders, licensing

PROHIBITED document types (these require professional specialist help):
- court_order: court orders, judgments, injunctions, subpoenas, warrants
- immigration: visa applications, asylum documents, immigration petitions
- medical_consent: medical consent forms, HIPAA authorizations, treatment agreements
- financial_instrument: mortgages, promissory notes, securities, loan agreements, bonds
- minor_involved: any document primarily concerning the rights or custody of a minor

Return ONLY valid JSON in this exact schema:
{
  "document_type": "<one of the type strings above>",
  "confidence": <float 0.0–1.0>,
  "reasoning": "<one sentence, 15 words max>"
}

No other text. No markdown. No explanation outside the JSON object.\
"""


def _first_500_words(text: str) -> str:
    words = text.split()
    return " ".join(words[:_MAX_WORDS])


# ── Result dataclass ──────────────────────────────────────────────────────────

from dataclasses import dataclass

@dataclass
class DocumentTypeResult:
    document_type: DocumentType
    is_prohibited: bool
    confidence: float
    reasoning: str
    referral: dict[str, str] | None   # populated only for prohibited types


# ── Detection function ────────────────────────────────────────────────────────

async def detect_document_type(text: str) -> DocumentTypeResult:
    """
    Classify the document type using Claude on the first 500 words.

    SECURITY:
    - Only first 500 words sent — reduced attack surface.
    - Text passed as USER message — never in system prompt.
    - Response validated as strict enum before use.

    Raises:
        ValueError: if Claude returns an unrecognised type or malformed JSON.
    """
    excerpt = _first_500_words(text)
    log = logger.bind(excerpt_words=len(excerpt.split()))

    raw = await _classify_raw(excerpt)
    log.info("document_type.raw_response", chars=len(raw))

    # OpenAI/JSON-mode may wrap output in a code fence — strip it defensively.
    if raw.startswith("```"):
        import re

        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()

    # Parse and validate
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("document_type.json_parse_error", error=str(exc))
        raise ValueError(f"Claude returned non-JSON: {raw[:100]}") from exc

    type_str = parsed.get("document_type", "")
    try:
        doc_type = DocumentType(type_str)
    except ValueError:
        log.error("document_type.unknown_type", received=type_str)
        raise ValueError(f"Unknown document type from Claude: {type_str!r}")

    confidence = float(parsed.get("confidence", 0.0))
    reasoning = str(parsed.get("reasoning", ""))[:200]
    is_prohibited = doc_type in PROHIBITED_TYPES

    log.info(
        "document_type.classified",
        document_type=doc_type.value,
        is_prohibited=is_prohibited,
        confidence=confidence,
    )

    return DocumentTypeResult(
        document_type=doc_type,
        is_prohibited=is_prohibited,
        confidence=confidence,
        reasoning=reasoning,
        referral=PROHIBITED_REFERRALS.get(doc_type) if is_prohibited else None,
    )
