"""Feature-flagged ML scorer — blends a calibrated model probability into
the deterministic rule score as a CORROBORATING signal only.

Honesty note (train/serve skew): the model was trained on point-in-time
features replayed from full transaction tables (24h/7d/30d payer & payee
histories). Live plug-in payloads expose only a subset of those signals,
so features we cannot observe are zero-filled — probabilities are
therefore approximate and the contribution is capped small (+≤30) so it
can never warn/reject alone. When the real sandbox dataset lands, retrain
and re-tune the mapping; until then this is the staged integration slot.
"""
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

# Training feature order must match the bundle's feature_columns minus
# "anomaly_score". Missing/unobserved features default to 0.0.
_DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "fraud_pipeline.joblib"
)
_TX_TYPES = ("p2p", "cash_in", "cash_out", "merchant_pay",
             "float_transfer", "bank_to_wallet", "approval_debit")
_TX_LIMIT = 5000.0

_bundle = None
_load_failed = False
_lock = threading.Lock()


def _load():
    global _bundle, _load_failed
    if _bundle is not None or _load_failed:
        return _bundle
    with _lock:
        if _bundle is not None or _load_failed:
            return _bundle
        path = Path(settings.ml_model_path) if settings.ml_model_path else _DEFAULT_MODEL_PATH
        if not path.is_file():
            _load_failed = True
            log.info("ML scorer disabled: no model bundle at %s", path)
            return None
        try:
            import joblib
            import pandas as pd  # noqa: F401 — bundle needs it at predict time

            _bundle = joblib.load(str(path))
            log.info("ML scorer loaded: %s (%d features)",
                     path.name, len(_bundle.get("feature_columns", [])))
        except Exception as exc:
            _load_failed = True
            log.warning("ML scorer load failed (fail-open): %s", exc)
    return _bundle


def _f(name: str, features: Dict[str, float]) -> float:
    v = features.get(name, 0.0)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if math.isfinite(f) else 0.0


def _hours_since(value: Any) -> float:
    if not value:
        return 720.0  # neutral: ~30 days
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    except (TypeError, ValueError):
        return 720.0


def build_feature_vector(point: str, data: Dict[str, Any], msisdn: str) -> Dict[str, float]:
    """Map a plug-in payload onto the trained feature space.

    Only signals the hook actually supplies are populated; everything else
    stays 0.0 (documented approximation — see module docstring).
    """
    payer = data.get("payer") if isinstance(data.get("payer"), dict) else {}
    payee = data.get("payee") if isinstance(data.get("payee"), dict) else {}
    amount = _f("amount", {"amount": data.get("amount")})
    fee = _f("fee", {"fee": data.get("fee")})
    now = datetime.now(timezone.utc)
    features: Dict[str, float] = {name: 0.0 for name in (
        "amount", "fee", "payer_tx_count_1h", "payer_tx_count_24h",
        "payer_tx_count_7d", "payer_out_count_24h", "payer_out_amount_24h",
        "payer_in_amount_24h", "payer_unique_payees_7d", "payer_new_payee",
        "payer_amount_mean_30d", "amount_vs_payer_mean",
        "payee_in_count_24h", "payee_in_amount_24h",
        "payee_unique_senders_24h", "payee_unique_senders_7d",
        "payee_out_amount_24h", "payee_pass_through_ratio",
        "amount_near_limit", "amount_to_limit_ratio",
        "payer_calls_window", "payee_calls_window", "call_before_tx",
        "payer_texts_1h", "payer_suspicious_texts_24h",
        "payee_suspicious_texts_24h", "payer_prize_texts_24h",
        "payer_urgent_texts_24h", "payer_credit_claim_texts_24h",
        "payer_credit_claim_mismatch_1h",
        "payer_hours_since_sim_replacement", "payer_hours_since_pin_reset",
        "payee_hours_since_sim_replacement", "payee_hours_since_pin_reset",
        "payer_sim_replacement_count_window", "payer_pin_reset_count_window",
        "payee_sim_replacement_count_window", "payee_pin_reset_count_window",
        "payer_sim_and_pin_reset_window",
        "payer_account_age_days", "payee_account_age_days",
        "hour_of_day", "is_weekend", "is_night",
        *(f"type_{t}" for t in _TX_TYPES),
    )}

    features["amount"] = amount
    features["fee"] = fee
    features["amount_near_limit"] = float(amount >= _TX_LIMIT * 0.9)
    features["amount_to_limit_ratio"] = amount / _TX_LIMIT
    features["hour_of_day"] = float(now.hour)
    features["is_weekend"] = float(now.weekday() >= 5)
    features["is_night"] = float(now.hour < 6 or now.hour >= 22)

    if point in ("payment.authorize", "switch.route"):
        features["type_p2p"] = 1.0
        wallet_type = str(payee.get("walletType") or "").lower()
        if "merchant" in wallet_type or "business" in wallet_type:
            features["type_merchant_pay"] = 1.0
            features["type_p2p"] = 0.0
        # Hook-supplied velocity fields (documented in Hackathon Env §4)
        p24 = data.get("paymentsInLast24Hours") or payer.get("paymentsInLast24Hours")
        if p24 is not None:
            try:
                features["payer_tx_count_24h"] = features["payer_out_count_24h"] = float(p24)
            except (TypeError, ValueError):
                pass
        prev = data.get("paymentsToThisPayeeBefore") or payer.get("paymentsToThisPayeeBefore")
        if prev is not None:
            try:
                features["payer_new_payee"] = float(int(prev) == 0)
            except (TypeError, ValueError):
                pass
        on_call = payer.get("onCallWith") or data.get("onCallWith")
        if on_call:
            features["call_before_tx"] = 1.0
            features["payer_calls_window"] = 1.0
        features["payer_hours_since_sim_replacement"] = _hours_since(
            payer.get("lastSimSwapAt") or data.get("lastSimSwapAt"))
    elif point == "payment.receive":
        features["type_p2p"] = 1.0
        recv = data.get("paymentsReceivedInLast24Hours")
        diff = data.get("differentPayersInLast24Hours")
        try:
            if recv is not None:
                features["payee_in_count_24h"] = float(recv)
            if diff is not None:
                features["payee_unique_senders_24h"] = float(diff)
        except (TypeError, ValueError):
            pass
    elif point == "transfer.authorize":
        features["type_bank_to_wallet"] = 1.0
    elif point == "payment.request":
        features["type_p2p"] = 1.0
    return features


def score(point: str, data: Dict[str, Any], msisdn: str) -> Optional[Dict[str, Any]]:
    """Return {"probability": p, "points": n} or None when disabled/missing.

    Points are corroborating-only: capped at +30 so the model can never
    produce a verdict alone — it must combine with rule/payload evidence.
    """
    if not settings.ml_scorer_enabled:
        return None
    bundle = _load()
    if bundle is None:
        return None
    try:
        import numpy as np
        import pandas as pd

        feature_columns = [c for c in bundle["feature_columns"] if c != "anomaly_score"]
        vec = build_feature_vector(point, data, msisdn)
        row = {name: _f(name, vec) for name in feature_columns}
        matrix = pd.DataFrame([row], columns=feature_columns)
        matrix["anomaly_score"] = _anomaly_score(bundle, matrix)

        lr = bundle["logistic"].predict_proba(matrix)[:, 1]
        gb = bundle["gradient_boosted"].predict_proba(matrix)[:, 1]
        # fuse_probabilities: 0.4*logistic + 0.6*gbm (mirrors stack.py)
        raw = np.clip(0.4 * lr + 0.6 * gb, 0.0, 1.0)
        prob = float(bundle["calibrator"].predict(raw)[0])
        prob = min(1.0, max(0.0, prob))
        points = int(min(30, prob * 40))
        return {"probability": round(prob, 4), "points": points}
    except Exception as exc:
        log.warning("ML scorer failed for %s (fail-open): %s", point, exc)
        return None


def _anomaly_score(bundle, matrix):
    """Inline equivalent of momo_fraud.models.anomaly.anomaly_score so the
    backend stays self-contained (no cross-project import)."""
    anomaly = bundle.get("anomaly")
    import numpy as np
    if anomaly is None:
        return np.zeros(len(matrix))
    try:
        if isinstance(anomaly, dict):
            model, med, mad = anomaly["model"], anomaly["median"], anomaly["mad"]
        else:
            model, med, mad = anomaly, 0.0, 1.0
        feats = matrix.drop(columns=["anomaly_score"], errors="ignore")
        raw = -model.score_samples(feats)
        scaled = (raw - med) / (5.0 * mad)
        return 1.0 / (1.0 + np.exp(-scaled))
    except Exception:
        return np.zeros(len(matrix))
