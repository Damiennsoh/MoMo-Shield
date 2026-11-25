import asyncio
import json
import re
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

# Data-protection (Act 843) hygiene: subscriber PII is masked before any
# text leaves the network boundary. Intent analysis only needs the
# linguistic pattern, not the actual numbers.
_MSISDN_RE = re.compile(r"(?:\+?233|0)\d{9}\b")
_GHANA_CARD_RE = re.compile(r"\bGHA-\d{3}-\d{3}-\d-\d\b|\b\d{9}-\d{1}\b")
_LONG_DIGITS_RE = re.compile(r"\b\d{4,}\b")


def redact_pii(text: str) -> str:
    """Mask phone numbers, Ghana Card IDs and long digit runs (OTPs,
    account references) while preserving the message's linguistic shape."""
    out = _MSISDN_RE.sub("[PHONE]", str(text or ""))
    out = _GHANA_CARD_RE.sub("[ID]", out)
    out = _LONG_DIGITS_RE.sub("[NUMBER]", out)
    return out


def _keyword_intent_fallback(text: str) -> str:
    lower = (text or "").lower()
    has_secret = any(w in lower for w in ["pin", "otp", "password", "passcode", "secret", "cvv", "code", "wo pin", "fa wo pin"])
    has_auth = any(w in lower for w in ["mtn", "telecel", "vodafone", "bank", "fraud department", "head office", "agent", "official", "regulator"])
    has_urgency = any(w in lower for w in ["urgent", "immediately", "right now", "suspended", "blocked", "locked", "expire", "terminate", "anya problem"])
    has_prize = any(w in lower for w in ["prize", "won", "winner", "congratulations", "lottery", "reward"])

    if has_secret and (has_auth or has_urgency):
        return "Authority Impersonation + Credential Solicitation (PIN/OTP)"
    if has_auth and has_urgency:
        return "Authority Impersonation + Coercive Urgency"
    if has_prize and (has_secret or has_urgency):
        return "Advance-Fee Lottery Bait + Urgent Secret Request"
    if has_secret:
        return "Direct Credential Harvesting (PIN/OTP Request)"
    if has_prize:
        return "Prize / Lottery Scam Pattern"
    if has_auth:
        return "Operator / Authority Reference"
    return "Neutral / Benign Communication"


async def analyze_intent(text: str, rag_context: str | None = None) -> str:
    if not text:
        return "Neutral / Benign Communication"
    if not settings.gemini_enabled or not settings.gemini_enrichment_enabled:
        return _keyword_intent_fallback(text)
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)

        if rag_context is None:
            try:
                from app.engine.kb import knowledge_base
                rag_context = knowledge_base.get_rag_context(text)
            except Exception:
                pass

        safe_text = redact_pii(text) if settings.gemini_redact_pii else text
        rag_prompt_section = f"\nRelevant Precedent from InnoFemme Fraud Case Library:\n{rag_context}\n" if rag_context else ""
        prompt = (
            f"Analyze this Ghanaian mobile money communication for fraud intent.{rag_prompt_section}"
            f"Return JSON: {{'pattern': str, 'secret_requested': bool}}. Text: {safe_text}"
        )

        def _call():
            return client.models.generate_content(
                model=settings.gemini_model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )

        resp = await asyncio.wait_for(asyncio.to_thread(_call), timeout=settings.gemini_timeout_seconds)
        data = json.loads(resp.text)
        return data.get('pattern') or _keyword_intent_fallback(text)
    except Exception as e:
        log.warning(f"Gemini API fallback to heuristic: {e}")
        return _keyword_intent_fallback(text)