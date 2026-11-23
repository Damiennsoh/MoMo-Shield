"""Chronological train/validation/test splits that keep fraud cases together."""

from typing import Dict, Tuple

import pandas as pd


def time_case_split(
    transactions: pd.DataFrame,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> Tuple[pd.Series, Dict[str, pd.Timestamp]]:
    """Return row assignments; cases crossing time boundaries are excluded.

    The returned Series is indexed like ``transactions`` and contains ``train``,
    ``validation``, ``test``, or ``excluded``. Fraud-case rows are assigned as a
    group, and a case spanning a boundary is excluded rather than split.
    """
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1.")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1.")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train_fraction + validation_fraction must be below 1.")
    required = {"timestamp"}
    missing = required.difference(transactions.columns)
    if missing:
        raise ValueError(f"Transactions missing columns: {', '.join(sorted(missing))}")

    timestamps = pd.to_datetime(transactions["timestamp"], errors="coerce", utc=True)
    if timestamps.isna().any():
        raise ValueError("Cannot split rows with invalid timestamps.")
    first_cut = timestamps.quantile(train_fraction)
    second_cut = timestamps.quantile(train_fraction + validation_fraction)
    if first_cut >= second_cut:
        raise ValueError("Time boundaries are identical; use more varied timestamps.")

    def period(value: pd.Timestamp) -> str:
        if value <= first_cut:
            return "train"
        if value <= second_cut:
            return "validation"
        return "test"

    assignment = pd.Series(
        [period(value) for value in timestamps], index=transactions.index, dtype="object"
    )
    if "fraud_case" in transactions:
        case_rows = transactions["fraud_case"].notna()
        for _, indices in transactions.loc[case_rows].groupby(
            "fraud_case", sort=False
        ).groups.items():
            case_periods = {period(timestamps.loc[index]) for index in indices}
            target = case_periods.pop() if len(case_periods) == 1 else "excluded"
            assignment.loc[list(indices)] = target

    boundaries = {"train_end": first_cut, "validation_end": second_cut}
    return assignment, boundaries
