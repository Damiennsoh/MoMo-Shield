import json
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.engine.state import global_window

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_gemini_healthcheck_requires_configuration(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=False))
    r = client.post("/api/v1/gemini/healthcheck")
    assert r.status_code == 503
    assert r.json()["detail"]["status"] == "not_configured"

def test_gemini_healthcheck_makes_a_real_extractor_call(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    calls = []

    async def fake_extract(text):
        calls.append(text)
        return {"pattern": None, "evidence_phrases": []}

    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True, gemini_model="gemini-3.5-flash-lite"))
    monkeypatch.setattr(routes, "extract_intent", fake_extract)
    r = client.post("/api/v1/gemini/healthcheck")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["model"] == "gemini-3.5-flash-lite"
    assert calls and "Connectivity test" in calls[0]

def test_gemini_healthcheck_reports_provider_failure_without_secrets(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace

    async def fail(_text):
        raise RuntimeError("provider failure detail")

    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True, gemini_model="gemini-3.5-flash-lite"))
    monkeypatch.setattr(routes, "extract_intent", fail)
    r = client.post("/api/v1/gemini/healthcheck")
    assert r.status_code == 502
    assert "provider failure detail" not in r.text

def test_demo_handset_page_is_available_and_event_publish_requires_token(monkeypatch):
    from app.api import demo_device
    from types import SimpleNamespace
    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(demo_device_token="demo-test-token"))
    page = client.get("/api/v1/demo-device")
    assert page.status_code == 200
    assert "synthetic demo handset" in page.text
    stream_denied = client.get("/api/v1/demo-device/stream")
    assert stream_denied.status_code == 403
    denied = client.post("/api/v1/demo-device/publish", json={"type": "sms", "message": "fake demo"})
    assert denied.status_code == 403
    sent = client.post("/api/v1/demo-device/publish", headers={"Authorization": "Bearer demo-test-token"},
                       json={"type": "sms", "message": "synthetic test message"})
    assert sent.status_code == 200
    assert sent.json()["status"] == "published"
    assert sent.json()["sip"] is None

def test_sip_bridge_is_only_requested_by_explicit_call_event(monkeypatch):
    from app.api import demo_device
    from types import SimpleNamespace
    calls = []

    async def fake_originate():
        calls.append("originated")
        return {"status": "requested", "message": "synthetic SIP call requested"}

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(demo_device_token="demo-test-token"))
    monkeypatch.setattr(demo_device, "_originate_demo_call", fake_originate)
    auth = {"Authorization": "Bearer demo-test-token"}
    client.post("/api/v1/demo-device/publish", headers=auth, json={"type": "call", "trigger_sip": False})
    assert calls == []
    result = client.post("/api/v1/demo-device/publish", headers=auth,
                         json={"type": "call", "trigger_sip": True})
    assert calls == ["originated"]
    assert result.json()["sip"]["status"] == "requested"

def test_asterisk_ari_uses_only_fixed_local_endpoint(monkeypatch):
    import asyncio
    from app.api import demo_device
    from types import SimpleNamespace
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            captured["auth"] = kwargs["auth"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, params):
            captured["url"] = url
            captured["params"] = params
            return Response()

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(
        asterisk_ari_url="http://asterisk:8088/ari/",
        asterisk_ari_username="demo-user",
        asterisk_ari_password="demo-password",
    ))
    monkeypatch.setattr(demo_device.httpx, "AsyncClient", Client)
    result = asyncio.run(demo_device._originate_demo_call())
    assert result["status"] == "requested"
    assert captured["url"] == "http://asterisk:8088/ari/channels"
    assert captured["params"]["endpoint"] == "PJSIP/200"
    assert captured["params"]["context"] == "momo-demo-outbound"
    assert captured["params"]["timeout"] == 20

def test_assess_endpoint_gh01():
    fixture = json.loads((FIXTURES_DIR / "gh01_fake_credit.json").read_text())
    global_window.reset()
    body = None
    for step in fixture["steps"]:
        r = client.post("/api/v1/assess", json={"event": step["event"]})
        assert r.status_code == 200
        body = r.json()
    assert body["risk_tier"] == "HIGH"
    assert body["recommended_action"] == "SIMULATED_HOLD"
