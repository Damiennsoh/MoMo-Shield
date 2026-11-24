"""Rolling per-subscriber event window.

Two backends behind one interface:
- In-memory (default): process-local dict, used when REDIS_URL is unset or
  Redis is unreachable. Correct for a single worker.
- Redis sorted sets: shared across workers/instances so correlation survives
  horizontal scaling. Keys: momo:window:{msisdn}, score = event epoch,
  member = JSON event. Falls back to memory per-call on Redis errors.
"""
import hashlib
import json
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def _naive_utc(value: Any) -> datetime:
    """Normalize stored timestamps to naive UTC for safe comparisons."""
    if not isinstance(value, datetime):
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _event_epoch(event: Any) -> float:
    """Epoch seconds for an event's timestamp; falls back to now."""
    ts = event.get("timestamp") if isinstance(event, dict) else None
    if isinstance(ts, datetime):
        dt = _naive_utc(ts)
    elif isinstance(ts, str):
        try:
            dt = _naive_utc(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except (TypeError, ValueError):
            dt = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        dt = datetime.now(timezone.utc).replace(tzinfo=None)
    return dt.replace(tzinfo=timezone.utc).timestamp()


_OBSERVE_LUA = """
local key = KEYS[1]
local window_cutoff = tonumber(ARGV[1])
local retain_cutoff = tonumber(ARGV[2])
local member = ARGV[3]
local score = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', key, '-inf', retain_cutoff)
local prior = redis.call('ZRANGEBYSCORE', key, window_cutoff, '+inf')
redis.call('ZADD', key, score, member)
redis.call('EXPIRE', key, ttl)
return prior
"""


class EventWindow:
    """Rolling event history with serializable, worker-shared access."""

    _KEY_PREFIX = "momo:window:"
    _KEY_TTL = 3600

    def __init__(self, retention_minutes: int = 30):
        self._events: Dict[str, List[Any]] = defaultdict(list)
        self._lock = threading.Lock()
        self._retention = timedelta(minutes=retention_minutes)
        self._redis = None
        self._redis_failed = False
        if settings.redis_url:
            try:
                import redis

                self._redis = redis.Redis.from_url(
                    settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
                )
                self._redis.ping()
                log.info("EventWindow: using shared Redis backend (%s).", settings.redis_url.split("@")[-1])
            except Exception as exc:
                log.warning("Redis unavailable (%s); falling back to in-memory window.", exc)
                self._redis = None
                self._redis_failed = True

    # ---------- memory backend ----------

    def _trim(self, msisdn: str, now: datetime) -> None:
        cutoff = now - self._retention
        self._events[msisdn] = [
            event for event in self._events[msisdn]
            if _naive_utc(event.get("timestamp")) >= cutoff
        ]

    def _mem_add(self, msisdn: str, event: Any) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self._lock:
            self._events[msisdn].append(event)
            self._trim(msisdn, now)

    def _mem_observe_and_add(self, msisdn: str, event: Any, within_minutes: int) -> List[Any]:
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

    def _mem_get_history(self, msisdn: str, within_minutes: int) -> List[Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(minutes=within_minutes)
        with self._lock:
            self._trim(msisdn, now)
            return [
                event for event in self._events.get(msisdn, [])
                if _naive_utc(event.get("timestamp")) >= cutoff
            ]

    def _mem_clear(self) -> None:
        with self._lock:
            self._events.clear()

    def _mem_event_count(self) -> int:
        with self._lock:
            return sum(len(events) for events in self._events.values())

    # ---------- redis backend ----------

    @staticmethod
    def _key(msisdn: str) -> str:
        return f"{EventWindow._KEY_PREFIX}{msisdn}"

    @staticmethod
    def _decode(member: Any) -> Any:
        try:
            return json.loads(member)
        except (TypeError, ValueError):
            return None

    def _redis_add(self, msisdn: str, event: Any) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None).timestamp()
        retain_cutoff = now - self._retention.total_seconds()
        self._redis.zadd(self._key(msisdn), {_event_json(event): _event_epoch(event)})
        self._redis.zremrangebyscore(self._key(msisdn), "-inf", retain_cutoff)
        self._redis.expire(self._key(msisdn), self._KEY_TTL)
        return True

    def _redis_observe_and_add(self, msisdn: str, event: Any, within_minutes: int) -> List[Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None).timestamp()
        window_cutoff = now - within_minutes * 60
        retain_cutoff = now - self._retention.total_seconds()
        prior_raw = self._redis.eval(
            _OBSERVE_LUA,
            1,
            self._key(msisdn),
            window_cutoff,
            retain_cutoff,
            _event_json(event),
            _event_epoch(event),
            self._KEY_TTL,
        )
        return [e for e in (_decode(m) for m in prior_raw) if isinstance(e, dict)]

    def _redis_get_history(self, msisdn: str, within_minutes: int) -> List[Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None).timestamp()
        window_cutoff = now - within_minutes * 60
        retain_cutoff = now - self._retention.total_seconds()
        self._redis.zremrangebyscore(self._key(msisdn), "-inf", retain_cutoff)
        members = self._redis.zrangebyscore(self._key(msisdn), window_cutoff, "+inf")
        return [e for e in (_decode(m) for m in members) if isinstance(e, dict)]

    def _redis_clear(self) -> bool:
        for key in self._redis.scan_iter(match=f"{self._KEY_PREFIX}*", count=200):
            self._redis.delete(key)
        return True

    # ---------- public interface ----------

    def _backend(self):
        """Return 'redis' when usable, else 'memory'."""
        return "redis" if self._redis is not None else "memory"

    def _guard(self, fn, *args, **kwargs):
        """Run fn against Redis; on failure fall back to memory permanently."""
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if self._redis is not None and not self._redis_failed:
                self._redis_failed = True
                log.warning("Redis window op failed (%s); permanently falling back to memory.", exc)
                self._redis = None
            return None

    def add(self, msisdn: str, event: Any) -> None:
        if self._backend() == "redis":
            if self._guard(self._redis_add, msisdn, event) is None:
                pass
            else:
                return
        self._mem_add(msisdn, event)

    def observe_and_add(self, msisdn: str, event: Any, within_minutes: int = 10) -> List[Any]:
        if self._backend() == "redis":
            result = self._guard(self._redis_observe_and_add, msisdn, event, within_minutes)
            if result is not None:
                return result
        return self._mem_observe_and_add(msisdn, event, within_minutes)

    def get_history(self, msisdn: str, within_minutes: int = 10) -> List[Any]:
        if self._backend() == "redis":
            result = self._guard(self._redis_get_history, msisdn, within_minutes)
            if result is not None:
                return result
        return self._mem_get_history(msisdn, within_minutes)

    def clear(self) -> None:
        if self._backend() == "redis":
            self._guard(self._redis_clear)
        self._mem_clear()

    def event_count(self) -> int:
        # Redis has no cheap global count; report process-local events only.
        return self._mem_event_count()


def _event_json(event: Any) -> str:
    return json.dumps(event, default=str)


global_window = EventWindow()


class SmsBlastWindow:
    """Cross-subscriber SMS blast detector.

    Complements the per-MSISDN EventWindow: indexes normalized SMS text
    across ALL subscribers so identical scam texts hitting many victims in a
    short window escalate the score. In-memory only — a Redis sorted-set
    backend can replace it the same way EventWindow does when needed.
    """

    _MIN_NORMALIZED_LEN = 10

    def __init__(self, window_minutes: int = 10):
        self._window_seconds = window_minutes * 60
        self._hits: Dict[str, List[tuple]] = defaultdict(list)  # hash -> [(epoch, msisdn)]
        self._lock = threading.Lock()
        self._ops = 0

    @staticmethod
    def _key(text: str) -> str:
        normalized = "".join(ch for ch in str(text).lower() if ch.isalnum())
        if len(normalized) < SmsBlastWindow._MIN_NORMALIZED_LEN:
            return ""
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def observe(self, text: str, msisdn: str) -> int:
        """Record an SMS delivery; return distinct victims seen in window."""
        key = self._key(text)
        if not key:
            return 0
        now = time.time()
        cutoff = now - self._window_seconds
        with self._lock:
            hits = [(t, m) for t, m in self._hits[key] if t >= cutoff]
            hits.append((now, msisdn))
            self._hits[key] = hits
            self._ops += 1
            if self._ops % 500 == 0:
                self._sweep(cutoff)
            return len({m for _, m in hits})

    def _sweep(self, cutoff: float) -> None:
        stale = [k for k, v in self._hits.items() if not any(t >= cutoff for t, _ in v)]
        for k in stale:
            del self._hits[k]

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


sms_blast_window = SmsBlastWindow()
