import asyncio
import base64
import json

import httpx

from app.config import settings
from app.integrations import infofemme
from app.integrations.infofemme import InnoFemmeNetworkClient
from app.integrations.nia import evaluate_ghana_card


def test_sim_swap_uses_carrier_scoped_post_and_basic_auth(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_base_url", "https://sandbox.example/api/w/team-a")
    monkeypatch.setattr(settings, "sandbox_network_client_id", "client-id")
    monkeypatch.setattr(settings, "sandbox_network_api_key", "api-secret")
    received = {}

    async def handler(request):
        received["method"] = request.method
        received["url"] = str(request.url)
        received["authorization"] = request.headers.get("Authorization")
        received["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"swapped": True})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def make_client(*, timeout):
        return real_async_client(transport=transport, timeout=timeout)

    monkeypatch.setattr(infofemme.httpx, "AsyncClient", make_client)
    result = asyncio.run(InnoFemmeNetworkClient().get_sim_swap_history("+233240000777", "MTN"))

    expected_auth = base64.b64encode(b"client-id:api-secret").decode("ascii")
    assert received == {
        "method": "POST",
        "url": "https://sandbox.example/api/w/team-a/network/mtn/v1/sim-swap/check",
        "authorization": f"Basic {expected_auth}",
        "body": {"phoneNumber": "233240000777", "maxAge": 48},
    }
    assert result["sim_swapped"] is True
    assert result["risk_boost"] == 45
    assert result["source"] == "innofemme_network_api"


def test_unknown_carrier_fails_open_without_network_request(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_network_client_id", "client-id")
    monkeypatch.setattr(settings, "sandbox_network_api_key", "api-secret")
    client = InnoFemmeNetworkClient()

    result = asyncio.run(client.get_sim_swap_history("0240000000", "unknown-carrier"))

    assert result["status"] == "UNKNOWN"
    assert result["risk_boost"] == 0


def test_nia_heuristic_handles_missing_malformed_and_high_counts():
    missing = evaluate_ghana_card(None, None)
    malformed_count = evaluate_ghana_card("GHA-123456789-0", "not-a-number")
    high_count_without_card = evaluate_ghana_card(None, "7")
    invalid_card = evaluate_ghana_card("not-a-card", 1)

    assert missing.is_flagged is False
    assert malformed_count.is_flagged is False
    assert high_count_without_card.is_flagged is True
    assert high_count_without_card.sims_count == 7
    assert invalid_card.is_flagged is True
    assert invalid_card.reason.startswith("Invalid Ghana Card format:")
