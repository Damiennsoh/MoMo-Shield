import re
from typing import List, Tuple

from app.models.schemas import EventType, SandboxEvent

_SECRET_RE = re.compile(r"\b(pin|otp|password|passcode|secret|cvv|card number)\b", re.I)
_REQUEST_RE = re.compile(
    r"\b(send|share|tell|give|provide|reply with|enter|confirm)\b[^.]{0,80}\b(pin|otp|password|passcode|secret|code)\b",
    re.I,
)
_AUTHORITY_RE = re.compile(
    r"\b(mtn|vodafone|telecel|airteltigo|bank|fraud department|security team|agent|office|head office|official|verified)\b",
    re.I,
)
_URGENCY_RE = re.compile(
    r"\b(urgent|immediately|right now|expires?|suspended|blocked|locked|terminate[sd]?|before it expires|be fast|act now|limited time)\b",
    re.I,
)
_PRIZE_RE = re.compile(r"\b(prize|winner|congratulations|reward|lottery|lucky)\b", re.I)

_CONTENT_TYPES = {EventType.SMS, EventType.VOICE, EventType.USSD}


def _text(event: SandboxEvent) -> str:
    payload = event.payload or {}
    parts = [
        str(payload.get("text") or ""),
        str(payload.get("transcript") or ""),
        str(payload.get("ussd_input") or ""),
        str(payload.get("message") or ""),
    ]
    return " ".join(p for p in parts if p)


def check_content_credential_request(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """Direct request for a secret (PIN/OTP/password) — strongest single signal."""
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if _SECRET_RE.search(text) and _REQUEST_RE.search(text):
        return 45, "Credential request: message asks the subscriber for a secret"
    if _SECRET_RE.search(text) and event.event_type == EventType.USSD:
        return 30, "USSD session solicits a secret value"
    return 0, ""


def check_content_impersonation(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if _AUTHORITY_RE.search(text) and _SECRET_RE.search(text):
        return 15, "Operator/authority impersonation combined with secret solicitation"
    if _AUTHORITY_RE.search(text) and _URGENCY_RE.search(text):
        return 15, "Authority impersonation with urgency pressure"
    return 0, ""


def check_content_urgency(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if _URGENCY_RE.search(text) and (_SECRET_RE.search(text) or _PRIZE_RE.search(text)):
        return 15, "Urgency/loss-aversion pressure combined with credential or prize bait"
    return 0, ""


def check_gh01_fake_credit(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if event.payload.get('type') == 'transfer_out' and event.payload.get('amount', 0) > 100:
        recent_credits = [e for e in history if e.get('payload', {}).get('type') == 'sms_credit' and not e.get('payload', {}).get('ledger_verified', True)]
        if recent_credits:
            return 40, "GH01: Unverified SMS credit followed by outbound transfer"
    return 0, ""


def check_gh18_device_takeover(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if event.payload.get('type') == 'new_device_binding':
        return 50, "GH18: New device binding detected"
    return 0, ""


def check_velocity(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if len(history) > 5:
        return 20, "High velocity: Multiple events in short window"
    return 0, ""


RULES = [
    check_content_credential_request,
    check_content_impersonation,
    check_content_urgency,
    check_gh01_fake_credit,
    check_gh18_device_takeover,
    check_velocity,
]
