from datetime import datetime
from app.config import settings
from app.models.events import parse_event, CommunicationEvent
from app.models.responses import AssessResponse, TriggeredRule, LLMIntent
from app.engine.state import global_window
from app.engine.rules import run_rules_for_event
from app.ai.gemini_client import extract_intent
from app.ai.fallback import keyword_intent
from app.utils.logger import get_logger

log = get_logger(__name__)

def _tier_from_score(score: int) -> str:
    if score >= settings.risk_threshold_high: return "HIGH"
    if score >= settings.risk_threshold_medium: return "MEDIUM"
    return "LOW"

def _action_from_tier(tier: str, event) -> str:
    if tier == "LOW":
        return "SEAMLESS_APPROVE"
    if tier == "MEDIUM":
        return "SOFT_WARNING"
    # HIGH tier: a communication event means no in-flight transaction exists to
    # hold (e.g. GH19 fake-helper call) -> FraudOps alert + cooling-off instead.
    if isinstance(event, CommunicationEvent):
        return "FRAUDOPS_ALERT"
    return "SIMULATED_HOLD"

def _twi_warning(tier: str, llm_intent: LLMIntent, action: str) -> str:
    if tier != "HIGH":
        return None
    if llm_intent and llm_intent.requested_secret:
        return "Wɔrehyɛ wo sɛ fa wo PIN kɔ ma! — Do not share your PIN."
    if action == "FRAUDOPS_ALERT":
        return "Sɛ wo yɛ den a, frɛ MTN 100. Mma wo PIN biara."
    return "Yɛn hu sɛ obi rehyɛ wo ma ɛyɛ den. Fa ayɛ nkyerɛ."

def _english_warning(tier: str, action: str) -> str:
    if tier != "HIGH":
        return None
    if action == "FRAUDOPS_ALERT":
        return "⚠️ HIGH RISK: FraudOps alerted. Customer cooling-off prompt shown. No transaction was executed."
    return "⚠️ HIGH RISK: Transaction placed on simulated hold."

async def assess(raw_event: dict) -> AssessResponse:
    event = parse_event(raw_event)
    global_window.add(event.msisdn, event)
    
    llm_intent = None
    llm_unavailable = False
    intent_source = "none"
    if isinstance(event, CommunicationEvent):
        raw_intent = None
        if settings.gemini_enabled:
            try:
                raw_intent = await extract_intent(event.text_or_transcript)
                if raw_intent is not None:
                    intent_source = "gemini"
            except Exception as e:
                log.warning(f"Gemini failed, using fallback: {e}")
                llm_unavailable = True
        if raw_intent is None:
            raw_intent = keyword_intent(event.text_or_transcript)
            intent_source = "keyword_fallback"
        if raw_intent:
            llm_intent = LLMIntent(**raw_intent)

    rule_results = run_rules_for_event(event, global_window, llm_intent.dict() if llm_intent else {})
    risk_score = global_window.add_risk(event.msisdn, sum(pts for pts, _ in rule_results))
    risk_tier = _tier_from_score(risk_score)
    action = _action_from_tier(risk_tier, event)
    
    triggered_rules = [TriggeredRule(rule_id=f"R{i+1}", description=desc, points=pts) for i, (pts, desc) in enumerate(rule_results)]

    return AssessResponse(
        msisdn=event.msisdn, risk_score=risk_score, risk_tier=risk_tier,
        triggered_rules=triggered_rules, llm_extracted_intent=llm_intent,
        llm_unavailable=llm_unavailable, intent_source=intent_source,
        recommended_action=action,
        twi_warning_message=_twi_warning(risk_tier, llm_intent, action),
        english_warning_message=_english_warning(risk_tier, action),
        event_id=event.event_id, timestamp=datetime.utcnow()
    )
