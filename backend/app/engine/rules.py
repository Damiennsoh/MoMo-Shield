from typing import Tuple, Optional, List
from datetime import timedelta
from app.models.events import TransactionEvent, DeviceBindingEvent, CommunicationEvent, TransactionType, DeviceAction, ChannelType
from app.engine.state import EventWindow

def rule_gh01_ledger_mismatch(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.transaction_type not in (TransactionType.P2P_SEND, TransactionType.USSD_SESSION):
        return 0, None
    recent_credits = window.get_events(msisdn=event.msisdn, event_type="transaction", within=timedelta(minutes=5), before=event.timestamp)
    unverified_credit = any(getattr(e, "transaction_type", None) == TransactionType.CREDIT and getattr(e, "ledger_verified", True) is False for e in recent_credits)
    if unverified_credit:
        return 30, "GH01: Unverified credit followed by outbound transfer"
    return 0, None

def rule_gh01_active_call(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.transaction_type != TransactionType.P2P_SEND:
        return 0, None
    recent_voice = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=3), before=event.timestamp)
    if any(getattr(e, "channel", None).value == "VOICE" for e in recent_voice):
        return 20, "GH01: Outbound transfer during active voice call"
    return 0, None

from app.engine.credential_requests import has_explicit_credential_request as _requests_secret
from app.knowledge.reported_numbers import is_reported_number as _is_reported

def rule_gh18_new_device(event: DeviceBindingEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.action in (DeviceAction.APP_INSTALL, DeviceAction.NEW_DEVICE_LOGIN, DeviceAction.WALLET_ENROLMENT, DeviceAction.SIM_SWAP):
        return 40, f"GH18: New device event — {event.action.value}"
    return 0, None

def rule_gh18_otp_activity(event: DeviceBindingEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    recent_comms = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=10), before=event.timestamp)
    if not recent_comms:
        return 0, None
    credential_comm = any(_requests_secret(getattr(c, "text_or_transcript", "")) for c in recent_comms)
    if getattr(event, "preceded_by_otp_activity", False) or credential_comm:
        return 25, "GH18: Device binding preceded by OTP/credential activity"
    return 0, None

def rule_communication_pin_request(event: CommunicationEvent, llm_secret: Optional[str]) -> Tuple[int, Optional[str]]:
    if _requests_secret(event.text_or_transcript or ""):
        return 45, "Credential request detected in communication"
    return 0, None


def rule_reported_number(event: CommunicationEvent) -> Tuple[int, Optional[str]]:
    if _is_reported(getattr(event, "counterparty_msisdn", None)):
        return 60, "Caller ID matches the reported-scam-number blocklist"
    return 0, None


def rule_communication_impersonation(event: CommunicationEvent) -> Tuple[int, Optional[str]]:
    text = (event.text_or_transcript or "").lower()
    if any(kw in text for kw in (
        "i am from", "i'm from", "this is", "we are from",
        "mtn", "vodafone", "telecel", "airteltigo", "moMo office",
        "customer care", "support team", "fraud department", "agent",
    )):
        return 15, "Operator/authority impersonation detected"
    return 0, None


def rule_communication_urgency(event: CommunicationEvent) -> Tuple[int, Optional[str]]:
    text = (event.text_or_transcript or "").lower()
    if any(kw in text for kw in (
        "expires", "expire", "urgent", "asap", "immediately", "right now",
        "be fast", "act now", "before it", "limited time", "quickly",
    )):
        return 15, "Urgency/loss-aversion pressure detected"
    return 0, None

def rule_communication_authority(event: CommunicationEvent, llm_pattern: Optional[str]) -> Tuple[int, Optional[str]]:
    pattern = (llm_pattern or "").lower()
    if "authority" in pattern and ("loss" in pattern or "block" in pattern):
        return 20, "Authority + Loss Aversion psychological levers detected"
    return 0, None

def rule_baseline(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    return 10, "Baseline: normal transaction telemetry"

def rule_gh17_loan_after_drain(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.transaction_type != TransactionType.XTRACASH_LOAN:
        return 0, None
    recent_debits = window.get_events(msisdn=event.msisdn, event_type="transaction", within=timedelta(minutes=10), before=event.timestamp)
    large_drain = any(
        getattr(e, "transaction_type", None) == TransactionType.P2P_SEND
        and getattr(e, "amount", 0) > 100
        for e in recent_debits
    )
    if large_drain:
        return 25, "GH17: Micro-loan activated immediately after large outbound transfer"
    return 0, None

def rule_payment_after_credential_comm(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.transaction_type not in (TransactionType.P2P_SEND, TransactionType.USSD_SESSION):
        return 0, None
    recent_comms = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=10), before=event.timestamp)
    if any(_requests_secret(getattr(c, "text_or_transcript", "")) for c in recent_comms):
        return 25, "Payment/transfer shortly after credential-harvesting communication"
    return 0, None

def rule_gh02_reversal_pretext(event: CommunicationEvent) -> Tuple[int, Optional[str]]:
    text = (event.text_or_transcript or "").lower()
    if any(kw in text for kw in ("reverse", "reversal", "send it back", "send back", "mistaken transfer", "transaction id", "receipt")):
        return 25, "GH02: Reversal/forge pretext detected in communication"
    return 0, None

def rule_gh15_link_credential(event: CommunicationEvent, llm_secret: Optional[str]) -> Tuple[int, Optional[str]]:
    text = (event.text_or_transcript or "").lower()
    has_link = any(kw in text for kw in ("http", "www.", ".com", ".net", ".link"))
    if has_link and _requests_secret(text):
        return 20, "GH15: Credential request via suspicious link/form"
    return 0, None

def rule_gh19_harassment_burst(event: CommunicationEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.channel != ChannelType.VOICE:
        return 0, None
    recent_calls = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=30), before=event.timestamp)
    distinct_callers = {
        getattr(c, "counterparty_msisdn", None)
        for c in recent_calls
        if getattr(c, "channel", None) == ChannelType.VOICE and getattr(c, "counterparty_msisdn", None)
    }
    if len(distinct_callers) >= 3:
        return 20, "GH19: Multiple nuisance calls from distinct numbers detected"
    return 0, None

def rule_gh19_helper_pretext(event: CommunicationEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if not _requests_secret(event.text_or_transcript or ""):
        return 0, None
    recent_calls = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=30), before=event.timestamp)
    distinct_callers = {
        getattr(c, "counterparty_msisdn", None)
        for c in recent_calls
        if getattr(c, "channel", None) == ChannelType.VOICE and getattr(c, "counterparty_msisdn", None)
    }
    if len(distinct_callers) >= 3:
        return 25, "GH19: 'Helper' credential request exploiting call fatigue"
    return 0, None

TRANSACTION_RULES = [rule_gh01_ledger_mismatch, rule_gh01_active_call, rule_gh17_loan_after_drain, rule_payment_after_credential_comm, rule_baseline]
DEVICE_RULES = [rule_gh18_new_device, rule_gh18_otp_activity]

def run_rules_for_event(event, window: EventWindow, llm_intent: dict = None) -> List[Tuple[int, str]]:
    llm_intent = llm_intent or {}
    results = []
    if isinstance(event, TransactionEvent):
        for rule in TRANSACTION_RULES:
            pts, desc = rule(event, window)
            if pts > 0 and desc: results.append((pts, desc))
    elif isinstance(event, DeviceBindingEvent):
        for rule in DEVICE_RULES:
            pts, desc = rule(event, window)
            if pts > 0 and desc: results.append((pts, desc))
    elif isinstance(event, CommunicationEvent):
        comm_window_rules = [
            (rule_reported_number, (event,)),
            (rule_communication_impersonation, (event,)),
            (rule_communication_urgency, (event,)),
            (rule_gh02_reversal_pretext, (event,)),
            (rule_gh15_link_credential, (event, llm_intent.get("requested_secret"))),
            (rule_gh19_harassment_burst, (event, window)),
            (rule_gh19_helper_pretext, (event, window)),
        ]
        pts, desc = rule_communication_pin_request(event, llm_intent.get("requested_secret"))
        if pts > 0 and desc: results.append((pts, desc))
        pts, desc = rule_communication_authority(event, llm_intent.get("pattern"))
        if pts > 0 and desc: results.append((pts, desc))
        for rule, args in comm_window_rules:
            pts, desc = rule(*args)
            if pts > 0 and desc: results.append((pts, desc))
    return results
