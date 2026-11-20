import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.engine.scorer import assess
from app.engine.state import EventWindow, global_window

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_risk_score_expires_and_assessments_are_idempotent():
    window = EventWindow(retention_minutes=30)
    start = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

    assert window.add_risk("+233240000001", 60, start, "event-1") == 60
    assert window.add_risk("+233240000001", 60, start, "event-1") == 60
    assert window.add_risk(
        "+233240000001", 20, start + timedelta(minutes=31), "event-2"
    ) == 20


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())

def _assess_all_steps(fixture: dict):
    global_window.reset()
    result = None
    for step in fixture["steps"]:
        result = asyncio.run(assess(step["event"]))
    return result

def test_gh01_scores_high():
    fixture = _load("gh01_fake_credit.json")
    result = _assess_all_steps(fixture)
    print(f"\nGH01: score={result.risk_score} tier={result.risk_tier} rules={[r.description for r in result.triggered_rules]}")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"
    assert result.recommended_action == "SIMULATED_HOLD"

def test_gh18_scores_high():
    fixture = _load("gh18_device_takeover.json")
    result = _assess_all_steps(fixture)
    print(f"\nGH18: score={result.risk_score} tier={result.risk_tier} rules={[r.description for r in result.triggered_rules]}")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"

def test_legitimate_scores_low():
    fixture = _load("legitimate_baseline.json")
    result = _assess_all_steps(fixture)
    print(f"\nLegit: score={result.risk_score} tier={result.risk_tier}")
    assert result.risk_score < 40
    assert result.risk_tier == "LOW"
    assert result.recommended_action == "SEAMLESS_APPROVE"

def test_gh17_scores_high():
    fixture = _load("gh17_fake_support.json")
    result = _assess_all_steps(fixture)
    print(f"\nGH17: score={result.risk_score} tier={result.risk_tier}")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"

def test_gh02_scores_high():
    fixture = _load("gh02_reversal_syndicate.json")
    result = _assess_all_steps(fixture)
    print(f"\nGH02: score={result.risk_score} tier={result.risk_tier}")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"

def test_gh15_scores_high():
    fixture = _load("gh15_fake_business_listing.json")
    result = _assess_all_steps(fixture)
    print(f"\nGH15: score={result.risk_score} tier={result.risk_tier}")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"

def test_gh19_scores_high():
    fixture = _load("gh19_nuisance_calls.json")
    result = _assess_all_steps(fixture)
    print(f"\nGH19: score={result.risk_score} tier={result.risk_tier} action={result.recommended_action}")
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"
    # Final event is a communication — nothing to hold, so FraudOps alert.
    assert result.recommended_action == "FRAUDOPS_ALERT"
