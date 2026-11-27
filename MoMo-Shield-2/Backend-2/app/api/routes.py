import asyncio
import hmac
import time
from uuid import UUID, uuid4
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Dict, List

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.config import settings
from app.engine.rules import RULES, looks_like_otp
from app.engine.state import global_window, sms_blast_window
from app.engine.kb import knowledge_base
from app.integrations.gemini import analyze_intent
from app.integrations.glance import check_glance_risk, report_fraud
from app.integrations.infofemme import infofemme_client
from app.integrations import local_threat_db
from app.integrations import ml_scorer
from app.integrations.fund_flow import fund_flow_ledger
from app.integrations.nia import evaluate_ghana_card, verify_card_live
from app.integrations.sandbox import intervene_sandbox
from app.integrations import mtn_momo
from app.models.schemas import AssessmentResult, EventType, RiskTier, SandboxEvent
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

ASSESSMENT_HISTORY: Deque[dict] = deque(maxlen=200)

# Rule-description markers that confirm scam typology — only these (plus
# Glance HIGH) justify writing a number into the local threat ledger.
_SCAM_MARKERS = (
    "credential-harvesting",
    "credential request",
    "unverified credit claim",
    "cross-channel precursor",
    "gh15",
    "gh16",
    "phishing link",
)


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


@router.get("/threat-ledger")
async def threat_ledger(limit: int = 50):
    """Ops view of the proprietary flagged-number ledger."""
    return {"entries": local_threat_db.list_entries(limit)}


@router.delete("/threat-ledger/{msisdn}")
async def exonerate_number(msisdn: str):
    """Appeal/override path: remove a number from the threat ledger."""
    removed = local_threat_db.remove(msisdn)
    if not removed:
        raise HTTPException(status_code=404, detail="Number not found in threat ledger")
    return {"removed": True, "msisdn": local_threat_db.normalize_msisdn(msisdn)}


def _node_role(stats: dict, flagged: bool) -> str:
    """Infer a forensic role from observed edge statistics."""
    if flagged:
        return "suspect"
    pay_in = stats["pay_in"]
    pay_out = stats["pay_out"]
    comms_out = stats["comms_out"]
    if pay_in >= 3 and pay_out >= 1:
        return "mule"
    if pay_in >= 3:
        return "collector"
    if comms_out >= 3 and pay_out == 0 and pay_in == 0:
        return "caller"
    if pay_out >= 2:
        return "payer"
    return "node"


def _build_fund_flow_graph(limit: int = 400) -> dict:
    """Cross-subscriber observed-relationship graph for Recovery Mode.

    Nodes are numbers/accounts seen in plug-in payloads; edges are directed
    observed relationships (sms, call, payment, payment_request, switch,
    bank_transfer) with amounts and interception decisions. Roles are
    heuristics over observed degree — they describe traffic shape, not
    verified identity.
    """
    edges = fund_flow_ledger.snapshot(limit)
    stats: dict = {}
    for e in edges:
        for endpoint in (e["src"], e["dst"]):
            s = stats.setdefault(endpoint, {
                "in": 0, "out": 0, "pay_in": 0, "pay_out": 0,
                "comms_out": 0, "volume": 0.0, "kinds": set(),
            })
            s["kinds"].add(e["kind"])
        s_src = stats[e["src"]]
        s_dst = stats[e["dst"]]
        s_src["out"] += 1
        s_dst["in"] += 1
        if e["kind"] in ("payment", "payment_request", "switch", "bank_transfer"):
            amt = e.get("amount") or 0
            s_src["pay_out"] += 1
            s_dst["pay_in"] += 1
            s_src["volume"] += amt
        elif e["kind"] in ("sms", "call"):
            s_src["comms_out"] += 1
    nodes = []
    for msisdn, s in stats.items():
        ledger = local_threat_db.check(msisdn)
        nodes.append({
            "id": msisdn,
            "role": _node_role(s, bool(ledger.get("found"))),
            "flagged": bool(ledger.get("found")),
            "in_count": s["in"],
            "out_count": s["out"],
            "pay_in": s["pay_in"],
            "pay_out": s["pay_out"],
            "volume": round(s["volume"], 2),
            "kinds": sorted(s["kinds"]),
            "ledger_reports": ledger.get("reports", 0),
        })
    return {
        "nodes": nodes,
        "edges": [
            {
                "from": e["src"], "to": e["dst"], "kind": e["kind"],
                "point": e["point"], "amount": e["amount"],
                "decision": e["decision"], "ts": e["iso"], "event_id": e["event_id"],
            }
            for e in edges
        ],
        "edge_count": len(edges),
        "node_count": len(nodes),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Observed plug-in events only — this deployment's telemetry, not the whole network.",
    }


@router.get("/fund-flow")
async def fund_flow_graph(limit: int = Query(400, ge=1, le=1000)):
    return _build_fund_flow_graph(limit)


@router.get("/velocity")
async def signal_velocity():
    """Real signal-velocity telemetry: observed event rate over time and
    the parties generating the most traffic right now.

    Two streams are merged: fund-flow edges (directed relationships) and
    assessment history (every scored event). Matching event IDs are counted
    once. Buckets are 1-minute over the last 15 minutes; burst is >=15 events
    in the current bucket, or >=8 and >=3x the 15-bucket median.
    """
    now = time.time()
    events: List[tuple] = []  # (epoch, kind_or_type, src, dst)
    flow_edges = fund_flow_ledger.snapshot(1000)
    flow_event_ids = {e.get("event_id") for e in flow_edges if e.get("event_id")}
    for e in flow_edges:
        events.append((e["ts"], e["kind"], e["src"], e["dst"]))
    for a in ASSESSMENT_HISTORY:
        if a.get("event_id") in flow_event_ids:
            continue
        ts = a.get("timestamp")
        epoch = None
        if isinstance(ts, datetime):
            epoch = ts.replace(tzinfo=timezone.utc).timestamp() if ts.tzinfo is None else ts.timestamp()
        elif isinstance(ts, str):
            try:
                epoch = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                epoch = None
        if epoch:
            events.append((epoch, str(a.get("event_type") or "event"), "", str(a.get("msisdn") or "")))

    window_start = now - 15 * 60
    recent = [e for e in events if e[0] >= window_start]
    buckets = [0] * 15
    for epoch, *_ in recent:
        idx = min(14, int((epoch - window_start) // 60))
        buckets[idx] += 1

    # Baseline = median across ALL 15 buckets (zeros included) so a
    # cold-start burst isn't masked by median==current. Absolute floor of
    # 15/min guarantees detection even with no prior baseline.
    median = sorted(buckets)[len(buckets) // 2]
    current = buckets[-1]
    burst = current >= 15 or (
        current >= 8 and median > 0 and current >= 3 * median
    )

    # Top talkers/payment originators in the last 10 minutes (edges only).
    cutoff10 = now - 10 * 60
    src_stats: dict = {}
    dst_stats: dict = {}
    for e in fund_flow_ledger.snapshot(1000):
        if e["ts"] < cutoff10:
            continue
        s = src_stats.setdefault(e["src"], {"events": 0, "payments": 0, "kinds": set()})
        s["events"] += 1
        s["kinds"].add(e["kind"])
        if e["kind"] in ("payment", "payment_request", "switch", "bank_transfer"):
            s["payments"] += 1
        d = dst_stats.setdefault(e["dst"], {"events": 0, "payments": 0, "kinds": set()})
        d["events"] += 1
        d["kinds"].add(e["kind"])
        if e["kind"] in ("payment", "payment_request", "switch", "bank_transfer"):
            d["payments"] += 1

    def _top(stats: dict, n: int = 4) -> list:
        return [
            {
                "msisdn": k,
                "events": v["events"],
                "payments": v["payments"],
                "kinds": sorted(v["kinds"]),
            }
            for k, v in sorted(stats.items(), key=lambda kv: -kv[1]["events"])[:n]
        ]

    return {
        "window_minutes": 15,
        "buckets": [
            {
                "minute_ago": 14 - i,
                "label": time.strftime("%H:%M", time.gmtime(window_start + i * 60)),
                "count": c,
            }
            for i, c in enumerate(buckets)
        ],
        "events_last_10m": sum(1 for e in events if e[0] >= cutoff10),
        "current_per_minute": current,
        "median_per_minute": median,
        "burst_detected": burst,
        "top_sources": _top(src_stats),
        "top_destinations": _top(dst_stats),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Recent in-memory observations from this deployment; matching flow edges and assessments are counted once. Not network-wide telemetry.",
    }


@router.get("/evidence-pack/{msisdn}")
async def evidence_pack(msisdn: str):
    """Post-incident forensic package for one number.

    Assembles everything this deployment observed about a suspect:
    ledger standing, directed fund-flow trail, linked assessments, and
    live identity/intel lookups where credentials exist. Everything is
    labeled by provenance — event-supplied claims vs verified lookups —
    so the pack is honest about what it does and does not prove.
    """
    target = local_threat_db.normalize_msisdn(msisdn)
    if not target:
        raise HTTPException(status_code=422, detail="Invalid MSISDN")

    edges = fund_flow_ledger.edges_for(target, limit=300)
    ledger_entry = local_threat_db.check(target)
    edge_event_ids = {e["event_id"] for e in edges}
    related = [
        a for a in ASSESSMENT_HISTORY
        if a.get("event_id") in edge_event_ids or a.get("msisdn") == target
    ][-50:]

    # Live lookups are best-effort and bounded; unconfigured integrations
    # report their status honestly instead of fabricating data.
    glance_task = asyncio.create_task(check_glance_risk(target))
    sim_task = asyncio.create_task(infofemme_client.get_sim_swap_history(target))
    profile_task = asyncio.create_task(infofemme_client.get_subscriber_profile(target))
    done, pending = await asyncio.wait(
        {glance_task, sim_task, profile_task}, timeout=1.5,
        return_when=asyncio.ALL_COMPLETED,
    )
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    def _res(task, default):
        if task not in done:
            return {"status": "timeout"}
        try:
            return task.result() or default
        except Exception:
            return {"status": "error"}

    glance_raw = _res(glance_task, {"risk_level": "UNKNOWN", "reports": 0})
    glance_res = (
        glance_raw.model_dump() if hasattr(glance_raw, "model_dump") else dict(glance_raw)
    )
    glance_res["configured"] = bool(settings.glance_enabled)
    sim_res = _res(sim_task, {"status": "UNKNOWN"})
    sim_res["configured"] = infofemme_client.enabled
    profile_res = _res(profile_task, {"status": "UNKNOWN"})
    profile_res["configured"] = infofemme_client.enabled

    volume = sum(e["amount"] or 0 for e in edges if e["kind"] in ("payment", "switch", "bank_transfer", "payment_request"))
    blocked = sum(1 for e in edges if str(e["decision"]).upper() in ("REJECT", "BLOCKED", "DELAY"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subject": {
            "msisdn": target,
            "ledger": ledger_entry if ledger_entry.get("found") else None,
        },
        "incident_summary": {
            "observed_edges": len(edges),
            "blocked_or_delayed": blocked,
            "observed_value_ghs": round(volume, 2),
            "first_seen": edges[0]["iso"] if edges else None,
            "last_seen": edges[-1]["iso"] if edges else None,
            "edge_kinds": sorted({e["kind"] for e in edges}),
        },
        "fund_trail": [
            {
                "ts": e["iso"], "kind": e["kind"], "point": e["point"],
                "direction": "outbound" if e["src"] == target else "inbound",
                "counterparty": e["dst"] if e["src"] == target else e["src"],
                "amount": e["amount"], "decision": e["decision"],
                "event_id": e["event_id"],
            }
            for e in edges
        ],
        "related_assessments": related,
        "identity_provenance": {
            "glance_risk_check": glance_res,
            "sim_swap_check": sim_res,
            "subscriber_profile": profile_res,
            "note": (
                "Entries marked configured:false are dormant pending sandbox "
                "credentials. Event-supplied fields (names, card numbers) are "
                "claims made by the sending institution, not independent "
                "verification. This pack is investigative evidence, not a "
                "substitute for lawful process."
            ),
        },
        "scope": "Derived solely from plug-in events observed by this deployment.",
    }


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

    # Fast in-memory semantic search over InnoFemme Fraud Case Corpus (< 2ms)
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
                rules_fired.append(f"RAG Knowledge Base ({top_kb.similarity:.0%} {kb_engine} match): Case Dossier {top_kb.case_id} - {top_kb.title}")
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

    # Proprietary threat ledger: repeat offenders known to our own DB.
    local_threat = local_threat_db.check(event.msisdn)
    if local_threat.get("found"):
        repeat_boost = 45 if _safe_float(local_threat.get("effective_reports")) >= 2 else 25
        score += repeat_boost
        rules_fired.append(
            f"Local threat ledger: known offender "
            f"({local_threat['reports']} confirmations, {local_threat.get('threat_type', 'fraud')})"
        )

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

    # Learning loop: persist scam-confirmed numbers to our own threat ledger.
    scam_marker = next(
        (m for m in _SCAM_MARKERS for r in rules_fired if m in r.lower()), ""
    )
    if getattr(glance_data, "risk_level", "") == "HIGH" or scam_marker:
        local_threat_db.record(
            event.msisdn,
            f"webhook:{event.event_type.value}:{scam_marker or 'glance-high'}",
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
    """Returns the precomputed InnoFemme Fraud Case Corpus."""
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
    fund_flow_ledger.clear()
    sms_blast_window.clear()
    _advisory_marks.clear()
    return {"status": "reset", "history_count": 0, "active_sessions": 0}


_OTP_ADVISORY_WINDOW_MIN = 15
_OTP_ADVISORY_MESSAGE = (
    "MoMo Shield: Never read a code to anyone on a call. Hang up now. "
    "MoMo: MMA obiara nka wo kɔde, fa kyɛrɛ."
)

# OTP read-out defense markers — kept OUT of EventWindow so they never
# pollute correlation history or event counts. msisdn -> [(epoch, kind)].
_advisory_marks: Dict[str, List[tuple]] = {}


def _mark_advisory(msisdn: str, kind: str) -> None:
    now = time.time()
    cutoff = now - _OTP_ADVISORY_WINDOW_MIN * 60
    marks = [(t, k) for t, k in _advisory_marks.get(msisdn, []) if t >= cutoff]
    marks.append((now, kind))
    _advisory_marks[msisdn] = marks


def _otp_advisory_state(msisdn: str) -> tuple[bool, bool]:
    """(risky flagged call fresh, advisory already sent) for this victim."""
    cutoff = time.time() - _OTP_ADVISORY_WINDOW_MIN * 60
    kinds = {k for t, k in _advisory_marks.get(msisdn, []) if t >= cutoff}
    return "risky_call" in kinds, "otp_advisory_sent" in kinds


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _norm_msisdn_local(value) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("233") and len(digits) == 12:
        digits = "0" + digits[3:]
    return digits


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


async def _kb_search_matches(text: str):
    """Hybrid KB retrieval bounded for the plug-in path.

    Semantic (Gemini embeddings) first; any failure or timeout degrades to
    the always-available lexical matcher.
    """
    try:
        return await asyncio.wait_for(
            knowledge_base.search_smart(text, top_k=1), timeout=0.5
        )
    except Exception:
        return knowledge_base.search(text, top_k=1)


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
        # Bank hooks carry party objects ({"msisdn": ...} / {"accountNumber": ...})
        # where telco hooks carry bare strings.
        if isinstance(candidate, dict):
            candidate = candidate.get("msisdn") or candidate.get("accountNumber")
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
            "paymentsToThisPayeeBefore": _safe_int(data.get("paymentsToThisPayeeBefore")),
            "payeeWalletOpenedAt": (payee.get("walletOpenedAt") if isinstance(payee, dict) else None),
            "payeeWalletType": (payee.get("walletType") if isinstance(payee, dict) else None),
            "payerKycTier": payer.get("kycTier") or (customer.get("kycTier") if isinstance(customer, dict) else None),
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
            "payeeWalletOpenedAt": (payee.get("walletOpenedAt") if isinstance(payee, dict) else None),
            "payeeWalletType": (payee.get("walletType") if isinstance(payee, dict) else None),
        }
    elif point == "payment.request":
        event_payload = {
            "type": "payment_request",
            "amount": data.get("amount", 0),
            "requester": data.get("requester"),
            "requestsFromThisRequesterToday": _safe_int(data.get("requestsFromThisRequesterToday")),
            "customerHasPaidThisRequesterBefore": data.get("customerHasPaidThisRequesterBefore"),
            "chargedWithoutAsking": bool(data.get("chargedWithoutAsking")),
        }
    elif point == "sim.swap":
        event_payload = {
            "type": "new_device_binding",
            "swapsOnThisNumberBefore": _safe_int(data.get("swapsOnThisNumberBefore")),
            "walletBalance": data.get("walletBalance"),
            "lastSimSwapAt": data.get("lastSimSwapAt") or data.get("previousSwapAt"),
            "replacedBy": data.get("replacedBy"),
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
        # Bank hooks name parties "from"/"to" (account/wallet objects), not
        # "payer"/"payee"/"toWallet" — observed in run_a3c439775d1649ad.
        to_wallet = data.get("to") if isinstance(data.get("to"), dict) else {}
        if not to_wallet:
            to_wallet = data.get("toWallet") if isinstance(data.get("toWallet"), dict) else {}
        from_party = data.get("from") if isinstance(data.get("from"), dict) else {}
        if not from_party:
            from_party = data.get("fromAccount") if isinstance(data.get("fromAccount"), dict) else data.get("fromAccount")
        opened_at = next(
            (to_wallet.get(k) for k in ("walletOpenedAt", "openedAt", "createdAt", "accountOpenedAt") if to_wallet.get(k)),
            None,
        ) or data.get("toWalletOpenedAt") or data.get("walletOpenedAt")
        event_payload = {
            "type": "transfer_out",
            "amount": data.get("amount", 0),
            "channel": "bank",
            "fromAccount": from_party or data.get("fromAccount"),
            "toWallet": to_wallet or data.get("toWallet"),
            "toWalletOpenedAt": opened_at,
            "payeeWalletOpenedAt": opened_at,
            "payeeWalletType": to_wallet.get("walletType"),
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
    # minutes corroborates fraud, but capped at +30 — legitimate bulk SMS
    # (school notices, promos) must never warn on blast volume alone.
    if point == "sms.deliver":
        victims = sms_blast_window.observe(str(event_payload.get("text") or ""), msisdn)
        if victims >= 8:
            score += 30
            rules_fired.append(f"SMS blast: identical text delivered to {victims} distinct subscribers in 10 min")
        elif victims >= 5:
            score += 25
            rules_fired.append(f"SMS blast: identical text delivered to {victims} distinct subscribers in 10 min")
        elif victims >= 3:
            score += 15
            rules_fired.append(f"SMS blast: identical text delivered to {victims} distinct subscribers in 10 min")

    # On-call co-occurrence bonus is applied AFTER the rules loop below:
    # menu.open maps to EventType.USSD, so check_call_ussd_cooccurrence (+50)
    # already fires on the same fact. Adding +40 here too double-counted it
    # into a reject — the observed false alarm on honest payments made
    # during calls. Dedup: only score onCallWith when no rule covered it.

    # Recency boost applies to *subsequent* activity after a swap — on
    # sim.swap itself the event IS the swap and lastSimSwapAt carries the
    # PREVIOUS swap time; scoring it would double-count and reject genuine
    # repeat replacements (observed false alarm: honest second swap).
    swap_ts = event_payload.get("lastSimSwapAt") or data.get("lastSimSwapAt")
    swap_dt = _parse_timestamp(swap_ts) if point != "sim.swap" else None
    if swap_dt is not None:
        age_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - swap_dt).total_seconds() / 3600
        if 0 <= age_hours <= 48:
            score += 45
            rules_fired.append(f"SIM Swap Recency: subscriber SIM changed {age_hours:.0f}h ago")

    # Paying the exact number the subscriber is on a call with — the
    # scammer directs the victim to send money to the caller's own line.
    # +30 stacks on the +45 co-occurrence signal toward reject.
    if point in ("payment.authorize", "payment.request", "transfer.authorize"):
        on_call = _norm_msisdn_local(event_payload.get("onCallWith") or data.get("onCallWith"))
        dest = ""
        if point == "transfer.authorize":
            tw = data.get("toWallet") if isinstance(data.get("toWallet"), dict) else {}
            dest = _norm_msisdn_local(tw.get("msisdn") or tw.get("wallet"))
        else:
            pe = data.get("payee") if isinstance(data.get("payee"), dict) else {}
            dest = _norm_msisdn_local(pe.get("msisdn"))
        if on_call and dest and on_call == dest:
            score += 30
            rules_fired.append("Paying active call party: payment destination is the number the subscriber is currently on a call with")

    # First-time / fresh-destination signals: mule wallets are opened
    # minutes before collection (observed: walletOpenedAt ~10s pre-payment).
    if point in ("payment.authorize", "transfer.authorize"):
        if "paymentsToThisPayeeBefore" in event_payload and event_payload.get("paymentsToThisPayeeBefore") == 0:
            score += 20
            rules_fired.append("First-time payee: subscriber has never paid this destination before")
            # Agent cash-out fraud (run_627eabbd): a complicit agent pulls
            # funds from a minimum-KYC customer who has never paid them.
            # Legit cash-outs come from customers with KYC history or prior
            # agent relationships — first-payee + agent walletType + lowest
            # KYC tier is the discriminating combo. Warn-tier on purpose:
            # honest first-time agent customers exist.
            if (
                str(event_payload.get("payeeWalletType") or "").lower() == "agent"
                and str(event_payload.get("payerKycTier") or "").lower()
                in ("basic", "minimum", "min", "tier1", "tier_1", "tier 1")
            ):
                score += 30
                rules_fired.append(
                    "First-time agent cash-out by minimum-KYC customer — "
                    "verify the agent initiated this with the customer present"
                )
        opened_raw = event_payload.get("payeeWalletOpenedAt") or event_payload.get("toWalletOpenedAt")
        opened_dt = _parse_timestamp(opened_raw)
        if opened_dt is not None:
            age_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - opened_dt).total_seconds() / 3600
            if 0 <= age_hours <= 24:
                score += 25
                rules_fired.append(f"Fresh payee wallet: destination opened {age_hours:.1f}h ago")
                # Unseasoned merchant wallets are the fake-shop pattern:
                # opened seconds before first victim payment, KYC enhanced
                # to look legitimate, forwards proceeds instantly.
                if str(event_payload.get("payeeWalletType") or "").lower() == "merchant" and age_hours <= 1:
                    score += 30
                    rules_fired.append("Unseasoned merchant wallet: merchant destination opened <1h ago")
                # Bank drain pattern (limit_splitting/mule_chain legs): a
                # large transfer into a minutes-old wallet, or one consuming
                # most of the account balance, is account-takeover drain —
                # stacks the fresh-wallet +25 toward reject (transfer.authorize
                # is not warn-capable, so MEDIUM alone would allow).
                if point == "transfer.authorize":
                    xfer_amount = _safe_float(event_payload.get("amount"))
                    if age_hours <= 1 and xfer_amount >= 1000:
                        score += 25
                        rules_fired.append(
                            f"Large transfer to minutes-old wallet: GHS {xfer_amount:,.0f} "
                            "to a destination opened under 1h ago"
                        )
                    # Ultra-fresh tier: wallets opened seconds before the
                    # transfer are mule hops minted for this exact leg
                    # (observed: 0.4s–7s). +25 stacks fresh+large to reject.
                    if age_hours * 3600 <= 300 and xfer_amount >= 1000:
                        score += 25
                        rules_fired.append(
                            f"Ultra-fresh wallet: destination opened "
                            f"{age_hours * 3600:.0f}s before a GHS {xfer_amount:,.0f} transfer"
                        )
                    from_acc = event_payload.get("fromAccount")
                    balance = _safe_float(from_acc.get("balance")) if isinstance(from_acc, dict) else 0.0
                    if balance > 0 and xfer_amount >= balance * 0.5 and xfer_amount >= 500:
                        score += 25
                        rules_fired.append(
                            f"Balance drain: GHS {xfer_amount:,.0f} consumes "
                            f"{xfer_amount / balance:.0%} of the source account balance"
                        )

    # Hook-specific payload signals documented in Hackathon Environment §4.
    if point == "payment.request":
        if event_payload.get("chargedWithoutAsking"):
            score += 40
            rules_fired.append("RTP abuse: merchant flagged as charging without subscriber consent")
        if event_payload.get("customerHasPaidThisRequesterBefore") is False:
            score += 20
            rules_fired.append("First-time requester: subscriber has never paid this requester before")
        if _safe_int(event_payload.get("requestsFromThisRequesterToday")) >= 5:
            score += 25
            rules_fired.append("RTP flood: requester has sent 5+ payment requests today")
    elif point == "payment.receive":
        if _safe_int(event_payload.get("differentPayersInLast24Hours")) >= 8:
            score += 20
            rules_fired.append("Mule inbound: 8+ distinct payers credited in 24h")
        recv_opened = _parse_timestamp(event_payload.get("payeeWalletOpenedAt"))
        if recv_opened is not None:
            recv_age_h = (datetime.now(timezone.utc).replace(tzinfo=None) - recv_opened).total_seconds() / 3600
            if 0 <= recv_age_h <= 1:
                score += 15
                rules_fired.append(f"Fresh receiving wallet: opened {recv_age_h * 60:.0f}min ago — mule-hop landing pattern")
    elif point == "sim.swap":
        if _safe_int(event_payload.get("swapsOnThisNumberBefore")) >= 1:
            score += 15
            rules_fired.append("Repeat SIM swap: number has been swapped before — mule/rotation pattern")
    elif point == "sim.register":
        if _safe_int(event_payload.get("simsAlreadyOnThisGhanaCard"), 1) >= 3:
            score += 25
            rules_fired.append("SIM sprawl: 3+ SIMs already registered on this Ghana Card — proxy/mule registration risk")
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

    # Mule-ring graph scoring: cross-subscriber fan-in/out observed in the
    # fund-flow ledger. A wallet receiving from many distinct payers and/or
    # fanning out to many payees inside an hour is a consolidation node —
    # invisible to per-subscriber windows. +25 warn-tier; stacks with
    # amount/velocity signals toward reject on payment points.
    if point in ("payment.authorize", "payment.receive", "payment.request",
                 "switch.route", "transfer.authorize"):
        mule = fund_flow_ledger.mule_stats(msisdn, window_seconds=3600)
        if mule["in_payers"] >= 5:
            score += 25
            rules_fired.append(
                f"Mule graph: {mule['in_payers']} distinct inbound payers in 1h "
                f"(GHS {mule['in_amount']:,.0f} collected) — fan-in consolidation"
            )
        if mule["out_payees"] >= 5:
            score += 20
            rules_fired.append(
                f"Mule graph: {mule['out_payees']} distinct outbound payees in 1h "
                f"(GHS {mule['out_amount']:,.0f} distributed) — fan-out layering"
            )
        # Pass-through hop: mule_chain wallets receive from 1–2 sources and
        # forward almost immediately — fan-in thresholds never reach 5.
        # In+out activity with near-equal volumes is the layering signature.
        if (
            mule["in_payers"] >= 2 and mule["out_payees"] >= 1
            and mule["in_amount"] > 0 and mule["out_amount"] >= mule["in_amount"] * 0.5
        ):
            score += 25
            rules_fired.append(
                f"Mule pass-through: collected GHS {mule['in_amount']:,.0f} from "
                f"{mule['in_payers']} payers and forwarded GHS {mule['out_amount']:,.0f} "
                "within 1h — layering hop"
            )

    for rule in RULES:
        points, description = rule(sandbox_event, history)
        if points > 0 and description:
            score += points
            rules_fired.append(description)

    # On-call co-occurrence fallback (+40): warn-tier signal. A scammer
    # keeps the victim on the line while walking them through approval —
    # but honest users also pay people they're talking to, so this alone
    # must never reach reject; it needs a second signal to stack past 75.
    # Skipped when a rule already scored call/USSD co-occurrence (menu.open
    # is EventType.USSD — the +50 rule covers the same fact).
    if point in ("payment.authorize", "menu.open", "wallet.open", "payment.request", "pin.reset") \
            and (event_payload.get("onCallWith") or data.get("onCallWith")) \
            and not any("co-occurrence" in r.lower() or "voice call" in r.lower() for r in rules_fired):
        score += 40
        rules_fired.append("Active Call Co-occurrence: subscriber is on an active call during a financial/USSD action")

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
    # KB retrieval runs concurrently with the intel lookups below — the
    # semantic embed (~300ms) hides inside the shared deadline instead of
    # serializing ahead of it. Bounded; lexical fallback on timeout.
    kb_task = (
        asyncio.create_task(_kb_search_matches(text_content))
        if text_content.strip()
        else None
    )

    # Check the suspicious party for SMS/calls, but the subscriber for wallet events.
    intel_msisdn = str(data.get("from") or msisdn) if point in ("sms.deliver", "call.connect") else msisdn
    # Proprietary threat ledger: sub-ms repeat-offender lookup on the
    # suspicious party — survives restarts and Glance outages.
    local_threat = local_threat_db.check(intel_msisdn)
    # Both optional lookups overlap and are bounded by one shared deadline.
    glance_task = asyncio.create_task(check_glance_risk(intel_msisdn))
    sim_task = asyncio.create_task(infofemme_client.get_sim_swap_history(msisdn, institution))
    # Live NIA registry verify only when the hook supplies a Ghana Card —
    # shares the same bounded deadline, fails open on any error.
    nia_task = (
        asyncio.create_task(verify_card_live(ghana_card))
        if ghana_card and settings.nia_live_enabled
        else None
    )
    lookup_tasks = {glance_task, sim_task} | ({nia_task} if nia_task else set()) | ({kb_task} if kb_task else set())
    timeout = min(max(settings.plugin_lookup_timeout_seconds, 0.05), 1.2)
    done, pending = await asyncio.wait(
        lookup_tasks, timeout=timeout, return_when=asyncio.ALL_COMPLETED
    )
    for task in pending:
        task.cancel()
    # Do NOT gather() the cancelled tasks: a stalled external connect can
    # take hundreds of ms to unwind, and awaiting it here would blow the
    # 2s plug-in budget. Let them die in the background; swallow late
    # exceptions via the done callback.
    for task in pending:
        task.add_done_callback(
            lambda t: None if t.cancelled() else t.exception()
        )
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

    # KB retrieval ran concurrently with the lookups; score its result here.
    if kb_task is not None and kb_task in done:
        try:
            kb_matches = kb_task.result()
        except Exception:
            kb_matches = knowledge_base.search(text_content, top_k=1)
        if kb_matches:
            top_kb = kb_matches[0]
            kb_engine = getattr(top_kb, "engine", "lexical")
            kb_match_data = {
                "case_id": top_kb.case_id,
                "title": top_kb.title,
                "typology": top_kb.typology,
                "similarity": top_kb.similarity,
                "is_benign": top_kb.is_benign,
                "psychological_levers": top_kb.psychological_levers,
                "source": top_kb.source,
                "engine": kb_engine,
            }
            fraud_floor = 0.72 if kb_engine == "semantic" else 0.40
            if not top_kb.is_benign and top_kb.similarity >= fraud_floor:
                score += int(top_kb.similarity * (40 if kb_engine == "semantic" else 50))
                rules_fired.append(f"RAG precedent ({top_kb.similarity:.0%} {kb_engine} match): {top_kb.title}")
            # A benign match is explanatory only; it never subtracts
            # points from deterministic fraud evidence.

    # Feature-flagged ML scorer: strictly corroborating — it may only add
    # points when deterministic rules/payload evidence already scored >0,
    # so a saturated model probability can never create suspicion alone.
    # Retrain on the real sandbox dataset + widen the hook-field mapping
    # before trusting its ranking (documented train/serve skew).
    if score > 0 and point in ("payment.authorize", "payment.receive",
                               "payment.request", "switch.route",
                               "transfer.authorize"):
        ml_result = await asyncio.to_thread(
            ml_scorer.score, point, data, msisdn
        )
        if ml_result and ml_result.get("points", 0) > 0:
            score += ml_result["points"]
            rules_fired.append(
                f"ML scorer (mock-trained ensemble): "
                f"p={ml_result['probability']:.2f} → +{ml_result['points']}"
            )

    glance_level = getattr(glance_data, "risk_level", "UNKNOWN")
    glance_reports = _safe_int(getattr(glance_data, "reports", 0))
    if glance_level == "HIGH":
        score += 40
        rules_fired.append(f"Glance cross-operator intelligence: HIGH ({glance_reports} reports)")
    elif glance_reports >= 2:
        score += 25
        rules_fired.append(f"Glance cross-operator intelligence: {glance_reports} prior reports")
    if local_threat.get("found"):
        repeat_boost = 45 if _safe_float(local_threat.get("effective_reports")) >= 2 else 25
        score += repeat_boost
        rules_fired.append(
            f"Local threat ledger: known offender "
            f"({local_threat['reports']} confirmations, {local_threat.get('threat_type', 'fraud')}, "
            f"first seen {local_threat.get('age_days', 0)}d ago)"
        )
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

    # OTP read-out defense, layer 1: a call judged risky leaves a marker so
    # a subsequent OTP SMS can trigger an advisory (side channel, not the
    # correlation window).
    if point == "call.connect" and decision in ("warn", "reject"):
        _mark_advisory(msisdn, "risky_call")

    # OTP read-out defense, layer 2: a genuine OTP SMS is NEVER scored or
    # blocked — it is legitimate operator traffic. But if it lands while a
    # flagged risky call is fresh, issue a bilingual advisory over the
    # warning channel and record it for telemetry.
    if point == "sms.deliver" and looks_like_otp(text_content, data.get("from")):
        risky_recent, advisory_sent = _otp_advisory_state(msisdn)
        if risky_recent and not advisory_sent:
            _mark_advisory(msisdn, "otp_advisory_sent")
            rules_fired.append(
                "OTP during flagged call: genuine OTP left untouched; "
                "bilingual read-out advisory issued to subscriber"
            )
            asyncio.create_task(
                infofemme_client.send_ussd_push(msisdn, _OTP_ADVISORY_MESSAGE)
            )

    # Learning loop: commit scam-confirmed suspicious parties to our own
    # ledger. Glance HIGH counts anywhere; content markers only on
    # sms/call where intel_msisdn is unambiguously the external party.
    scam_marker = next(
        (m for m in _SCAM_MARKERS for r in rules_fired if m in r.lower()), ""
    )
    if intel_msisdn and (
        glance_level == "HIGH"
        or (point in ("sms.deliver", "call.connect") and scam_marker)
    ):
        local_threat_db.record(intel_msisdn, f"{point}:{scam_marker or 'glance-high'}")

    # Forensic trail: record the observed directed relationship for
    # Recovery Mode (fund-flow graph + evidence pack). Post-decision data
    # only — never influences the verdict.
    fund_flow_ledger.observe(point, data, msisdn, decision, event_id)

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
    # OTP-class messages never leave the perimeter: zero fraud-intel value
    # to Gemini, maximum sensitivity under Act 843. Enrichment is skipped.
    is_otp = (
        point == "sms.deliver"
        and looks_like_otp(text_content, data.get("from"))
    )
    if text_content.strip() and not is_otp:
        asyncio.create_task(_enrich_plugin_assessment(event_id, text_content, point))

    if decision == "allow":
        return {"decision": "allow"}
    if decision == "delay":
        return {"decision": "delay", "minutes": 10, "message": message}
    return {"decision": decision, "message": message}

# Bound concurrent post-decision enrichment so a 55-incident simulator burst
# can't exhaust the Gemini quota or thread pool. Enrichment is best-effort;
# excess tasks queue briefly, then proceed — verdicts are never affected.
_ENRICH_SEMAPHORE = asyncio.Semaphore(4)


async def _enrich_plugin_assessment(event_id: str, text: str, point: str) -> None:
    """Runs after the plug-in decision is returned: semantic KB retrieval and
    Gemini intent grounded in the retrieved precedent, broadcast to telemetry."""
    try:
        await asyncio.wait_for(_ENRICH_SEMAPHORE.acquire(), timeout=8)
    except asyncio.TimeoutError:
        return  # queue saturated — drop stale enrichment, verdict unaffected
    try:
        await _enrich_plugin_assessment_inner(event_id, text, point)
    finally:
        _ENRICH_SEMAPHORE.release()


async def _enrich_plugin_assessment_inner(event_id: str, text: str, point: str) -> None:
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
