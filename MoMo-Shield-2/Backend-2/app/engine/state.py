from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from collections import defaultdict
import threading


def _naive_utc(value: Any) -> datetime:
    """Normalize stored timestamps to naive UTC for safe comparisons."""
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class EventWindow:
    def __init__(self, retention_minutes: int = 30):
        self._events: Dict[str, List[Any]] = defaultdict(list)
        self._lock = threading.Lock()
        self._retention = timedelta(minutes=retention_minutes)

    def add(self, msisdn: str, event: Any) -> None:
        with self._lock:
            self._events[msisdn].append(event)
            cutoff = datetime.utcnow() - self._retention
            self._events[msisdn] = [
                e for e in self._events[msisdn]
                if _naive_utc(e.get('timestamp')) >= cutoff
            ]

    def get_history(self, msisdn: str, within_minutes: int = 10) -> List[Any]:
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(minutes=within_minutes)
            return [
                e for e in self._events.get(msisdn, [])
                if _naive_utc(e.get('timestamp')) >= cutoff
            ]


global_window = EventWindow()
