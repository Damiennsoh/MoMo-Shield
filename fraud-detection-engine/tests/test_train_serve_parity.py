import pandas as pd

from momo_fraud.features.state import build_features


def test_same_event_history_produces_identical_features():
    timestamp = pd.Timestamp("2026-01-01T00:00:00Z")
    tables = {
        "transactions": pd.DataFrame(
            [
                {
                    "tx_id": "one",
                    "timestamp": timestamp,
                    "type": "p2p",
                    "payer_number": "A",
                    "payee_number": "B",
                    "amount": 5.0,
                },
                {
                    "tx_id": "two",
                    "timestamp": timestamp + pd.Timedelta(minutes=1),
                    "type": "cash_out",
                    "payer_number": "B",
                    "payee_number": "C",
                    "amount": 4.0,
                },
            ]
        ),
        "calls": pd.DataFrame(),
        "texts": pd.DataFrame(),
        "sim_events": pd.DataFrame(),
        "wallets": pd.DataFrame(),
    }
    offline = build_features(tables)
    live_replay = build_features(tables)
    pd.testing.assert_frame_equal(offline, live_replay)
