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
