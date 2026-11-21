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


# ---------------------------------------------------------------------------
# GH15 — Phishing link in SMS (credential harvesting via link)
# ---------------------------------------------------------------------------
_LINK_RE = re.compile(r"https?://\S+", re.I)
_LINK_CRED_RE = re.compile(
    r"\b(verify|login|confirm|update|click|tap|visit|enter)\b", re.I
)

def check_gh15_phishing_link(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """GH15: Suspicious URL in SMS combined with credential/action prompt."""
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if _LINK_RE.search(text) and (_SECRET_RE.search(text) or _LINK_CRED_RE.search(text)):
        return 45, "GH15: Phishing link detected — URL combined with credential/action prompt"
    return 0, ""


# ---------------------------------------------------------------------------
# GH19 — Nuisance call preconditioning → authority "helper"
# ---------------------------------------------------------------------------
_HELPER_RE = re.compile(
    r"\b(help you|on your behalf|calling to assist|resolve your issue|sent by mtn|"
    r"official representative|customer care|case number|ticket number)\b",
    re.I,
)

def check_gh19_nuisance_preconditioning(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """GH19: Multiple short prior calls + current authority helper narrative."""
    text = _text(event)
    short_calls = [
        e for e in history
        if e.get("event_type") == "voice"
        and (e.get("payload", {}).get("duration_seconds") or 999) < 90
    ]
    if len(short_calls) >= 2 and _HELPER_RE.search(text) and _AUTHORITY_RE.search(text):
        return 40, "GH19: Nuisance preconditioning — multiple short calls followed by authority helper"
    return 0, ""


# ---------------------------------------------------------------------------
# Composite — Active voice call + simultaneous USSD session (highest value)
# ---------------------------------------------------------------------------
def check_call_ussd_cooccurrence(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """Composite: Subscriber on voice call while starting a USSD session — strongest fraud signal."""
    if event.event_type == EventType.USSD:
        recent_voice = [
            e for e in history
            if e.get("event_type") == "voice"
            and (e.get("payload", {}).get("status") in ("active", "ringing", "answered"))
        ]
        if recent_voice:
            return 50, "Composite: Active voice call + concurrent USSD session — primary social-engineering signal"
    if event.event_type == EventType.VOICE:
        recent_ussd = [
            e for e in history
            if e.get("event_type") == "ussd"
            and (e.get("payload", {}).get("status") in ("active", "in_progress"))
        ]
        if recent_ussd:
            return 50, "Composite: Active USSD session + concurrent voice call — primary social-engineering signal"
    return 0, ""


# ---------------------------------------------------------------------------
# Task Momentum — Psychological lever pushing subscriber to complete an action
# ---------------------------------------------------------------------------
_MOMENTUM_RE = re.compile(
    r"\b(complete your|finish the|finalise|just one more step|almost done|"
    r"to complete your|to finish your|your subscription|your verification|"
    r"your registration|your activation|your upgrade)\b",
    re.I,
)

def check_task_momentum(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """Task momentum lever: pressure to complete an action combined with credential request."""
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if _MOMENTUM_RE.search(text) and (_SECRET_RE.search(text) or _URGENCY_RE.search(text)):
        return 15, "Task momentum lever: completion pressure combined with secret/urgency"
    return 0, ""


# ---------------------------------------------------------------------------
# GH02 — Money mule (large credit in → immediate full transfer out)
# ---------------------------------------------------------------------------
def check_money_mule(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """GH02: Receives large credit then immediately transfers equivalent or more out."""
    if event.payload.get("type") == "transfer_out":
        amount_out = event.payload.get("amount", 0)
        if amount_out < 200:
            return 0, ""
        recent_credits = [
            e for e in history
            if e.get("payload", {}).get("type") in ("credit", "transfer_in", "sms_credit")
            and e.get("payload", {}).get("amount", 0) >= amount_out * 0.8
        ]
        if recent_credits:
            return 40, "GH02: Money mule pattern — large inbound credit followed by immediate equivalent transfer out"
    return 0, ""


# ---------------------------------------------------------------------------
# GH22 — Structuring (multiple sub-limit transfers to avoid detection)
# ---------------------------------------------------------------------------
_STRUCTURING_MIN = 850
_STRUCTURING_MAX = 999

def check_structuring(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """GH22: Multiple transfers just below reporting threshold (900-999 GHS)."""
    if event.payload.get("type") != "transfer_out":
        return 0, ""
    amount = event.payload.get("amount", 0)
    if _STRUCTURING_MIN <= amount <= _STRUCTURING_MAX:
        prior_structured = [
            e for e in history
            if e.get("payload", {}).get("type") == "transfer_out"
            and _STRUCTURING_MIN <= e.get("payload", {}).get("amount", 0) <= _STRUCTURING_MAX
        ]
        if len(prior_structured) >= 2:
            return 40, f"GH22: Structuring detected — {len(prior_structured)+1} sub-limit transfers (850–999 GHS)"
    return 0, ""


# ---------------------------------------------------------------------------
# GH16 — Approve-to-receive trick
# ---------------------------------------------------------------------------
_APPROVE_RE = re.compile(r"\b(approve|confirm|authorise|authorize|accept|click ok|press ok)\b", re.I)
_RECEIVE_RE = re.compile(r"\b(receive|reversal|refund|credit|money back|cashback|reward|payment)\b", re.I)

def check_approve_to_receive(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """GH16: 'Approve/confirm this to receive a credit/reversal' trick."""
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if _APPROVE_RE.search(text) and _RECEIVE_RE.search(text):
        return 40, "GH16: Approve-to-receive trick — subscriber asked to approve an action to receive a credit"
    return 0, ""


# ---------------------------------------------------------------------------
# GH19B — Relative-on-new-number social engineering
# ---------------------------------------------------------------------------
_RELATIVE_RE = re.compile(
    r"\b(mum|mummy|mom|dad|daddy|father|mother|sister|brother|uncle|auntie|aunt|"
    r"cousin|friend|son|daughter|wife|husband)\b",
    re.I,
)
_NEW_NUMBER_RE = re.compile(r"\b(new number|new phone|lost my phone|changed my number|new sim)\b", re.I)
_DISTRESS_RE = re.compile(r"\b(accident|hospital|emergency|urgent|help me|please help|stranded|stuck)\b", re.I)

def check_relative_new_number(event: SandboxEvent, history: List) -> Tuple[int, str]:
    """GH19B: Social engineering via distressed relative on a new number."""
    if event.event_type not in _CONTENT_TYPES:
        return 0, ""
    text = _text(event)
    if (_RELATIVE_RE.search(text) and _NEW_NUMBER_RE.search(text)) or \
       (_RELATIVE_RE.search(text) and _DISTRESS_RE.search(text) and _SECRET_RE.search(text)):
        return 25, "GH19B: Relative-on-new-number social engineering — distress narrative from unfamiliar number"
    return 0, ""


RULES = [
    check_content_credential_request,
    check_content_impersonation,
    check_content_urgency,
    check_gh01_fake_credit,
    check_gh18_device_takeover,
    check_velocity,
    # --- New rules (added for startup-grade coverage) ---
    check_gh15_phishing_link,
    check_gh19_nuisance_preconditioning,
    check_call_ussd_cooccurrence,
    check_task_momentum,
    check_money_mule,
    check_structuring,
    check_approve_to_receive,
    check_relative_new_number,
]
