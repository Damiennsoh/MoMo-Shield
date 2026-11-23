import pandas as pd

from momo_fraud.splits import time_case_split


def test_case_crossing_time_boundary_is_excluded_as_a_group():
    timestamps = pd.date_range("2026-01-01", periods=10, freq="h", tz="UTC")
    transactions = pd.DataFrame(
        {
            "timestamp": timestamps,
            "fraud_case": [None, None, None, None, None, "crossing", "crossing", None, None, None],
        }
    )
    assignment, _ = time_case_split(transactions)
    assert assignment.iloc[5] == "excluded"
    assert assignment.iloc[6] == "excluded"
