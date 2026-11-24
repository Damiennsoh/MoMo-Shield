import asyncio
import hmac
import time
from uuid import UUID, uuid4
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, List

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import settings
from app.engine.rules import RULES
from app.engine.state import global_window, sms_blast_window
from app.engine.kb import knowledge_base
from app.integrations.gemini import analyze_intent
from app.integrations.glance import check_glance_risk, report_fraud
from app.integrations.infofemme import infofemme_client
from app.integrations.nia import evaluate_ghana_card, verify_card_live
from app.integrations.sandbox import intervene_sandbox
from app.integrations import mtn_momo
from app.models.schemas import AssessmentResult, EventType, RiskTier, SandboxEvent
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

ASSESSMENT_HISTORY: Deque[dict] = deque(maxlen=200)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, data: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(data)
            except Exception:
                self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/events")
async def recent_events(limit: int = 50):
    """Recent assessments for dashboard hydration on connect."""
    return {"events": list(ASSESSMENT_HISTORY)[-min(limit, 200):]}


@router.get("/integrations/mtn-momo/status")
async def mtn_momo_status():
    return mtn_momo.status()


def _require_mtn_request_key(authorization: str | None) -> None:
    configured_key = settings.mtn_momo_request_api_key
    if not configured_key:
        raise HTTPException(status_code=503, detail="MTN MoMo request API is not enabled")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, configured_key):
        raise HTTPException(status_code=401, detail="Invalid API credentials")


@router.post("/integrations/mtn-momo/collection/request-to-pay", status_code=202)
async def mtn_momo_request_to_pay(
    payload: mtn_momo.RequestToPay,
    authorization: str | None = Header(default=None),
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
):
    _require_mtn_request_key(authorization)
    return await mtn_momo.request_to_pay(payload, idempotency_key)


@router.get("/integrations/mtn-momo/collection/request-to-pay/{reference_id}")
async def mtn_momo_request_status(
    reference_id: UUID,
    authorization: str | None = Header(default=None),
):
    _require_mtn_request_key(authorization)
    return await mtn_momo.get_request_status(reference_id)


@router.post("/integrations/mtn-momo/callback")
async def mtn_momo_callback(
    payload: dict,
    x_reference_id: str | None = Header(default=None, alias="X-Reference-Id"),
):
    """MTN callbacks are unauthenticated; verify the final state server-to-server."""
    reference = x_reference_id or payload.get("referenceId") or payload.get("reference_id")
    try:
        reference_id = UUID(str(reference))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="A valid referenceId is required")
    transaction = await mtn_momo.get_request_status(reference_id)
    return {"accepted": True, "status": transaction.get("status")}


def _verify_webhook_key(authorization: str | None) -> None:
    """When WEBHOOK_API_KEY is configured, sandbox/MNO callers must present it."""
    if not settings.webhook_api_key:
        return
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token != settings.webhook_api_key:
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")


@router.post("/webhook/sandbox", response_model=AssessmentResult)
async def receive_sandbox_event(
    event: SandboxEvent,
    authorization: str | None = Header(default=None),
):
    started = time.perf_counter()
    _verify_webhook_key(authorization)

    history = global_window.observe_and_add(event.msisdn, event.model_dump())

    score = 0
    rules_fired: List[str] = []
    for rule in RULES:
        pts, desc = rule(event, history)
        if pts > 0 and desc:
            score += pts
            rules_fired.append(desc)

    text_payload = str(
        event.payload.get("text") or event.payload.get("transcript") or ""
    )

    # Fast in-memory semantic search over InnoFemme KNUST Case Study Knowledge Base (< 2ms)
    kb_match_data = None
    rag_context = None
    if text_payload.strip():
        kb_matches = await knowledge_base.search_smart(text_payload, top_k=1)
        if kb_matches:
            top_kb = kb_matches[0]
            kb_match_data = {
                "case_id": top_kb.case_id,
                "title": top_kb.title,
                "typology": top_kb.typology,
                "similarity": top_kb.similarity,
                "is_benign": top_kb.is_benign,
                "psychological_levers": top_kb.psychological_levers,
                "source": top_kb.source,
                "engine": getattr(top_kb, "engine", "lexical"),
            }
            kb_engine = getattr(top_kb, "engine", "lexical")
            if kb_engine == "semantic":
                fraud_floor, benign_floor = 0.72, 0.78
            else:
                fraud_floor, benign_floor = 0.40, 0.50
            if not top_kb.is_benign and top_kb.similarity >= fraud_floor:
                score += int(top_kb.similarity * (40 if kb_engine == "semantic" else 50))
                rules_fired.append(f"RAG Knowledge Base ({top_kb.similarity:.0%} {kb_engine} match): KNUST Dossier {top_kb.case_id} - {top_kb.title}")
            elif top_kb.is_benign and top_kb.similarity >= benign_floor:
                score = max(0, score - (25 if kb_engine == "semantic" else 30))
                rules_fired.append(f"RAG Benign Control ({top_kb.similarity:.0%} {kb_engine} match): {top_kb.title} (Legitimate Pattern)")
        rag_context = await knowledge_base.get_rag_context_smart(text_payload)

    # External lookups run concurrently to keep decision latency low.
    glance_task = asyncio.create_task(check_glance_risk(event.msisdn))
    intent_task = asyncio.create_task(analyze_intent(text_payload, rag_context))
    sim_task = asyncio.create_task(infofemme_client.get_sim_swap_history(event.msisdn))
    glance_data, llm_intent, sim_data = await asyncio.gather(glance_task, intent_task, sim_task)

    if glance_data.risk_level == "HIGH":
        score += 40
        rules_fired.append(f"Glance Intelligence: Cross-operator high-risk flag ({glance_data.reports} prior reports){' [DEMO SEED]' if getattr(glance_data, 'simulated', False) else ''}")

    if sim_data.get("risk_boost", 0) > 0:
        score += sim_data["risk_boost"]
        rules_fired.append(f"Network Edge: SIM swapped {sim_data.get('days_since_swap')}d ago ({sim_data.get('status')}){' [DEMO SEED]' if sim_data.get('simulated') else ''}")

    tier = (
        RiskTier.HIGH
        if score >= settings.risk_threshold_high
        else RiskTier.MEDIUM
        if score >= settings.risk_threshold_medium
        else RiskTier.LOW
    )
    action = "ALLOWED"

    if tier == RiskTier.HIGH:
        action = "BLOCKED"
        await intervene_sandbox(event.event_id, "BLOCK_USSD")
        await report_fraud(event.msisdn, "Social Engineering")
        asyncio.create_task(trigger_real_phone_bridge("warn"))
        asyncio.create_task(
            infofemme_client.send_ussd_push(
                event.msisdn,
                "FRAUD ALERT: Session blocked by MoMo Shield. Never share your MoMo PIN with anyone."
            )
        )
    elif tier == RiskTier.MEDIUM:
        action = "WARNED"
        await intervene_sandbox(event.event_id, "PUSH_WARNING")
        asyncio.create_task(
            infofemme_client.send_ussd_push(
                event.msisdn,
                "WARNING: Suspicious prompt detected. Official agents will never request credentials."
            )
        )

    result = AssessmentResult(
        event_id=event.event_id,
        msisdn=event.msisdn,
        event_type=event.event_type,
        risk_score=min(100, score),
        risk_tier=tier,
        triggered_rules=rules_fired,
        glance_status=f"{glance_data.risk_level} ({glance_data.reports} reports){' · demo seed' if getattr(glance_data, 'simulated', False) else ''}",
        llm_intent=llm_intent,
        kb_match=kb_match_data,
        action_taken=action,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    payload = result.model_dump(mode="json")
    ASSESSMENT_HISTORY.append(payload)
    await manager.broadcast(payload)

    return result


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@router.get("/audio/{asset_name}")
async def get_audio_asset(asset_name: str):
    """Serve ring, sms, alert, and momo-warning audio files to handsets/clients."""
    file_path = ASSETS_DIR / Path(asset_name).name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio asset not found")
    media_type = "audio/wav" if file_path.suffix.lower() == ".wav" else "audio/mpeg" if file_path.suffix.lower() == ".mp3" else "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)


async def trigger_real_phone_bridge(action: str = "warn") -> dict:
    """Bridge action for local Asterisk PBX ringing/warning the judge's real phone (Linphone)."""
    ari_url = "http://asterisk:8088/ari"
    try:
        async with httpx.AsyncClient(timeout=1.2) as client:
            resp = await client.get(f"{ari_url}/asterisk/info", auth=("asterisk", "asterisk"))
            if resp.status_code == 200:
                if action == "ring":
                    originate = await client.post(
                        f"{ari_url}/channels",
                        params={"endpoint": "PJSIP/200", "extension": "200", "context": "from-internal", "priority": "1"},
                        auth=("asterisk", "asterisk"),
                    )
                    return {"status": "dispatched", "carrier": "Asterisk PJSIP", "endpoint": "PJSIP/200", "code": originate.status_code}
                elif action in ("hangup", "warn"):
                    channels = await client.get(f"{ari_url}/channels", auth=("asterisk", "asterisk"))
                    for ch in channels.json():
                        try:
                            await client.delete(f"{ari_url}/channels/{ch['id']}", auth=("asterisk", "asterisk"))
                        except Exception:
                            pass
                    return {"status": "hangup_executed", "action": action}
    except Exception as exc:
        log.debug(f"Asterisk PBX offline or simulated: {exc}")
    return {"status": "simulated", "action": action, "detail": "Asterisk PBX offline; simulated fallback active."}


@router.get("/knowledge-base")
async def get_fraud_knowledge_base():
    """Returns the precomputed InnoFemme KNUST Case Study Knowledge Base."""
    return {
        "count": len(knowledge_base.chunks),
        "chunks": [
            {k: v for k, v in c.items() if k != "vector"}
            for c in knowledge_base.chunks
        ]
    }


@router.post("/demo/real-phone-action")
async def real_phone_action(action: str = Query("ring", description="ring | hangup | warn")):
    return await trigger_real_phone_bridge(action)


@router.post("/demo/reset")
async def reset_demo_state():
    """Clear in-process assessment and correlation state for a fresh demo run."""
    ASSESSMENT_HISTORY.clear()
    global_window.clear()
    return {"status": "reset", "history_count": 0, "active_sessions": 0}


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        return None


@router.post("/plugin")
async def receive_innofemme_plugin(payload: dict):
    """Score a documented InnoFemme plug-in event against the two-second target."""
    started = time.perf_counter()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Plug-in request must be a JSON object")

    point = str(payload.get("point") or "").strip()
    institution = str(payload.get("institution") or "mtn").strip().lower()
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Plug-in 'data' must be a JSON object")

    # events is informational only (answer ignored); accept and allow.
    if point == "events":
        return {"decision": "allow"}

    # All 16 documented InnoFemme interception points (Hackathon Environment §4).
    supported_points = {
        # Network events
        "pin.set", "wallet.open", "menu.open", "payment.authorize",
        "payment.receive", "payment.request", "kyc.upgrade", "pin.reset",
        "business.onboard", "sim.register", "sim.swap", "sms.deliver",
        "call.connect",
        # Bank events
        "transfer.authorize", "account.open",
        # Switch event
        "switch.route",
    }
    if point not in supported_points:
        raise HTTPException(status_code=422, detail=f"Unsupported plug-in point: {point or '(missing)'}")

    payer = data.get("payer") if isinstance(data.get("payer"), dict) else {}
    payee = data.get("payee") if isinstance(data.get("payee"), dict) else {}
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}

    # Subscriber MSISDN differs per hook: deliveries/calls target "to",
    # payments name payer/payee, lifecycle hooks carry "msisdn".
    msisdn = ""
    for candidate in (
        data.get("to"),
        payer.get("msisdn"),
        data.get("msisdn"),
        payee.get("msisdn"),
        customer.get("msisdn"),
    ):
        if candidate:
            msisdn = str(candidate).strip()
            break
    if not msisdn:
        raise HTTPException(status_code=422, detail=f"Missing subscriber MSISDN for {point}")
    # For inbound money the protected subscriber is the payee — the plug-in
    # is asked on the payee's network, so correlate under their window.
    if point == "payment.receive" and payee.get("msisdn"):
        msisdn = str(payee["msisdn"]).strip()

    event_type = EventType.TRANSACTION
    event_payload = {}
    if point == "sms.deliver":
        event_type = EventType.SMS
        event_payload = {
            "text": data.get("text", ""),
            "from": data.get("from", ""),
            "textsBetweenThemBefore": _safe_int(data.get("textsBetweenThemBefore")),
        }
    elif point == "call.connect":
        event_type = EventType.VOICE
        event_payload = {
            "from": data.get("from", ""),
            "callerSimRegisteredAt": data.get("callerSimRegisteredAt"),
            "numbersTheCallerHasRungToday": _safe_int(data.get("numbersTheCallerHasRungToday")),
            "callsBetweenThemBefore": _safe_int(data.get("callsBetweenThemBefore")),
            "status": "ringing",
        }
    elif point == "menu.open":
        event_type = EventType.USSD
        event_payload = {
            "ussd_input": str(data.get("shortcode") or "*170#"),
            "status": "active",
            "onCallWith": data.get("onCallWith"),
            "lastSimSwapAt": data.get("lastSimSwapAt"),
        }
    elif point == "payment.authorize":
        event_payload = {
            "type": "transfer_out",
            "amount": data.get("amount", 0),
            "fee": data.get("fee", 0),
            "payee": data.get("payee"),
            "onCallWith": payer.get("onCallWith"),
            "lastSimSwapAt": payer.get("lastSimSwapAt"),
        }
    elif point == "payment.receive":
        event_payload = {
            "type": "transfer_in",
            "amount": data.get("amount", 0),
            "payer": data.get("payer"),
            "paymentsReceivedInLast24Hours": _safe_int(data.get("paymentsReceivedInLast24Hours")),
            "differentPayersInLast24Hours": _safe_int(data.get("differentPayersInLast24Hours")),
        }
    elif point == "payment.request":
        event_payload = {
            "type": "payment_request",
            "amount": data.get("amount", 0),
            "requester": data.get("requester"),
            "requestsFromThisRequesterToday": _safe_int(data.get("requestsFromThisRequesterToday")),
            "chargedWithoutAsking": bool(data.get("chargedWithoutAsking")),
        }
    elif point == "sim.swap":
        event_payload = {
            "type": "new_device_binding",
            "swapsOnThisNumberBefore": _safe_int(data.get("swapsOnThisNumberBefore")),
            "walletBalance": data.get("walletBalance"),
            "lastSimSwapAt": data.get("lastSimSwapAt"),
        }
    elif point == "sim.register":
        event_payload = {
            "type": "sim_register",
            "registeredBy": data.get("registeredBy"),
            "simsAlreadyOnThisGhanaCard": _safe_int(data.get("simsAlreadyOnThisGhanaCard"), 1),
        }
    elif point == "wallet.open":
        event_payload = {
            "type": "wallet_open",
            "walletType": data.get("walletType"),
            "kycTier": data.get("kycTier"),
            "onCallWith": data.get("onCallWith"),
            "lastSimSwapAt": data.get("lastSimSwapAt"),
        }
    elif point == "pin.set":
        event_payload = {"type": "pin_set", "customer": customer or None}
    elif point == "pin.reset":
        event_payload = {
            "type": "pin_reset",
            "walletBalance": data.get("walletBalance"),
            "lastSimSwapAt": data.get("lastSimSwapAt"),
            "pinResetsBefore": _safe_int(data.get("pinResetsBefore")),
        }
    elif point == "kyc.upgrade":
        event_payload = {
            "type": "kyc_upgrade",
            "fromTier": data.get("fromTier"),
            "toTier": data.get("toTier"),
            "requestedBy": data.get("requestedBy"),
        }
    elif point == "business.onboard":
        event_payload = {
            "type": "business_onboard",
            "businessType": data.get("businessType"),
            "owner": customer or None,
        }
    elif point == "account.open":
        event_payload = {
            "type": "account_open",
            "accountsAtOtherBanks": _safe_int(data.get("accountsAtOtherBanks")),
            "walletsOnThisGhanaCard": _safe_int(data.get("walletsOnThisGhanaCard")),
        }
    elif point == "transfer.authorize":
        event_payload = {
            "type": "transfer_out",
            "amount": data.get("amount", 0),
            "channel": "bank",
            "fromAccount": data.get("fromAccount"),
            "toWallet": data.get("toWallet"),
        }
    elif point == "switch.route":
        event_payload = {
            "type": "switch_route",
            "amount": data.get("amount", 0),
            "paymentsRoutedBetweenThemToday": _safe_int(data.get("paymentsRoutedBetweenThemToday")),
        }

    event_id = f"inno_{uuid4().hex}"
    sandbox_event = SandboxEvent(
        event_id=event_id,
        msisdn=msisdn,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        payload=event_payload,
    )
    history = global_window.observe_and_add(msisdn, sandbox_event.model_dump())

    score = 0
    rules_fired: List[str] = []

    # Cross-subscriber SMS blast: identical text hitting many victims in 10
    # minutes is a campaign signature, independent of content rules.
    if point == "sms.deliver":
        victims = sms_blast_window.observe(str(event_payload.get("text") or ""), msisdn)
        if victims >= 8:
            score += 45
            rules_fired.append(f"SMS blast: identical text delivered to {victims} distinct subscribers in 10 min")
        elif victims >= 5:
            score += 30
            rules_fired.append(f"SMS blast: identical text delivered to {victims} distinct subscribers in 10 min")
        elif victims >= 3:
            score += 15
            rules_fired.append(f"SMS blast: identical text delivered to {victims} distinct subscribers in 10 min")

    if point in ("payment.authorize", "menu.open", "wallet.open", "payment.request", "pin.reset") \
            and (event_payload.get("onCallWith") or data.get("onCallWith")):
        score += 50
        rules_fired.append("Active Call Co-occurrence: subscriber is on an active call during a financial/USSD action")

    swap_ts = event_payload.get("lastSimSwapAt") or data.get("lastSimSwapAt")
    swap_dt = _parse_timestamp(swap_ts)
    if swap_dt is not None:
        age_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - swap_dt).total_seconds() / 3600
        if 0 <= age_hours <= 48:
            score += 45
            rules_fired.append(f"SIM Swap Recency: subscriber SIM changed {age_hours:.0f}h ago")

    # Hook-specific payload signals documented in Hackathon Environment §4.
    if point == "payment.request":
        if event_payload.get("chargedWithoutAsking"):
            score += 40
            rules_fired.append("RTP abuse: merchant flagged as charging without subscriber consent")
        if _safe_int(event_payload.get("requestsFromThisRequesterToday")) >= 5:
            score += 25
            rules_fired.append("RTP flood: requester has sent 5+ payment requests today")
    elif point == "payment.receive":
        if _safe_int(event_payload.get("differentPayersInLast24Hours")) >= 8:
            score += 20
            rules_fired.append("Mule inbound: 8+ distinct payers credited in 24h")
    elif point == "pin.reset":
        if _safe_int(event_payload.get("pinResetsBefore")) >= 2:
            score += 30
            rules_fired.append("PIN-reset abuse: subscriber has reset PIN 2+ times")
    elif point == "kyc.upgrade" and data.get("requestedBy"):
        score += 15
        rules_fired.append("Agent-initiated KYC upgrade — verify agent authority")
    elif point == "switch.route":
        if _safe_int(event_payload.get("paymentsRoutedBetweenThemToday")) >= 10:
            score += 20
            rules_fired.append("Switch velocity: 10+ routed payments between same institutions today")

    for rule in RULES:
        points, description = rule(sandbox_event, history)
        if points > 0 and description:
            score += points
            rules_fired.append(description)

    # NIA is not queried here: these are local checks over event-supplied claims.
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    ghana_card = data.get("ghanaCard") or customer.get("ghanaCard")
    count_keys = (
        "simsAlreadyOnThisGhanaCard",
        "walletsOnThisGhanaCard",
        "businessLinesAlreadyOnThisGhanaCard",
        "accountsAtOtherBanks",
    )
    sims_count = _safe_int(data.get("simsAlreadyOnThisGhanaCard", 1), 1)
    wallets_on_card = _safe_int(data.get("walletsOnThisGhanaCard"))
    business_lines = _safe_int(data.get("businessLinesAlreadyOnThisGhanaCard"))
    accounts_other_banks = _safe_int(data.get("accountsAtOtherBanks"))
    identity_data_present = bool(ghana_card) or any(key in data for key in count_keys)
    if identity_data_present:
        nia_result = evaluate_ghana_card(ghana_card, sims_count)
        if nia_result.is_flagged:
            score += 45
            rules_fired.append(f"Local identity/SIM-count heuristic (not live NIA verification): {nia_result.reason}")
    if wallets_on_card >= 3:
        score += 30
        rules_fired.append(f"Identity sprawl heuristic: {wallets_on_card} wallets on supplied Ghana Card")
    if business_lines >= 3:
        score += 25
        rules_fired.append(f"Identity sprawl heuristic: {business_lines} business lines on supplied Ghana Card")
    if accounts_other_banks >= 4:
        score += 15
        rules_fired.append(f"Identity sprawl heuristic: {accounts_other_banks} other-bank accounts on supplied identity")

    text_content = str(event_payload.get("text") or "")
    kb_match_data = None
    if text_content.strip():
        kb_matches = knowledge_base.search(text_content, top_k=1)
        if kb_matches:
            top_kb = kb_matches[0]
            kb_match_data = {
                "case_id": top_kb.case_id,
                "title": top_kb.title,
                "typology": top_kb.typology,
                "similarity": top_kb.similarity,
                "is_benign": top_kb.is_benign,
                "psychological_levers": top_kb.psychological_levers,
                "source": top_kb.source,
                "engine": "lexical",
            }
            if not top_kb.is_benign and top_kb.similarity >= 0.40:
                score += int(top_kb.similarity * 50)
                rules_fired.append(f"Lexical fraud precedent ({top_kb.similarity:.0%} match): {top_kb.title}")
            # A benign lexical similarity is explanatory only; it never subtracts
            # points from deterministic fraud evidence.

    # Check the suspicious party for SMS/calls, but the subscriber for wallet events.
    intel_msisdn = str(data.get("from") or msisdn) if point in ("sms.deliver", "call.connect") else msisdn
    # Both optional lookups overlap and are bounded by one shared deadline.
    glance_task = asyncio.create_task(check_glance_risk(intel_msisdn))
    sim_task = asyncio.create_task(infofemme_client.get_sim_swap_history(msisdn, institution))
    # Live NIA registry verify only when the hook supplies a Ghana Card —
    # shares the same bounded deadline, fails open on any error.
    nia_task = (
        asyncio.create_task(verify_card_live(ghana_card)) if ghana_card else None
    )
    lookup_tasks = {glance_task, sim_task} | ({nia_task} if nia_task else set())
    timeout = min(max(settings.plugin_lookup_timeout_seconds, 0.05), 1.2)
    done, pending = await asyncio.wait(
        lookup_tasks, timeout=timeout, return_when=asyncio.ALL_COMPLETED
    )
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    glance_data = None
    sim_data = {"status": "UNKNOWN", "risk_boost": 0}
    if glance_task in done:
        try:
            glance_data = glance_task.result()
        except Exception as exc:
            log.warning("Glance lookup failed for plug-in event %s: %s", event_id, exc)
    if sim_task in done:
        try:
            sim_data = sim_task.result() or sim_data
        except Exception as exc:
            log.warning("SIM-swap lookup failed for plug-in event %s: %s", event_id, exc)
    nia_live = None
    if nia_task is not None and nia_task in done:
        try:
            nia_live = nia_task.result()
        except Exception as exc:
            log.warning("NIA verify failed for plug-in event %s: %s", event_id, exc)

    glance_level = getattr(glance_data, "risk_level", "UNKNOWN")
    glance_reports = _safe_int(getattr(glance_data, "reports", 0))
    if glance_level == "HIGH":
        score += 40
        rules_fired.append(f"Glance cross-operator intelligence: HIGH ({glance_reports} reports)")
    elif glance_reports >= 2:
        score += 25
        rules_fired.append(f"Glance cross-operator intelligence: {glance_reports} prior reports")
    if _safe_int(sim_data.get("risk_boost")) > 0:
        score += _safe_int(sim_data.get("risk_boost"))
        rules_fired.append("InnoFemme network-edge SIM-swap check: recent swap reported")
    if isinstance(nia_live, dict):
        if nia_live.get("valid") is False:
            score += 40
            rules_fired.append("Live NIA verify: Ghana Card not found in national registry")
        elif nia_live.get("biometricMatch") is False:
            score += 50
            rules_fired.append("Live NIA verify: biometric check failed")

    score = min(100, max(0, score))
    tier = (
        RiskTier.HIGH if score >= settings.risk_threshold_high
        else RiskTier.MEDIUM if score >= settings.risk_threshold_medium
        else RiskTier.LOW
    )
    delay_payment = point == "payment.authorize" and tier == RiskTier.HIGH and not bool(data.get("afterDelay"))
    if delay_payment:
        decision = "delay"
        message = "MoMo Shield: High-risk transfer held for a 10-minute cooling period."
    elif tier == RiskTier.HIGH:
        decision = "reject"
        message = "MoMo Shield Alert: High-risk fraudulent activity detected."
        if point == "payment.authorize":
            message += " Transfer blocked."
    elif tier == RiskTier.MEDIUM:
        decision = "warn"
        message = "MoMo Shield Warning: Suspicious activity. Never share your MoMo PIN."
    else:
        decision = "allow"
        message = ""

    # Hackathon Environment §7: warn/delay are only accepted at menu.open,
    # payment.authorize, sms.deliver and call.connect. Every other step takes
    # allow/reject only — answering warn there is a contract violation. The
    # suspicion is still recorded in telemetry via triggered_rules.
    WARN_CAPABLE_POINTS = {"menu.open", "payment.authorize", "sms.deliver", "call.connect"}
    if decision == "warn" and point not in WARN_CAPABLE_POINTS:
        decision = "allow"
        message = ""
    message = message[:150]

    result = AssessmentResult(
        event_id=event_id,
        msisdn=msisdn,
        event_type=event_type,
        risk_score=score,
        risk_tier=tier,
        triggered_rules=rules_fired,
        glance_status=f"{glance_level} ({glance_reports} reports)",
        llm_intent="deferred (post-decision enrichment)",
        kb_match=kb_match_data,
        action_taken=decision.upper(),
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    result_payload = result.model_dump(mode="json")
    ASSESSMENT_HISTORY.append(result_payload)
    # Dashboard delivery and semantic/LLM enrichment must not hold up the MNO response.
    asyncio.create_task(manager.broadcast(result_payload))
    if text_content.strip():
        asyncio.create_task(_enrich_plugin_assessment(event_id, text_content, point))

    if decision == "allow":
        return {"decision": "allow"}
    if decision == "delay":
        return {"decision": "delay", "minutes": 10, "message": message}
    return {"decision": decision, "message": message}

async def _enrich_plugin_assessment(event_id: str, text: str, point: str) -> None:
    """Runs after the plug-in decision is returned: semantic KB retrieval and
    Gemini intent grounded in the retrieved precedent, broadcast to telemetry."""
    try:
        rag_context = await knowledge_base.get_rag_context_smart(text)
        llm_intent = await analyze_intent(text, rag_context)
        kb_matches = await knowledge_base.search_smart(text, top_k=1)
        kb_match = None
        if kb_matches:
            top_kb = kb_matches[0]
            kb_match = {
                "case_id": top_kb.case_id,
                "title": top_kb.title,
                "typology": top_kb.typology,
                "similarity": top_kb.similarity,
                "is_benign": top_kb.is_benign,
                "source": top_kb.source,
                "engine": getattr(top_kb, "engine", "lexical"),
            }
        await manager.broadcast({
            "type": "assessment_enrichment",
            "event_id": event_id,
            "point": point,
            "llm_intent": llm_intent,
            "kb_match": kb_match,
        })
    except Exception as exc:
        log.debug(f"Plugin enrichment failed for {event_id}: {exc}")


BENCHMARK_SCENARIOS = [
    {
        "id": "bench_01",
        "name": "Reversal Scam (GH01)",
        "typology": "reversal_scam",
        "msisdn": "+233240000310",
        "event_type": EventType.TRANSACTION,
        "amount": 800,
        "payload": {"type": "transfer_out", "amount": 800},
        "history": [{"payload": {"type": "sms_credit", "ledger_verified": False, "amount": 800}}],
        "is_fraud": True,
        "estimated_loss": 800,
    },
    {
        "id": "bench_02",
        "name": "PIN Phishing Link (GH15)",
        "typology": "pin_phishing",
        "msisdn": "+233240000311",
        "event_type": EventType.SMS,
        "amount": 0,
        "payload": {"text": "MTN Notice: Click http://momo-gh-update.net/login and confirm your PIN immediately."},
        "history": [],
        "is_fraud": True,
        "estimated_loss": 2500,
    },
    {
        "id": "bench_03",
        "name": "SIM Swap Device Drain (GH18)",
        "typology": "sim_swap",
        "msisdn": "+233240000312",
        "event_type": EventType.TRANSACTION,
        "amount": 3500,
        "payload": {"type": "new_device_binding"},
        "history": [],
        "is_fraud": True,
        "estimated_loss": 3500,
    },
    {
        "id": "bench_04",
        "name": "Robocall Preconditioning (GH19)",
        "typology": "agent_fraud",
        "msisdn": "+233240000313",
        "event_type": EventType.VOICE,
        "amount": 0,
        "payload": {"transcript": "Official MTN security team calling to assist on your behalf with customer care."},
        "history": [
            {"event_type": "voice", "payload": {"duration_seconds": 40}},
            {"event_type": "voice", "payload": {"duration_seconds": 35}},
        ],
        "is_fraud": True,
        "estimated_loss": 5000,
    },
    {
        "id": "bench_05",
        "name": "Mule Chain Cash-Out (GH02)",
        "typology": "mule_chain",
        "msisdn": "+233240000314",
        "event_type": EventType.TRANSACTION,
        "amount": 4200,
        "payload": {"type": "transfer_out", "amount": 4200},
        "history": [{"payload": {"type": "credit", "amount": 4200}}],
        "is_fraud": True,
        "estimated_loss": 4200,
    },
    {
        "id": "bench_06",
        "name": "Fake Promo Fee Bait",
        "typology": "fake_promo",
        "msisdn": "+233240000315",
        "event_type": EventType.SMS,
        "amount": 0,
        "payload": {"text": "Congratulations winner! You won GHc 50,000 prize. Reply with your PIN immediately."},
        "history": [],
        "is_fraud": True,
        "estimated_loss": 1500,
    },
    {
        "id": "bench_07",
        "name": "Approve-To-Receive (GH16)",
        "typology": "rtp_abuse",
        "msisdn": "+233240000316",
        "event_type": EventType.SMS,
        "amount": 0,
        "payload": {"text": "Please approve the prompt on your phone right now to receive your refund credit of GHs 600."},
        "history": [],
        "is_fraud": True,
        "estimated_loss": 600,
    },
    {
        "id": "bench_08",
        "name": "Relative on New Number (GH19B)",
        "typology": "relative_impersonation",
        "msisdn": "+233240000317",
        "event_type": EventType.SMS,
        "amount": 0,
        "payload": {"text": "Mum, this is my new number. I had an accident and am in hospital, send emergency money and PIN."},
        "history": [],
        "is_fraud": True,
        "estimated_loss": 1800,
    },
    {
        "id": "bench_09",
        "name": "Structuring / Sub-limit (GH22)",
        "typology": "limit_splitting",
        "msisdn": "+233240000318",
        "event_type": EventType.TRANSACTION,
        "amount": 950,
        "payload": {"type": "transfer_out", "amount": 950},
        "history": [
            {"payload": {"type": "transfer_out", "amount": 900}},
            {"payload": {"type": "transfer_out", "amount": 920}},
        ],
        "is_fraud": True,
        "estimated_loss": 2800,
    },
    {
        "id": "bench_10",
        "name": "Call + USSD Co-occurrence",
        "typology": "call_cooccurrence",
        "msisdn": "+233240000319",
        "event_type": EventType.USSD,
        "amount": 0,
        "payload": {"ussd_input": "*170#"},
        "history": [{"event_type": "voice", "payload": {"status": "active"}}],
        "is_fraud": True,
        "estimated_loss": 3200,
    },
    {
        "id": "bench_11",
        "name": "Task Momentum Coercion",
        "typology": "pin_phishing",
        "msisdn": "+233240000320",
        "event_type": EventType.SMS,
        "amount": 0,
        "payload": {"text": "To complete your verification and avoid wallet suspension immediately, reply with your secret passcode."},
        "history": [],
        "is_fraud": True,
        "estimated_loss": 1200,
    },
    # Legitimate controls: must NOT be blocked
    {
        "id": "bench_12",
        "name": "School Fees Payment (Legitimate)",
        "typology": "legitimate_transfer",
        "msisdn": "+233240000350",
        "event_type": EventType.TRANSACTION,
        "amount": 1200,
        "payload": {"type": "transfer_out", "amount": 1200, "text": "Term 1 School fees for Kwesi"},
        "history": [],
        "is_fraud": False,
        "estimated_loss": 0,
    },
    {
        "id": "bench_13",
        "name": "Grocery Supermarket Pay (Legitimate)",
        "typology": "legitimate_transfer",
        "msisdn": "+233240000351",
        "event_type": EventType.TRANSACTION,
        "amount": 145,
        "payload": {"type": "transfer_out", "amount": 145, "text": "Melcom groceries receipt"},
        "history": [],
        "is_fraud": False,
        "estimated_loss": 0,
    },
    {
        "id": "bench_14",
        "name": "Benign Greeting Text (Legitimate)",
        "typology": "legitimate_sms",
        "msisdn": "+233240000352",
        "event_type": EventType.SMS,
        "amount": 0,
        "payload": {"text": "Hi Kofi, are we still having lunch at Osu at 1pm? Let me know."},
        "history": [],
        "is_fraud": False,
        "estimated_loss": 0,
    },
]


@router.post("/demo/benchmark")
async def run_fraud_benchmark():
    """Run local deterministic regression fixtures, not the InnoFemme simulator."""
    started_total = time.perf_counter()
    results = []
    stopped = 0
    held = 0
    got_through = 0
    false_positives = 0
    total_saved = 0

    for item in BENCHMARK_SCENARIOS:
        t0 = time.perf_counter()
        ev = SandboxEvent(
            event_id=item["id"],
            msisdn=item["msisdn"],
            event_type=item["event_type"],
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            payload=item["payload"],
        )
        score = 0
        fired = []
        for rule in RULES:
            pts, desc = rule(ev, item["history"])
            if pts > 0 and desc:
                score += pts
                fired.append(desc)

        tier = (
            RiskTier.HIGH
            if score >= settings.risk_threshold_high
            else RiskTier.MEDIUM
            if score >= settings.risk_threshold_medium
            else RiskTier.LOW
        )

        decision = "BLOCKED" if tier == RiskTier.HIGH else "WARNED" if tier == RiskTier.MEDIUM else "ALLOWED"
        lat = round((time.perf_counter() - t0) * 1000, 3)

        if item["is_fraud"]:
            if decision in ("BLOCKED", "WARNED"):
                stopped += 1
                total_saved += item["estimated_loss"]
            else:
                got_through += 1
        else:
            if decision == "BLOCKED":
                false_positives += 1

        results.append({
            "id": item["id"],
            "name": item["name"],
            "typology": item["typology"],
            "msisdn": item["msisdn"],
            "is_fraud": item["is_fraud"],
            "score": score,
            "tier": tier.value,
            "decision": decision,
            "rules_fired": fired,
            "latency_ms": lat,
            "estimated_loss_ghc": item["estimated_loss"],
        })

    total_time = round((time.perf_counter() - started_total) * 1000, 1)
    fraud_count = sum(1 for x in BENCHMARK_SCENARIOS if x["is_fraud"])
    legit_count = sum(1 for x in BENCHMARK_SCENARIOS if not x["is_fraud"])

    return {
        "summary": {
            "total_incidents": len(BENCHMARK_SCENARIOS),
            "fraud_scenarios": fraud_count,
            "legitimate_scenarios": legit_count,
            "stopped_count": stopped,
            "held_before_cashout": held,
            "got_through": got_through,
            "false_positives": false_positives,
            "precision": f"{round((stopped / (stopped + false_positives)) * 100, 1)}%",
            "recall": f"{round((stopped / fraud_count) * 100, 1)}%",
            "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / len(results), 1),
            "ghc_protected": total_saved,
            "benchmark_time_ms": total_time,
            "status": "COMPLETED",
            "measurement_scope": "local deterministic rule fixtures only; not end-to-end sandbox latency or judge scorecard",
        },
        "results": results,
        "scope": "Synthetic local rule-only regression fixtures; does not invoke the InnoFemme Fraud Simulator or optional network/LLM services.",
    }
