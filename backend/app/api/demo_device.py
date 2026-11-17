"""Local-only second-device demo handset and optional SIP call bridge.

This module deliberately supports only synthetic in-app events and a single
configured SIP endpoint. It has no PSTN trunk or arbitrary-number dial route.
"""

import asyncio
import hmac
import json
import time
import uuid
from collections import deque
from threading import Lock
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()
_EVENTS = deque(maxlen=100)
_NEXT_ID = 1
_EVENT_LOCK = Lock()


class DemoDeviceEvent(BaseModel):
    type: Literal["sms", "call", "screen", "warning", "reset"]
    scenario: str = Field(default="MoMo Shield synthetic demo", max_length=120)
    caller: str = Field(default="Unknown caller", max_length=80)
    message: str = Field(default="", max_length=1200)
    status: str = Field(default="", max_length=80)
    transcript: str = Field(default="", max_length=1200)
    warning: str = Field(default="", max_length=600)
    ussd_lines: list[str] = Field(default_factory=list, max_length=10)
    trigger_sip: bool = False


def _check_token(value: Optional[str]) -> None:
    configured = settings.demo_device_token
    if not configured or not value or not hmac.compare_digest(value, configured):
        raise HTTPException(status_code=403, detail="Demo device access is disabled or the token is invalid.")


def _append_event(event: dict) -> int:
    global _NEXT_ID
    with _EVENT_LOCK:
        event_id = _NEXT_ID
        _NEXT_ID += 1
        _EVENTS.append({"id": event_id, "created": time.time(), "event": event})
    return event_id


def _events_after(cursor: int) -> tuple[int, list[dict]]:
    with _EVENT_LOCK:
        latest = _EVENTS[-1]["id"] if _EVENTS else 0
        return latest, [item for item in _EVENTS if item["id"] > cursor]


async def _originate_demo_call() -> dict:
    """Ring only the explicitly configured PJSIP endpoint on the private PBX."""
    if not (settings.asterisk_ari_url and settings.asterisk_ari_username
            and settings.asterisk_ari_password):
        return {"status": "not_configured", "message": "Asterisk SIP calling is not configured."}
    base = settings.asterisk_ari_url.rstrip("/")
    if not base.endswith("/ari"):
        base += "/ari"
    params = {
        "endpoint": "PJSIP/200",
        "extension": "s",
        "context": "momo-demo-outbound",
        "priority": 1,
        "callerId": "MoMo Shield Demo <7000>",
        "timeout": 20,
        "channelId": "momo-demo-" + uuid.uuid4().hex[:16],
    }
    try:
        async with httpx.AsyncClient(timeout=3.0, auth=(settings.asterisk_ari_username,
                                                        settings.asterisk_ari_password)) as client:
            response = await client.post(base + "/channels", params=params)
            response.raise_for_status()
        return {"status": "requested", "message": "SIP call requested for the configured demo softphone."}
    except Exception as exc:
        log.warning("Local Asterisk call request failed: %s", exc)
        return {"status": "unavailable", "message": "Asterisk did not accept the local SIP call request."}


@router.get("/demo-device", response_class=HTMLResponse)
async def demo_device_page():
    """Mobile-sized second-screen simulator. Token remains in the URL fragment."""
    return HTMLResponse(_PHONE_PAGE)


@router.get("/demo-device/stream")
async def demo_device_stream(authorization: Optional[str] = Header(default=None)):
    token = authorization.removeprefix("Bearer ") if authorization else None
    _check_token(token)

    async def events():
        cursor, _ = _events_after(0)
        last_keepalive = time.monotonic()
        while True:
            _, pending = _events_after(cursor)
            for item in pending:
                cursor = item["id"]
                payload = json.dumps(item["event"], ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\ndata: {payload}\n\n"
            now = time.monotonic()
            if now - last_keepalive >= 15:
                yield ": keepalive\n\n"
                last_keepalive = now
            await asyncio.sleep(0.25)

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@router.post("/demo-device/publish")
async def publish_demo_device_event(event: DemoDeviceEvent,
                                    authorization: Optional[str] = Header(default=None)):
    token = authorization.removeprefix("Bearer ") if authorization else None
    _check_token(token)
    event_id = _append_event(event.model_dump(exclude={"trigger_sip"}))
    sip = None
    if event.type == "call" and event.trigger_sip:
        sip = await _originate_demo_call()
    return {"status": "published", "event_id": event_id, "sip": sip}


_PHONE_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MoMo Shield · Demo handset</title><style>
:root{color-scheme:dark;--bg:#0b1120;--panel:#111b2d;--line:#29384e;--yellow:#facc15}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#f8fafc;font:16px system-ui,-apple-system,Segoe UI,sans-serif;padding:18px;min-height:100vh}
header{max-width:460px;margin:0 auto 14px;color:#94a3b8;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.phone{max-width:460px;min-height:75vh;margin:auto;border:8px solid #334155;border-radius:32px;background:#020617;overflow:hidden;box-shadow:0 20px 60px #0008;display:flex;flex-direction:column}
.status{padding:13px 18px;background:#0f172a;display:flex;justify-content:space-between;font-size:12px;color:#cbd5e1}.screen{padding:18px;flex:1}.card{border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:16px;margin:10px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.sms{border-radius:18px 18px 18px 4px;background:#1e293b}.label{color:var(--yellow);font-size:12px;font-weight:800;margin-bottom:8px}.call{text-align:center;padding:30px 16px}.avatar{font-size:42px;margin:12px}.warning{border:1px solid #ef4444;background:#450a0a;padding:16px;border-radius:14px;margin-top:16px;color:#fff}
.actions{display:flex;gap:10px;margin-top:20px}.actions button,#connect{flex:1;border:0;border-radius:12px;padding:14px;font-weight:800;background:#15803d;color:white}.actions button:last-child{background:#b91c1c}#connect{display:block;width:100%;max-width:460px;margin:16px auto;background:#1d4ed8}.quiet{font-size:12px;color:#94a3b8;text-align:center;padding:12px}.connection{color:#facc15;font-size:13px;text-align:center}
</style></head><body><header>MoMo Shield · synthetic demo handset</header>
<main class="phone"><div class="status"><span>DEMO DEVICE</span><span id="clock">● Standby</span></div><section class="screen" id="screen"><div class="card">Waiting for a scenario from the FraudOps dashboard.</div></section></main>
<button id="connect">Connect this demo handset and enable sound</button><div class="connection" id="connection">Not connected</div>
<div class="quiet">Synthetic simulation only. No cellular SMS or PSTN call is made. Browser answer buttons change only this screen; answer a separate SIP softphone to accept the local Asterisk call.</div>
<script>
const token=location.hash.startsWith('#token=')?decodeURIComponent(location.hash.slice(7)):'';
const screen=document.getElementById('screen'),status=document.getElementById('clock'),info=document.getElementById('connection'),button=document.getElementById('connect');
let audio=null;
function node(tag,cls,text){const item=document.createElement(tag);if(cls)item.className=cls;item.textContent=text||'';return item;}
function tone(pattern){if(!audio)return;const now=audio.currentTime;for(const [frequency,offset,duration] of pattern){const osc=audio.createOscillator(),gain=audio.createGain();osc.frequency.value=frequency;gain.gain.setValueAtTime(.0001,now+offset);gain.gain.exponentialRampToValueAtTime(.1,now+offset+.025);gain.gain.exponentialRampToValueAtTime(.0001,now+offset+duration);osc.connect(gain);gain.connect(audio.destination);osc.start(now+offset);osc.stop(now+offset+duration+.04);}}
function add(card){screen.append(card);while(screen.children.length>30)screen.firstElementChild.remove();}
function draw(event){
  if(event.type==='reset'){screen.replaceChildren(node('div','card','Waiting for a scenario from the FraudOps dashboard.'));status.textContent='● Ready';return;}
  if(event.type==='sms'){const card=node('article','card sms','');card.append(node('div','label',event.scenario||'Incoming message'),node('div','',event.caller||'MoMo'),node('div','',event.message||''));add(card);tone([[880,0,.10],[1175,.13,.12]]);status.textContent='✉ New simulated message';return;}
  if(event.type==='call'){const missed=(event.status||'').toLowerCase().includes('missed');const card=node('article','card call','');card.append(node('div','label',missed?'MISSED CALL · SIMULATED':'INCOMING CALL · SIMULATED'),node('div','avatar','☎'),node('div','',event.caller||'Unknown caller'),node('div','quiet',event.status||'Ringing'));
    if(!missed){const actions=node('div','actions',''),answer=node('button','','Answer (demo)'),decline=node('button','','Decline');answer.onclick=()=>{status.textContent='Answered · simulated handset';tone([[660,0,.12],[880,.18,.12]]);};decline.onclick=()=>{status.textContent='Call declined · demo';};actions.append(answer,decline);card.append(actions);tone([[440,0,.38],[480,.42,.38],[440,.9,.38],[480,1.32,.38]]);status.textContent='☎ Incoming call';}
    if(event.transcript)card.append(node('div','card',event.transcript));add(card);return;}
  if(event.type==='warning'){const card=node('article','warning','');card.append(node('div','label','FRAUD ALERT · SYNTHETIC DEMO'),node('div','',event.warning||event.message||'Verify before sharing a PIN or code.'));add(card);tone([[880,0,.14],[880,.2,.14],[620,.42,.24]]);status.textContent='⚠ Safety warning';return;}
  add(node('article','card',event.message||event.status||'Scenario update'));
}
async function connect(){
  if(!token){info.textContent='Missing access token. Reopen the handset link from the dashboard.';return;}
  button.disabled=true;button.textContent='Connecting…';
  try{audio=new(window.AudioContext||window.webkitAudioContext)();await audio.resume();const response=await fetch('/api/v1/demo-device/stream',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!response.ok)throw new Error('Access denied');
    info.textContent='Connected · waiting for scenario events';status.textContent='● Connected';const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
    while(true){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});const blocks=buffer.split('\n\n');buffer=blocks.pop();for(const block of blocks){const line=block.split('\n').find(item=>item.startsWith('data: '));if(line){try{draw(JSON.parse(line.slice(6)));}catch(_){}}}}
    throw new Error('Stream ended');
  }catch(_){info.textContent='Connection ended. Check Wi-Fi, token, and backend, then reconnect.';status.textContent='○ Disconnected';button.disabled=false;button.textContent='Reconnect and enable sound';}
}
button.addEventListener('click',connect);
</script></body></html>'''
