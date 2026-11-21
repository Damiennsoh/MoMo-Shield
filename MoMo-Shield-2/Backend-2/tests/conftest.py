import pytest

from app.models.schemas import EventType, SandboxEvent


@pytest.fixture
def make_event():
    def _make(event_type=EventType.SMS, payload=None, msisdn="+233240000001"):
        from datetime import datetime

        return SandboxEvent(
            event_id=f"evt-{msisdn}-{event_type.value}",
            msisdn=msisdn,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            payload=payload or {},
        )

    return _make
