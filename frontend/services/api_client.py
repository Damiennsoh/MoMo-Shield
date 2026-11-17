# Backend client with graceful offline fallback.
#
# Talks to the FastAPI engine (backend). ANY failure — connection
# refused, timeout (>8s), 4xx/5xx — falls back to the built-in deterministic
# rule engine, so the demo never dies on hackathon Wi-Fi.
#
# Wire contract:
#   POST {backend}/api/v1/assess   body {"event": {...}, "context": {...}}
#   POST {backend}/api/v1/reset    clears per-MSIDN window + risk scores

import uuid
from datetime import datetime

import httpx

from services.local_engine import assess_local

TIMEOUT_SECONDS = 8.0

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
        httpx.post(backend_url.rstrip("/") + "/api/v1/reset", timeout=1.0)
    except Exception:
        pass


def assess_event(event: dict, backend_url: str, accumulator: dict):
    # Returns (assessment_dict, source) where source is 'backend' or 'local'.
    # A refused connection means the engine is down; remember that for the
    # rest of this scenario so each event doesn't stall on a dead socket.
    prepared_event = _prepare_event(event)
    if accumulator.get("_backend_unreachable"):
        return assess_local(prepared_event, accumulator), "local"
    try:
        resp = httpx.post(
            backend_url.rstrip("/") + "/api/v1/assess",
            json={"event": prepared_event},
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = _normalize(resp.json())
        data["source"] = "backend"
        return data, "backend"
    except httpx.ConnectError:
        accumulator["_backend_unreachable"] = True
        return assess_local(prepared_event, accumulator), "local"
    except Exception:
        return assess_local(prepared_event, accumulator), "local"
