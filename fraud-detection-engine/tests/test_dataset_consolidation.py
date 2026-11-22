from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "data" / "synthetic"


def test_combined_communication_preserves_source_fields_and_labels():
    communication = pd.read_csv(SYNTHETIC / "communication_events.csv")

    assert len(communication) == 1300
    assert communication["source_dataset"].nunique() == 3
    assert {"scenario_tags", "data_origin", "source_record_id", "is_social_engineering"} <= set(communication.columns)
    assert communication.groupby("source_dataset")["is_fraudulent"].nunique().eq(2).all()


def test_combined_transactions_preserve_both_feature_schemas():
    transactions = pd.read_csv(SYNTHETIC / "transactions.csv")

    assert len(transactions) == 2000
    assert transactions["source_dataset"].nunique() == 2
    assert {"credential_request_detected", "recipient_recently_reported", "transaction_type"} <= set(transactions.columns)
    assert transactions.groupby("source_dataset")["is_fraudulent"].nunique().eq(2).all()


def test_integrated_test_scenarios_have_consistent_labels():
    events = pd.read_csv(SYNTHETIC / "integrated_event_test.csv")
    labels_per_scenario = events.groupby("scenario_id")["scenario_is_fraudulent"].nunique()

    assert labels_per_scenario.eq(1).all()
    scam_without_transfer = events.loc[
        events["scenario_name"] == "suspicious_message_no_transaction",
        "scenario_is_fraudulent",
    ]
    assert scam_without_transfer.eq(1).all()
