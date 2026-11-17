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
