import numpy as np
import pytest
from fastapi import HTTPException

from momo_fraud.features.state import NUMBER_COLUMNS
from serving import plugin_api


class FakeAnomalyModel:
    def score_samples(self, features):
        return np.array([-0.25])


class FakeClassifier:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, features):
        return np.array([[1 - self.probability, self.probability]])


class FakeCalibrator:
    def predict(self, probabilities):
        return probabilities


def _mock_model_bundle():
    return {
        "feature_columns": list(NUMBER_COLUMNS) + ["anomaly_score"],
        "anomaly": FakeAnomalyModel(),
        "logistic": FakeClassifier(0.1),
        "gradient_boosted": FakeClassifier(0.2),
        "calibrator": FakeCalibrator(),
        "decision_config": {
            "costs": {"warn": 5.0, "hold": 50.0, "freeze": 250.0}
        },
    }


def test_score_response_contains_expected_fields(monkeypatch):
    monkeypatch.setattr(plugin_api, "_model_bundle", _mock_model_bundle())
    values = {name: 0.0 for name in NUMBER_COLUMNS}
    values["amount"] = 100.0
    response = plugin_api.score(
        plugin_api.ScoreRequest(transaction_id="tx-1", features=values)
    )
    assert response.transaction_id == "tx-1"
    assert response.probability == pytest.approx(0.15)
    assert response.action == "warn"
    assert response.tier == "medium"
    assert response.warning


def test_score_rejects_missing_features(monkeypatch):
    monkeypatch.setattr(plugin_api, "_model_bundle", _mock_model_bundle())
    with pytest.raises(HTTPException) as error:
        plugin_api.score(
            plugin_api.ScoreRequest(transaction_id="tx-1", features={"amount": 10.0})
        )
    assert error.value.status_code == 422


def test_score_does_not_send_unreviewed_twi_warning(monkeypatch):
    monkeypatch.setattr(plugin_api, "_model_bundle", _mock_model_bundle())
    values = {name: 0.0 for name in NUMBER_COLUMNS}
    values["amount"] = 100.0
    with pytest.raises(HTTPException) as error:
        plugin_api.score(
            plugin_api.ScoreRequest(
                transaction_id="tx-1", features=values, language="tw"
            )
        )
    assert error.value.status_code == 422
