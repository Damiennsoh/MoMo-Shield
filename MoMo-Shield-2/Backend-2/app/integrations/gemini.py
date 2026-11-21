import asyncio
import json
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


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


async def analyze_intent(text: str) -> str:
    if not text:
        return "Neutral / Benign Communication"
    if not settings.gemini_enabled:
        return _keyword_intent_fallback(text)
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)

        prompt = f"Analyze this MoMo message for fraud intent. Return JSON: {{'pattern': str, 'secret_requested': bool}}. Text: {text}"

        def _call():
            return client.models.generate_content(
                model=settings.gemini_model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )

        resp = await asyncio.wait_for(asyncio.to_thread(_call), timeout=2.0)
        data = json.loads(resp.text)
        return data.get('pattern') or _keyword_intent_fallback(text)
    except Exception as e:
        log.warning(f"Gemini API fallback to heuristic: {e}")
        return _keyword_intent_fallback(text)