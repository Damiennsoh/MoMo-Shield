import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.config import settings
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _stub_integrations(monkeypatch):
    "# No network in tests: stub Glance, Gemini, and sandbox interventions."""
    calls = {"intervene": [], "report": [], "glance_high": False}

    async def fake_glance(msisdn):
        from app.models.schemas import GlanceRiskResponse
        if calls["glance_high"]:
            return GlanceRiskResponse(risk_level="HIGH", reports=7, threat_type="wallet_harvest")
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)

    async def fake_intent(text):
        return "test-intent"

    async def fake_intervene(event_id, action):
        calls["intervene"].append((event_id, action))

    async def fake_report(msisdn, threat_type):
        calls["report"].append((msisdn, threat_type))

    monkeypatch.setattr(routes, "check_glance_risk", fake_glance)
    monkeypatch.setattr(routes, "analyze_intent", fake_intent)
    monkeypatch.setattr(routes, "intervene_sandbox", fake_intervene)
    monkeypatch.setattr(routes, "report_fraud", fake_report)
    routes.ASSESSMENT_HISTORY.clear()
    return calls


def _event(event_type="sms", payload=None, msisdn="+233240000777"):
    from datetime import datetime
    return {
        "event_id": f"test-{msisdn}",
        "msisdn": msisdn,
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": payload or {"text": "Hello"},
    }


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "operational"


def test_low_risk_event_allowed(_stub_integrations):
    resp = client.post("/api/v1/webhook/sandbox", json=_event())
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_tier"] == "LOW"
    assert body["action_taken"] == "ALLOWED"
    assert body["latency_ms"] >= 0
    assert _stub_integrations["intervene"] == []


def test_high_risk_blocks_and_reports(_stub_integrations):
    # GH18 device binding (50) + Glance HIGH (+40) = 90 -> BLOCKED
    _stub_integrations["glance_high"] = True
    resp = client.post(
        "/api/v1/webhook/sandbox",
        json=_event("transaction", {"type": "new_device_binding", "amount": 900}),
    )
    body = resp.json()
    assert body["risk_score"] >= 75
    assert body["risk_tier"] == "HIGH"
    assert body["action_taken"] == "BLOCKED"
    assert ("test-+233240000777", "BLOCK_USSD") in _stub_integrations["intervene"]
    assert _stub_integrations["report"]


def test_events_history_endpoint(_stub_integrations):
    client.post("/api/v1/webhook/sandbox", json=_event(msisdn="+233240000778"))
    resp = client.get("/api/v1/events")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert any(e["msisdn"] == "+233240000778" for e in events)


def test_webhook_auth_when_configured(_stub_integrations, monkeypatch):
    monkeypatch.setattr(settings, "webhook_api_key", "secret-key")
    try:
        resp = client.post("/api/v1/webhook/sandbox", json=_event())
        assert resp.status_code == 401
        resp = client.post(
            "/api/v1/webhook/sandbox",
            json=_event(),
            headers={"Authorization": "Bearer secret-key"},
        )
        assert resp.status_code == 200
    finally:
        monkeypatch.setattr(settings, "webhook_api_key", "")


def test_invalid_event_rejected():
    resp = client.post("/api/v1/webhook/sandbox", json={"bad": "payload"})
    assert resp.status_code == 422


def test_mtn_status_discloses_only_configuration_state(monkeypatch):
    monkeypatch.setattr(settings, "mtn_momo_api_user", "")
    resp = client.get("/api/v1/integrations/mtn-momo/status")
    assert resp.status_code == 200
    assert resp.json()["provider"] == "MTN MoMo"
    assert resp.json()["environment"] == "sandbox"
    assert resp.json()["configured"] is False


def test_mtn_request_to_pay_requires_separate_operator_key(monkeypatch):
    monkeypatch.setattr(settings, "mtn_momo_request_api_key", "operator-secret")
    payload = {
        "amount": "1.00",
        "currency": "GHS",
        "externalId": "order-123",
        "payer": {"partyIdType": "MSISDN", "partyId": "233240000777"},
        "payerMessage": "Sandbox test",
        "payeeNote": "Sandbox test",
    }
    headers = {"Idempotency-Key": "34d1fa5e-1e1e-4679-aee2-2f4765359694"}
    denied = client.post("/api/v1/integrations/mtn-momo/collection/request-to-pay", json=payload, headers=headers)
    assert denied.status_code == 401
    denied = client.post(
        "/api/v1/integrations/mtn-momo/collection/request-to-pay",
        json={**payload, "payer": {"partyIdType": "EMAIL", "partyId": "a@example.com"}},
        headers={**headers, "Authorization": "Bearer operator-secret"},
    )
    assert denied.status_code == 422


def test_innofemme_plugin_allows_benign_sms():
    payload = {
        "point": "sms.deliver",
        "institution": "mtn",
        "data": {
            "from": "0209876543",
            "to": "0241234567",
            "text": "Hello Ama, are we still having lunch tomorrow?",
            "textsBetweenThemBefore": 5,
        },
    }
    resp = client.post("/api/v1/plugin", json=payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "allow"


def test_innofemme_plugin_blocks_credential_harvesting_sms():
    payload = {
        "point": "sms.deliver",
        "institution": "mtn",
        "data": {
            "from": "0590001122",
            "to": "0241234567",
            "text": "MTN Notice: Your MoMo wallet is blocked. Reply with your PIN immediately to unlock.",
            "textsBetweenThemBefore": 0,
        },
    }
    resp = client.post("/api/v1/plugin", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] in ("reject", "warn")


def test_fraud_benchmark_endpoint():
    resp = client.post("/api/v1/demo/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    summary = data["summary"]
    assert summary["total_incidents"] == 14
    assert summary["stopped_count"] == 11
    assert summary["false_positives"] == 0
    assert summary["ghc_protected"] > 20000
    assert len(data["results"]) == 14

    assert "MoMo Shield" in data["message"]


def test_innofemme_plugin_detects_call_payment_cooccurrence():
    payload = {
        "point": "payment.authorize",
        "institution": "mtn",
        "data": {
            "amount": 400,
            "payer": {
                "msisdn": "0241234567",
                "onCallWith": "0559998877",
            },
            "payee": {"msisdn": "0559998877"},
        },
    }
    resp = client.post("/api/v1/plugin", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] in ("reject", "warn")


def test_fraud_benchmark_endpoint():
    resp = client.post("/api/v1/demo/benchmark")
    assert resp.status_code == 200
    data = resp.json()
    summary = data["summary"]
    assert summary["total_incidents"] == 14
    assert summary["stopped_count"] == 11
    assert summary["false_positives"] == 0
    assert summary["ghc_protected"] > 20000
    assert len(data["results"]) == 14


