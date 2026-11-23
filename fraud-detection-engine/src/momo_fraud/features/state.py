"""Replay events in time order and construct point-in-time transaction features."""

from collections import defaultdict, deque
from datetime import timedelta
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from momo_fraud.events import iter_event_batches
from momo_fraud.features.graph import graph_feature_values
from momo_fraud.features.sim_call import sim_call_feature_values
from momo_fraud.features.transactional import transactional_feature_values
from momo_fraud.features.text import message_flags


DEFAULT_WINDOWS = {
    "history_days": 30,
    "velocity_hours": 1,
    "day_hours": 24,
    "week_days": 7,
    "call_minutes": 30,
    "text_hours": 1,
    "text_days": 24,
    "sim_hours": 72,
}
TX_TYPES = (
    "p2p",
    "cash_in",
    "cash_out",
    "merchant_pay",
    "float_transfer",
    "bank_to_wallet",
    "approval_debit",
)
NUMBER_COLUMNS = (
    "amount",
    "fee",
    "payer_tx_count_1h",
    "payer_tx_count_24h",
    "payer_tx_count_7d",
    "payer_out_count_24h",
    "payer_out_amount_24h",
    "payer_in_amount_24h",
    "payer_unique_payees_7d",
    "payer_new_payee",
    "payer_amount_mean_30d",
    "amount_vs_payer_mean",
    "payee_in_count_24h",
    "payee_in_amount_24h",
    "payee_unique_senders_24h",
    "payee_unique_senders_7d",
    "payee_out_amount_24h",
    "payee_pass_through_ratio",
    "amount_near_limit",
    "amount_to_limit_ratio",
    "payer_calls_window",
    "payee_calls_window",
    "call_before_tx",
    "payer_texts_1h",
    "payer_suspicious_texts_24h",
    "payee_suspicious_texts_24h",
    "payer_prize_texts_24h",
    "payer_urgent_texts_24h",
    "payer_credit_claim_texts_24h",
    "payer_credit_claim_mismatch_1h",
    "payer_hours_since_sim_replacement",
    "payer_hours_since_pin_reset",
    "payee_hours_since_sim_replacement",
    "payee_hours_since_pin_reset",
    "payer_sim_replacement_count_window",
    "payer_pin_reset_count_window",
    "payee_sim_replacement_count_window",
    "payee_pin_reset_count_window",
    "payer_sim_and_pin_reset_window",
    "payer_account_age_days",
    "payee_account_age_days",
    "hour_of_day",
    "is_weekend",
    "is_night",
    *(f"type_{name}" for name in TX_TYPES),
)

def _as_number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _identifier(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _records_in_window(
    records: Iterable[tuple], timestamp: pd.Timestamp, window: timedelta
) -> List[tuple]:
    start = timestamp - window
    return [record for record in records if start < record[0] < timestamp]


def build_features(
    tables: Dict[str, pd.DataFrame], config: Dict[str, object] | None = None
) -> pd.DataFrame:
    """Create numeric features using only events strictly earlier than each transaction.

    Fraud labels and case metadata are deliberately not read by this function.
    """
    config = config or {}
    windows = config.get("windows") or {}
    configured_thresholds = config.get("thresholds") or {}
    if not isinstance(windows, dict) or not isinstance(configured_thresholds, dict):
        raise ValueError("Feature windows and thresholds must be YAML mappings.")
    window_config = {**DEFAULT_WINDOWS, **windows}
    thresholds = {
        "transaction_limit": 5000.0,
        "near_limit_fraction": 0.9,
        **configured_thresholds,
    }
    if any(float(value) <= 0 for value in window_config.values()):
        raise ValueError("Feature windows must be positive.")
    if float(thresholds["transaction_limit"]) <= 0:
        raise ValueError("transaction_limit must be positive.")
    if not 0 < float(thresholds["near_limit_fraction"]) <= 1:
        raise ValueError("near_limit_fraction must be between 0 and 1.")
    history_retention = timedelta(days=float(window_config["history_days"]))
    history_hours = history_retention.total_seconds() / 3600.0
    velocity_window = timedelta(hours=float(window_config["velocity_hours"]))
    day_window = timedelta(hours=float(window_config["day_hours"]))
    week_window = timedelta(days=float(window_config["week_days"]))
    text_window = timedelta(hours=float(window_config["text_hours"]))
    text_day_window = timedelta(hours=float(window_config["text_days"]))

    transactions = tables.get("transactions")
    if transactions is None or transactions.empty:
        raise ValueError("A non-empty transactions table is required to build features.")
    if "timestamp" not in transactions:
        raise ValueError("Transactions must contain a 'timestamp' column.")

    tables = dict(tables)
    tables["transactions"] = transactions.copy()
    tables["transactions"]["timestamp"] = pd.to_datetime(
        tables["transactions"]["timestamp"], errors="coerce", utc=True
    )
    if tables["transactions"]["timestamp"].isna().any():
        raise ValueError("Transactions contain invalid timestamps.")
    if "tx_id" not in tables["transactions"]:
        tables["transactions"]["tx_id"] = [
            f"TX{index:09d}" for index in range(len(transactions))
        ]

    wallets = tables.get("wallets", pd.DataFrame())
    wallet_opened: Dict[str, pd.Timestamp] = {}
    if not wallets.empty and {"number", "opened_at"}.issubset(wallets.columns):
        opened_at = pd.to_datetime(wallets["opened_at"], errors="coerce", utc=True)
        wallet_opened = {
            _identifier(number): opened
            for number, opened in zip(wallets["number"], opened_at)
            if _identifier(number) and pd.notna(opened)
        }

    histories: Dict[str, deque] = defaultdict(deque)
    calls: Dict[str, deque] = defaultdict(deque)
    texts: Dict[str, deque] = defaultdict(deque)
    sim_events: Dict[str, deque] = defaultdict(deque)
    latest_sim_event: Dict[Tuple[str, str], pd.Timestamp] = {}
    feature_rows: List[dict] = []

    for timestamp, batch in iter_event_batches(tables):
        transaction_rows = batch.get("transactions", [])
        touched_history = set()
        touched_calls = set()
        touched_texts = set()
        touched_sim_events = set()
        for transaction in transaction_rows:
            payer = _identifier(transaction.get("payer_number"))
            payee = _identifier(transaction.get("payee_number"))
            amount = max(_as_number(transaction.get("amount")), 0.0)
            fee = max(_as_number(transaction.get("fee")), 0.0)
            payer_history = list(histories.get(payer, ()))
            payee_history = list(histories.get(payee, ()))
            payer_1h = _records_in_window(payer_history, timestamp, velocity_window)
            payer_24h = _records_in_window(payer_history, timestamp, day_window)
            payer_7d = _records_in_window(payer_history, timestamp, week_window)
            payer_30d = _records_in_window(payer_history, timestamp, history_retention)
            payee_24h = _records_in_window(payee_history, timestamp, day_window)
            payee_7d = _records_in_window(payee_history, timestamp, week_window)

            transaction_features = transactional_feature_values(
                payer_1h,
                payer_24h,
                payer_7d,
                payer_30d,
                amount,
                float(thresholds["transaction_limit"]),
                float(thresholds["near_limit_fraction"]),
            )
            graph_features = graph_feature_values(
                payer_7d, payee_24h, payee_7d, payee
            )
            call_sim_features = sim_call_feature_values(
                payer,
                payee,
                calls,
                sim_events,
                latest_sim_event,
                timestamp,
                float(window_config["call_minutes"]),
                float(window_config["sim_hours"]),
                history_hours,
            )
            payer_text_1h = _records_in_window(
                texts.get(payer, ()), timestamp, text_window
            )
            payer_text_24h = _records_in_window(
                texts.get(payer, ()), timestamp, text_day_window
            )
            payer_credit_claims_1h = [
                message
                for message in payer_text_1h
                if message[1][3] and message[1][4] > 0
            ]
            credit_claim_mismatches = 0
            for message_time, flags in payer_credit_claims_1h:
                claimed_amount = flags[4]
                matched_credit = any(
                    item[1] == "in"
                    and abs(item[3] - claimed_amount)
                    <= max(1.0, claimed_amount * 0.02)
                    and abs((item[0] - message_time).total_seconds()) <= 10 * 60
                    for item in payer_history
                )
                credit_claim_mismatches += int(not matched_credit)
            payee_text_24h = _records_in_window(
                texts.get(payee, ()), timestamp, text_day_window
            )
            suspicious_payer = [row for row in payer_text_24h if row[1][0]]
            suspicious_payee = [row for row in payee_text_24h if row[1][0]]
            payer_opened = wallet_opened.get(payer)
            payee_opened = wallet_opened.get(payee)
            transaction_type = _identifier(transaction.get("type")).lower()
            row = {
                "tx_id": _identifier(transaction.get("tx_id")),
                "timestamp": timestamp,
                "amount": amount,
                "fee": fee,
                "payer_texts_1h": len(payer_text_1h),
                "payer_suspicious_texts_24h": len(suspicious_payer),
                "payee_suspicious_texts_24h": len(suspicious_payee),
                "payer_prize_texts_24h": sum(item[1][1] for item in payer_text_24h),
                "payer_urgent_texts_24h": sum(item[1][2] for item in payer_text_24h),
                "payer_credit_claim_texts_24h": sum(item[1][3] for item in payer_text_24h),
                "payer_credit_claim_mismatch_1h": credit_claim_mismatches,
                "payer_account_age_days": (
                    max((timestamp - payer_opened).total_seconds() / 86400.0, 0.0)
                    if payer_opened is not None
                    else 3650.0
                ),
                "payee_account_age_days": (
                    max((timestamp - payee_opened).total_seconds() / 86400.0, 0.0)
                    if payee_opened is not None
                    else 3650.0
                ),
                "hour_of_day": timestamp.hour,
                "is_weekend": int(timestamp.dayofweek >= 5),
                "is_night": int(timestamp.hour < 6 or timestamp.hour >= 22),
            }
            for known_type in TX_TYPES:
                row[f"type_{known_type}"] = int(transaction_type == known_type)
            row.update(transaction_features)
            row.update(graph_features)
            row.update(call_sim_features)
            feature_rows.append(row)

        # Update transaction history only after all transactions at this timestamp
        # have been scored, so simultaneous events cannot leak into one another.
        for transaction in transaction_rows:
            payer = _identifier(transaction.get("payer_number"))
            payee = _identifier(transaction.get("payee_number"))
            amount = max(_as_number(transaction.get("amount")), 0.0)
            if payer:
                histories[payer].append((timestamp, "out", payee, amount))
                touched_history.add(payer)
            if payee:
                histories[payee].append((timestamp, "in", payer, amount))
                touched_history.add(payee)

        for call in batch.get("calls", []):
            caller = _identifier(call.get("caller_number"))
            callee = _identifier(call.get("callee_number"))
            if caller:
                calls[caller].append((timestamp, callee))
                touched_calls.add(caller)
            if callee:
                calls[callee].append((timestamp, caller))
                touched_calls.add(callee)
        for text in batch.get("texts", []):
            recipient = _identifier(text.get("recipient_number"))
            sender = _identifier(text.get("sender"))
            flags = message_flags(text.get("body"))
            if recipient:
                texts[recipient].append((timestamp, flags))
                touched_texts.add(recipient)
            if sender and not sender.lower().endswith(("momo", "cash", "money")):
                texts[sender].append((timestamp, flags))
                touched_texts.add(sender)
        for event in batch.get("sim_events", []):
            number = _identifier(event.get("number"))
            event_name = _identifier(event.get("event")).strip().lower()
            if number and event_name in {"sim_replacement", "pin_reset"}:
                sim_events[number].append((timestamp, event_name))
                latest_sim_event[(number, event_name)] = timestamp
                touched_sim_events.add(number)

        cutoff = timestamp - history_retention
        for collection, touched in (
            (histories, touched_history),
            (calls, touched_calls),
            (texts, touched_texts),
            (sim_events, touched_sim_events),
        ):
            for number in touched:
                while collection[number] and collection[number][0][0] <= cutoff:
                    collection[number].popleft()
                if not collection[number]:
                    del collection[number]

    result = pd.DataFrame(feature_rows)
    if result.empty:
        raise ValueError("No transaction features were produced.")
    result = result.set_index("tx_id", drop=False)
    result[list(NUMBER_COLUMNS)] = result[list(NUMBER_COLUMNS)].replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0.0)
    return result
