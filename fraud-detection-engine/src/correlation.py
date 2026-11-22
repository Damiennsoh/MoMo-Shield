import pandas as pd


def correlate_events(transaction: dict, events: pd.DataFrame, window_minutes: int = 15) -> pd.DataFrame:
    transaction_time = pd.Timestamp(transaction["timestamp"])
    if transaction_time.tzinfo is None:
        transaction_time = transaction_time.tz_localize("UTC")
    else:
        transaction_time = transaction_time.tz_convert("UTC")

    data = events.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)
    lower = transaction_time - pd.Timedelta(minutes=window_minutes)
    mask = (
        (data["user_id"] == transaction["user_id"])
        & (data["timestamp"] >= lower)
        & (data["timestamp"] <= transaction_time)
    )
    return data.loc[mask].sort_values("timestamp")
