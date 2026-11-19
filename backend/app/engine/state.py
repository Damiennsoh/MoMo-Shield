from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from collections import defaultdict
import threading

class EventWindow:
    def __init__(self, retention_minutes: int = 30):
        self._events: Dict[str, List[Any]] = defaultdict(list)
        self._scores: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._retention = timedelta(minutes=retention_minutes)

    def add_risk(self, msisdn: str, points: int) -> int:
        with self._lock:
            self._scores[msisdn] = min(100, self._scores[msisdn] + points)
            return self._scores[msisdn]

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._scores.clear()

    @staticmethod
    def _ts(value: Any) -> datetime:
        # Event timestamps may arrive naive (fixture local time) or aware
        # (live-signal UTC). Normalize everything to aware UTC for compares.
        if not isinstance(value, datetime):
            return datetime.min.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def add(self, msisdn: str, event: Any) -> None:
        with self._lock:
            self._events[msisdn].append(event)
            self._prune(msisdn, cutoff=datetime.now(timezone.utc) - self._retention)

    def _prune(self, msisdn: str, cutoff: datetime) -> None:
        self._events[msisdn] = [e for e in self._events[msisdn] if self._ts(getattr(e, "timestamp", None)) >= cutoff]

    def get_events(self, msisdn: str, event_type: str = None, within: timedelta = None, before: datetime = None) -> List[Any]:
        with self._lock:
            events = list(self._events.get(msisdn, []))
        if before is not None:
            before = self._ts(before)
            events = [e for e in events if self._ts(getattr(e, "timestamp", None)) < before]
        if within and before is not None:
            cutoff = before - within
            events = [e for e in events if self._ts(getattr(e, "timestamp", None)) >= cutoff]
        if event_type:
            events = [e for e in events if getattr(e, "event_type", None) and e.event_type.value == event_type]
        return events

global_window = EventWindow(retention_minutes=30)