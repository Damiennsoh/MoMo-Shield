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
from components import mock_phone
from components.mock_phone import phone_markup
from services.api_client import demo_device_event_key

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


def test_phone_markup_is_compact_and_warning_caption_are_nested():
    markup = phone_markup({
        "screen": "ussd",
        "ussd_lines": ["*170#", "SIMULATED TRANSACTION HOLD"],
        "warning": {"title": "FRAUD ALERT", "body": "Do not share your PIN."},
    })
    assert markup.startswith('<div class="phone-frame"')
    assert "\n" not in markup
    body_start = markup.index('<div class="phone-body">')
    body_end = markup.index('<div class="phone-caption">', body_start)
    warning_start = markup.index('<div class="phone-warning', body_start)
    assert body_start < warning_start < body_end
    assert markup.count('<div class="phone-frame"') == 1
    assert "*170#<br>SIMULATED TRANSACTION HOLD" in markup


def test_active_call_ends_inside_the_intervention_warning():
    markup = phone_markup({
        "screen": "ussd",
        "ussd_lines": ["*170#", "SIMULATED TRANSACTION HOLD"],
        "warning": {"title": "FRAUD ALERT", "body": "Do not share your PIN.", "call_ended": True},
    })
    assert "Call disconnected at FraudOps intervention" in markup
    assert markup.count('<div class="phone-warning') == 1


def test_all_fixture_phone_screens_render_as_one_html_fragment():
    for fixture_path in sorted(FIXTURES.glob("*.json")):
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        state = {"screen": "home"}
        for step in fixture["steps"]:
            if step.get("phone_ui"):
                state.update(step["phone_ui"])
                markup = phone_markup(state)
                assert markup.startswith('<div class="phone-frame"'), fixture_path.name
                assert "\n" not in markup, fixture_path.name
                assert markup.count('<div class="phone-frame"') == 1, fixture_path.name
                assert '<div class="phone-caption">' in markup, fixture_path.name
                # Exercise an intervention overlay on every fixture's final
                # handset state, not only the scenario that exposed the bug.
                alerted = dict(state, warning={"title": "FRAUD ALERT", "body": "Keep your PIN private."})
                alert_markup = phone_markup(alerted)
                assert "<div class=\"phone-warning\"" in alert_markup, fixture_path.name
                assert alert_markup.index('<div class="phone-body">') < alert_markup.index('<div class="phone-warning') < alert_markup.index('<div class="phone-caption">'), fixture_path.name


def test_render_phone_uses_single_unsafe_html_markdown_call(monkeypatch):
    calls = []
    monkeypatch.setattr(mock_phone.st, "markdown", lambda body, **kwargs: calls.append((body, kwargs)))
    mock_phone.render_phone({"screen": "home"})
    assert len(calls) == 1
    assert calls[0][0].startswith('<div class="phone-frame"')
    assert calls[0][1] == {"unsafe_allow_html": True}


def test_live_phone_render_uses_the_same_single_html_path():
    calls = []

    class Placeholder:
        def markdown(self, body, **kwargs):
            calls.append((body, kwargs))

    mock_phone.render_phone({"screen": "call", "caller": "Safe Number"}, target=Placeholder())
    assert len(calls) == 1
    assert '<div class="call-screen">' in calls[0][0]
    assert calls[0][1] == {"unsafe_allow_html": True}


def test_second_device_keys_upsert_call_updates_without_collapsing_distinct_callers():
    scenario = "GH19 — Nuisance Call Swarm → Fake Helper"
    first = demo_device_event_key(scenario, "call", "055 000 0055")
    same_call_update = demo_device_event_key(scenario, "call", "055 000 0055")
    other_call = demo_device_event_key(scenario, "call", "055 000 0044")
    warning_1 = demo_device_event_key(scenario, "warning")
    warning_2 = demo_device_event_key(scenario, "warning")
    assert first == same_call_update
    assert first != other_call
    assert warning_1 == warning_2
    assert len(first) <= 140


def test_bundled_sfx_assets_are_valid_offline_wavs():
    for name in ("sms.wav", "ring.wav", "alert.wav"):
        with wave.open(str(FRONTEND / "assets" / name), "rb") as audio:
            assert audio.getnchannels() == 1
            assert audio.getframerate() == 22050
            assert audio.getnframes() > 0
    for name in ("sms.mp3", "ring.mp3"):
        assert (FRONTEND / "assets" / name).stat().st_size > 1000
    assert (FRONTEND / "assets" / "ring.mp3").read_bytes().startswith(b"ID3")


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


def test_contextual_warning_uses_english_tts_without_loading_recorded_safety_clips(monkeypatch):
    import services.audio as audio_service
    spoken = []
    monkeypatch.setattr(audio_service, "play_sfx", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Warning clips are not used")))
    monkeypatch.setattr(audio_service, "speak_english_warning", lambda text: spoken.append(text) or True)
    assert audio_service.play_warning_audio("unreviewed localization", "Do not send money back based on a screenshot.") == "english_tts"
    assert spoken == ["Do not send money back based on a screenshot."]


def test_spoken_warning_has_a_stop_control(monkeypatch):
    import services.audio as audio_service
    rendered = []
    monkeypatch.setattr(audio_service.components, "html", lambda markup, **kwargs: rendered.append(markup))
    audio_service.stop_spoken_warning()
    assert "speechSynthesis.cancel()" in rendered[0]


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


def test_gh01_call_disconnect_state_survives_the_later_hold_screen():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=60).run()
    app.text_input[0].set_value("http://127.0.0.1:1").run()
    app.selectbox[0].set_value("GH01 — Fake Credit → Refund Scam").run()
    app.button[0].click().run(timeout=60)

    warning = app.session_state["phone"].get("warning", {})
    phone_markup = [element.value for element in app.markdown
                    if '<div class="phone-frame"' in element.value][-1]
    assert warning["call_ended"] is True
    assert "Call disconnected at FraudOps intervention" in phone_markup
    assert phone_markup.count('<div class="phone-frame"') == 1
    assert not app.exception
