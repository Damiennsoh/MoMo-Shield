import asyncio
import hmac
import time
from uuid import UUID
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, List

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import settings
from app.engine.rules import RULES
from app.engine.state import global_window
from app.integrations.gemini import analyze_intent
from app.integrations.glance import check_glance_risk, report_fraud
from app.integrations.sandbox import intervene_sandbox
from app.integrations import mtn_momo
from app.models.schemas import AssessmentResult, RiskTier, SandboxEvent
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

    history = global_window.get_history(event.msisdn)
    global_window.add(event.msisdn, event.model_dump())

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
    # External lookups run concurrently to keep decision latency low.
    glance_task = asyncio.create_task(check_glance_risk(event.msisdn))
    intent_task = asyncio.create_task(analyze_intent(text_payload))
    glance_data, llm_intent = await asyncio.gather(glance_task, intent_task)

    if glance_data.risk_level == "HIGH":
        score += 40

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
    elif tier == RiskTier.MEDIUM:
        action = "WARNED"
        await intervene_sandbox(event.event_id, "PUSH_WARNING")

    result = AssessmentResult(
        event_id=event.event_id,
        msisdn=event.msisdn,
        event_type=event.event_type,
        risk_score=min(100, score),
        risk_tier=tier,
        triggered_rules=rules_fired,
        glance_status=f"{glance_data.risk_level} ({glance_data.reports} reports)",
        llm_intent=llm_intent,
        action_taken=action,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        timestamp=datetime.utcnow(),
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


@router.post("/demo/real-phone-action")
async def real_phone_action(action: str = Query("ring", description="ring | hangup | warn")):
    return await trigger_real_phone_bridge(action)

