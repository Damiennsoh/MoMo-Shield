from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from collections import defaultdict
import threading

class EventWindow:
    def __init__(self, retention_minutes: int = 30):
        self._events: Dict[str, List[Any]] = defaultdict(list)
        self._risk_points: Dict[str, List[tuple[datetime, int, str | None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._retention = timedelta(minutes=retention_minutes)

    def add_risk(
        self,
        msisdn: str,
        points: int,
        timestamp: datetime | None = None,
        event_id: str | None = None,
    ) -> int:
        with self._lock:
            observed_at = self._ts(timestamp or datetime.now(timezone.utc))
            entries = self._risk_points[msisdn]
            watermark = max([observed_at, *(entry[0] for entry in entries)])
            cutoff = watermark - self._retention
            entries = [entry for entry in entries if entry[0] >= cutoff]
            already_counted = event_id is not None and any(entry[2] == event_id for entry in entries)
            if not already_counted and points > 0:
                entries.append((observed_at, points, event_id))
            self._risk_points[msisdn] = entries
            return min(100, sum(entry[1] for entry in entries))

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._risk_points.clear()

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
