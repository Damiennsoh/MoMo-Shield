import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))

from services.interventions import build_intervention
from services.live_signal import (
    build_communication_event,
    new_synthetic_identity,
    validate_synthetic_text,
)
from services.local_engine import assess_local, new_accumulator


def test_each_live_sample_gets_a_fresh_synthetic_identity_and_score_state():
    first_identity, first_alias = new_synthetic_identity()
    second_identity, second_alias = new_synthetic_identity()
    assert first_identity != second_identity
    assert first_alias != second_alias
    assert first_identity.startswith("+233000")
    assert first_alias.startswith("SYN-")

    accumulator = new_accumulator()
    attack = build_communication_event("Please send your PIN.", "SMS")
    benign = build_communication_event("Your data bundle is active.", "SMS")
    assert attack["msisdn"] != benign["msisdn"]
    attack_result = assess_local(attack, accumulator)
    benign_result = assess_local(benign, accumulator)
    assert attack_result["risk_score"] > 0
    assert benign_result["risk_score"] == 0
    assert len(accumulator) == 2


def test_sensitive_phone_and_numeric_credential_values_are_blocked():
    assert any("phone number" in issue.casefold() for issue in validate_synthetic_text("Call 0241234567"))
    assert any("pin/otp/code" in issue.casefold() for issue in validate_synthetic_text("Send your OTP 123456"))
    assert any("pin/otp/code" in issue.casefold() for issue in validate_synthetic_text("Your code is 123456"))
    assert validate_synthetic_text("A fictional note with [PHONE] and [CODE] placeholders.") == []


def test_benign_credential_warning_does_not_trigger_credential_request_score():
    event = build_communication_event(
        "We will never ask for your OTP. Do not give your PIN to callers.",
        "SMS",
    )
    result = assess_local(event, new_accumulator())
    assert not any("credential request" in rule.casefold() for rule in result["triggered_rules"])
    guidance = build_intervention(event, result)
    assert guidance["category"] == "no_high_risk_signal"


def test_safety_warning_in_one_clause_does_not_suppress_a_direct_request_in_another():
    from services.credential_requests import has_explicit_credential_request
    mixed = "Never share your PIN. Read me your OTP now."
    assert has_explicit_credential_request(mixed)
    event = build_communication_event(mixed, "SMS")
    result = assess_local(event, new_accumulator())
    assert any("credential request" in rule.casefold() for rule in result["triggered_rules"])


def test_contextual_guidance_distinguishes_credential_request_and_reversal():
    credential = {
        "event_type": "communication",
        "channel": "SMS",
        "text_or_transcript": "Please send your one-time code.",
    }
    credential_warning = build_intervention(credential, {"risk_tier": "MEDIUM", "triggered_rules": []})
    assert credential_warning["category"] == "credential_request"
    assert "Do not share" in credential_warning["message"]

    reversal = {
        "event_type": "communication",
        "channel": "SMS",
        "text_or_transcript": "Send the mistaken transfer back now.",
    }
    reversal_warning = build_intervention(reversal, {
        "risk_tier": "MEDIUM",
        "triggered_rules": ["GH02: Reversal/forge pretext detected in communication"],
    })
    assert reversal_warning["category"] == "reversal_or_refund"
    assert reversal_warning["category"] != credential_warning["category"]


def test_repeated_calls_alone_are_not_labelled_as_confirmed_fraud():
    call_event = {
        "event_type": "communication",
        "channel": "VOICE",
        "text_or_transcript": "",
    }
    warning = build_intervention(call_event, {
        "risk_tier": "MEDIUM",
        "triggered_rules": ["GH19: Multiple nuisance calls from distinct numbers detected"],
    })
    assert warning["category"] == "repeated_calls"
    assert "not proof" in warning["message"].casefold()


def test_streamlit_audio_input_requires_explicit_consent():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=45).run()
    app.radio[0].set_value("Live Signal Lab").run(timeout=45)
    assert len(app.audio_input) == 0
    consent = next(item for item in app.checkbox if item.label.startswith("I consent to send"))
    consent.set_value(True).run(timeout=45)
    assert len(app.audio_input) == 1
    assert not app.exception


def test_provider_readiness_workspace_displays_not_connected():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=45).run()
    app.radio[0].set_value("Provider Feed Readiness").run(timeout=45)
    assert any("NOT CONNECTED" in item.value for item in app.error)
    assert not app.exception
