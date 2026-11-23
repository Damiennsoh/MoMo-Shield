"""Generate concise, evidence-based reason codes for scored transactions."""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path


def tree_shap_values(model, background, examples):
    """Return SHAP values for a tree model and a bounded reference sample."""
    import shap

    explainer = shap.TreeExplainer(model, data=background)
    values = explainer.shap_values(examples, check_additivity=False)
    if isinstance(values, list):
        values = values[-1]
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, -1]
    if values.shape != examples.shape:
        raise ValueError(
            f"Unexpected SHAP shape {values.shape}; expected {examples.shape}."
        )
    return shap.Explanation(
        values=values,
        data=examples.to_numpy(),
        feature_names=list(examples.columns),
    )


def shap_importance(explanation, limit: int = 20) -> pd.DataFrame:
    """Rank features by mean absolute SHAP value."""
    importance = np.abs(explanation.values).mean(axis=0)
    return (
        pd.DataFrame({"feature": explanation.feature_names, "mean_abs_shap": importance})
        .sort_values("mean_abs_shap", ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def reason_codes(features, limit: int = 3):
    """Return observable signals; these are not model-specific SHAP attributions."""
    candidates = [
        (
            features.get("payer_sim_replacement_count_window", 0) > 0
            and features.get("payer_pin_reset_count_window", 0) > 0,
            "recent_sim_change_and_pin_reset",
        ),
        (
            features.get("payer_new_payee", 0) > 0,
            "first_payment_to_recipient",
        ),
        (
            features.get("payer_suspicious_texts_24h", 0) > 0,
            "suspicious_recent_message",
        ),
        (
            features.get("payer_credit_claim_mismatch_1h", 0) > 0,
            "claimed_credit_not_found_in_transaction_history",
        ),
        (features.get("payer_calls_window", 0) > 0, "recent_call_before_transaction"),
        (
            features.get("payee_unique_senders_24h", 0) >= 3,
            "recipient_recently_received_from_many_senders",
        ),
        (
            features.get("payer_unique_payees_7d", 0) >= 5,
            "sender_recently_paid_many_recipients",
        ),
        (
            features.get("amount_vs_payer_mean", 0) >= 3,
            "amount_unusual_for_sender",
        ),
        (
            features.get("amount_near_limit", 0) > 0,
            "amount_near_transaction_limit",
        ),
        (
            features.get("payer_hours_since_sim_replacement", 720) <= 72,
            "recent_sim_replacement",
        ),
    ]
    return [code for active, code in candidates if active][:limit]


def warning_text(language: str = "en") -> str:
    """Return English template or a Twi translation only after recorded review."""
    config_path = Path(__file__).resolve().parents[2] / "configs" / "warnings.yaml"
    with config_path.open(encoding="utf-8") as file:
        languages = (yaml.safe_load(file) or {}).get("languages", {})
    entry = languages.get(language)
    if not entry or not entry.get("text"):
        raise ValueError(f"No warning text is configured for language: {language}")
    if language == "tw" and (
        entry.get("status") != "approved"
        or not entry.get("reviewer")
        or not entry.get("reviewed_on")
    ):
        raise ValueError("Twi warning text is unavailable until a native reviewer approves it.")
    if language not in {"en", "tw"}:
        raise ValueError(f"Unsupported warning language: {language}")
    return str(entry["text"])
