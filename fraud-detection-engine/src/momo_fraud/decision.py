"""Map calibrated probabilities and transaction amounts to actions."""

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import yaml


DEFAULT_COSTS = {"warn": 5.0, "hold": 50.0, "freeze": 250.0}


def load_decision_config(path: str | Path | None = None) -> Dict[str, object]:
    if path is None:
        return {"costs": DEFAULT_COSTS}
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Decision config does not exist: {config_path}")
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    costs = config.get("costs") or DEFAULT_COSTS
    expected_actions = ("warn", "hold", "freeze")
    if any(action not in costs for action in expected_actions):
        raise ValueError("Decision costs must define warn, hold, and freeze.")
    if not costs["warn"] <= costs["hold"] <= costs["freeze"]:
        raise ValueError("Decision costs must increase from warn to freeze.")
    return {"costs": costs}


def decide(probabilities, amounts, config: Optional[Dict[str, object]] = None):
    """Choose the strongest action whose intervention cost is below expected loss."""
    config = config or {"costs": DEFAULT_COSTS}
    costs = config.get("costs", DEFAULT_COSTS)
    probabilities = np.asarray(probabilities, dtype=float)
    amounts = np.asarray(amounts, dtype=float)
    if probabilities.shape != amounts.shape:
        raise ValueError("probabilities and amounts must have matching shapes.")
    if np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("probabilities must be between 0 and 1.")
    expected_loss = probabilities * np.maximum(amounts, 0)
    actions = np.full(len(probabilities), "allow", dtype=object)
    actions[expected_loss >= costs["warn"]] = "warn"
    actions[expected_loss >= costs["hold"]] = "hold"
    actions[expected_loss >= costs["freeze"]] = "freeze"
    tiers = np.select(
        [
            expected_loss >= costs["freeze"],
            expected_loss >= costs["hold"],
            expected_loss >= costs["warn"],
        ],
        ["critical", "high", "medium"],
        default="low",
    )
    return pd.DataFrame(
        {
            "probability": probabilities,
            "expected_loss": expected_loss,
            "tier": tiers,
            "action": actions,
        }
    )
