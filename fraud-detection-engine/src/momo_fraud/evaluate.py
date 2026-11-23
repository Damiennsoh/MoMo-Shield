"""Operational metrics for imbalanced fraud-detection experiments."""

from typing import Dict

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


def threshold_at_fpr(labels, probabilities, max_fpr: float = 0.01) -> float:
    """Choose the lowest threshold whose observed false-positive rate is in budget."""
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if not 0 <= max_fpr < 1:
        raise ValueError("max_fpr must be between 0 and 1.")
    if len(np.unique(labels)) < 2:
        raise ValueError("Threshold selection requires both classes.")
    candidates = np.unique(probabilities)[::-1]
    candidates = np.append(candidates, 1.0 + np.finfo(float).eps)
    negatives = labels == 0
    positives = labels == 1
    for threshold in candidates:
        predicted = probabilities >= threshold
        false_positive_rate = np.sum(predicted & negatives) / max(np.sum(negatives), 1)
        if false_positive_rate <= max_fpr:
            return float(threshold)
    return 1.0


def metrics_at_threshold(
    labels, probabilities, amounts, threshold: float
) -> Dict[str, float]:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    amounts = np.asarray(amounts, dtype=float)
    predicted = probabilities >= threshold
    positive = labels == 1
    negative = ~positive
    true_positive = predicted & positive
    false_positive = predicted & negative
    false_negative = ~predicted & positive
    return {
        "threshold": float(threshold),
        "precision": float(np.sum(true_positive) / max(np.sum(predicted), 1)),
        "recall": float(np.sum(true_positive) / max(np.sum(positive), 1)),
        "false_positive_rate": float(
            np.sum(false_positive) / max(np.sum(negative), 1)
        ),
        "amount_weighted_recall": float(
            amounts[true_positive].sum() / max(amounts[positive].sum(), 1.0)
        ),
        "amount_stopped": float(amounts[true_positive].sum()),
        "false_positive_count": int(np.sum(false_positive)),
        "false_negative_count": int(np.sum(false_negative)),
    }


def evaluate_predictions(
    labels,
    probabilities,
    amounts,
    threshold: float,
    fraud_kinds=None,
) -> Dict[str, object]:
    """Compute PR-AUC and thresholded metrics, including per-kind recall."""
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    amounts = np.asarray(amounts, dtype=float)
    result: Dict[str, object] = metrics_at_threshold(
        labels, probabilities, amounts, threshold
    )
    result["pr_auc"] = float(average_precision_score(labels, probabilities))
    result["roc_auc"] = (
        float(roc_auc_score(labels, probabilities))
        if len(np.unique(labels)) == 2
        else float("nan")
    )
    result["positive_count"] = int(np.sum(labels == 1))
    result["negative_count"] = int(np.sum(labels == 0))
    if fraud_kinds is not None:
        kinds = np.asarray(fraud_kinds, dtype=object)
        per_kind = {}
        for kind in sorted(set(kinds[labels == 1])):
            selected = (labels == 1) & (kinds == kind)
            caught = selected & (probabilities >= threshold)
            per_kind[str(kind)] = {
                "count": int(np.sum(selected)),
                "recall": float(np.sum(caught) / max(np.sum(selected), 1)),
                "amount_weighted_recall": float(
                    amounts[caught].sum() / max(amounts[selected].sum(), 1.0)
                ),
            }
        result["per_fraud_kind"] = per_kind
    return result


def labeled_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return labeled synthetic or sandbox rows using the generator's label columns."""
    required = {"is_fraud", "fraud_scenario"}
    missing = required.difference(transactions.columns)
    if missing:
        raise ValueError(
            "Evaluation needs transaction labels: " + ", ".join(sorted(missing))
        )
    result = transactions.copy()
    result["is_fraud"] = result["is_fraud"].fillna(0).astype(int)
    result["fraud_scenario"] = result["fraud_scenario"].fillna("legitimate")
    return result
