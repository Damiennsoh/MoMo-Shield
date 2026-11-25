"""Unsupervised anomaly detector — Isolation Forest over feature space.

The fitted bundle stores the train-split median/MAD of raw anomaly scores
so single-row serving produces stable, bounded outputs in [0, 1] where
higher means more anomalous.
"""

import numpy as np
from sklearn.ensemble import IsolationForest


def _raw_scores(model, X) -> np.ndarray:
    return -model.score_samples(X)  # higher = more anomalous


def fit_anomaly_model(X_train, y_train=None, random_state: int = 7):
    """Fit an Isolation Forest and freeze its score normalization stats.

    y_train is accepted for API symmetry but unused — the detector is
    deliberately unsupervised.
    """
    model = IsolationForest(
        n_estimators=200,
        contamination="auto",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train)
    raw = _raw_scores(model, X_train)
    med = float(np.median(raw))
    mad = float(np.median(np.abs(raw - med))) + 1e-6
    return {"model": model, "median": med, "mad": mad}


def anomaly_score(bundle, X) -> np.ndarray:
    """Normalized anomaly score in ~[0, 1]; higher = more anomalous."""
    if isinstance(bundle, dict):
        model, med, mad = bundle["model"], bundle["median"], bundle["mad"]
    else:  # bare IsolationForest fallback: use its own offset_
        model, med, mad = bundle, 0.0, 1.0
    raw = _raw_scores(model, X)
    scaled = (raw - med) / (5.0 * mad)
    return 1.0 / (1.0 + np.exp(-scaled))
