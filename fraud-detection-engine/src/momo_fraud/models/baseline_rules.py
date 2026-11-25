"""Transparent baseline rules over engineered features — the 'rules' arm
of the benchmark comparison. Returns scores in [0, 1]."""

import numpy as np
import pandas as pd


def score_rules(features: pd.DataFrame) -> np.ndarray:
    """Heuristic fraud score from observable feature columns only."""
    f = features

    def col(name, default=0.0):
        return f[name].astype(float) if name in f.columns else pd.Series(default, index=f.index)

    score = pd.Series(0.0, index=f.index)

    # SIM replacement + PIN reset in window — classic takeover pair
    score += np.clip(col("payer_sim_replacement_count_window") + col("payer_pin_reset_count_window"), 0, 2) * 0.25

    # Brand-new payee + amount spike vs payer mean
    score += col("payer_new_payee") * np.clip(col("amount_vs_payer_mean") / 5.0, 0, 1) * 0.3

    # Velocity: many outgoing tx / unique payees
    score += np.clip(col("payer_unique_payees_7d") / 10.0, 0, 1) * 0.15
    score += np.clip(col("payer_out_count_24h") / 10.0, 0, 1) * 0.15

    # Mule shape: many unique inbound senders + pass-through ratio
    score += np.clip(col("payee_unique_senders_24h") / 10.0, 0, 1) * 0.2
    score += np.clip(col("payee_pass_through_ratio"), 0, 1) * 0.2

    # Suspicious text exposure
    score += np.clip(col("payer_suspicious_texts_24h") / 3.0, 0, 1) * 0.2
    score += col("payer_credit_claim_mismatch_1h") * 0.25

    # Call immediately before transaction
    score += col("call_before_tx") * 0.15

    # Proximity to transaction limit (structuring evasion)
    score += col("amount_near_limit") * 0.2

    return np.clip(score.to_numpy(), 0.0, 1.0)
