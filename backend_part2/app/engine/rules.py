from typing import Tuple, Optional, List
from datetime import timedelta
from app.models.events import TransactionEvent, DeviceBindingEvent, CommunicationEvent, TransactionType, DeviceAction
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

def rule_gh18_new_device(event: DeviceBindingEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.action in (DeviceAction.NEW_DEVICE_LOGIN, DeviceAction.WALLET_ENROLMENT, DeviceAction.SIM_SWAP):
        return 40, f"GH18: New device event — {event.action.value}"
    return 0, None

def rule_gh18_otp_activity(event: DeviceBindingEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if not getattr(event, "preceded_by_otp_activity", False):
        return 0, None
    recent_comms = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=10), before=event.timestamp)
    if recent_comms:
        return 25, "GH18: Device binding preceded by OTP/credential activity"
    return 0, None

def rule_communication_pin_request(event: CommunicationEvent, llm_secret: Optional[str]) -> Tuple[int, Optional[str]]:
    secret = (llm_secret or "").lower()
    text = (event.text_or_transcript or "").lower()
    if any(kw in secret for kw in ("pin", "otp", "code")) or any(kw in text for kw in ("send your pin", "enter your pin", "fa wo pin")):
        return 30, "Credential request detected in communication"
    return 0, None

def rule_communication_authority(event: CommunicationEvent, llm_pattern: Optional[str]) -> Tuple[int, Optional[str]]:
    pattern = (llm_pattern or "").lower()
    if "authority" in pattern and ("loss" in pattern or "block" in pattern):
        return 20, "Authority + Loss Aversion psychological levers detected"
    return 0, None

def rule_baseline(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    return 10, "Baseline: normal transaction telemetry"

TRANSACTION_RULES = [rule_gh01_ledger_mismatch, rule_gh01_active_call, rule_baseline]
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
        pts, desc = rule_communication_pin_request(event, llm_intent.get("requested_secret"))
        if pts > 0 and desc: results.append((pts, desc))
        pts, desc = rule_communication_authority(event, llm_intent.get("pattern"))
        if pts > 0 and desc: results.append((pts, desc))
    return results