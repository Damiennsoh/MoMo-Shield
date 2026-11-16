"""Replay the Streamlit dashboard's fixtures through the engine.

The frontend (frontend_part1/fixtures) sends sandbox events that omit
fields the backend requires; services/api_client._prepare_event fills them
in. These tests apply the same defaults so the demo scenarios are covered
end-to-end, not just the backend's own fixtures.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
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
    base = datetime.now()
    step_i = 0
    for step in _load(name)["steps"]:
        if "event" in step:
            ev = _prepare(step["event"])
            # Windows clock granularity can give identical now() values to
            # back-to-back events; space timestamps so window ordering is deterministic.
            ev["timestamp"] = (base + timedelta(seconds=step_i * 2)).isoformat()
            step_i += 1
            result = asyncio.run(assess(ev))
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


def test_frontend_gh17_fake_support_reaches_high():
    result = _run_scenario("gh17_fake_support.json")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"


def test_frontend_gh02_reversal_syndicate_reaches_high():
    result = _run_scenario("gh02_reversal_syndicate.json")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"


def test_frontend_gh15_fake_business_reaches_high():
    result = _run_scenario("gh15_fake_business_listing.json")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"


def test_frontend_gh19_nuisance_calls_reaches_high():
    result = _run_scenario("gh19_nuisance_calls.json")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"
