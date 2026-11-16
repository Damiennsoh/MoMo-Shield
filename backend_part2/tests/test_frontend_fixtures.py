"""Replay the Streamlit dashboard's fixtures through the engine.

The frontend (frontend_part1/fixtures) sends sandbox events that omit
fields the backend requires; services/api_client._prepare_event fills them
in. These tests apply the same defaults so the demo scenarios are covered
end-to-end, not just the backend's own fixtures.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from app.engine.scorer import assess
from app.engine.state import global_window

FRONTEND_FIXTURES = Path(__file__).parent.parent.parent / "frontend_part1" / "fixtures"

pytestmark = pytest.mark.skipif(
    not FRONTEND_FIXTURES.exists(), reason="frontend_part1 fixtures not present"
)


def _load(name: str) -> dict:
    return json.loads((FRONTEND_FIXTURES / name).read_text(encoding="utf-8"))


def _prepare(ev: dict) -> dict:
    ev = dict(ev)
    ev.setdefault("event_id", f"fe-test-{uuid.uuid4().hex[:8]}")
    ev.setdefault("timestamp", datetime.now().isoformat())
    if ev.get("event_type") == "transaction":
        ev.setdefault("ledger_verified", True)
    return ev


def _run_scenario(name: str):
    global_window.reset()
    result = None
    for step in _load(name)["steps"]:
        if "event" in step:
            result = asyncio.run(assess(_prepare(step["event"])))
    return result


def test_frontend_gh01_fake_credit_reaches_high():
    result = _run_scenario("gh01_fake_credit.json")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"
    assert result.recommended_action == "SIMULATED_HOLD"


def test_frontend_gh18_device_takeover_reaches_high():
    result = _run_scenario("gh18_device_takeover.json")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"
    assert result.recommended_action == "SIMULATED_HOLD"


def test_frontend_legitimate_baseline_stays_low():
    result = _run_scenario("legit_baseline.json")
    assert result.risk_score < 40
    assert result.risk_tier == "LOW"
    assert result.recommended_action == "SEAMLESS_APPROVE"
