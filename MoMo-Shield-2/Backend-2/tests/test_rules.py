from app.engine.rules import (
    RULES,
    check_content_credential_request,
    check_content_impersonation,
    check_content_urgency,
    check_gh01_fake_credit,
    check_gh18_device_takeover,
    check_velocity,
)
from app.models.schemas import EventType


def _hist(msisdn_payload_pairs):
    return [
        {"msisdn": m, "payload": p, "timestamp": __import__("datetime").datetime.utcnow()}
        for m, p in msisdn_payload_pairs
    ]


def test_gh01_fake_credit_fires(make_event):
    history = _hist([("+233240000001", {"type": "sms_credit", "ledger_verified": False})])
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500})
    pts, desc = check_gh01_fake_credit(event, history)
    assert pts == 40
    assert "GH01" in desc


def test_gh01_does_not_fire_on_verified_credit(make_event):
    history = _hist([("+233240000001", {"type": "sms_credit", "ledger_verified": True})])
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500})
    pts, _ = check_gh01_fake_credit(event, history)
    assert pts == 0


def test_gh01_does_not_fire_without_prior_credit(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500})
    pts, _ = check_gh01_fake_credit(event, [])
    assert pts == 0


def test_gh01_ignores_small_transfers(make_event):
    history = _hist([("+233240000001", {"type": "sms_credit", "ledger_verified": False})])
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 50})
    pts, _ = check_gh01_fake_credit(event, history)
    assert pts == 0


def test_gh18_device_takeover(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "new_device_binding"})
    pts, desc = check_gh18_device_takeover(event, [])
    assert pts == 50
    assert "GH18" in desc


def test_velocity_fires_after_threshold(make_event):
    history = _hist([("+233240000001", {})] * 6)
    pts, desc = check_velocity(make_event(), history)
    assert pts == 20
    assert desc


def test_velocity_quiet_below_threshold(make_event):
    pts, _ = check_velocity(make_event(), _hist([("+233240000001", {})] * 5))
    assert pts == 0


def test_rules_registry_has_descriptions():
    assert len(RULES) == 6


def test_credential_request_sms_scores_high(make_event):
    event = make_event(EventType.SMS, {"text": "MTN here: reply with your PIN or OTP immediately to secure your account"})
    pts, desc = check_content_credential_request(event, [])
    assert pts == 45
    assert "Credential" in desc


def test_credential_request_voice_transcript(make_event):
    event = make_event(EventType.VOICE, {"transcript": "please tell me your mobile money PIN now"})
    pts, _ = check_content_credential_request(event, [])
    assert pts == 45


def test_benign_sms_scores_zero(make_event):
    event = make_event(EventType.SMS, {"text": "You received GHs 50 from Ama. New balance GHs 1,247.80."})
    assert check_content_credential_request(event, []) == (0, "")
    assert check_content_impersonation(event, []) == (0, "")
    assert check_content_urgency(event, []) == (0, "")


def test_impersonation_plus_secret(make_event):
    event = make_event(EventType.SMS, {"text": "MTN fraud department needs your OTP now"})
    pts, _ = check_content_impersonation(event, [])
    assert pts == 15


def test_transaction_events_skip_content_rules(make_event):
    event = make_event(EventType.TRANSACTION, {"type": "transfer_out", "amount": 500, "text": "send PIN now"})
    assert check_content_credential_request(event, []) == (0, "")
