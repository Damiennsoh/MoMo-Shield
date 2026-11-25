"""Fund-flow ledger + evidence pack: observed relationships power Recovery Mode."""
import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    async def fake_glance(msisdn):
        from app.models.schemas import GlanceRiskResponse
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)

    async def fake_lookup(*args, **kwargs):
        return {"status": "UNCONFIGURED"}

    monkeypatch.setattr(routes, "check_glance_risk", fake_glance)
    monkeypatch.setattr(routes.infofemme_client, "get_sim_swap_history", fake_lookup)
    monkeypatch.setattr(routes.infofemme_client, "get_subscriber_profile", fake_lookup)
    routes.ASSESSMENT_HISTORY.clear()
    routes.global_window.clear()
    routes.sms_blast_window.clear()
    routes.local_threat_db.clear_all()
    routes.fund_flow_ledger.clear()


def _plugin(point: str, data: dict):
    return client.post("/api/v1/plugin", json={
        "point": point, "institution": "mtn", "data": data,
    })


def test_fund_flow_records_directed_edges():
    _plugin("sms.deliver", {
        "to": "0241111111", "from": "+233240000001",
        "text": "Congratulations! Your MoMo refund of GHc 500 is ready.",
    })
    _plugin("payment.authorize", {
        "amount": 500,
        "payer": {"msisdn": "0241111111"},
        "payee": {"msisdn": "+233240000001"},
    })
    graph = client.get("/api/v1/fund-flow").json()
    kinds = {(e["from"], e["to"], e["kind"]) for e in graph["edges"]}
    # Ghana formats normalize: +233240000001 == 0240000001
    assert ("0240000001", "0241111111", "sms") in kinds
    assert ("0241111111", "0240000001", "payment") in kinds


def test_evidence_pack_assembles_trail_and_provenance():
    _plugin("call.connect", {
        "to": "0242222222", "from": "233240000002",
        "callerSimRegisteredAt": "2026-11-20T00:00:00Z",
        "numbersTheCallerHasRungToday": 30,
    })
    pack = client.get("/api/v1/evidence-pack/0240000002").json()
    assert pack["subject"]["msisdn"] == "0240000002"
    assert pack["incident_summary"]["observed_edges"] >= 1
    assert pack["fund_trail"][0]["direction"] == "outbound"
    assert pack["fund_trail"][0]["counterparty"] == "0242222222"
    prov = pack["identity_provenance"]
    assert prov["glance_risk_check"]["configured"] is False
    assert "claim" in prov["note"]


def test_evidence_pack_rejects_bad_msisdn():
    res = client.get("/api/v1/evidence-pack/!!!")
    assert res.status_code == 422


def test_demo_reset_clears_fund_flow():
    _plugin("sms.deliver", {
        "to": "0243333333", "from": "0240000003", "text": "Hi there, lunch?",
    })
    assert client.get("/api/v1/fund-flow").json()["edge_count"] >= 1
    client.post("/api/v1/demo/reset")
    assert client.get("/api/v1/fund-flow").json()["edge_count"] == 0
