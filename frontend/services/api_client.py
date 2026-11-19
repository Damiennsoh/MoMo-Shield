# Backend client with graceful offline fallback.
#
# Talks to the FastAPI engine (backend). ANY failure — connection
# refused, timeout (>9s), 4xx/5xx — falls back to the built-in deterministic
# rule engine, so the demo never dies on hackathon Wi-Fi.
#
# Wire contract:
#   POST {backend}/api/v1/assess   body {"event": {...}, "context": {...}}
#   POST {backend}/api/v1/reset    clears per-MSIDN window + risk scores

import hashlib
import uuid
from datetime import datetime

import httpx

from services.local_engine import assess_local

TIMEOUT_SECONDS = 9.0
DEMO_DEVICE_TIMEOUT_SECONDS = 4.0


def demo_device_event_key(scenario: str, kind: str, identity: str = "") -> str:
    """Return a bounded stable key for a simulated handset card/update slot."""
    digest = hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:16]
    scenario_part = "-".join(str(scenario).casefold().split())[:96]
    kind_part = "-".join(str(kind).casefold().split())[:24]
    return f"{scenario_part}|{kind_part}|{digest}"

# Backend base URLs that refused a connection. A refused socket costs seconds
# on some networks, so once one call proves the engine is down we stop probing
# until reset_backend() sees it come back (it runs at every scenario start).
_UNREACHABLE_URLS = set()


def _base(backend_url: str) -> str:
    return backend_url.rstrip("/")


def _mark_unreachable(backend_url: str) -> None:
    _UNREACHABLE_URLS.add(_base(backend_url))


def _is_unreachable(backend_url: str) -> bool:
    return _base(backend_url) in _UNREACHABLE_URLS


def publish_demo_device_event(backend_url: str, token: str, event: dict) -> dict:
    """Mirror a synthetic fixture event to the opt-in second-device page."""
    if not token:
        return {"status": "disabled"}
    if _is_unreachable(backend_url):
        return {"status": "unreachable"}
    try:
        response = httpx.post(
            _base(backend_url) + "/api/v1/demo-device/publish",
            json=event,
            headers={"Authorization": "Bearer " + token},
            timeout=DEMO_DEVICE_TIMEOUT_SECONDS,
        )
    except httpx.ConnectError:
        _mark_unreachable(backend_url)
        return {"status": "unreachable"}
    response.raise_for_status()
    return response.json()


def check_gemini(backend_url: str) -> dict:
    """Ask the backend to make a real Gemini request using its configured key."""
    response = httpx.post(
        _base(backend_url) + "/api/v1/gemini/healthcheck",
        timeout=TIMEOUT_SECONDS,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"message": response.text or "Backend returned an unreadable response."}
    if response.is_error:
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            message = detail.get("message", str(detail))
        else:
            message = str(detail)
        raise RuntimeError(message)
    return data


def transcribe_audio(backend_url: str, audio_bytes: bytes, language_hint: str = "English") -> dict:
    """Send consented synthetic WAV for a draft transcript; no assessment is made here."""
    response = httpx.post(
        _base(backend_url) + "/api/v1/transcribe",
        params={"language_hint": language_hint},
        content=audio_bytes,
        headers={"Content-Type": "audio/wav"},
        timeout=TIMEOUT_SECONDS * 2,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text or "Backend returned an unreadable response."}
    if response.is_error:
        detail = data.get("detail", data)
        raise RuntimeError(str(detail))
    if not isinstance(data.get("transcript"), str):
        raise RuntimeError("Backend returned an invalid transcript response.")
    return data


def find_case_reference(backend_url: str, text: str, language_hint: str = "English") -> dict:
    """Request a separate advisory retrieval result for synthetic text only."""
    response = httpx.post(
        _base(backend_url) + "/api/v1/case-reference",
        json={"text": text, "language_hint": language_hint},
        timeout=TIMEOUT_SECONDS * 3,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text or "Backend returned an unreadable response."}
    if response.is_error:
        raise RuntimeError(str(data.get("detail", data)))
    if not isinstance(data.get("retrieved_cases"), list):
        raise RuntimeError("Backend returned an invalid case-reference response.")
    return data


# Backend action names -> labels the FraudOps panel knows how to render.
_ACTION_MAP = {
    "SOFT_WARNING": "COOLING_OFF_PROMPT",
}


def _prepare_event(event: dict) -> dict:
    """Fill fields the backend models require but sandbox fixtures omit."""
    ev = dict(event)
    ev.setdefault("event_id", f"fe-{uuid.uuid4().hex[:10]}")
    ev.setdefault("timestamp", datetime.now().isoformat())
    if ev.get("event_type") == "transaction":
        ev.setdefault("ledger_verified", True)
    return ev


def _normalize(data: dict) -> dict:
    """Map the backend AssessResponse onto the shape the panel expects."""
    data["recommended_action"] = _ACTION_MAP.get(
        data.get("recommended_action"), data.get("recommended_action"))
    data["intent"] = data.pop("llm_extracted_intent", None)
    rules = data.get("triggered_rules") or []
    data["triggered_rules"] = [
        r.get("description", str(r)) if isinstance(r, dict) else str(r)
        for r in rules
    ]
    return data


def reset_backend(backend_url: str) -> None:
    """Best-effort reset of backend session state before a scenario replay."""
    try:
        resp = httpx.post(_base(backend_url) + "/api/v1/reset", timeout=1.0)
        resp.raise_for_status()
        _UNREACHABLE_URLS.discard(_base(backend_url))
    except httpx.ConnectError:
        _mark_unreachable(backend_url)
    except Exception:
        pass


def assess_event(event: dict, backend_url: str, accumulator: dict):
    # Returns (assessment_dict, source) where source is 'backend' or 'local'.
    # A refused connection means the engine is down; remember that for the
    # rest of this scenario so each event doesn't stall on a dead socket.
    prepared_event = _prepare_event(event)
    if accumulator.get("_backend_unreachable") or _is_unreachable(backend_url):
        accumulator["_backend_unreachable"] = True
        return assess_local(prepared_event, accumulator), "local"
    try:
        resp = httpx.post(
            _base(backend_url) + "/api/v1/assess",
            json={"event": prepared_event},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = _normalize(resp.json())
        data["source"] = "backend"
        return data, "backend"
    except httpx.ConnectError:
        _mark_unreachable(backend_url)
        accumulator["_backend_unreachable"] = True
        return assess_local(prepared_event, accumulator), "local"
    except Exception:
        return assess_local(prepared_event, accumulator), "local"
