import io
import json
import sys
import wave
from pathlib import Path

import httpx

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))

from services.api_client import assess_event
from services.audio import alert_tone_bytes
from services.local_engine import new_accumulator
from components.mock_phone import phone_markup

FIXTURES = FRONTEND / "fixtures"
EXPECTED = {
    "gh01_fake_credit.json": ("HIGH", "SIMULATED_HOLD"),
    "gh02_reversal_syndicate.json": ("HIGH", "SIMULATED_HOLD"),
    "gh15_fake_business_listing.json": ("HIGH", "SIMULATED_HOLD"),
    "gh17_fake_support.json": ("HIGH", "SIMULATED_HOLD"),
    "gh18_device_takeover.json": ("HIGH", "SIMULATED_HOLD"),
    "gh19_nuisance_calls.json": ("HIGH", "FRAUDOPS_ALERT"),
    "legit_baseline.json": ("LOW", "SEAMLESS_APPROVE"),
}
LABEL_FIXTURE = {
    "GH01 — Fake Credit → Refund Scam": "gh01_fake_credit.json",
    "GH18 — New Device Takeover": "gh18_device_takeover.json",
    "GH17 — Fake Support → Wallet Drain": "gh17_fake_support.json",
    "GH02 — Reversal Syndicate & Forged Receipt": "gh02_reversal_syndicate.json",
    "GH15 — Fake Business Listing & PIN Harvest": "gh15_fake_business_listing.json",
    "GH19 — Nuisance Call Swarm → Fake Helper": "gh19_nuisance_calls.json",
    "Legitimate Baseline (False-Positive Control)": "legit_baseline.json",
}


def test_all_scenario_fixtures_have_expected_offline_decisions(monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("backend unavailable")

    monkeypatch.setattr("services.api_client.httpx.post", unavailable)
    for filename, expected in EXPECTED.items():
        fixture = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
        accumulator = new_accumulator()
        result = None
        source = None
        for step in fixture["steps"]:
            if "event" in step:
                result, source = assess_event(step["event"], "http://127.0.0.1:8000", accumulator)
        assert result is not None, filename
        assert source == "local", filename
        assert (result["risk_tier"], result["recommended_action"]) == expected, filename


def test_alert_tone_is_valid_playable_wav():
    with wave.open(io.BytesIO(alert_tone_bytes()), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 22050
        assert audio.getnframes() > 0


def test_phone_warning_and_caption_are_nested_in_single_phone_fragment():
    markup = phone_markup({
        "screen": "ussd",
        "ussd_lines": ["*170#", "SIMULATED TRANSACTION HOLD"],
        "warning": {"title": "FRAUD ALERT", "body": "Do not share your PIN."},
    })
    body_start = markup.index('<div class="phone-body">')
    body_end = markup.index('</div>\n      <div class="phone-caption">', body_start)
    warning_start = markup.index('<div class="phone-warning', body_start)
    assert body_start < warning_start < body_end
    assert '<div class="phone-caption">' in markup
    assert markup.count('<div class="phone-frame">') == 1


def test_bundled_sfx_assets_are_valid_offline_wavs():
    for name in ("sms.wav", "ring.wav", "alert.wav"):
        with wave.open(str(FRONTEND / "assets" / name), "rb") as audio:
            assert audio.getnchannels() == 1
            assert audio.getframerate() == 22050
            assert audio.getnframes() > 0


def test_recorded_mp3_sfx_overrides_bundled_wav(monkeypatch):
    import services.audio as audio_service
    requested = []
    rendered = []

    def read_asset(name):
        requested.append(name)
        return (b"recorded-mp3", "audio/mpeg") if name == "sms.mp3" else (None, None)

    monkeypatch.setattr(audio_service, "_audio_bytes", read_asset)
    monkeypatch.setattr(audio_service.components, "html", lambda markup, **kwargs: rendered.append(markup))
    assert audio_service.play_sfx("sms.wav")
    assert requested[0] == "sms.mp3"
    assert "audio/mpeg" in rendered[0]


def test_recorded_warning_clip_is_preferred_over_browser_tts(monkeypatch):
    import services.audio as audio_service
    requested = []
    monkeypatch.setattr(audio_service, "play_sfx", lambda name, **kwargs: requested.append(name) or name == "warning_twi.mp3")
    monkeypatch.setattr(audio_service, "speak_english_warning", lambda text: (_ for _ in ()).throw(AssertionError("TTS should not run")))
    assert audio_service.play_warning_audio("Twi text", "English text") == "recorded"
    assert requested == ["warning_twi.wav", "warning_twi.mp3"]


def test_warning_falls_back_to_english_only_when_no_recording_is_supplied(monkeypatch):
    import services.audio as audio_service
    spoken = []
    monkeypatch.setattr(audio_service, "play_sfx", lambda *args, **kwargs: False)
    monkeypatch.setattr(audio_service, "speak_english_warning", lambda text: spoken.append(text) or True)
    assert audio_service.play_warning_audio("Twi text", "English warning") == "english_tts"
    assert spoken == ["English warning"]


def test_prerecorded_english_warning_is_used_when_localized_clip_is_missing(monkeypatch):
    import services.audio as audio_service
    requested = []
    monkeypatch.setattr(audio_service, "play_sfx", lambda name, **kwargs: requested.append(name) or name == "warning_en.mp3")
    monkeypatch.setattr(audio_service, "speak_english_warning", lambda text: (_ for _ in ()).throw(AssertionError("TTS should not run")))
    assert audio_service.play_warning_audio("Twi text", "English warning") == "recorded_english"
    assert requested == ["warning_twi.wav", "warning_twi.mp3", "warning_en.wav", "warning_en.mp3"]


def test_batch_replay_retains_inspectable_events_and_intent():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=60).run()
    assert sum(text.label == "Backend API URL" for text in app.text_input) == 1
    app.text_input[0].set_value("http://127.0.0.1:1").run()
    app.button[2].click().run(timeout=60)

    records = app.session_state["scenario_records"]
    assert len(records) == 7
    for record in records:
        assessment = record["assessment"]
        fixture = json.loads((FIXTURES / LABEL_FIXTURE[record["Scenario"]]).read_text(encoding="utf-8"))
        assert len(assessment["event_log"]) == len(fixture["steps"])
        if any("event" in step and step["event"].get("event_type") == "communication"
               for step in fixture["steps"]):
            assert assessment["intent_text"]
            assert assessment["intent_source"] == "keyword_fallback"
    by_name = {record["Scenario"]: record["assessment"] for record in records}
    gh19 = by_name["GH19 — Nuisance Call Swarm → Fake Helper"]
    assert gh19["intent_source"] == "keyword_fallback"
    assert gh19["intent_text"]
    assert len(app.metric) >= 13
    assert len(app.selectbox) >= 2
    assert not app.dataframe
    assert not app.exception
