"""Probability fusion and calibration for the logistic+GBM stack."""

import numpy as np
from sklearn.isotonic import IsotonicRegression


def fuse_probabilities(logistic_probs, gbm_probs, weight_gbm: float = 0.6) -> np.ndarray:
    """Weighted blend favoring the GBM (better at interactions), bounded."""
    lr = np.asarray(logistic_probs, dtype=float)
    gb = np.asarray(gbm_probs, dtype=float)
    return np.clip((1 - weight_gbm) * lr + weight_gbm * gb, 0.0, 1.0)


def fit_calibrator(scores, labels):
    """Isotonic calibration of blended scores -> calibrated fraud probability."""
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(np.asarray(scores, dtype=float), np.asarray(labels, dtype=float))
    return iso
