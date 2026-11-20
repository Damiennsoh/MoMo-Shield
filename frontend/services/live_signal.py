"""Safe construction helpers for one-off synthetic MoMo Shield assessments."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

MAX_TEXT_LENGTH = 5000
LANGUAGE_OPTIONS = (
    "English",
    "Twi/Akan (evaluation only)",
    "Ghanaian Pidgin (evaluation only)",
    "Mixed / unsure",
)

PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+233|0)(?:[\s().-]?\d){9}(?!\w)")
CODE_VALUE_PATTERN = re.compile(
    r"\b(?:pin|otp|code|one[- ]time\s+(?:pin|password|code)|verification code|security code)\b"
    r"\b\s*(?:is|:|=)?\s*(?:\d[\s-]*){4,8}(?!\d)",
    re.IGNORECASE,
)

EXAMPLE_MESSAGES = {
    "Benign synthetic message": (
        "Your GHS 20 data bundle purchase is complete. Thank you for using MoMo."
    ),
    "Ambiguous synthetic message": (
        "We noticed a payment issue. Please contact customer care when convenient."
    ),
    "Suspicious synthetic message": (
        "This is MoMo support. Your wallet may be blocked. Please read me the one-time code "
        "to secure the account."
    ),
}


def validate_synthetic_text(text: str) -> list[str]:
    """Return blockers for empty, oversized, or likely sensitive demo text."""
    value = str(text or "").strip()
    problems = []
    if not value:
        problems.append("Enter a synthetic message or transcript first.")
    if len(value) > MAX_TEXT_LENGTH:
        problems.append(f"Keep the text to {MAX_TEXT_LENGTH} characters or fewer.")
    if PHONE_PATTERN.search(value):
        problems.append("A phone number may be present. Replace it with [PHONE] before sending.")
    if CODE_VALUE_PATTERN.search(value):
        problems.append("A numeric PIN/OTP/code may be present. Replace it with [CODE] before sending.")
    return problems


def new_synthetic_identity() -> tuple[str, str]:
    """Create an impossible-number-namespace identity for process-local scoring."""
    suffix = f"{secrets.randbelow(1_000_000):06d}"
    return f"+233000{suffix}", f"SYN-{secrets.token_hex(3).upper()}"


def _base_event(event_type: str) -> dict[str, Any]:
    msisdn, _label = new_synthetic_identity()
    return {
        "event_id": f"demo-{uuid.uuid4().hex[:12]}",
        "msisdn": msisdn,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_communication_event(
    text: str,
    channel: str,
    language_hint: str = "English",
    input_source: str = "typed",
    counterparty_msisdn: str = "",
) -> dict[str, Any]:
    problems = validate_synthetic_text(text)
    if problems:
        raise ValueError(" ".join(problems))
    channel_value = str(channel).upper()
    if channel_value not in {"SMS", "VOICE"}:
        raise ValueError("Channel must be SMS or VOICE.")
    allowed_languages = {option for option in LANGUAGE_OPTIONS}
    if language_hint not in allowed_languages:
        raise ValueError("Choose one of the listed language/evaluation options.")
    if input_source not in {"typed", "transcribed_then_edited"}:
        raise ValueError("Input source must be typed or transcribed and edited.")
    event = _base_event("communication")
    event.update({
        "channel": channel_value,
        "text_or_transcript": str(text).strip(),
        "language_hint": language_hint,
        "input_source": input_source,
    })
    if counterparty_msisdn:
        event["counterparty_msisdn"] = str(counterparty_msisdn).strip()
    return event


def build_transaction_event(
    transaction_type: str,
    amount: float,
    ledger_verified: bool,
) -> dict[str, Any]:
    allowed = {"P2P_SEND", "CREDIT", "XTRACASH_LOAN", "USSD_SESSION"}
    if transaction_type not in allowed:
        raise ValueError("Choose a supported synthetic transaction type.")
    value = float(amount)
    if not 0 <= value <= 100000:
        raise ValueError("Synthetic amount must be between GHS 0 and GHS 100,000.")
    event = _base_event("transaction")
    event.update({
        "transaction_type": transaction_type,
        "amount": value,
        "ledger_verified": bool(ledger_verified),
        "ussd_session_active": False,
        "counterparty_msisdn": None,
    })
    return event


def build_device_event(action: str, preceded_by_otp_activity: bool) -> dict[str, Any]:
    allowed = {"APP_INSTALL", "NEW_DEVICE_LOGIN", "SIM_SWAP", "WALLET_ENROLMENT"}
    if action not in allowed:
        raise ValueError("Choose a supported synthetic device action.")
    event = _base_event("device_binding")
    event.update({
        "action": action,
        "new_imei": f"SYNTHETIC-DEVICE-{secrets.token_hex(3).upper()}",
        "preceded_by_otp_activity": bool(preceded_by_otp_activity),
    })
    return event


def identity_label_for_event(event: dict[str, Any]) -> str:
    """Display a non-phone alias, never the synthetic number used internally."""
    return "SYN-" + str(event.get("event_id", "demo"))[-6:].upper()
