"""HTTP scoring endpoint for already-computed point-in-time feature vectors."""

from pathlib import Path
import sys
from typing import Dict, List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import joblib
import numpy as np
import pandas as pd

from momo_fraud.decision import decide
from momo_fraud.explain import reason_codes, warning_text
from momo_fraud.models.anomaly import anomaly_score
from momo_fraud.models.stack import fuse_probabilities


class ScoreRequest(BaseModel):
    transaction_id: str
    features: Dict[str, float]
    language: Literal["en", "tw"] = "en"


class ScoreResponse(BaseModel):
    transaction_id: str
    probability: float
    expected_loss: float
    tier: str
    action: str
    reason_codes: List[str]
    warning: str | None


app = FastAPI(title="MoMo Fraud Scoring API")
_model_bundle = None


def _load_model():
    global _model_bundle
    if _model_bundle is None:
        model_path = PROJECT_ROOT / "models" / "fraud_pipeline.joblib"
        if not model_path.is_file():
            raise HTTPException(
                status_code=503,
                detail="Trained model not found. Run the training experiment first.",
            )
        _model_bundle = joblib.load(model_path)
    return _model_bundle


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score", response_model=ScoreResponse)
def score(request: ScoreRequest):
    """Score one transaction from features produced by the live event pipeline."""
    bundle = _load_model()
    feature_columns = bundle["feature_columns"][:-1]
    missing = sorted(set(feature_columns).difference(request.features))
    if missing:
        raise HTTPException(
            status_code=422, detail=f"Missing required features: {', '.join(missing)}"
        )
    try:
        values = {name: float(request.features[name]) for name in feature_columns}
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="Features must be numeric.") from error
    if not np.isfinite(list(values.values())).all():
        raise HTTPException(status_code=422, detail="Features must be finite numbers.")

    matrix = pd.DataFrame([values], columns=feature_columns)
    matrix["anomaly_score"] = anomaly_score(bundle["anomaly"], matrix)
    lr_probability = bundle["logistic"].predict_proba(matrix)[:, 1]
    gbm_probability = bundle["gradient_boosted"].predict_proba(matrix)[:, 1]
    raw_probability = fuse_probabilities(lr_probability, gbm_probability)
    probability = float(bundle["calibrator"].predict(raw_probability)[0])
    amount = values["amount"]
    decision = decide([probability], [amount], bundle["decision_config"]).iloc[0]
    action = str(decision["action"])
    warning = None
    if action in {"warn", "hold", "freeze"}:
        try:
            warning = warning_text(request.language)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
    return ScoreResponse(
        transaction_id=request.transaction_id,
        probability=probability,
        expected_loss=float(decision["expected_loss"]),
        tier=str(decision["tier"]),
        action=action,
        reason_codes=reason_codes(values),
        warning=warning,
    )
