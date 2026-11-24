from concurrent.futures import ThreadPoolExecutor
import asyncio
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.config import settings
from app.engine.state import EventWindow
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _stub_integrations(monkeypatch):
    """Keep tests deterministic and prevent all outbound calls."""
    calls = {"intervene": [], "report": [], "glance_high": False}

    async def fake_glance(msisdn):
        from app.models.schemas import GlanceRiskResponse
        if calls["glance_high"]:
            return GlanceRiskResponse(risk_level="HIGH", reports=7, threat_type="wallet_harvest")
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)

    async def fake_sim_history(msisdn, carrier="mtn"):
        return {"status": "UNCONFIGURED", "risk_boost": 0}

    async def fake_intent(text, rag_context=None):
        return "test-intent"

    async def fake_search_smart(query, top_k=1):
        return []

    async def fake_rag_context(query):
        return None

    async def fake_intervene(event_id, action):
        calls["intervene"].append((event_id, action))

    async def fake_report(msisdn, threat_type):
        calls["report"].append((msisdn, threat_type))

    async def fake_enrichment(*args, **kwargs):
        return None

    monkeypatch.setattr(routes, "check_glance_risk", fake_glance)
    monkeypatch.setattr(routes.infofemme_client, "get_sim_swap_history", fake_sim_history)
    monkeypatch.setattr(routes, "analyze_intent", fake_intent)
    monkeypatch.setattr(routes, "intervene_sandbox", fake_intervene)
    monkeypatch.setattr(routes.knowledge_base, "search", lambda query, top_k=1: [])
    monkeypatch.setattr(routes.knowledge_base, "search_smart", fake_search_smart)
    monkeypatch.setattr(routes.knowledge_base, "get_rag_context_smart", fake_rag_context)
    monkeypatch.setattr(routes, "report_fraud", fake_report)
    monkeypatch.setattr(routes, "_enrich_plugin_assessment", fake_enrichment)
    routes.ASSESSMENT_HISTORY.clear()
    routes.global_window.clear()
    routes.sms_blast_window.clear()
    return calls


def _event(event_type="sms", payload=None, msisdn="+233240000777"):
    return {
        "event_id": f"test-{uuid4().hex}",
        "msisdn": msisdn,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {"text": "Hello"},
    }


def _plugin(point, data, institution="mtn"):
    return {"point": point, "institution": institution, "world": "test-team", "data": data}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "operational"


def test_low_risk_event_allowed(_stub_integrations):
    response = client.post("/api/v1/webhook/sandbox", json=_event())
    assert response.status_code == 200
    body = response.json()
    assert body["risk_tier"] == "LOW"
    assert body["action_taken"] == "ALLOWED"
    assert body["latency_ms"] >= 0
    assert _stub_integrations["intervene"] == []


def test_high_risk_webhook_blocks_and_reports(_stub_integrations):
    _stub_integrations["glance_high"] = True
    response = client.post(
        "/api/v1/webhook/sandbox",
        json=_event("transaction", {"type": "new_device_binding", "amount": 900}),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["risk_score"] >= 75
    assert body["risk_tier"] == "HIGH"
    assert body["action_taken"] == "BLOCKED"
    assert _stub_integrations["intervene"]
    assert _stub_integrations["report"]


def test_events_history_endpoint(_stub_integrations):
    client.post("/api/v1/webhook/sandbox", json=_event(msisdn="+233240000778"))
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    assert any(event["msisdn"] == "+233240000778" for event in response.json()["events"])


def test_webhook_auth_when_configured(_stub_integrations, monkeypatch):
    monkeypatch.setattr(settings, "webhook_api_key", "secret-key")
    try:
        denied = client.post("/api/v1/webhook/sandbox", json=_event())
        assert denied.status_code == 401
        allowed = client.post(
            "/api/v1/webhook/sandbox",
            json=_event(),
            headers={"Authorization": "Bearer secret-key"},
        )
        assert allowed.status_code == 200
    finally:
        monkeypatch.setattr(settings, "webhook_api_key", "")


def test_invalid_event_rejected():
    assert client.post("/api/v1/webhook/sandbox", json={"bad": "payload"}).status_code == 422


def test_mtn_status_discloses_only_configuration_state(monkeypatch):
    monkeypatch.setattr(settings, "mtn_momo_api_user", "")
    response = client.get("/api/v1/integrations/mtn-momo/status")
    assert response.status_code == 200
    assert response.json()["provider"] == "MTN MoMo"
    assert response.json()["environment"] == "sandbox"
    assert response.json()["configured"] is False


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
    denied = client.post(
        "/api/v1/integrations/mtn-momo/collection/request-to-pay",
        json=payload,
        headers=headers,
    )
    assert denied.status_code == 401
    denied = client.post(
        "/api/v1/integrations/mtn-momo/collection/request-to-pay",
        json={**payload, "payer": {"partyIdType": "EMAIL", "partyId": "a@example.com"}},
        headers={**headers, "Authorization": "Bearer operator-secret"},
    )
    assert denied.status_code == 422


def test_plugin_allows_benign_sms(_stub_integrations):
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("sms.deliver", {
            "from": "0209876543",
            "to": "0241234567",
            "text": "Hello Ama, are we still having lunch tomorrow?",
            "textsBetweenThemBefore": 5,
        }),
    )
    assert response.status_code == 200
    assert response.json() == {"decision": "allow"}


def test_plugin_flags_credential_harvesting_sms(_stub_integrations):
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("sms.deliver", {
            "from": "0590001122",
            "to": "0241234567",
            "text": "MTN Notice: Your MoMo wallet is blocked. Reply with your PIN immediately to unlock.",
        }),
    )
    assert response.status_code == 200
    assert response.json()["decision"] in ("reject", "warn")
    assert len(response.json().get("message", "")) <= 150
    assert routes.ASSESSMENT_HISTORY[-1]["risk_score"] >= settings.risk_threshold_medium


def test_plugin_call_multi_signal_reaches_warn(_stub_integrations):
    """Probabilistic model: new SIM (+15) + fan-out >25 (+20) + cold call (+5)
    = 40 → warn. No single signal blocks on its own."""
    recent_sim = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None).isoformat() + "Z"
    payload = _plugin("call.connect", {
        "from": "0209876543",
        "to": "0241234567",
        "callerSimRegisteredAt": recent_sim,
        "callsBetweenThemBefore": 0,
        "numbersTheCallerHasRungToday": 30,
    })
    response = client.post("/api/v1/plugin", json=payload)
    assert response.status_code == 200
    assert response.json()["decision"] == "warn"
    rules = routes.ASSESSMENT_HISTORY[-1]["triggered_rules"]
    assert any("Call metadata" in rule for rule in rules)


def test_plugin_call_single_signal_stays_allowed(_stub_integrations):
    """Union-leader case: high volume alone must not warn or block."""
    old_sim = (datetime.now(timezone.utc) - timedelta(days=400)).replace(tzinfo=None).isoformat() + "Z"
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("call.connect", {
            "from": "0209876543",
            "to": "0241234567",
            "callerSimRegisteredAt": old_sim,
            "callsBetweenThemBefore": 3,
            "numbersTheCallerHasRungToday": 30,
        }),
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "allow"


def test_plugin_call_at_twenty_numbers_is_minor_weight(_stub_integrations):
    recent_sim = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None).isoformat() + "Z"
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("call.connect", {
            "from": "0209876543",
            "to": "0241234567",
            "callerSimRegisteredAt": recent_sim,
            "callsBetweenThemBefore": 0,
            "numbersTheCallerHasRungToday": 20,
        }),
    )

    assert response.status_code == 200
    # +15 SIM +5 fan-out +5 cold = 25 → below warn threshold
    assert response.json()["decision"] == "allow"


def test_plugin_does_not_warn_for_old_caller_sim(_stub_integrations):
    old_sim = (datetime.now(timezone.utc) - timedelta(hours=50)).replace(tzinfo=None).isoformat() + "Z"
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("call.connect", {
            "from": "0209876543",
            "to": "0241234567",
            "callerSimRegisteredAt": old_sim,
            "callsBetweenThemBefore": 0,
            "numbersTheCallerHasRungToday": 42,
        }),
    )
    # +20 fan-out +5 cold = 25 → allow; old SIM contributes nothing
    assert response.status_code == 200
    assert response.json()["decision"] == "allow"


def test_plugin_call_rejects_when_glance_and_metadata_align(_stub_integrations):
    _stub_integrations["glance_high"] = True
    recent_sim = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None).isoformat() + "Z"
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("call.connect", {
            "from": "0209876543",
            "to": "0241234567",
            "callerSimRegisteredAt": recent_sim,
            "callsBetweenThemBefore": 0,
            "numbersTheCallerHasRungToday": 30,
        }),
    )
    # +15 SIM +20 fan-out +5 cold +40 Glance HIGH = 80 → reject
    assert response.status_code == 200
    assert response.json()["decision"] == "reject"


def test_plugin_call_cross_channel_credit_sms_precursor(_stub_integrations):
    """GH01 aha-moment: credit-claim SMS then a call from the same number."""
    sms = client.post(
        "/api/v1/plugin",
        json=_plugin("sms.deliver", {
            "from": "0209876543",
            "to": "0241234567",
            "text": "You have received GH₵500. Reply YES within 10 minutes to claim your refund.",
        }),
    )
    assert sms.status_code == 200

    recent_sim = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None).isoformat() + "Z"
    call = client.post(
        "/api/v1/plugin",
        json=_plugin("call.connect", {
            "from": "0209876543",
            "to": "0241234567",
            "callerSimRegisteredAt": recent_sim,
            "callsBetweenThemBefore": 0,
            "numbersTheCallerHasRungToday": 0,
        }),
    )
    assert call.status_code == 200
    # +30 cross-channel +15 SIM +5 cold = 50 → warn
    assert call.json()["decision"] == "warn"
    rules = routes.ASSESSMENT_HISTORY[-1]["triggered_rules"]
    assert any("Cross-channel precursor" in rule for rule in rules)


def test_plugin_sms_blast_identical_text_escalates(_stub_integrations):
    """Same text to 8 distinct victims in 10 min → +45 blast signal."""
    text = ("Congratulations! Your MoMo wallet was selected for a verified "
            "data bonus. Confirm your details now to claim it.")
    for i in range(8):
        response = client.post(
            "/api/v1/plugin",
            json=_plugin("sms.deliver", {
                "from": "0240000099",
                "to": f"024555{i:04d}",
                "text": text,
            }),
        )
        assert response.status_code == 200
    rules = routes.ASSESSMENT_HISTORY[-1]["triggered_rules"]
    assert any("SMS blast" in rule for rule in rules)
    assert routes.ASSESSMENT_HISTORY[-1]["risk_score"] >= 40


def test_plugin_sms_blast_single_victim_no_escalation(_stub_integrations):
    """Same text to one victim twice is not a blast (distinct-victim count)."""
    text = "Your MoMo statement for this month is now ready to view."
    for _ in range(3):
        client.post(
            "/api/v1/plugin",
            json=_plugin("sms.deliver", {
                "from": "0240000099",
                "to": "0245559999",
                "text": text,
            }),
        )
    rules = routes.ASSESSMENT_HISTORY[-1]["triggered_rules"]
    assert not any("SMS blast" in rule for rule in rules)


def test_plugin_unverified_credit_claim_warns(_stub_integrations):
    """Credit claim + reciprocal pressure + empty ledger → +40 → warn."""
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("sms.deliver", {
            "from": "0240000001",
            "to": "0247770001",
            "text": "You have received GH₵500 from 0551234567. Send it back to reverse the transaction.",
        }),
    )
    assert response.status_code == 200
    rules = routes.ASSESSMENT_HISTORY[-1]["triggered_rules"]
    assert any("Unverified credit claim" in rule for rule in rules)
    assert response.json()["decision"] == "warn"


def test_plugin_verified_credit_claim_does_not_fire(_stub_integrations):
    """A real payment.receive in the victim's window corroborates the SMS."""
    victim, sender = "0247770002", "0240000002"
    client.post(
        "/api/v1/plugin",
        json=_plugin("payment.receive", {
            "amount": 500,
            "payer": {"msisdn": sender},
            "payee": {"msisdn": victim},
        }),
    )
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("sms.deliver", {
            "from": sender,
            "to": victim,
            "text": "You have received GH₵500 from 0551234567. Send it back to reverse the transaction.",
        }),
    )
    assert response.status_code == 200
    rules = routes.ASSESSMENT_HISTORY[-1]["triggered_rules"]
    assert not any("Unverified credit claim" in rule for rule in rules)


def test_plugin_payment_uses_one_time_cooling_period_then_rejects(_stub_integrations):
    recent_swap = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat() + "Z"
    base_data = {
        "amount": 500,
        "payer": {
            "msisdn": "0241234567",
            "onCallWith": "0209876543",
            "lastSimSwapAt": recent_swap,
        },
        "payee": {"msisdn": "0209876543"},
        "afterDelay": False,
    }
    delayed = client.post(
        "/api/v1/plugin", json=_plugin("payment.authorize", base_data)
    )
    assert delayed.status_code == 200
    assert delayed.json()["decision"] == "delay"
    assert delayed.json()["minutes"] == 10

    base_data["afterDelay"] = True
    rejected = client.post(
        "/api/v1/plugin", json=_plugin("payment.authorize", base_data)
    )
    assert rejected.status_code == 200
    assert rejected.json()["decision"] == "reject"


def test_plugin_missing_msisdn_and_unknown_point_are_rejected(_stub_integrations):
    missing = client.post(
        "/api/v1/plugin", json=_plugin("sms.deliver", {"from": "0200000000", "text": "hi"})
    )
    unknown = client.post(
        "/api/v1/plugin", json=_plugin("unregistered.hook", {"msisdn": "0241234567"})
    )
    assert missing.status_code == 422
    assert unknown.status_code == 422
    assert all(event["msisdn"] != "+233240000000" for event in routes.ASSESSMENT_HISTORY)


def test_plugin_menu_open_warns_when_subscriber_is_on_call(_stub_integrations):
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("menu.open", {"msisdn": "0241234567", "onCallWith": "0209876543"}),
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "warn"


def test_plugin_events_have_collision_resistant_ids(_stub_integrations):
    data = {"from": "0209876543", "to": "0241234567", "text": "Hi"}
    first = client.post("/api/v1/plugin", json=_plugin("sms.deliver", data)).json()
    second = client.post("/api/v1/plugin", json=_plugin("sms.deliver", data)).json()
    assert first["decision"] == second["decision"] == "allow"
    events = [item for item in routes.ASSESSMENT_HISTORY if item["msisdn"] == "0241234567"]
    assert len(events) == 2
    assert events[-1]["event_id"] != events[-2]["event_id"]


def test_event_window_observe_and_add_is_atomic_under_concurrency():
    window = EventWindow()
    count = 40

    def add_one(index):
        event = {"timestamp": datetime.now(timezone.utc), "index": index}
        return window.observe_and_add("0241234567", event)

    with ThreadPoolExecutor(max_workers=12) as pool:
        snapshots = list(pool.map(add_one, range(count)))

    assert window.event_count() == count
    assert sum(len(snapshot) for snapshot in snapshots) == count * (count - 1) // 2
    assert sorted(len(snapshot) for snapshot in snapshots) == list(range(count))


def test_demo_reset_clears_assessments_and_event_window(_stub_integrations):
    client.post("/api/v1/plugin", json=_plugin(
        "sms.deliver", {"from": "0209876543", "to": "0241234567", "text": "Hello"}
    ))
    assert routes.ASSESSMENT_HISTORY
    assert routes.global_window.event_count() > 0
    response = client.post("/api/v1/demo/reset")
    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    assert not routes.ASSESSMENT_HISTORY
    assert routes.global_window.event_count() == 0


def test_local_benchmark_discloses_scope_and_returns_measured_fixture_time():
    response = client.post("/api/v1/demo/benchmark")
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == body["summary"]["total_incidents"]
    assert "local rule" in body["scope"].lower()
    assert "end-to-end" in body["summary"]["measurement_scope"].lower()
    assert all(result["latency_ms"] >= 0 for result in body["results"])
    assert all(result["id"] for result in body["results"])


def test_mixed_plugin_events_complete_concurrently_without_losing_history(_stub_integrations):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat() + "Z"
    requests = []
    for index in range(20):
        kind = index % 5
        if kind == 0:
            point, data = "sms.deliver", {"from": "0209876543", "to": "0241234567", "text": "Urgent, send your MoMo PIN now"}
        elif kind == 1:
            point, data = "call.connect", {"from": "0209876543", "to": "0241234567", "callerSimRegisteredAt": recent, "callsBetweenThemBefore": 0, "numbersTheCallerHasRungToday": 25}
        elif kind == 2:
            point, data = "payment.authorize", {"amount": 300, "payer": {"msisdn": "0241234567", "onCallWith": "0209876543", "lastSimSwapAt": recent}, "payee": {"msisdn": "0209876543"}}
        elif kind == 3:
            point, data = "menu.open", {"msisdn": "0241234567", "onCallWith": "0209876543"}
        else:
            point, data = "sim.swap", {"msisdn": "0241234567", "ghanaCard": "GHA-729104829-1", "simsAlreadyOnThisGhanaCard": 6}
        requests.append(_plugin(point, data))

    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(lambda body: client.post("/api/v1/plugin", json=body), requests))

    assert all(response.status_code == 200 for response in responses)
    assert routes.global_window.event_count() == len(requests)
    observed_ids = [item["event_id"] for item in routes.ASSESSMENT_HISTORY]
    assert len(observed_ids) == len(requests)
    assert len(set(observed_ids)) == len(requests)


def test_optional_lookups_respect_shared_timeout_and_fail_open(_stub_integrations, monkeypatch):
    async def slow_lookup(*args, **kwargs):
        await asyncio.sleep(2)

    monkeypatch.setattr(routes, "check_glance_risk", slow_lookup)
    monkeypatch.setattr(routes.infofemme_client, "get_sim_swap_history", slow_lookup)
    monkeypatch.setattr(settings, "plugin_lookup_timeout_seconds", 0.05)
    started = time.perf_counter()
    response = client.post(
        "/api/v1/plugin",
        json=_plugin("sms.deliver", {"from": "0209876543", "to": "0241234567", "text": "Hello"}),
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert response.json() == {"decision": "allow"}
    assert elapsed < 0.75
