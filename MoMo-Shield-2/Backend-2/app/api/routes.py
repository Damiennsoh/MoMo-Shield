import asyncio
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Deque, List

from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect

from app.config import settings
from app.engine.rules import RULES
from app.engine.state import global_window
from app.integrations.gemini import analyze_intent
from app.integrations.glance import check_glance_risk, report_fraud
from app.integrations.sandbox import intervene_sandbox
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
