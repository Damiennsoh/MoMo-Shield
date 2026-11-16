from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class LLMIntent(BaseModel):
    pattern: Optional[str] = None
    evidence_phrases: List[str] = Field(default_factory=list)
    requested_secret: Optional[str] = None
    language_detected: Optional[str] = None
    suggested_warning: Optional[str] = None

class TriggeredRule(BaseModel):
    rule_id: str
    description: str
    points: int

class AssessResponse(BaseModel):
    msisdn: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_tier: str
    triggered_rules: List[TriggeredRule]
    llm_extracted_intent: Optional[LLMIntent] = None
    llm_unavailable: bool = False
    intent_source: str = "none"
    recommended_action: str
    twi_warning_message: Optional[str] = None
    english_warning_message: Optional[str] = None
    event_id: str
    timestamp: datetime
