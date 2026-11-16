import asyncio
import json
from typing import Optional, Dict, Any
from app.config import settings
from app.ai.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES, RESPONSE_SCHEMA
from app.utils.logger import get_logger

log = get_logger(__name__)

async def extract_intent(text: str) -> Optional[Dict[str, Any]]:
    if not settings.gemini_enabled: return None
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Google GenAI SDK is unavailable") from exc

    client = genai.Client(api_key=settings.gemini_api_key)
    examples_text = "\n".join([f"Input: {ex['input']}\nOutput: {ex['output']}" for ex in FEW_SHOT_EXAMPLES])
    full_prompt = f"{SYSTEM_PROMPT}\n\nExamples:\n{examples_text}\n\nNOW ANALYZE THIS TEXT:\n{text}\nReturn ONLY JSON."

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model, contents=full_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RESPONSE_SCHEMA, temperature=0.1)
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=settings.gemini_timeout_seconds)
        return json.loads(response.text)
    except asyncio.TimeoutError:
        log.warning("Gemini call timed out")
        raise
    except Exception as e:
        log.warning(f"Gemini call failed: {e}")
        raise
