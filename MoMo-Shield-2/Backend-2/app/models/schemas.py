from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    USSD = "ussd"
    SMS = "sms"
    VOICE = "voice"
    TRANSACTION = "transaction"

class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class SandboxEvent(BaseModel):
    event_id: str
    msisdn: str
    event_type: EventType
    timestamp: datetime
    payload: Dict[str, Any]

class GlanceRiskResponse(BaseModel):
    risk_level: str = "UNKNOWN"
    reports: int = 0
    threat_type: Optional[str] = None

class AssessmentResult(BaseModel):
    event_id: str
    msisdn: str
    event_type: EventType
    risk_score: int
    risk_tier: RiskTier
    triggered_rules: List[str]
    glance_status: Optional[str] = None
    llm_intent: Optional[str] = None
    kb_match: Optional[Dict[str, Any]] = None
    action_taken: str
    latency_ms: float = 0.0
    timestamp: datetime