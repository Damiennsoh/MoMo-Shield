import pandas as pd

from momo_fraud.features.state import build_features


def _tables(transaction_count=3):
    base = pd.Timestamp("2026-01-01T00:00:00Z")
    transactions = pd.DataFrame(
        [
            {
                "tx_id": "first",
                "timestamp": base,
                "type": "p2p",
                "payer_number": "A",
                "payee_number": "B",
                "amount": 10.0,
                "fee": 0.0,
                "is_fraud": 0,
                "fraud_case": None,
            },
            {
                "tx_id": "second",
                "timestamp": base + pd.Timedelta(minutes=10),
                "type": "p2p",
                "payer_number": "A",
                "payee_number": "C",
                "amount": 20.0,
                "fee": 0.0,
                "is_fraud": 1,
                "fraud_case": "case-hidden-from-features",
            },
            {
                "tx_id": "third",
                "timestamp": base + pd.Timedelta(minutes=20),
                "type": "cash_out",
                "payer_number": "A",
                "payee_number": "D",
                "amount": 30.0,
                "fee": 0.0,
                "is_fraud": 1,
                "fraud_case": "case-hidden-from-features",
            },
        ][:transaction_count]
    )
    return {
        "transactions": transactions,
        "wallets": pd.DataFrame(),
        "calls": pd.DataFrame(
            [
                {
                    "timestamp": base + pd.Timedelta(minutes=10),
                    "caller_number": "X",
                    "callee_number": "A",
                    "duration_s": 30,
                },
                {
                    "timestamp": base + pd.Timedelta(minutes=19),
                    "caller_number": "X",
                    "callee_number": "A",
                    "duration_s": 30,
                },
            ]
        ),
        "texts": pd.DataFrame(),
        "sim_events": pd.DataFrame(),
    }


def test_features_use_only_strictly_prior_events():
    features = build_features(_tables()).set_index("tx_id")
    assert features.loc["first", "payer_tx_count_24h"] == 0
    assert features.loc["second", "payer_tx_count_24h"] == 1
    assert features.loc["second", "payer_calls_window"] == 0
    assert features.loc["third", "payer_tx_count_24h"] == 2
    assert features.loc["third", "payer_calls_window"] == 2


def test_adding_future_rows_does_not_change_earlier_features():
    original = build_features(_tables(transaction_count=2)).set_index("tx_id")
    extended = build_features(_tables(transaction_count=3)).set_index("tx_id")
    pd.testing.assert_series_equal(
        original.loc["first"],
        extended.loc["first"],
        check_names=False,
    )


def test_near_limit_threshold_uses_feature_configuration():
    tables = _tables(transaction_count=1)
    tables["transactions"].loc[0, "amount"] = 4600.0
    default = build_features(tables)
    stricter = build_features(
        tables,
        config={"thresholds": {"transaction_limit": 5000, "near_limit_fraction": 0.95}},
    )
    assert default.iloc[0]["amount_near_limit"] == 1
    assert stricter.iloc[0]["amount_near_limit"] == 0


def test_credit_claim_is_checked_against_prior_ledger_entries():
    base = pd.Timestamp("2026-01-01T00:00:00Z")
    transactions = pd.DataFrame(
        [
            {
                "tx_id": "incoming",
                "timestamp": base,
                "type": "p2p",
                "payer_number": "C",
                "payee_number": "A",
                "amount": 100.0,
            },
            {
                "tx_id": "outgoing",
                "timestamp": base + pd.Timedelta(minutes=2),
                "type": "p2p",
                "payer_number": "A",
                "payee_number": "B",
                "amount": 100.0,
            },
        ]
    )
    tables = {
        "transactions": transactions,
        "texts": pd.DataFrame(
            [
                {
                    "timestamp": base + pd.Timedelta(minutes=1),
                    "sender": "MTN MoMo",
                    "recipient_number": "A",
                    "body": "Payment received for GHS 100.00 from C",
                }
            ]
        ),
    }
    features = build_features(tables).set_index("tx_id")
    assert features.loc["outgoing", "payer_credit_claim_mismatch_1h"] == 0

    tables["transactions"] = transactions.iloc[[1]].copy()
    features = build_features(tables).set_index("tx_id")
    assert features.loc["outgoing", "payer_credit_claim_mismatch_1h"] == 1
