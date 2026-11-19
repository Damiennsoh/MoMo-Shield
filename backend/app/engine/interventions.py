"""Backend counterpart of the dashboard's plain-language intervention taxonomy."""

from app.engine.credential_requests import has_explicit_credential_request


def _text(event) -> str:
    return str(getattr(event, "text_or_transcript", "") or "").casefold()


def build_intervention(event, risk_tier: str, triggered_rules, prior_events=()) -> dict:
    text = ". ".join([_text(item) for item in prior_events] + [_text(event)]).strip()
    rules = " ".join(str(rule.description if hasattr(rule, "description") else rule) for rule in triggered_rules).casefold()
    event_type = str(getattr(getattr(event, "event_type", ""), "value", getattr(event, "event_type", ""))).casefold()
    credential_request = has_explicit_credential_request(text)
    link_signal = any(term in text for term in ("http://", "https://", "www.", ".com", ".net", "link"))
    reversal_signal = any(term in text for term in ("reverse", "reversal", "refund", "send it back", "send back", "mistaken transfer", "receipt"))

    if "gh19: multiple nuisance calls" in rules and not credential_request:
        category = "repeated_calls"
    elif "gh19:" in rules and credential_request:
        category = "call_fatigue_credential_request"
    elif reversal_signal or "gh02:" in rules:
        category = "reversal_or_refund"
    elif link_signal and credential_request:
        category = "suspicious_link"
    elif event_type == "device_binding" or "new device" in rules or "sim_swap" in text:
        category = "device_or_sim_change"
    elif credential_request or "credential-harvesting" in rules:
        category = "credential_request"
    elif any(term in text for term in ("blocked", "unusual activity", "urgent", "secure your account", "support")) and risk_tier != "LOW":
        category = "impersonation_or_pressure"
    elif risk_tier == "LOW":
        category = "no_high_risk_signal"
    elif event_type == "transaction" or any(term in rules for term in ("transfer", "loan", "ledger")):
        category = "transaction_review"
    else:
        category = "insufficient_context"

    messages = {
        "credential_request": ("Possible credential request — verify safely", "Do not share a PIN, OTP, or verification code. Stop responding and verify through the official app or a known support contact."),
        "call_fatigue_credential_request": ("Unsolicited caller requesting a code", "Do not share a code with a caller offering to help. A call burst is not proof by itself; verify any helper independently through official support."),
        "reversal_or_refund": ("Possible refund or reversal pressure", "Do not send money back based only on a caller, SMS, or screenshot. Check the transaction in the official MoMo history and verify with the provider."),
        "suspicious_link": ("Suspicious link — do not enter details", "Do not open the link or enter wallet details there. Open the provider’s official app directly or use a known support contact."),
        "device_or_sim_change": ("Unexpected device or SIM change", "Do not approve an unexpected new-device or SIM change. Use the official app or contact provider support to secure access."),
        "impersonation_or_pressure": ("Urgent support claim — verify independently", "Do not act under threats or urgency. Do not share codes or PINs; verify the claim through an official support channel."),
        "repeated_calls": ("Repeated calls — not proof of fraud", "Repeated calls alone are not proof of fraud. Avoid sharing information with unsolicited callers and verify any request independently."),
        "transaction_review": ("Transaction needs independent review", "Pause before sending or approving money. Check the amount and recipient in the official app, and contact support if the activity is unexpected."),
        "no_high_risk_signal": ("No high-risk signal in this test", "No high-risk signal was identified in this synthetic test. That is not proof that a message or transaction is safe."),
        "insufficient_context": ("More context is needed", "There is not enough context to confirm fraud. If money, account access, or a code is involved, pause and verify through the official app or known support contact."),
    }
    title, message = messages[category]
    return {
        "category": category,
        "title": title,
        "message": message,
        "severity": "urgent" if risk_tier == "HIGH" else "caution" if risk_tier == "MEDIUM" else "informational",
        "language": "English (reviewed demo copy; not a translated safety script)",
        "action_is_simulated": True,
    }
