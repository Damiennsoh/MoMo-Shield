import asyncio
import json
from pathlib import Path
from app.engine.scorer import assess
from app.engine.state import global_window

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

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
