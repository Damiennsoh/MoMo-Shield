import re
import pandas as pd


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\.\S+", " url ", text)
    text = re.sub(r"\b\d{9,15}\b", " phone ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def prepare_event_dataframe(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    required = {"event_id", "user_id", "event_type", "timestamp"}
    missing = required.difference(result.columns)
    if missing:
        raise ValueError(f"Missing event fields: {sorted(missing)}")
    result["timestamp"] = pd.to_datetime(result["timestamp"], utc=True)
    if "message" in result:
        result["clean_message"] = result["message"].fillna("").map(clean_text)
    return result
