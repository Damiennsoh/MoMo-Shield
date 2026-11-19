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
from pathlib import Path
from threading import Lock
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()
_EVENTS = deque(maxlen=100)
_NEXT_ID = 1
_EVENT_LOCK = Lock()
_ACTIVE_SIP_CHANNEL_ID: Optional[str] = None
_CALL_DECLINED = False
_HANGUP_TASK = None
_WARNING_TASK = None
DEMO_SIP_RING_SECONDS = 60
_AUDIO_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg"}
_AUDIO_ASSETS = {
    f"{stem}{suffix}"
    for stem in ("ring", "sms", "alert")
    for suffix in _AUDIO_MIME
}


async def _hangup_after_answer(channel_id: str, timeout: float = 65.0) -> dict:
    """Background task: let the call ring until the victim answers (channel
    state 'Up'), then end it. Gives up if the channel dies or times out."""
    global _ACTIVE_SIP_CHANNEL_ID
    base = _ari_base()
    deadline = time.monotonic() + timeout
    try:
        async with httpx.AsyncClient(timeout=2.0, auth=_ari_auth()) as client:
            while time.monotonic() < deadline:
                try:
                    response = await client.get(base + "/channels/" + channel_id)
                except Exception:
                    await asyncio.sleep(1.0)
                    continue
                if response.status_code == 404:
                    if _ACTIVE_SIP_CHANNEL_ID == channel_id:
                        _ACTIVE_SIP_CHANNEL_ID = None
                    return {"status": "already_ended", "channel_id": channel_id}
                if response.status_code == 200:
                    state = str(response.json().get("state") or "").lower()
                    if state == "up":
                        try:
                            await client.delete(base + "/channels/" + channel_id)
                        except Exception:
                            pass
                        if _ACTIVE_SIP_CHANNEL_ID == channel_id:
                            _ACTIVE_SIP_CHANNEL_ID = None
                        return {"status": "hangup_after_answer", "channel_id": channel_id}
                await asyncio.sleep(1.0)
    except Exception as exc:
        log.warning("Deferred SIP hangup failed: %s", exc)
    return {"status": "answer_timeout", "channel_id": channel_id}


def _schedule_hangup_after_answer() -> dict:
    """Schedule the answer-aware hangup for the active demo call, if any."""
    global _HANGUP_TASK
    channel_id = _ACTIVE_SIP_CHANNEL_ID
    if not channel_id:
        return {"status": "no_active_call"}
    if _HANGUP_TASK and not _HANGUP_TASK.done():
        return {"status": "already_pending", "channel_id": channel_id}
    _HANGUP_TASK = asyncio.create_task(_hangup_after_answer(channel_id))
    return {"status": "pending_answer", "channel_id": channel_id}


async def _deliver_warning_after_answer(channel_id: str, payload: dict,
                                        timeout: float = 65.0) -> dict:
    """Hold a HIGH-tier warning until the victim answers (or the ring window
    ends), then push it to handsets, notify Linphone by SIP MESSAGE, and end
    the call. The FraudOps dashboard shows its own alert independently."""
    global _ACTIVE_SIP_CHANNEL_ID
    base = _ari_base()
    deadline = time.monotonic() + timeout
    answered = False
    try:
        async with httpx.AsyncClient(timeout=2.0, auth=_ari_auth()) as client:
            while time.monotonic() < deadline:
                try:
                    response = await client.get(base + "/channels/" + channel_id)
                except Exception:
                    await asyncio.sleep(1.0)
                    continue
                if response.status_code == 404:
                    break
                if response.status_code == 200:
                    state = str(response.json().get("state") or "").lower()
                    if state == "up":
                        answered = True
                        try:
                            await client.delete(base + "/channels/" + channel_id)
                        except Exception:
                            pass
                        break
                await asyncio.sleep(1.0)
    except Exception as exc:
        log.warning("Answer-aware warning delivery failed: %s", exc)
    if _ACTIVE_SIP_CHANNEL_ID == channel_id:
        _ACTIVE_SIP_CHANNEL_ID = None
    if _CALL_DECLINED:
        return {"status": "suppressed", "suppressed": "call_declined",
                "answered": answered, "sip": None}
    event_id = _append_event(payload)
    warn_text = payload.get("warning_english") or payload.get("warning")
    sip = None
    if warn_text and await _endpoint_registered():
        sip = await _send_sip_message("MoMo Shield: " + warn_text[:300])
    return {"status": "delivered", "event_id": event_id,
            "answered": answered, "sip": sip}


def _schedule_warning_after_answer(payload: dict) -> dict:
    """Queue a warning so handset delivery waits for call pickup."""
    global _WARNING_TASK
    channel_id = _ACTIVE_SIP_CHANNEL_ID
    if not channel_id:
        return {"status": "no_active_call"}
    if _WARNING_TASK and not _WARNING_TASK.done():
        return {"status": "already_pending", "channel_id": channel_id}
    _WARNING_TASK = asyncio.create_task(
        _deliver_warning_after_answer(channel_id, payload))
    return {"status": "pending_answer", "channel_id": channel_id}


class DemoDeviceEvent(BaseModel):
    type: Literal["sms", "call", "screen", "warning", "reset"]
    scenario: str = Field(default="MoMo Shield synthetic demo", max_length=120)
    event_key: str = Field(default="", max_length=360)
    caller: str = Field(default="Unknown caller", max_length=80)
    message: str = Field(default="", max_length=1200)
    status: str = Field(default="", max_length=80)
    transcript: str = Field(default="", max_length=1200)
    warning: str = Field(default="", max_length=600)
    warning_english: str = Field(default="", max_length=800)
    suppress_audio: bool = False
    ussd_lines: list[str] = Field(default_factory=list, max_length=10)
    trigger_sip: bool = False
    sip_message: bool = False
    sip_hangup: bool = False


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




def _ari_base() -> str:
    base = settings.asterisk_ari_url.rstrip("/")
    return base if base.endswith("/ari") else base + "/ari"


def _ari_auth() -> tuple:
    return (settings.asterisk_ari_username, settings.asterisk_ari_password)


async def _endpoint_registered() -> bool:
    """True only when the fixed demo softphone has a live registration."""
    try:
        async with httpx.AsyncClient(timeout=2.0, auth=_ari_auth()) as client:
            response = await client.get(_ari_base() + "/endpoints/PJSIP/200")
        if response.status_code != 200:
            return False
        return bool(response.json().get("channel_ids"))
    except Exception:
        return False


async def _send_sip_message(body: str) -> dict:
    """Deliver a SIP MESSAGE to the registered demo softphone (text, not a call)."""
    try:
        async with httpx.AsyncClient(timeout=3.0, auth=_ari_auth()) as client:
            response = await client.post(_ari_base() + "/messages", json={
                "to": "PJSIP/200",
                "from": "MoMo Shield Demo <7000>",
                "body": body[:500],
            })
        if response.status_code in (200, 201, 202):
            return {"status": "sent", "message": "SIP text message sent to the demo softphone."}
        return {"status": "unavailable", "message": "Asterisk did not accept the SIP message."}
    except Exception as exc:
        log.warning("SIP MESSAGE send failed: %s", exc)
        return {"status": "unavailable", "message": "Asterisk did not accept the SIP message."}

async def _originate_demo_call() -> dict:
    """Ring only the explicitly configured PJSIP endpoint on the private PBX."""
    if not (settings.asterisk_ari_url and settings.asterisk_ari_username
            and settings.asterisk_ari_password):
        return {"status": "not_configured", "message": "Asterisk SIP calling is not configured."}
    base = _ari_base()
    if not await _endpoint_registered():
        return {"status": "unregistered",
                "message": "Demo softphone is not registered; using browser ringtone fallback."}
    channel_id = "momo-demo-" + uuid.uuid4().hex[:16]
    params = {
        "endpoint": "PJSIP/200",
        "extension": "s",
        "context": "momo-demo-outbound",
        "priority": 1,
        "callerId": "MoMo Shield Demo <7000>",
        "timeout": DEMO_SIP_RING_SECONDS,
        "channelId": channel_id,
    }
    try:
        async with httpx.AsyncClient(timeout=3.0, auth=(settings.asterisk_ari_username,
                                                        settings.asterisk_ari_password)) as client:
            response = await client.post(base + "/channels", params=params)
            response.raise_for_status()
        return {"status": "requested", "channel_id": channel_id,
                "message": "SIP call requested for the configured demo softphone."}
    except Exception as exc:
        log.warning("Local Asterisk call request failed: %s", exc)
        return {"status": "unavailable", "message": "Asterisk did not accept the local SIP call request."}


async def _hangup_demo_call() -> dict:
    """End only the active call created by this demo when FraudOps intervenes."""
    global _ACTIVE_SIP_CHANNEL_ID
    channel_id = _ACTIVE_SIP_CHANNEL_ID
    if not channel_id:
        return {"status": "no_active_call"}
    _ACTIVE_SIP_CHANNEL_ID = None
    if not (settings.asterisk_ari_url and settings.asterisk_ari_username
            and settings.asterisk_ari_password):
        return {"status": "not_configured"}
    base = settings.asterisk_ari_url.rstrip("/")
    if not base.endswith("/ari"):
        base += "/ari"
    try:
        async with httpx.AsyncClient(timeout=2.0, auth=(settings.asterisk_ari_username,
                                                        settings.asterisk_ari_password)) as client:
            response = await client.delete(base + "/channels/" + channel_id)
            if response.status_code == 404:
                return {"status": "already_ended", "channel_id": channel_id}
            response.raise_for_status()
        return {"status": "hangup_requested", "channel_id": channel_id}
    except Exception as exc:
        log.warning("Local Asterisk call termination failed: %s", exc)
        return {"status": "unavailable", "channel_id": channel_id}


@router.get("/demo-device", response_class=HTMLResponse)
async def demo_device_page():
    """Mobile-sized second-screen simulator. Token remains in the URL fragment."""
    return HTMLResponse(_PHONE_PAGE)


@router.get("/demo-device/audio/{asset_name}")
async def demo_device_audio(asset_name: str, authorization: Optional[str] = Header(default=None)):
    """Serve only known demo sounds to a token-authenticated handset browser."""
    token = authorization.removeprefix("Bearer ") if authorization else None
    _check_token(token)
    if asset_name not in _AUDIO_ASSETS:
        raise HTTPException(status_code=404, detail="Demo audio asset not found.")
    configured_dir = getattr(settings, "demo_device_audio_dir", "")
    asset_dir = (Path(configured_dir).expanduser() if configured_dir else
                 Path(__file__).resolve().parents[3] / "frontend" / "assets")
    path = asset_dir / asset_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Demo audio asset not found.")
    return FileResponse(path, media_type=_AUDIO_MIME[path.suffix.lower()],
                        headers={"Cache-Control": "private, max-age=3600"})


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
    global _ACTIVE_SIP_CHANNEL_ID
    token = authorization.removeprefix("Bearer ") if authorization else None
    _check_token(token)
    payload = event.model_dump(exclude={"trigger_sip"})
    if event.type == "call" and event.trigger_sip:
        # The handset keeps the visual call card but does not duplicate the
        # Linphone ringtone. If ARI rejects the request, a follow-up event
        # explicitly asks the handset to provide the browser ringtone.
        payload["sip_managed"] = True
    global _CALL_DECLINED
    if event.type == "reset":
        _CALL_DECLINED = False
    if event.type == "call" and event.trigger_sip:
        _CALL_DECLINED = False
    if event.type == "warning" and _CALL_DECLINED:
        # Victim declined the call: FraudOps still logs the alert, but the
        # handset stays silent — no warning sound or card for a declined call.
        return {"status": "suppressed", "suppressed": "call_declined", "sip": None}
    if (event.type == "warning" and event.sip_hangup
            and _ACTIVE_SIP_CHANNEL_ID and not _CALL_DECLINED):
        queued = _schedule_warning_after_answer(payload)
        if queued.get("status") == "pending_answer":
            return {"status": "queued", "sip": queued}
    event_id = _append_event(payload)
    sip = None
    if event.type == "call" and event.trigger_sip:
        sip = await _originate_demo_call()
        _ACTIVE_SIP_CHANNEL_ID = sip.get("channel_id") if sip.get("status") == "requested" else None
        if sip.get("status") != "requested":
            fallback = dict(payload, sip_managed=False, force_browser_ring=True)
            _append_event(fallback)
    elif event.type == "call" and event.sip_hangup:
        sip = _schedule_hangup_after_answer()
    elif event.type == "warning":
        if event.sip_hangup:
            sip = _schedule_hangup_after_answer()
        warn_text = event.warning_english or event.warning
        if warn_text and await _endpoint_registered():
            msg = await _send_sip_message("MoMo Shield: " + warn_text[:300])
            sip = sip or msg
    elif event.type == "sms" and event.sip_message:
        if await _endpoint_registered():
            sip = await _send_sip_message(f"MoMo Shield demo: {event.caller} — {event.message}")
        else:
            sip = {"status": "unregistered",
                   "message": "Demo softphone is not registered; handset shows the SMS only."}
    elif event.type == "reset" and _ACTIVE_SIP_CHANNEL_ID:
        sip = await _hangup_demo_call()
    return {"status": "published", "event_id": event_id, "sip": sip}


class CallActionRequest(BaseModel):
    action: Literal["answer", "decline", "end"]


@router.post("/demo-device/call-action")
async def demo_device_call_action(req: CallActionRequest,
                                  authorization: Optional[str] = Header(default=None)):
    """Handset Answer/Decline controls. Decline ends the SIP leg and suppresses
    the pending warning; Answer is acknowledged (assessment runs in parallel)."""
    global _CALL_DECLINED
    token = authorization.removeprefix("Bearer ") if authorization else None
    _check_token(token)
    if req.action == "decline":
        _CALL_DECLINED = True
        sip = await _hangup_demo_call()
        return {"status": "declined", "sip": sip}
    if req.action == "end":
        sip = await _hangup_demo_call()
        return {"status": "ended", "sip": sip}
    return {"status": "answered", "sip": None}


_PHONE_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MoMo Shield · Demo handset</title><style>
:root{color-scheme:dark;--bg:#0b1120;--panel:#111b2d;--line:#29384e;--yellow:#facc15}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#f8fafc;font:16px system-ui,-apple-system,Segoe UI,sans-serif;padding:18px;min-height:100vh}
header{max-width:460px;margin:0 auto 14px;color:#94a3b8;font-size:12px;letter-spacing:.08em;text-transform:uppercase}
.phone{max-width:460px;min-height:75vh;margin:auto;border:8px solid #334155;border-radius:32px;background:#020617;overflow:hidden;box-shadow:0 20px 60px #0008;display:flex;flex-direction:column}
.status{padding:13px 18px;background:#0f172a;display:flex;justify-content:space-between;font-size:12px;color:#cbd5e1}.screen{padding:18px;flex:1}.card{border:1px solid var(--line);background:var(--panel);border-radius:18px;padding:16px;margin:10px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.sms{border-radius:18px 18px 18px 4px;background:#1e293b}.label{color:var(--yellow);font-size:12px;font-weight:800;margin-bottom:8px}.call{text-align:center;padding:30px 16px}.avatar{font-size:42px;margin:12px}.warning{border:1px solid #ef4444;background:#450a0a;padding:16px;border-radius:14px;margin-top:16px;color:#fff}
.warning.large{font-size:1.3rem;line-height:1.6}.warning.large .label{font-size:1rem}.warning .actions{flex-wrap:wrap}.warning .actions button{min-height:48px}
.call.ended{border-color:#475569;opacity:.86}.call.ended .label{color:#fca5a5}
.actions{display:flex;gap:10px;margin-top:20px}.actions button,#connect{flex:1;border:0;border-radius:12px;padding:14px;font-weight:800;background:#15803d;color:white}.actions button:last-child{background:#b91c1c}#connect{display:block;width:100%;max-width:460px;margin:16px auto;background:#1d4ed8}.quiet{font-size:12px;color:#94a3b8;text-align:center;padding:12px}.connection{color:#facc15;font-size:13px;text-align:center}
</style></head><body><header>MoMo Shield · synthetic demo handset</header>
<main class="phone"><div class="status"><span>DEMO DEVICE</span><span id="clock">● Standby</span></div><section class="screen" id="screen"><div class="card" data-placeholder="waiting">Waiting for a scenario from the FraudOps dashboard.</div></section></main>
<button id="connect">Connect this demo handset and enable sound</button><div class="connection" id="connection">Not connected</div>
<div class="quiet">Synthetic simulation only. No cellular SMS or PSTN call is made. Browser answer buttons change only this screen; answer a separate SIP softphone to accept the local Asterisk call.</div>
<script>
const token=location.hash.startsWith('#token=')?decodeURIComponent(location.hash.slice(7)):'';
const screen=document.getElementById('screen'),status=document.getElementById('clock'),info=document.getElementById('connection'),button=document.getElementById('connect');
const audioFiles={sms:['sms.mp3','sms.wav'],call:['ring.mp3','ring.wav'],alert:['alert.mp3','alert.wav'],warning:[]};
const audioLimits={sms:1.8,call:6,alert:1.2,warning:15};
let audio=null,currentNodes=[],currentTimer=null,currentFinish=null,currentSoundKind='',playbackVersion=0;
let soundQueue=Promise.resolve(),warningPlayback=Promise.resolve(),warningInProgress=false;
const audioCache=new Map();
function node(tag,cls,text){const item=document.createElement(tag);if(cls)item.className=cls;item.textContent=text||'';return item;}
function stopPlayback(){
  playbackVersion++;if(currentTimer){clearTimeout(currentTimer);currentTimer=null;}
  for(const sound of currentNodes){try{sound.stop();}catch(_){}}
  currentNodes=[];if(window.speechSynthesis)window.speechSynthesis.cancel();
  const finish=currentFinish;currentFinish=null;currentSoundKind='';if(finish)finish();
}
function tone(pattern,kind){
  if(!audio)return Promise.resolve();const generation=playbackVersion;currentSoundKind=kind;
  return new Promise(resolve=>{
    let done=false;const finish=()=>{if(done)return;done=true;if(generation===playbackVersion){currentNodes=[];currentTimer=null;currentFinish=null;currentSoundKind='';}resolve();};currentFinish=finish;
    const now=audio.currentTime;let last=0;
    for(const [frequency,offset,duration] of pattern){const osc=audio.createOscillator(),gain=audio.createGain();osc.frequency.value=frequency;gain.gain.setValueAtTime(.0001,now+offset);gain.gain.exponentialRampToValueAtTime(.1,now+offset+.025);gain.gain.exponentialRampToValueAtTime(.0001,now+offset+duration);osc.connect(gain);gain.connect(audio.destination);osc.start(now+offset);osc.stop(now+offset+duration+.04);currentNodes.push(osc);last=Math.max(last,offset+duration+.05);}
    currentTimer=setTimeout(finish,last*1000);
  });
}
async function getBuffer(name){
  if(audioCache.has(name))return audioCache.get(name);
  const pending=(async()=>{try{const response=await fetch('/api/v1/demo-device/audio/'+encodeURIComponent(name),{headers:{Authorization:'Bearer '+token},cache:'force-cache'});if(!response.ok)return null;return await audio.decodeAudioData(await response.arrayBuffer());}catch(_){return null;}})();audioCache.set(name,pending);return pending;
}
function playBuffer(buffer,kind,generation){
  return new Promise(resolve=>{
    if(generation!==playbackVersion){resolve();return;}
    const source=audio.createBufferSource(),gain=audio.createGain(),limit=audioLimits[kind],seconds=Math.min(buffer.duration,limit),now=audio.currentTime;
    source.buffer=buffer;source.connect(gain);gain.connect(audio.destination);gain.gain.setValueAtTime(1,now);
    if(buffer.duration>seconds+.08){gain.gain.setValueAtTime(1,now+seconds-.08);gain.gain.linearRampToValueAtTime(.0001,now+seconds);}
    currentSoundKind=kind;currentNodes=[source];let done=false;
    const finish=()=>{if(done)return;done=true;if(generation===playbackVersion){if(currentTimer){clearTimeout(currentTimer);currentTimer=null;}currentNodes=[];currentFinish=null;currentSoundKind='';}resolve();};currentFinish=finish;source.onended=finish;
    source.start(0,0,seconds);currentTimer=setTimeout(()=>{try{source.stop();}catch(_){}finish();},seconds*1000);
  });
}
function speakEnglish(text,generation){
  if(generation!==playbackVersion||!text||!window.speechSynthesis||!window.SpeechSynthesisUtterance)return Promise.resolve(false);
  const spokenText=String(text||'').replace(/\bPIN\b/gi,'pin').replace(/\bOTP\b/gi,'one-time password');const utterance=new SpeechSynthesisUtterance(spokenText.slice(0,360));utterance.lang='en-GH';
  const voices=window.speechSynthesis.getVoices();const voice=voices.find(v=>v.lang.toLowerCase()==='en-gh')||voices.find(v=>v.lang.toLowerCase().startsWith('en-gb'))||voices.find(v=>v.lang.toLowerCase().startsWith('en-us'));if(voice)utterance.voice=voice;
  currentSoundKind='warning';return new Promise(resolve=>{let done=false;const finish=()=>{if(done)return;done=true;if(generation===playbackVersion){if(currentTimer){clearTimeout(currentTimer);currentTimer=null;}currentFinish=null;currentSoundKind='';}resolve(true);};currentFinish=finish;utterance.onend=finish;utterance.onerror=finish;window.speechSynthesis.speak(utterance);currentTimer=setTimeout(()=>{window.speechSynthesis.cancel();finish();},audioLimits.warning*1000);});
}
async function playOne(kind,text,generation){
  if(!audio||generation!==playbackVersion)return;
  for(const name of audioFiles[kind]||[]){const buffer=await getBuffer(name);if(generation!==playbackVersion)return;if(buffer)return await playBuffer(buffer,kind,generation);}
  if(kind==='warning'){
    const alert=await getBuffer('alert.wav');if(generation!==playbackVersion)return;
    if(alert)await playBuffer(alert,'alert',generation);else await tone([[880,0,.14],[880,.2,.14],[620,.42,.24]],'alert');
    if(generation!==playbackVersion)return;
    const spoken=await speakEnglish(text||'MoMo Shield demo guidance. Pause and verify through official support. Do not share your PIN or OTP.',generation);
    if(!spoken&&generation===playbackVersion)await tone([[880,0,.14],[880,.2,.14],[620,.42,.24]],'warning');
    return;
  }
  const patterns={sms:[[880,0,.11],[1175,.14,.16]],call:[[440,0,.36],[480,.4,.36],[440,.88,.36],[480,1.28,.36]],warning:[[880,0,.14],[880,.2,.14],[620,.42,.24]]};
  return await tone(patterns[kind]||patterns.warning,kind);
}
function queueSound(kind,text=''){
  if(kind==='call'||kind==='warning'){stopPlayback();soundQueue=Promise.resolve();}
  const generation=playbackVersion;const task=()=>playOne(kind,text,generation);
  soundQueue=soundQueue.then(task,task).catch(()=>{});
  if(kind==='warning'){warningInProgress=true;warningPlayback=soundQueue.finally(()=>{warningInProgress=false;});soundQueue=warningPlayback;}
  return soundQueue;
}
function add(card,eventKey=''){
  const placeholder=screen.querySelector('[data-placeholder="waiting"]');if(placeholder)placeholder.remove();
  if(eventKey){const previous=[...screen.querySelectorAll('[data-event-key]')].find(item=>item.dataset.eventKey===eventKey);card.dataset.eventKey=eventKey;if(previous){previous.replaceWith(card);return true;}}
  screen.append(card);while(screen.children.length>30)screen.firstElementChild.remove();return false;
}
async function draw(event){
  if(event.type==='reset'){
    if(warningInProgress)await warningPlayback;
    stopPlayback();soundQueue=Promise.resolve();const waiting=node('div','card','Waiting for a scenario from the FraudOps dashboard.');waiting.dataset.placeholder='waiting';screen.replaceChildren(waiting);status.textContent='● Ready';return;
  }
  if(event.type==='sms'){const card=node('article','card sms','');card.append(node('div','label',event.scenario||'Incoming message'),node('div','',event.caller||'MoMo'),node('div','',event.message||''));const updated=add(card,event.event_key||'');if(!updated)queueSound('sms');status.textContent='✉ New simulated message';return;}
  if(event.type==='call'){
    const callStatus=event.status||'Ringing',statusText=callStatus.toLowerCase(),missed=statusText.includes('missed'),ended=statusText.includes('ended')||statusText.includes('declined'),incoming=statusText.includes('incoming')||statusText.includes('ringing');
    const card=node('article','card call',''),title=missed?'MISSED CALL · SIMULATED':ended?'CALL ENDED · SIMULATED':incoming?'INCOMING CALL · SIMULATED':'CALL IN PROGRESS · SIMULATED';card.dataset.callStatus=callStatus;
    card.append(node('div','label',title),node('div','avatar','☎'),node('div','',event.caller||'Unknown caller'),node('div','quiet',event.sip_managed&&!event.force_browser_ring?'Linphone ringtone selected · browser ringtone suppressed':callStatus));
    if(incoming){const actions=node('div','actions',''),answer=node('button','','Answer (demo)'),decline=node('button','','Decline');const callAction=(action)=>{fetch('/api/v1/demo-device/call-action',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({action})}).catch(()=>{});};answer.onclick=()=>{callAction('answer');stopPlayback();status.textContent='Answered · simulated handset';};decline.onclick=()=>{callAction('decline');stopPlayback();status.textContent='Call declined · demo';};const end=node('button','','End call');end.onclick=()=>{callAction('end');stopPlayback();const lbl=card.querySelector('.label');if(lbl)lbl.textContent='CALL ENDED · USER ENDED';const act=card.querySelector('.actions');if(act)act.remove();status.textContent='Call ended by user';};actions.append(answer,decline,end);card.append(actions);}
    if(event.transcript)card.append(node('div','card',event.transcript));
    const updated=add(card,event.event_key||'');
    if(incoming&&(!updated||event.force_browser_ring)){if(event.sip_managed&&!event.force_browser_ring){stopPlayback();status.textContent='☎ Incoming call · Linphone audio';}else{queueSound('call');status.textContent='☎ Incoming call';}}
    else if(!incoming){stopPlayback();if(!ended&&!missed){const act=node('div','actions',''),end=node('button','','End call');end.onclick=()=>{fetch('/api/v1/demo-device/call-action',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({action:'end'})}).catch(()=>{});stopPlayback();const lbl=card.querySelector('.label');if(lbl)lbl.textContent='CALL ENDED · USER ENDED';act.remove();status.textContent='Call ended by user';};act.append(end);card.append(act);}}
    return;
  }
  if(event.type==='warning'){
    for(const activeCall of screen.querySelectorAll('.call[data-event-key]')){
      const priorStatus=(activeCall.dataset.callStatus||activeCall.querySelector('.quiet')?.textContent||'').toLowerCase();
      if(/missed|ended|declined/.test(priorStatus)||!/(incoming|ringing|on call|connected|answered)/.test(priorStatus))continue;
      activeCall.classList.add('ended');const callLabel=activeCall.querySelector('.label');if(callLabel)callLabel.textContent='CALL ENDED · FRAUD INTERVENTION';
      const callStatus=activeCall.querySelector('.quiet');if(callStatus)callStatus.textContent='Disconnected at simulated transaction hold';
      const actions=activeCall.querySelector('.actions');if(actions)actions.remove();
    }
    const card=node('article','warning','');card.setAttribute('role','alert');card.setAttribute('aria-live','assertive');card.setAttribute('aria-atomic','true');
    card.append(node('div','label','SAFETY GUIDANCE · SYNTHETIC DEMO'));
    const warningText=event.warning_english||event.warning||event.message||'Pause and verify through official support. Do not share a PIN or code.';
    card.append(node('div','',warningText));
    const controls=node('div','actions',''),read=node('button','','Read warning aloud'),stop=node('button','','Stop speech'),large=node('button','','Larger text');
    read.onclick=()=>{stopPlayback();speakEnglish(warningText,playbackVersion);};
    stop.onclick=()=>stopPlayback();
    large.setAttribute('aria-pressed','false');large.onclick=()=>{const enabled=card.classList.toggle('large');large.setAttribute('aria-pressed',String(enabled));large.textContent=enabled?'Standard text':'Larger text';};
    controls.append(read,stop,large);card.append(controls);
    if(event.suppress_audio)card.append(node('div','quiet','Browser speech muted to avoid competing with the local SIP call.'));
    const updated=add(card,event.event_key||((event.scenario||'')+'|warning'));
    if(!updated&&!event.suppress_audio)queueSound('warning',event.warning_english||event.warning||event.message||'');else if(event.suppress_audio)stopPlayback();
    status.textContent='⚠ Safety warning';return;
  }
  add(node('article','card',event.message||event.status||'Scenario update'),event.event_key||'');
}
async function connect(){
  if(!token){info.textContent='Missing access token. Reopen the handset link from the dashboard.';return;}
  button.disabled=true;button.textContent='Connecting…';
  try{audio=new(window.AudioContext||window.webkitAudioContext)();await audio.resume();const response=await fetch('/api/v1/demo-device/stream',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!response.ok)throw new Error('Access denied');
    info.textContent='Connected · waiting for scenario events';status.textContent='● Connected';const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
    while(true){const part=await reader.read();if(part.done)break;buffer+=decoder.decode(part.value,{stream:true});const blocks=buffer.split('\n\n');buffer=blocks.pop();for(const block of blocks){const line=block.split('\n').find(item=>item.startsWith('data: '));if(line){try{await draw(JSON.parse(line.slice(6)));}catch(_){}}}}
    throw new Error('Stream ended');
  }catch(_){info.textContent='Connection ended. Check Wi-Fi, token, and backend, then reconnect.';status.textContent='○ Disconnected';button.disabled=false;button.textContent='Reconnect and enable sound';}
}
button.addEventListener('click',connect);
</script></body></html>'''
