from collections import defaultdict
from datetime import datetime, timedelta, timezone
import threading
from typing import Any, Dict, List


def _naive_utc(value: Any) -> datetime:
    """Normalize stored timestamps to naive UTC for safe comparisons."""
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class EventWindow:
    """Process-local rolling event history with serializable access."""

    def __init__(self, retention_minutes: int = 30):
        self._events: Dict[str, List[Any]] = defaultdict(list)
        self._lock = threading.Lock()
        self._retention = timedelta(minutes=retention_minutes)

    def _trim(self, msisdn: str, now: datetime) -> None:
        cutoff = now - self._retention
        self._events[msisdn] = [
            event for event in self._events[msisdn]
            if _naive_utc(event.get("timestamp")) >= cutoff
        ]

    def add(self, msisdn: str, event: Any) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self._lock:
            self._events[msisdn].append(event)
            self._trim(msisdn, now)

    def observe_and_add(
        self, msisdn: str, event: Any, within_minutes: int = 10
    ) -> List[Any]:
        """Atomically return recent prior events and append this event."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(minutes=within_minutes)
        with self._lock:
            self._trim(msisdn, now)
            prior = [
                item for item in self._events[msisdn]
                if _naive_utc(item.get("timestamp")) >= cutoff
            ]
            self._events[msisdn].append(event)
            self._trim(msisdn, now)
            return prior

    def get_history(self, msisdn: str, within_minutes: int = 10) -> List[Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(minutes=within_minutes)
        with self._lock:
            self._trim(msisdn, now)
            return [
                event for event in self._events.get(msisdn, [])
                if _naive_utc(event.get("timestamp")) >= cutoff
            ]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def event_count(self) -> int:
        with self._lock:
            return sum(len(events) for events in self._events.values())


global_window = EventWindow()
