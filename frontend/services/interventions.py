"""Plain-language, context-aware victim guidance for the synthetic dashboard."""

from __future__ import annotations

from services.credential_requests import has_explicit_credential_request


def _value(event, key, default=None):
    if isinstance(event, dict):
        return event.get(key, default)
    return getattr(event, key, default)


def _event_text(event) -> str:
    value = _value(event, "text_or_transcript", "") or ""
    return str(value).casefold()


def _rules(assessment: dict) -> list[str]:
    return [str(rule) for rule in (assessment.get("triggered_rules") or [])]


def build_intervention(event, assessment: dict, prior_events=()) -> dict:
    """Return an English safety message whose category follows the available evidence."""
    current = _event_text(event)
    prior_text = " ".join(_event_text(item) for item in prior_events)
    combined = f"{prior_text}. {current}".casefold()
    rules = " ".join(_rules(assessment)).casefold()
    event_type = str(_value(event, "event_type", "")).casefold()
    channel = str(_value(event, "channel", "")).casefold()
    tier = str(assessment.get("risk_tier", "LOW")).upper()

    explicit_credential_request = has_explicit_credential_request(combined)
    link_signal = any(term in combined for term in ("http://", "https://", "www.", ".com", ".net", "link"))
    reversal_signal = any(term in combined for term in ("reverse", "reversal", "refund", "send it back", "send back", "mistaken transfer", "receipt"))

    if "gh19: multiple nuisance calls" in rules and not explicit_credential_request:
        category = "repeated_calls"
    elif "gh19:" in rules and explicit_credential_request:
        category = "call_fatigue_credential_request"
    elif reversal_signal or "gh02:" in rules:
        category = "reversal_or_refund"
    elif link_signal and explicit_credential_request:
        category = "suspicious_link"
    elif event_type == "device_binding" or "new device" in rules or "sim_swap" in combined:
        category = "device_or_sim_change"
    elif explicit_credential_request or "credential-harvesting" in rules:
        category = "credential_request"
    elif any(term in combined for term in ("blocked", "unusual activity", "urgent", "secure your account", "support")) and tier != "LOW":
        category = "impersonation_or_pressure"
    elif tier == "LOW":
        category = "no_high_risk_signal"
    elif event_type == "transaction" or any(term in rules for term in ("transfer", "loan", "ledger")):
        category = "transaction_review"
    else:
        category = "insufficient_context"

    messages = {
        "credential_request": (
            "Do not share a PIN, OTP, or verification code. Stop responding and verify through the official app or a known support contact."
        ),
        "call_fatigue_credential_request": (
            "Do not share a code with a caller offering to help. A call burst is not proof by itself; verify any helper independently through official support."
        ),
        "reversal_or_refund": (
            "Do not send money back based only on a caller, SMS, or screenshot. Check the transaction in the official MoMo history and verify with the provider."
        ),
        "suspicious_link": (
            "Do not open the link or enter wallet details there. Open the provider’s official app directly or use a known support contact."
        ),
        "device_or_sim_change": (
            "Do not approve an unexpected new-device or SIM change. Use the official app or contact provider support to secure access."
        ),
        "impersonation_or_pressure": (
            "Do not act under threats or urgency. Do not share codes or PINs; verify the claim through an official support channel."
        ),
        "repeated_calls": (
            "Repeated calls alone are not proof of fraud. Avoid sharing information with unsolicited callers and verify any request independently."
        ),
        "transaction_review": (
            "Pause before sending or approving money. Check the amount and recipient in the official app, and contact support if the activity is unexpected."
        ),
        "no_high_risk_signal": (
            "No high-risk signal was identified in this synthetic test. That is not proof that a message or transaction is safe."
        ),
        "insufficient_context": (
            "There is not enough context to confirm fraud. If money, account access, or a code is involved, pause and verify through the official app or known support contact."
        ),
    }
    titles = {
        "credential_request": "Possible credential request — verify safely",
        "call_fatigue_credential_request": "Unsolicited caller requesting a code",
        "reversal_or_refund": "Possible refund or reversal pressure",
        "suspicious_link": "Suspicious link — do not enter details",
        "device_or_sim_change": "Unexpected device or SIM change",
        "impersonation_or_pressure": "Urgent support claim — verify independently",
        "repeated_calls": "Repeated calls — not proof of fraud",
        "transaction_review": "Transaction needs independent review",
        "no_high_risk_signal": "No high-risk signal in this test",
        "insufficient_context": "More context is needed",
    }
    severity = "urgent" if tier == "HIGH" else "caution" if tier == "MEDIUM" else "informational"
    if channel == "voice":
        channel_label = "voice transcript"
    else:
        channel_label = "synthetic event"
    return {
        "category": category,
        "title": titles[category],
        "message": messages[category],
        "severity": severity,
        "source": "context-aware prototype guidance",
        "channel_context": channel_label,
        "language": "English (reviewed demo copy; not a translated safety script)",
        "action_is_simulated": True,
    }
