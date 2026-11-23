"""Merge transaction and side-channel tables into point-in-time event batches."""

from itertools import groupby
from typing import Dict, Iterator, List, Tuple

import pandas as pd


EVENT_COLUMNS = {
    "transactions": "timestamp",
    "calls": "timestamp",
    "texts": "timestamp",
    "sim_events": "timestamp",
}


def iter_event_batches(
    tables: Dict[str, pd.DataFrame],
) -> Iterator[Tuple[pd.Timestamp, Dict[str, List[dict]]]]:
    """Yield all events grouped by exact timestamp, in chronological order.

    Batching equal timestamps lets feature generation score transactions without
    accidentally using another event that occurred at the same instant.
    """
    events = []
    for table_name, timestamp_column in EVENT_COLUMNS.items():
        frame = tables.get(table_name)
        if frame is None or frame.empty or timestamp_column not in frame:
            continue
        valid = frame.loc[frame[timestamp_column].notna()]
        for row in valid.to_dict(orient="records"):
            timestamp = pd.to_datetime(
                row.pop(timestamp_column), errors="coerce", utc=True
            )
            if pd.isna(timestamp):
                continue
            events.append((timestamp, table_name, row))

    events.sort(key=lambda event: event[0])
    for timestamp, group in groupby(events, key=lambda event: event[0]):
        batch: Dict[str, List[dict]] = {}
        for _, table_name, row in group:
            batch.setdefault(table_name, []).append(row)
        yield timestamp, batch
