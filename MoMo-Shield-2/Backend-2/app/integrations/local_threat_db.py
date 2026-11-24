"""Proprietary local threat ledger — "Mini-Glance".

Complements the Rancard Glance API: a fast, persistent, self-owned record of
numbers our engine has confirmed as fraudulent. Repeat offenders are caught
in <1ms without an external call, and the ledger survives restarts and Glance
outages. Entries decay after TTL_DAYS unless re-confirmed.

Write discipline matters: callers must only record *suspicious-party* numbers
(the SMS/call sender, not the victim) and only on scam-confirmed signals —
never on bare HIGH scores, which would poison the ledger with victims and
innocent payers.
"""
import sqlite3
import threading
import time
from pathlib import Path

from app.utils.logger import get_logger

log = get_logger(__name__)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "threat_intel.db"
TTL_DAYS = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flagged_numbers (
    msisdn TEXT PRIMARY KEY,
    threat_type TEXT,
    report_count INTEGER DEFAULT 1,
    first_seen REAL,
    last_seen REAL
)
"""

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def normalize_msisdn(msisdn) -> str:
    """Canonical local form: digits only, 233… → 0…"""
    digits = "".join(ch for ch in str(msisdn or "") if ch.isdigit())
    if digits.startswith("233"):
        digits = "0" + digits[3:]
    return digits


def check(msisdn: str) -> dict:
    """Look up a number. Returns found/reports/threat_type/age_days."""
    key = normalize_msisdn(msisdn)
    if not key:
        return {"found": False, "reports": 0}
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT * FROM flagged_numbers WHERE msisdn = ?", (key,)
            ).fetchone()
    except sqlite3.Error as exc:
        log.warning("Local threat DB read failed (fail-open): %s", exc)
        return {"found": False, "reports": 0}
    if not row:
        return {"found": False, "reports": 0}
    age_days = (time.time() - row["last_seen"]) / 86400
    if age_days > TTL_DAYS:
        return {"found": False, "reports": 0, "expired": True}
    return {
        "found": True,
        "reports": row["report_count"],
        "threat_type": row["threat_type"],
        "age_days": round(age_days, 1),
    }


def record(msisdn: str, threat_type: str) -> None:
    """Upsert a confirmed-fraud number. Repeat sightings strengthen it."""
    key = normalize_msisdn(msisdn)
    if not key:
        return
    now = time.time()
    try:
        with _lock, _connect() as conn:
            conn.execute(
                """
                INSERT INTO flagged_numbers (msisdn, threat_type, report_count, first_seen, last_seen)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(msisdn) DO UPDATE SET
                    report_count = report_count + 1,
                    last_seen = excluded.last_seen,
                    threat_type = excluded.threat_type
                """,
                (key, threat_type[:120], now, now),
            )
            conn.commit()
        log.info("Local threat DB: %s flagged (%s, count updated)", key, threat_type)
    except sqlite3.Error as exc:
        log.warning("Local threat DB write failed: %s", exc)


def clear_all() -> None:
    """Test hook: empty the ledger."""
    try:
        with _lock, _connect() as conn:
            conn.execute("DELETE FROM flagged_numbers")
            conn.commit()
    except sqlite3.Error as exc:
        log.warning("Local threat DB clear failed: %s", exc)


init_db()
