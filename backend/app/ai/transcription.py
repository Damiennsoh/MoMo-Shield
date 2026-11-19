"""Optional, non-persistent speech-to-text for consented synthetic demo audio."""

import asyncio
import json
import re
from typing import Any

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

TRANSCRIPTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "transcript": {"type": "STRING"},
        "uncertain": {"type": "BOOLEAN"},
        "note": {"type": "STRING"},
    },
    "required": ["transcript", "uncertain", "note"],
}

_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+233|0)(?:[\s().-]?\d){9}(?!\w)")
_CODE_PATTERN = re.compile(
    r"\b(?:pin|otp|code|one[- ]time\s+(?:pin|password|code)|verification code|security code)"
    r"\b\s*(?:is|:|=)?\s*(?:\d[\s-]*){4,8}(?!\d)",
    re.IGNORECASE,
)


def _redact_likely_sensitive_values(text: str) -> str:
    text = _PHONE_PATTERN.sub("[PHONE]", text)
    return _CODE_PATTERN.sub(lambda match: re.sub(r"(?:\d[\s-]*){4,8}(?!\d)", "[CODE]", match.group(0)), text)


async def transcribe_wav(audio_bytes: bytes, language_hint: str = "English") -> dict[str, Any]:
    """Transcribe a short WAV using the configured Gemini model without storing audio."""
    if not settings.gemini_enabled:
        raise RuntimeError("Speech transcription is not configured. Set GEMINI_API_KEY on the backend.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Google GenAI SDK is unavailable on the backend.") from exc

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = (
        "Transcribe the supplied speech as faithfully as possible. Do not summarize, translate, "
        "classify, infer missing words, or add advice. Preserve the spoken language and any "
        "code-switching. If a phrase is unclear, mark it [inaudible] and set uncertain=true. "
        "Return only JSON matching the response schema. Language hint supplied by the user: "
        f"{language_hint}. The hint is not proof that the speech uses that language."
    )

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=[prompt, types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TRANSCRIPTION_SCHEMA,
                temperature=0.0,
            ),
        )

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_call), timeout=settings.gemini_timeout_seconds
        )
        payload = json.loads(response.text or "{}")
        transcript = str(payload.get("transcript", "")).strip()
        uncertain = bool(payload.get("uncertain", True)) or not transcript
        transcript = _redact_likely_sensitive_values(transcript)
        note = str(payload.get("note", "")).strip()
        if not note:
            note = "Review and correct this transcript before assessment."
        if "[inaudible]" in transcript.casefold():
            uncertain = True
        return {
            "transcript": transcript,
            "uncertain": uncertain,
            "note": note,
            "source": "Gemini transcription draft",
        }
    except asyncio.TimeoutError as exc:
        raise RuntimeError("Speech transcription timed out. You can type the synthetic text instead.") from exc
    except Exception as exc:
        log.warning("Speech transcription failed (%s)", type(exc).__name__)
        raise RuntimeError("Speech transcription was unavailable. Type or paste a synthetic example instead.") from exc
