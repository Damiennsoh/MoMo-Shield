from datetime import datetime, timedelta
from app.config import settings
from app.models.events import parse_event, CommunicationEvent
from app.models.responses import AssessResponse, TriggeredRule, LLMIntent
from app.engine.state import global_window
from app.engine.rules import run_rules_for_event
from app.knowledge.reported_numbers import is_reported_number
from app.engine.interventions import build_intervention
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
    # Safety-critical Twi wording is intentionally withheld until a fluent-speaker review.
    return None

async def assess(raw_event: dict) -> AssessResponse:
    event = parse_event(raw_event)
    prior_events = global_window.get_events(
        msisdn=event.msisdn,
        within=timedelta(minutes=30),
        before=event.timestamp,
    )
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
    risk_score = global_window.add_risk(
        event.msisdn,
        sum(pts for pts, _ in rule_results),
        timestamp=event.timestamp,
        event_id=event.event_id,
    )
    risk_tier = _tier_from_score(risk_score)
    action = _action_from_tier(risk_tier, event)
    
    triggered_rules = [TriggeredRule(rule_id=f"R{i+1}", description=desc, points=pts) for i, (pts, desc) in enumerate(rule_results)]
    intervention = build_intervention(event, risk_tier, triggered_rules, prior_events)

    return AssessResponse(
        msisdn=event.msisdn, risk_score=risk_score, risk_tier=risk_tier,
        triggered_rules=triggered_rules, llm_extracted_intent=llm_intent,
        llm_unavailable=llm_unavailable, intent_source=intent_source,
        recommended_action=action,
        twi_warning_message=None,
        english_warning_message=intervention["message"],
        intervention_category=intervention["category"],
        intervention_title=intervention["title"],
        intervention_message=intervention["message"],
        reported_number_match=(
            isinstance(event, CommunicationEvent)
            and is_reported_number(getattr(event, "counterparty_msisdn", None))
        ),
        event_id=event.event_id, timestamp=datetime.utcnow()
    )
