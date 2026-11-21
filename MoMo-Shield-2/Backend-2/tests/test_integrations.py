import pytest
from uuid import uuid4
import httpx
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.integrations.glance import check_glance_risk, report_fraud
from app.integrations.sandbox import intervene_sandbox
from app.integrations.gemini import analyze_intent, _keyword_intent_fallback
from app.integrations import mtn_momo


@pytest.mark.asyncio
async def test_glance_risk_fallback_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "glance_api_key", "")
    res = await check_glance_risk("+233240000001")
    assert res.risk_level == "UNKNOWN"
    assert res.reports == 0


@pytest.mark.asyncio
async def test_glance_risk_when_enabled_and_live(monkeypatch):
    monkeypatch.setattr(settings, "glance_api_key", "live-key-xyz")
    monkeypatch.setattr(settings, "glance_base_url", "https://api.glance.test/v1")

    async def mock_handler(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer live-key-xyz"
        assert "233240000999" in str(request.url)
        return httpx.Response(200, json={"risk_level": "HIGH", "reports": 12, "threat_type": "credential_harvest"})

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        res = await check_glance_risk("+233240000999")
        assert res.risk_level == "HIGH"
        assert res.reports == 12


@pytest.mark.asyncio
async def test_sandbox_intervene_mock_and_live(monkeypatch):
    # When unconfigured or 'your_' key, it mocks without network error
    monkeypatch.setattr(settings, "sandbox_api_key", "")
    await intervene_sandbox("evt-123", "BLOCK_USSD")

    # When live key is supplied, dispatches properly
    monkeypatch.setattr(settings, "sandbox_api_key", "live-sandbox-key")
    monkeypatch.setattr(settings, "sandbox_base_url", "https://api.sandbox.test/v1")

    called = False

    async def mock_handler(request: httpx.Request):
        nonlocal called
        called = True
        assert request.headers["Authorization"] == "Bearer live-sandbox-key"
        assert b"BLOCK_USSD" in request.content
        return httpx.Response(200, json={"status": "accepted"})

    transport = httpx.MockTransport(mock_handler)
    with patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        await intervene_sandbox("evt-999", "BLOCK_USSD")
        assert called is True


@pytest.mark.asyncio
async def test_gemini_intent_heuristic_fallback(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    res = await analyze_intent("Congratulations! Your MoMo wallet is blocked. Send your PIN immediately.")
    assert "Credential Solicitation" in res or "Authority" in res or "Urgency" in res

    safe_res = await analyze_intent("Thank you for buying airtime.")
    assert "Benign" in safe_res or "Neutral" in safe_res


@pytest.mark.asyncio
async def test_mtn_momo_status_and_validation():
    # Check status endpoint model
    st = mtn_momo.status()
    assert "provider" in st
    assert st["provider"] == "MTN MoMo"

    # Validation test for RequestToPay
    with pytest.raises(Exception):
        mtn_momo.RequestToPay(
            amount="-50.00", # invalid negative
            currency="GHS",
            externalId="ext-1",
            payer={"partyIdType": "MSISDN", "partyId": "233240000111"}
        )


def test_audio_asset_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    # Check alert.wav exists and is served
    resp = client.get("/api/v1/audio/alert.wav")
    assert resp.status_code == 200
    assert "audio/wav" in resp.headers["content-type"]
    assert len(resp.content) > 1000

    # Non-existent asset returns 404
    missing = client.get("/api/v1/audio/nonexistent.wav")
    assert missing.status_code == 404


def test_real_phone_action_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    # When Asterisk is offline, gracefully returns simulated status
    resp = client.post("/api/v1/demo/real-phone-action?action=ring")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("simulated", "dispatched")

