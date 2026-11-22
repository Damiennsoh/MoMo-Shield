import pandas as pd
from src.features import detect_behaviours
from src.preprocessing import clean_text
from src.correlation import correlate_events
from src.risk_engine import calculate_risk
from src.synthetic_data import generate_communication_data


def test_legitimate_support_mentioning_otp_is_not_multi_indicator():
    behaviours = detect_behaviours(
        "Thank you for contacting support. Your OTP was used for your successful transaction."
    )
    assert "credential_request" not in behaviours


def test_sms_behaviour_detection():
    behaviours = detect_behaviours(
        "This is an MTN agent. Your account will be suspended. Send your OTP immediately."
    )
    assert {"authority_impersonation", "threats", "credential_request", "urgency"} <= set(behaviours)


def test_text_cleaning():
    assert clean_text("  URGENT!!! Send $100  ") == "urgent send 100"


def test_correlation_is_user_and_past_event_scoped():
    events = pd.DataFrame([
        {"event_id": "a", "user_id": "1", "event_type": "SMS", "timestamp": "2026-01-01T10:00:00Z"},
        {"event_id": "b", "user_id": "2", "event_type": "SMS", "timestamp": "2026-01-01T10:06:00Z"},
        {"event_id": "c", "user_id": "1", "event_type": "SMS", "timestamp": "2026-01-01T10:20:00Z"},
    ])
    related = correlate_events(
        {"user_id": "1", "timestamp": "2026-01-01T10:10:00Z"},
        events,
        window_minutes=15,
    )
    assert related["event_id"].tolist() == ["a"]


def test_risk_levels_and_thresholds():
    low = calculate_risk({"is_new_recipient": False})
    assert low["risk_level"] == "LOW"
    critical = calculate_risk({
        "detected_behaviours": ["authority_impersonation", "threats", "credential_request", "urgency"],
        "is_new_recipient": True,
        "new_device": True,
    })
    assert critical["risk_level"] == "CRITICAL"


def test_synthetic_communication_has_varied_templates():
    first = generate_communication_data(seed=42)
    second = generate_communication_data(seed=43)
    assert first["message"].nunique() >= 20
    assert len(set(first["message"]) & set(second["message"])) > 10
