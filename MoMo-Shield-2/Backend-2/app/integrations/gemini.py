import asyncio
import json
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

async def analyze_intent(text: str) -> str:
    if not settings.gemini_enabled or not text:
        return "N/A"
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
            
        resp = await asyncio.wait_for(asyncio.to_thread(_call), timeout=1.5)
        data = json.loads(resp.text)
        return data.get('pattern', 'Unknown')
    except Exception as e:
        log.warning(f"Gemini failed: {e}")
        return "Fallback: Keyword Match"