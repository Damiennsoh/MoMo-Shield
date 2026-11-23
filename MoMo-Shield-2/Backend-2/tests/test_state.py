from datetime import datetime, timedelta, timezone

from app.engine.state import EventWindow


def test_add_and_get_history():
    w = EventWindow()
    w.add("+233240000001", {"msisdn": "+233240000001", "payload": {"type": "sms"}, "timestamp": datetime.now(timezone.utc)})
    history = w.get_history("+233240000001")
    assert len(history) == 1
    assert history[0]["payload"]["type"] == "sms"


def test_history_is_per_msisdn():
    w = EventWindow()
    for msisdn in ("+233240000001", "+233240000002"):
        w.add(msisdn, {"msisdn": msisdn, "payload": {}, "timestamp": datetime.now(timezone.utc)})
    assert len(w.get_history("+233240000001")) == 1
    assert len(w.get_history("+233240000002")) == 1


def test_timezone_aware_timestamps_compare_safely():
    from datetime import timezone
    w = EventWindow()
    aware = {"msisdn": "+233240000001", "payload": {}, "timestamp": datetime.now(timezone.utc)}
    w.add("+233240000001", aware)
    assert len(w.get_history("+233240000001")) == 1


def test_old_events_expire():
    w = EventWindow(retention_minutes=30)
    old = {"msisdn": "+233240000001", "payload": {}, "timestamp": datetime.now(timezone.utc) - timedelta(minutes=45)}
    w._events["+233240000001"].append(old)
    w.add("+233240000001", {"msisdn": "+233240000001", "payload": {}, "timestamp": datetime.now(timezone.utc)})
    history = w.get_history("+233240000001", within_minutes=60)
    assert all(e["timestamp"] > datetime.now(timezone.utc) - timedelta(minutes=30) for e in history)
