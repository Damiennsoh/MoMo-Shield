import asyncio
from datetime import datetime
from types import SimpleNamespace

from app.engine import scorer
from app.engine.state import global_window


BASE_SETTINGS = SimpleNamespace(
    risk_threshold_medium=40,
    risk_threshold_high=75,
)


def _event(text):
    return {
        "event_id": "provenance-test",
        "msisdn": "233245550123",
        "event_type": "communication",
        "channel": "SMS",
        "text_or_transcript": text,
        "timestamp": datetime.utcnow().isoformat(),
    }


def test_gemini_intent_source_is_reported(monkeypatch):
    async def fake_extract(_text):
        return {
            "pattern": "Credential Request",
            "evidence_phrases": ["send your OTP"],
            "requested_secret": "OTP",
            "language_detected": "English",
            "suggested_warning": "Do not share your OTP.",
        }

    monkeypatch.setattr(scorer, "settings", SimpleNamespace(
        **vars(BASE_SETTINGS), gemini_enabled=True
    ))
    monkeypatch.setattr(scorer, "extract_intent", fake_extract)
    global_window.reset()
    result = asyncio.run(scorer.assess(_event("Send your OTP now.")))
    assert result.intent_source == "gemini"
    assert result.llm_extracted_intent.requested_secret == "OTP"
    assert result.llm_unavailable is False


def test_keyword_fallback_source_is_reported(monkeypatch):
    monkeypatch.setattr(scorer, "settings", SimpleNamespace(
        **vars(BASE_SETTINGS), gemini_enabled=False
    ))
    global_window.reset()
    result = asyncio.run(scorer.assess(_event("MTN says send your OTP now.")))
    assert result.intent_source == "keyword_fallback"
    assert result.llm_extracted_intent.requested_secret == "OTP"
    assert result.llm_unavailable is False
