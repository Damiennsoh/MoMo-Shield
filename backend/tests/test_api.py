import json
import re
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.engine.state import global_window

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_gemini_healthcheck_requires_configuration(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=False))
    r = client.post("/api/v1/gemini/healthcheck")
    assert r.status_code == 503
    assert r.json()["detail"]["status"] == "not_configured"

def test_gemini_healthcheck_makes_a_real_extractor_call(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    calls = []

    async def fake_extract(text):
        calls.append(text)
        return {"pattern": None, "evidence_phrases": []}

    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True, gemini_model="gemini-3.5-flash-lite"))
    monkeypatch.setattr(routes, "extract_intent", fake_extract)
    r = client.post("/api/v1/gemini/healthcheck")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["model"] == "gemini-3.5-flash-lite"
    assert calls and "Connectivity test" in calls[0]

def test_gemini_healthcheck_reports_provider_failure_without_secrets(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace

    async def fail(_text):
        raise RuntimeError("provider failure detail")

    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True, gemini_model="gemini-3.5-flash-lite"))
    monkeypatch.setattr(routes, "extract_intent", fail)
    r = client.post("/api/v1/gemini/healthcheck")
    assert r.status_code == 502
    assert "provider failure detail" not in r.text

def test_demo_handset_page_is_available_and_event_publish_requires_token(monkeypatch, tmp_path):
    from app.api import demo_device
    from types import SimpleNamespace
    audio = tmp_path / "ring.mp3"
    audio.write_bytes(b"synthetic test audio")
    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(
        demo_device_token="demo-test-token", demo_device_audio_dir=str(tmp_path),
    ))
    page = client.get("/api/v1/demo-device")
    assert page.status_code == 200
    assert "synthetic demo handset" in page.text
    stream_denied = client.get("/api/v1/demo-device/stream")
    assert stream_denied.status_code == 403
    denied = client.post("/api/v1/demo-device/publish", json={"type": "sms", "message": "fake demo"})
    assert denied.status_code == 403
    sent = client.post("/api/v1/demo-device/publish", headers={"Authorization": "Bearer demo-test-token"},
                       json={"type": "sms", "message": "synthetic test message"})
    assert sent.status_code == 200
    assert sent.json()["status"] == "published"
    assert sent.json()["sip"] is None
    assert client.get("/api/v1/demo-device/audio/ring.mp3").status_code == 403
    audio_response = client.get(
        "/api/v1/demo-device/audio/ring.mp3",
        headers={"Authorization": "Bearer demo-test-token"},
    )
    assert audio_response.status_code == 200
    assert audio_response.content == b"synthetic test audio"
    assert audio_response.headers["content-type"].startswith("audio/mpeg")
    assert client.get(
        "/api/v1/demo-device/audio/not-allowlisted.mp3",
        headers={"Authorization": "Bearer demo-test-token"},
    ).status_code == 404

def test_sip_bridge_is_only_requested_by_explicit_call_event(monkeypatch):
    from app.api import demo_device
    from types import SimpleNamespace
    calls = []

    async def fake_originate():
        calls.append("originated")
        return {"status": "requested", "message": "synthetic SIP call requested"}

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(demo_device_token="demo-test-token"))
    monkeypatch.setattr(demo_device, "_originate_demo_call", fake_originate)
    auth = {"Authorization": "Bearer demo-test-token"}
    client.post("/api/v1/demo-device/publish", headers=auth, json={"type": "call", "trigger_sip": False})
    assert calls == []
    result = client.post("/api/v1/demo-device/publish", headers=auth,
                         json={"type": "call", "trigger_sip": True})
    assert calls == ["originated"]
    assert result.json()["sip"]["status"] == "requested"

def test_idle_registered_softphone_is_detected_from_endpoint_state(monkeypatch):
    import asyncio
    from app.api import demo_device
    from types import SimpleNamespace

    class Response:
        status_code = 200

        def json(self):
            return {"state": "online", "channel_ids": []}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return Response()

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(
        asterisk_ari_url="http://asterisk:8088/ari",
        asterisk_ari_username="demo-user",
        asterisk_ari_password="demo-password",
    ))
    monkeypatch.setattr(demo_device.httpx, "AsyncClient", Client)

    assert asyncio.run(demo_device._endpoint_registered()) is True


def test_asterisk_ari_uses_only_fixed_local_endpoint(monkeypatch):
    import asyncio
    from app.api import demo_device
    from types import SimpleNamespace
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            captured["auth"] = kwargs["auth"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, params):
            captured["url"] = url
            captured["params"] = params
            return Response()

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(
        asterisk_ari_url="http://asterisk:8088/ari/",
        asterisk_ari_username="demo-user",
        asterisk_ari_password="demo-password",
    ))
    monkeypatch.setattr(demo_device.httpx, "AsyncClient", Client)

    async def registered():
        return True

    monkeypatch.setattr(demo_device, "_endpoint_registered", registered)
    result = asyncio.run(demo_device._originate_demo_call())
    assert result["status"] == "requested"
    assert result["channel_id"] == captured["params"]["channelId"]
    assert captured["url"] == "http://asterisk:8088/ari/channels"
    assert captured["params"]["endpoint"] == "PJSIP/200"
    assert captured["params"]["context"] == "momo-demo-outbound"
    assert captured["params"]["timeout"] == demo_device.DEMO_SIP_RING_SECONDS == 60


def test_dashboard_and_sip_call_timeouts_are_explicit():
    from app.api import demo_device
    root = Path(__file__).resolve().parents[2]
    dashboard = (root / "frontend" / "app.py").read_text(encoding="utf-8")
    dialplan = (root / "demo" / "asterisk" / "extensions.conf").read_text(encoding="utf-8")
    match = re.search(r"CALL_RING_MIN_SECONDS\s*=\s*([0-9.]+)", dashboard)
    assert match and float(match.group(1)) == 3
    assert demo_device.DEMO_SIP_RING_SECONDS == 60
    assert 'Set(TIMEOUT(absolute)=300)' in dialplan
    assert 'Wait(300)' in dialplan


def test_sip_call_is_hung_up_on_intervention(monkeypatch):
    from app.api import demo_device
    from types import SimpleNamespace
    deleted = []

    class Response:
        status_code = 204
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def delete(self, url):
            deleted.append(url)
            return Response()

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(
        demo_device_token="demo-test-token", asterisk_ari_url="http://asterisk:8088/ari",
        asterisk_ari_username="demo-user", asterisk_ari_password="demo-password",
    ))
    monkeypatch.setattr(demo_device.httpx, "AsyncClient", Client)
    monkeypatch.setattr(demo_device, "_ACTIVE_SIP_CHANNEL_ID", "momo-demo-fixed1234")
    response = client.post(
        "/api/v1/demo-device/publish",
        headers={"Authorization": "Bearer demo-test-token"},
        json={
            "type": "warning", "scenario": "GH01", "warning": "Synthetic fraud warning",
            "sip_hangup": True, "interrupt_now": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["sip"]["status"] == "hangup_requested"
    assert deleted == ["http://asterisk:8088/ari/channels/momo-demo-fixed1234"]
    assert demo_device._ACTIVE_SIP_CHANNEL_ID is None


def test_reported_high_risk_call_interrupts_before_answer(monkeypatch):
    from app.api import demo_device
    from types import SimpleNamespace
    hangups = []
    queued = []

    async def hangup():
        hangups.append(True)
        demo_device._ACTIVE_SIP_CHANNEL_ID = None
        return {"status": "hangup_requested"}

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(demo_device_token="demo-test-token"))
    monkeypatch.setattr(demo_device, "_ACTIVE_SIP_CHANNEL_ID", "momo-demo-known123")
    monkeypatch.setattr(demo_device, "_hangup_demo_call", hangup)
    monkeypatch.setattr(demo_device, "_schedule_warning_after_answer", lambda payload: queued.append(payload))
    async def not_registered():
        return False

    monkeypatch.setattr(demo_device, "_endpoint_registered", not_registered)

    response = client.post(
        "/api/v1/demo-device/publish",
        headers={"Authorization": "Bearer demo-test-token"},
        json={"type": "warning", "sip_hangup": True, "interrupt_now": True},
    )

    assert response.status_code == 200
    assert response.json()["sip"]["status"] == "hangup_requested"
    assert hangups == [True]
    assert queued == []


def test_sms_warning_does_not_disconnect_an_active_call(monkeypatch):
    from app.api import demo_device
    from types import SimpleNamespace
    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(demo_device_token="demo-test-token"))
    monkeypatch.setattr(demo_device, "_ACTIVE_SIP_CHANNEL_ID", "momo-demo-active123")

    async def not_registered():
        return False

    monkeypatch.setattr(demo_device, "_endpoint_registered", not_registered)

    response = client.post(
        "/api/v1/demo-device/publish",
        headers={"Authorization": "Bearer demo-test-token"},
        json={"type": "warning", "sip_hangup": False, "warning_english": "Check this SMS"},
    )

    assert response.status_code == 200
    assert demo_device._ACTIVE_SIP_CHANNEL_ID == "momo-demo-active123"


def test_unanswered_high_risk_call_reports_timeout_not_intervention(monkeypatch):
    import asyncio
    from app.api import demo_device
    from types import SimpleNamespace

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(
        asterisk_ari_url="http://asterisk:8088/ari",
        asterisk_ari_username="demo-user",
        asterisk_ari_password="demo-password",
    ))
    monkeypatch.setattr(demo_device, "_ACTIVE_SIP_CHANNEL_ID", "momo-demo-noanswer")

    async def not_registered():
        return False

    monkeypatch.setattr(demo_device, "_endpoint_registered", not_registered)
    before = demo_device._NEXT_ID
    result = asyncio.run(demo_device._deliver_warning_after_answer(
        "momo-demo-noanswer",
        {
            "type": "warning",
            "scenario": "Live Signal Lab",
            "event_key": "warning-1",
            "call_event_key": "call-1",
            "warning_english": "Pause and verify.",
        },
        timeout=0,
    ))

    _cursor, published = demo_device._events_after(before - 1)
    assert result["answered"] is False
    assert published[0]["event"]["status"] == "Call ended before pickup"
    assert published[1]["event"]["sip_hangup"] is False


def test_sip_failure_emits_browser_ringtone_fallback(monkeypatch):
    import asyncio
    from app.api import demo_device
    from types import SimpleNamespace

    async def unavailable():
        return {"status": "not_configured", "message": "SIP is unavailable."}

    monkeypatch.setattr(demo_device, "settings", SimpleNamespace(demo_device_token="demo-test-token"))
    monkeypatch.setattr(demo_device, "_originate_demo_call", unavailable)
    before = demo_device._NEXT_ID
    response = client.post(
        "/api/v1/demo-device/publish",
        headers={"Authorization": "Bearer demo-test-token"},
        json={"type": "call", "scenario": "GH01", "event_key": "gh01|call|a", "trigger_sip": True},
    )
    assert response.status_code == 200
    assert response.json()["sip"]["status"] == "not_configured"
    _cursor, events = demo_device._events_after(before - 1)
    published = [item["event"] for item in events]
    assert published[-2]["sip_managed"] is True
    assert published[-1]["force_browser_ring"] is True
    assert published[-1]["event_key"] == published[-2]["event_key"]

def test_assess_endpoint_gh01():
    fixture = json.loads((FIXTURES_DIR / "gh01_fake_credit.json").read_text())
    global_window.reset()
    body = None
    for step in fixture["steps"]:
        r = client.post("/api/v1/assess", json={"event": step["event"]})
        assert r.status_code == 200
        body = r.json()
    assert body["risk_tier"] == "HIGH"
    assert body["recommended_action"] == "SIMULATED_HOLD"


def test_transaction_amount_above_synthetic_ceiling_is_rejected():
    response = client.post("/api/v1/assess", json={"event": {
        "event_type": "transaction",
        "msisdn": "+233000000000",
        "transaction_type": "P2P_SEND",
        "amount": 100001,
        "ledger_verified": False,
        "timestamp": "2026-11-19T00:00:00Z",
    }})
    assert response.status_code == 400


def test_transcription_requires_configured_gemini(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=False))
    response = client.post("/api/v1/transcribe", content=b"", headers={"Content-Type": "audio/wav"})
    assert response.status_code == 503


def test_transcription_accepts_only_a_wav_draft_and_does_not_assess_audio(monkeypatch):
    import asyncio
    from app.api import routes
    from types import SimpleNamespace
    captured = {}

    async def fake_transcribe(audio_bytes, language_hint):
        captured["audio"] = audio_bytes
        captured["language"] = language_hint
        return {"transcript": "fictional words", "uncertain": False, "note": "Review draft."}

    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True))
    monkeypatch.setattr(routes, "transcribe_wav", fake_transcribe)
    wav = b"RIFF" + (4).to_bytes(4, "little") + b"WAVE" + b"test"
    response = client.post(
        "/api/v1/transcribe?language_hint=English",
        content=wav,
        headers={"Content-Type": "audio/wav"},
    )
    assert response.status_code == 200
    assert response.json()["transcript"] == "fictional words"
    assert captured == {"audio": wav, "language": "English"}
    assert "risk_score" not in response.json()


def test_transcription_rejects_non_wav_and_malformed_wav(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True))
    wrong_type = client.post("/api/v1/transcribe", content=b"audio", headers={"Content-Type": "text/plain"})
    assert wrong_type.status_code == 415
    malformed = client.post("/api/v1/transcribe", content=b"not a wav file", headers={"Content-Type": "audio/wav"})
    assert malformed.status_code == 415


def test_transcription_rejects_payload_over_eight_mb(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True))
    response = client.post(
        "/api/v1/transcribe",
        content=b"RIFF" + b"x" * (8 * 1024 * 1024),
        headers={"Content-Type": "audio/wav"},
    )
    assert response.status_code == 413


def test_case_reference_response_is_advisory_and_has_no_decision_fields(monkeypatch):
    from app.api import routes
    from types import SimpleNamespace
    monkeypatch.setattr(routes, "settings", SimpleNamespace(gemini_enabled=True))

    async def fake_reference(text):
        return {"status": "possible_match", "matched_case_ids": ["SYN-001"], "advisory_only": True}

    monkeypatch.setattr(routes, "run_case_reference", fake_reference)
    response = client.post("/api/v1/case-reference", json={"text": "fictional support asks for code"})
    assert response.status_code == 200
    assert response.json()["advisory_only"] is True
    assert "risk_score" not in response.json()
    assert "recommended_action" not in response.json()


def test_provider_listener_is_not_registered():
    paths = set(app.openapi()["paths"])
    assert not any("provider" in path.casefold() or "feed" in path.casefold() for path in paths)


def test_credential_warning_is_not_a_credential_request():
    from app.engine.rules import _requests_secret
    assert not _requests_secret("We will never ask for your OTP. Do not give your PIN to callers.")
    assert _requests_secret("Send me your OTP now.")
    assert _requests_secret("Never share your PIN. Read me your OTP now.")


def test_transcription_redacts_generic_numeric_code_and_phone_values():
    from app.ai.transcription import _redact_likely_sensitive_values
    redacted = _redact_likely_sensitive_values("Your code is 123456. Call 0241234567.")
    assert "123456" not in redacted
    assert "0241234567" not in redacted
    assert "[CODE]" in redacted
    assert "[PHONE]" in redacted


def test_demo_handset_does_not_allow_unreviewed_warning_audio_assets():
    from app.api import demo_device
    assert not any(name.startswith("warning_") for name in demo_device._AUDIO_ASSETS)
