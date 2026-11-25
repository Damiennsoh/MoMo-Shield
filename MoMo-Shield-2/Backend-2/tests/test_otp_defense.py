"""OTP read-out defense: genuine OTPs are never flagged; the call around
 them and the transaction they unlock are."""
import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.engine.rules import looks_like_otp
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    sent = []

    async def fake_push(msisdn, message):
        sent.append((msisdn, message))
        return True

    async def fake_glance(msisdn):
        from app.models.schemas import GlanceRiskResponse
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)

    async def fake_lookup(*args, **kwargs):
        return {"status": "UNCONFIGURED"}

    monkeypatch.setattr(routes.infofemme_client, "send_ussd_push", fake_push)
    monkeypatch.setattr(routes.infofemme_client, "get_sim_swap_history", fake_lookup)
    monkeypatch.setattr(routes, "check_glance_risk", fake_glance)
    routes.ASSESSMENT_HISTORY.clear()
    routes.global_window.clear()
    routes.sms_blast_window.clear()
    routes._advisory_marks.clear()
    routes.local_threat_db.clear_all()
    routes.fund_flow_ledger.clear()
    return sent


def _plugin(point, data):
    return client.post("/api/v1/plugin", json={
        "point": point, "institution": "mtn", "data": data,
    }).json()


def test_otp_detector_narrow():
    assert looks_like_otp("Your MTN OTP is 483920. Valid 5 mins.", "MTN")
    assert looks_like_otp("479213 is your verification code", "233628")
    assert not looks_like_otp("You have received GHc 850. Reply YES to claim.", "+233240001234")
    assert not looks_like_otp("Lunch at 12:30? Bring the documents please.", "+233240001234")


def test_otp_sms_itself_is_never_blocked(_clean_state):
    """A genuine OTP during NO risky call: plain allow, no advisory."""
    res = _plugin("sms.deliver", {
        "to": "0245550001", "from": "MTN",
        "text": "Your MoMo OTP is 731204. Do not share it with anyone.",
    })
    assert res["decision"] == "allow"
    assert _clean_state == []


def test_otp_after_risky_call_triggers_advisory(_clean_state):
    """Risky call (new SIM + fan-out) → marker; OTP SMS → allow + advisory."""
    call = _plugin("call.connect", {
        "to": "0245550002", "from": "+233550001111",
        "callerSimRegisteredAt": "2026-11-25T00:00:00Z",
        "numbersTheCallerHasRungToday": 40,
        "callsBetweenThemBefore": 0,
    })
    assert call["decision"] in ("warn", "reject")

    sms = _plugin("sms.deliver", {
        "to": "0245550002", "from": "MTN",
        "text": "Your MoMo OTP is 582913. Do not share this code.",
    })
    # Genuine OTP must NOT be intercepted
    assert sms["decision"] == "allow"
    # Advisory is a post-decision background task — let the loop tick
    import time
    time.sleep(0.3)
    assert len(_clean_state) == 1
    assert "kɔde" in _clean_state[0][1]  # Twi warning delivered


def test_otp_then_payment_escalates(_clean_state):
    """OTP SMS then payment.authorize → OTP-primed velocity adds points."""
    _plugin("sms.deliver", {
        "to": "0245550003", "from": "MTN",
        "text": "Your transaction code is 229184.",
    })
    pay = _plugin("payment.authorize", {
        "amount": 1200,
        "payer": {"msisdn": "0245550003"},
        "payee": {"msisdn": "+233240009999"},
        "onCallWith": "+233550001111",
    })
    # OTP-primed (+30) + onCallWith (+50) = 80 → HIGH → delay/reject
    assert pay["decision"] in ("delay", "reject")
