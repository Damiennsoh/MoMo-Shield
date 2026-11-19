from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field


def _new_event_id() -> str:
    return f"evt-{uuid4().hex[:12]}"

class EventType(str, Enum):
    TRANSACTION = "transaction"
    DEVICE_BINDING = "device_binding"
    COMMUNICATION = "communication"

class TransactionType(str, Enum):
    P2P_SEND = "P2P_SEND"
    CREDIT = "CREDIT"
    XTRACASH_LOAN = "XTRACASH_LOAN"
    USSD_SESSION = "USSD_SESSION"

class DeviceAction(str, Enum):
    APP_INSTALL = "APP_INSTALL"
    NEW_DEVICE_LOGIN = "NEW_DEVICE_LOGIN"
    SIM_SWAP = "SIM_SWAP"
    WALLET_ENROLMENT = "WALLET_ENROLMENT"

class ChannelType(str, Enum):
    SMS = "SMS"
    VOICE = "VOICE"

class TransactionEvent(BaseModel):
    event_id: str = Field(default_factory=_new_event_id)
    msisdn: str = Field(..., pattern=r"^\+?[0-9]{9,15}$")
    event_type: EventType = EventType.TRANSACTION
    transaction_type: TransactionType
    amount: float = Field(ge=0, le=100000)
    counterparty_msisdn: Optional[str] = None
    ledger_verified: bool
    ussd_session_active: bool = False
    timestamp: datetime

class DeviceBindingEvent(BaseModel):
    event_id: str = Field(default_factory=_new_event_id)
    msisdn: str = Field(..., pattern=r"^\+?[0-9]{9,15}$")
    event_type: EventType = EventType.DEVICE_BINDING
    new_imei: str
    action: DeviceAction
    preceded_by_otp_activity: bool = False
    timestamp: datetime

class CommunicationEvent(BaseModel):
    event_id: str = Field(default_factory=_new_event_id)
    msisdn: str = Field(..., pattern=r"^\+?[0-9]{9,15}$")
    event_type: EventType = EventType.COMMUNICATION
    channel: ChannelType
    text_or_transcript: str = Field(..., min_length=1, max_length=5000)
    language_hint: Optional[str] = Field(default=None, max_length=48)
    input_source: Optional[str] = Field(default=None, max_length=32)
    counterparty_msisdn: Optional[str] = None
    timestamp: datetime

class AssessRequest(BaseModel):
    event: dict
    context: Optional[dict] = None

class CaseReferenceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language_hint: Optional[str] = Field(default=None, max_length=48)

def parse_event(raw: dict):
    event_type = raw.get("event_type")
    if event_type == EventType.TRANSACTION.value:
        return TransactionEvent(**raw)
    if event_type == EventType.DEVICE_BINDING.value:
        return DeviceBindingEvent(**raw)
    if event_type == EventType.COMMUNICATION.value:
        return CommunicationEvent(**raw)
    raise ValueError(f"Unknown event_type: {event_type}")
