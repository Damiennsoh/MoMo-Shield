"""Reproducible point-in-time feature, train, calibration, and evaluation pipeline."""

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from momo_fraud.decision import decide, load_decision_config
from momo_fraud.evaluate import evaluate_predictions, labeled_transactions, threshold_at_fpr
from momo_fraud.features.state import NUMBER_COLUMNS, build_features
from momo_fraud.io import load_yaml_config
from momo_fraud.models.anomaly import anomaly_score, fit_anomaly_model
from momo_fraud.models.baseline_rules import score_rules
from momo_fraud.models.gbm import make_gbm
from momo_fraud.models.stack import fit_calibrator, fuse_probabilities
from momo_fraud.splits import time_case_split


def _benchmark_single_transaction(
    feature_rows,
    anomaly,
    logistic,
    gradient_boosted,
    calibrator,
    decision_settings,
    sample_limit: int = 200,
):
    """Measure warmed in-process model scoring, excluding feature construction."""
    sample = feature_rows.iloc[: min(len(feature_rows), sample_limit)]
    if sample.empty:
        raise ValueError("Latency benchmark requires at least one row.")

    def score_one(row):
        matrix = row.to_frame().T
        matrix["anomaly_score"] = anomaly_score(anomaly, matrix)
        lr_score = logistic.predict_proba(matrix)[:, 1]
        gbm_score = gradient_boosted.predict_proba(matrix)[:, 1]
        raw = fuse_probabilities(lr_score, gbm_score)
        calibrated = calibrator.predict(raw)
        return decide(calibrated, [float(row["amount"])], decision_settings)

    for _, row in sample.iloc[: min(len(sample), 10)].iterrows():
        score_one(row)

    durations_ms = []
    for _, row in sample.iterrows():
        started = perf_counter()
        score_one(row)
        durations_ms.append((perf_counter() - started) * 1000)
    return {
        "scope": "warmed in-process scoring; excludes feature construction and network",
        "transactions": len(durations_ms),
        "p50_ms": float(np.percentile(durations_ms, 50)),
        "p95_ms": float(np.percentile(durations_ms, 95)),
        "p99_ms": float(np.percentile(durations_ms, 99)),
    }


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def run_experiment(
    tables: Dict[str, pd.DataFrame],
    max_fpr: float = 0.01,
    random_state: int = 7,
    model_dir: str | Path = "models",
    report_dir: str | Path = "reports/metrics",
    processed_dir: str | Path = "data/processed",
    decision_config: Optional[str | Path] = "configs/decision.yaml",
    feature_config: Optional[str | Path] = "configs/features.yaml",
) -> Dict[str, object]:
    """Run one complete experiment and persist models, features, and metrics.

    This function requires historical transaction labels for evaluation. Labels,
    fraud scenarios, and case IDs are never included in the model feature matrix.
    """
    transactions = labeled_transactions(tables["transactions"]).reset_index(drop=True)
    if "tx_id" not in transactions:
        transactions["tx_id"] = [
            f"TX{index:09d}" for index in range(len(transactions))
        ]
    if transactions["tx_id"].duplicated().any():
        raise ValueError("Transaction IDs must be unique.")

    feature_settings = load_yaml_config(feature_config)
    features = build_features(
        {**tables, "transactions": transactions}, config=feature_settings
    )
    assignment, boundaries = time_case_split(transactions)
    transaction_indexed = transactions.set_index("tx_id", drop=False)
    assignment.index = transactions["tx_id"]
    feature_indexed = features.set_index("tx_id", drop=False)
    feature_columns = list(NUMBER_COLUMNS)
    missing_features = set(feature_columns).difference(feature_indexed.columns)
    if missing_features:
        raise ValueError(
            "Feature generation omitted columns: " + ", ".join(sorted(missing_features))
        )
    X = feature_indexed[feature_columns].astype(float)
    metadata = transaction_indexed.loc[
        X.index, ["timestamp", "is_fraud", "fraud_scenario", "amount"]
    ].copy()
    metadata["split"] = assignment.loc[metadata.index]
    keep = metadata["split"].isin(["train", "validation", "test"])
    X = X.loc[keep]
    metadata = metadata.loc[keep]

    split_indices = {
        split: metadata.index[metadata["split"] == split]
        for split in ("train", "validation", "test")
    }
    for split_name, indices in split_indices.items():
        labels = metadata.loc[indices, "is_fraud"].astype(int)
        if len(indices) < 20 or labels.nunique() != 2:
            raise ValueError(
                f"The {split_name} split needs at least 20 rows and both classes; "
                f"found {len(indices)} rows and {labels.nunique()} classes."
            )

    y_train = metadata.loc[split_indices["train"], "is_fraud"].astype(int)
    y_validation = metadata.loc[split_indices["validation"], "is_fraud"].astype(int)
    y_test = metadata.loc[split_indices["test"], "is_fraud"].astype(int)

    anomaly = fit_anomaly_model(
        X.loc[split_indices["train"]], y_train, random_state=random_state
    )
    X_with_anomaly = X.copy()
    X_with_anomaly["anomaly_score"] = anomaly_score(anomaly, X)

    logistic = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced", max_iter=500, random_state=random_state
        ),
    )
    logistic.fit(X_with_anomaly.loc[split_indices["train"]], y_train)

    gradient_boosted = make_gbm(random_state=random_state)
    weights = compute_sample_weight("balanced", y_train)
    gradient_boosted.fit(
        X_with_anomaly.loc[split_indices["train"]], y_train, sample_weight=weights
    )

    def base_probabilities(indices):
        matrix = X_with_anomaly.loc[indices]
        return (
            logistic.predict_proba(matrix)[:, 1],
            gradient_boosted.predict_proba(matrix)[:, 1],
        )

    valid_lr, valid_gbm = base_probabilities(split_indices["validation"])
    valid_blend = fuse_probabilities(valid_lr, valid_gbm)
    calibrator = fit_calibrator(valid_blend, y_validation)
    valid_calibrated = calibrator.predict(valid_blend)
    ensemble_threshold = threshold_at_fpr(y_validation, valid_calibrated, max_fpr)

    test_lr, test_gbm = base_probabilities(split_indices["test"])
    test_blend = fuse_probabilities(test_lr, test_gbm)
    test_calibrated = calibrator.predict(test_blend)
    test_data = metadata.loc[split_indices["test"]]
    test_features = features.set_index("tx_id").loc[split_indices["test"]]
    fraud_kinds = test_data["fraud_scenario"].to_numpy()
    test_amounts = test_data["amount"].astype(float).to_numpy()

    validation_scores = {
        "rules": score_rules(features.set_index("tx_id").loc[split_indices["validation"]]),
        "logistic": valid_lr,
        "gradient_boosted": valid_gbm,
        "ensemble_calibrated": valid_calibrated,
    }
    test_scores = {
        "rules": score_rules(test_features),
        "logistic": test_lr,
        "gradient_boosted": test_gbm,
        "ensemble_calibrated": test_calibrated,
    }
    thresholds = {}
    metrics = {}
    for name, valid_score in validation_scores.items():
        threshold = (
            ensemble_threshold
            if name == "ensemble_calibrated"
            else threshold_at_fpr(y_validation, valid_score, max_fpr)
        )
        thresholds[name] = threshold
        metrics[name] = evaluate_predictions(
            y_test,
            test_scores[name],
            test_amounts,
            threshold,
            fraud_kinds=fraud_kinds,
        )
        metrics[name]["recall_at_fpr_budget_on_test"] = evaluate_predictions(
            y_test,
            test_scores[name],
            test_amounts,
            threshold_at_fpr(y_test, test_scores[name], max_fpr),
        )["recall"]

    decision_settings = load_decision_config(decision_config)
    latency = _benchmark_single_transaction(
        X.loc[split_indices["test"]],
        anomaly,
        logistic,
        gradient_boosted,
        calibrator,
        decision_settings,
    )
    test_decisions = decide(test_calibrated, test_amounts, decision_settings)
    test_decisions.index = test_data.index
    test_decisions["is_fraud"] = y_test
    test_decisions["fraud_scenario"] = fraud_kinds
    test_decisions["tx_id"] = test_data.index
    action_report = (
        test_decisions.groupby("action", observed=False)
        .agg(transaction_count=("tx_id", "size"), fraud_count=("is_fraud", "sum"))
        .to_dict(orient="index")
    )

    model_path = Path(model_dir)
    report_path = Path(report_dir)
    processed_path = Path(processed_dir)
    model_path.mkdir(parents=True, exist_ok=True)
    report_path.mkdir(parents=True, exist_ok=True)
    processed_path.mkdir(parents=True, exist_ok=True)
    model_bundle = {
        "feature_columns": feature_columns + ["anomaly_score"],
        "feature_windows": feature_settings.get("windows", {}),
        "anomaly": anomaly,
        "logistic": logistic,
        "gradient_boosted": gradient_boosted,
        "calibrator": calibrator,
        "decision_config": decision_settings,
    }
    joblib.dump(model_bundle, model_path / "fraud_pipeline.joblib")

    feature_output = features.reset_index(drop=True).merge(
        transactions[["tx_id", "is_fraud", "fraud_scenario", "fraud_case"]],
        on="tx_id",
        how="left",
        validate="one_to_one",
    )
    feature_output.to_csv(processed_path / "transaction_features.csv", index=False)
    test_decisions.to_csv(processed_path / "test_decisions.csv", index=False)

    report = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
        "warning": "Mock-data metrics are rehearsal results, not evidence of real-world performance.",
        "rows": {
            "all_transactions": len(transactions),
            "excluded_boundary_case_rows": int((assignment == "excluded").sum()),
            **{name: len(indices) for name, indices in split_indices.items()},
        },
        "boundaries": boundaries,
        "max_fpr_target": max_fpr,
        "selected_thresholds": thresholds,
        "models": metrics,
        "expected_cost_actions": action_report,
        "latency_benchmark": latency,
        "tree_implementation": type(gradient_boosted).__name__,
        "feature_columns": feature_columns + ["anomaly_score"],
    }
    serialized_report = json.dumps(_json_safe(report), indent=2, allow_nan=False) + "\n"
    report_file = report_path / f"run_{report['run_id']}.json"
    report_file.write_text(serialized_report, encoding="utf-8")
    (report_path / "latest.json").write_text(serialized_report, encoding="utf-8")
    return {
        "report": report,
        "report_path": report_file,
        "model_path": model_path / "fraud_pipeline.joblib",
        "features": features,
        "decisions": test_decisions,
        "models": model_bundle,
        "assignment": assignment,
    }
