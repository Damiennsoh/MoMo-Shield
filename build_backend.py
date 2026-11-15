import os
import zipfile
from pathlib import Path

# Define the base directory
BASE_DIR = Path("backend_part2")

# Dictionary of all files and their contents
FILES = {
    "main.py": """\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.api.sandbox import router as sandbox_router
from app.config import settings
from app.utils.logger import setup_logging

setup_logging()

app = FastAPI(
    title="InnoFemme Track 1 — Fraud Detection Engine",
    version="1.0.0",
    description="Early detection of social engineering in mobile money ecosystems",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1/sandbox")

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "track1-fraud-detection", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
""",
    "requirements.txt": """\
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.5.2
google-genai==0.3.0
httpx==0.27.2
python-dotenv==1.0.1
pytest==8.3.3
""",
    ".env.example": """\
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TIMEOUT_SECONDS=2
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=["http://localhost:8501","http://127.0.0.1:8501"]
RISK_THRESHOLD_MEDIUM=40
RISK_THRESHOLD_HIGH=75
""",
    "Dockerfile": """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
    "README.md": """\
# InnoFemme Track 1 — Fraud Detection Engine (Backend)

## Quick Start
1. `pip install -r requirements.txt`
2. `cp .env.example .env` (Add your GEMINI_API_KEY)
3. `python main.py`

Server runs at `http://localhost:8000`. Frontend connects here.
""",
    "app/__init__.py": "",
    "app/config.py": """\
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_timeout_seconds: int = 2
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: List[str] = ["http://localhost:8501", "http://127.0.0.1:8501"]
    risk_threshold_medium: int = 40
    risk_threshold_high: int = 75

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key) and self.gemini_api_key != "your_gemini_api_key_here"

settings = Settings()
""",
    "app/models/__init__.py": "",
    "app/models/events.py": """\
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class EventType(str, Enum):
    TRANSACTION = "transaction"
    DEVICE_BINDING = "device_binding"
    COMMUNICATION = "communication"

class TransactionType(str, Enum):
    P2P_SEND = "P2P_SEND"
    CREDIT = "CREDIT"
    XTRACASH_LOAN = "XTRACASH_LOAN"
    USSD_SESSION = "USSD_SESSION"

class DeviceAction(str, Enum):
    APP_INSTALL = "APP_INSTALL"
    NEW_DEVICE_LOGIN = "NEW_DEVICE_LOGIN"
    SIM_SWAP = "SIM_SWAP"
    WALLET_ENROLMENT = "WALLET_ENROLMENT"

class ChannelType(str, Enum):
    SMS = "SMS"
    VOICE = "VOICE"

class TransactionEvent(BaseModel):
    event_id: str
    msisdn: str = Field(..., pattern=r"^\\\\+?[0-9]{9,15}$")
    event_type: EventType = EventType.TRANSACTION
    transaction_type: TransactionType
    amount: float = Field(ge=0)
    counterparty_msisdn: Optional[str] = None
    ledger_verified: bool
    ussd_session_active: bool = False
    timestamp: datetime

class DeviceBindingEvent(BaseModel):
    event_id: str
    msisdn: str = Field(..., pattern=r"^\\\\+?[0-9]{9,15}$")
    event_type: EventType = EventType.DEVICE_BINDING
    new_imei: str
    action: DeviceAction
    preceded_by_otp_activity: bool = False
    timestamp: datetime

class CommunicationEvent(BaseModel):
    event_id: str
    msisdn: str = Field(..., pattern=r"^\\\\+?[0-9]{9,15}$")
    event_type: EventType = EventType.COMMUNICATION
    channel: ChannelType
    text_or_transcript: str = Field(..., min_length=1, max_length=5000)
    counterparty_msisdn: Optional[str] = None
    timestamp: datetime

class AssessRequest(BaseModel):
    event: dict
    context: Optional[dict] = None

def parse_event(raw: dict):
    event_type = raw.get("event_type")
    if event_type == EventType.TRANSACTION.value:
        return TransactionEvent(**raw)
    if event_type == EventType.DEVICE_BINDING.value:
        return DeviceBindingEvent(**raw)
    if event_type == EventType.COMMUNICATION.value:
        return CommunicationEvent(**raw)
    raise ValueError(f"Unknown event_type: {event_type}")
""",
    "app/models/responses.py": """\
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
    recommended_action: str
    twi_warning_message: Optional[str] = None
    english_warning_message: Optional[str] = None
    event_id: str
    timestamp: datetime
""",
    "app/engine/__init__.py": "",
    "app/engine/state.py": """\
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict
import threading

class EventWindow:
    def __init__(self, retention_minutes: int = 30):
        self._events: Dict[str, List[Any]] = defaultdict(list)
        self._lock = threading.Lock()
        self._retention = timedelta(minutes=retention_minutes)

    def add(self, msisdn: str, event: Any) -> None:
        with self._lock:
            self._events[msisdn].append(event)
            self._prune(msisdn, cutoff=datetime.utcnow() - self._retention)

    def _prune(self, msisdn: str, cutoff: datetime) -> None:
        self._events[msisdn] = [e for e in self._events[msisdn] if getattr(e, "timestamp", datetime.min) >= cutoff]

    def get_events(self, msisdn: str, event_type: str = None, within: timedelta = None, before: datetime = None) -> List[Any]:
        with self._lock:
            events = list(self._events.get(msisdn, []))
        if before:
            events = [e for e in events if getattr(e, "timestamp", datetime.min) < before]
        if within and before:
            cutoff = before - within
            events = [e for e in events if getattr(e, "timestamp", datetime.min) >= cutoff]
        if event_type:
            events = [e for e in events if getattr(e, "event_type", None) and e.event_type.value == event_type]
        return events

global_window = EventWindow(retention_minutes=30)
""",
    "app/engine/rules.py": """\
from typing import Tuple, Optional, List
from datetime import timedelta
from app.models.events import TransactionEvent, DeviceBindingEvent, CommunicationEvent, TransactionType, DeviceAction
from app.engine.state import EventWindow

def rule_gh01_ledger_mismatch(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.transaction_type not in (TransactionType.P2P_SEND, TransactionType.USSD_SESSION):
        return 0, None
    recent_credits = window.get_events(msisdn=event.msisdn, event_type="transaction", within=timedelta(minutes=5), before=event.timestamp)
    unverified_credit = any(getattr(e, "transaction_type", None) == TransactionType.CREDIT and getattr(e, "ledger_verified", True) is False for e in recent_credits)
    if unverified_credit:
        return 30, "GH01: Unverified credit followed by outbound transfer"
    return 0, None

def rule_gh01_active_call(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.transaction_type != TransactionType.P2P_SEND:
        return 0, None
    recent_voice = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=3), before=event.timestamp)
    if any(getattr(e, "channel", None).value == "VOICE" for e in recent_voice):
        return 20, "GH01: Outbound transfer during active voice call"
    return 0, None

def rule_gh18_new_device(event: DeviceBindingEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if event.action in (DeviceAction.NEW_DEVICE_LOGIN, DeviceAction.WALLET_ENROLMENT, DeviceAction.SIM_SWAP):
        return 40, f"GH18: New device event — {event.action.value}"
    return 0, None

def rule_gh18_otp_activity(event: DeviceBindingEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    if not getattr(event, "preceded_by_otp_activity", False):
        return 0, None
    recent_comms = window.get_events(msisdn=event.msisdn, event_type="communication", within=timedelta(minutes=10), before=event.timestamp)
    if recent_comms:
        return 25, "GH18: Device binding preceded by OTP/credential activity"
    return 0, None

def rule_communication_pin_request(event: CommunicationEvent, llm_secret: Optional[str]) -> Tuple[int, Optional[str]]:
    secret = (llm_secret or "").lower()
    text = (event.text_or_transcript or "").lower()
    if any(kw in secret for kw in ("pin", "otp", "code")) or any(kw in text for kw in ("send your pin", "enter your pin", "fa wo pin")):
        return 30, "Credential request detected in communication"
    return 0, None

def rule_communication_authority(event: CommunicationEvent, llm_pattern: Optional[str]) -> Tuple[int, Optional[str]]:
    pattern = (llm_pattern or "").lower()
    if "authority" in pattern and ("loss" in pattern or "block" in pattern):
        return 20, "Authority + Loss Aversion psychological levers detected"
    return 0, None

def rule_baseline(event: TransactionEvent, window: EventWindow) -> Tuple[int, Optional[str]]:
    return 10, "Baseline: normal transaction telemetry"

TRANSACTION_RULES = [rule_gh01_ledger_mismatch, rule_gh01_active_call, rule_baseline]
DEVICE_RULES = [rule_gh18_new_device, rule_gh18_otp_activity]

def run_rules_for_event(event, window: EventWindow, llm_intent: dict = None) -> List[Tuple[int, str]]:
    llm_intent = llm_intent or {}
    results = []
    if isinstance(event, TransactionEvent):
        for rule in TRANSACTION_RULES:
            pts, desc = rule(event, window)
            if pts > 0 and desc: results.append((pts, desc))
    elif isinstance(event, DeviceBindingEvent):
        for rule in DEVICE_RULES:
            pts, desc = rule(event, window)
            if pts > 0 and desc: results.append((pts, desc))
    elif isinstance(event, CommunicationEvent):
        pts, desc = rule_communication_pin_request(event, llm_intent.get("requested_secret"))
        if pts > 0 and desc: results.append((pts, desc))
        pts, desc = rule_communication_authority(event, llm_intent.get("pattern"))
        if pts > 0 and desc: results.append((pts, desc))
    return results
""",
    "app/engine/scorer.py": """\
from datetime import datetime
from app.config import settings
from app.models.events import parse_event, CommunicationEvent
from app.models.responses import AssessResponse, TriggeredRule, LLMIntent
from app.engine.state import global_window
from app.engine.rules import run_rules_for_event
from app.ai.gemini_client import extract_intent
from app.utils.logger import get_logger

log = get_logger(__name__)

def _tier_from_score(score: int) -> str:
    if score >= settings.risk_threshold_high: return "HIGH"
    if score >= settings.risk_threshold_medium: return "MEDIUM"
    return "LOW"

def _action_from_tier(tier: str) -> str:
    return {"LOW": "SEAMLESS_APPROVE", "MEDIUM": "SOFT_WARNING", "HIGH": "SIMULATED_HOLD"}[tier]

def _twi_warning(tier: str, llm_intent: LLMIntent) -> str:
    if tier != "HIGH": return None
    if llm_intent and llm_intent.requested_secret:
        return "Wɔrehyɛ wo sɛ fa wo PIN kɔ ma! — Do not share your PIN."
    return "Yɛn hu sɛ obi rehyɛ wo ma ɛyɛ den. Fa ayɛ nkyerɛ."

async def assess(raw_event: dict) -> AssessResponse:
    event = parse_event(raw_event)
    global_window.add(event.msisdn, event)
    
    llm_intent = None
    llm_unavailable = False
    if isinstance(event, CommunicationEvent) and settings.gemini_enabled:
        try:
            raw_intent = await extract_intent(event.text_or_transcript)
            if raw_intent: llm_intent = LLMIntent(**raw_intent)
        except Exception as e:
            log.warning(f"Gemini failed, using fallback: {e}")
            llm_unavailable = True

    rule_results = run_rules_for_event(event, global_window, llm_intent.dict() if llm_intent else {})
    risk_score = min(100, sum(pts for pts, _ in rule_results))
    risk_tier = _tier_from_score(risk_score)
    
    triggered_rules = [TriggeredRule(rule_id=f"R{i+1}", description=desc, points=pts) for i, (pts, desc) in enumerate(rule_results)]

    return AssessResponse(
        msisdn=event.msisdn, risk_score=risk_score, risk_tier=risk_tier,
        triggered_rules=triggered_rules, llm_extracted_intent=llm_intent, llm_unavailable=llm_unavailable,
        recommended_action=_action_from_tier(risk_tier),
        twi_warning_message=_twi_warning(risk_tier, llm_intent),
        english_warning_message="⚠️ HIGH RISK: Transaction placed on simulated hold." if risk_tier == "HIGH" else None,
        event_id=event.event_id, timestamp=datetime.utcnow()
    )
""",
    "app/ai/__init__.py": "",
    "app/ai/prompts.py": """\
SYSTEM_PROMPT = \"\"\"You are a fraud-intent classifier for mobile money social engineering in Ghana.
Analyze SMS texts and voice-call transcripts to detect scam patterns. Scammers mix Twi/Akan and English.
Common phrases: "wo MoMo account no anya problem", "fa wo PIN kɔ ma", "E-Levy refund", "account will be blocked".
Return STRICT JSON matching the schema. If benign, return null values.\"\"\"

FEW_SHOT_EXAMPLES = [
    {"input": "Mepa wo kyɛw, wo MoMo account no anya problem. Fa wo PIN kɔ ma na yɛnsiesie.",
     "output": {"pattern": "Authority + Loss Aversion", "evidence_phrases": ["wo MoMo account no anya problem", "fa wo pin kɔ ma"], "requested_secret": "PIN", "language_detected": "Twi/English Code-Switch", "suggested_warning": "Wɔrehyɛ wo sɛ fa wo PIN kɔ ma!"}},
    {"input": "Hello, this is MTN head office. Your account will be blocked. Send your OTP now.",
     "output": {"pattern": "Authority + Loss Aversion", "evidence_phrases": ["mtn head office", "account will be blocked", "send your otp"], "requested_secret": "OTP", "language_detected": "English", "suggested_warning": "MTN will never ask for your OTP."}},
    {"input": "Hey, are we still meeting at the market tomorrow?",
     "output": {"pattern": None, "evidence_phrases": [], "requested_secret": None, "language_detected": "English", "suggested_warning": None}}
]

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pattern": {"type": ["STRING", "NULL"]},
        "evidence_phrases": {"type": "ARRAY", "items": {"type": "STRING"}},
        "requested_secret": {"type": ["STRING", "NULL"]},
        "language_detected": {"type": ["STRING", "NULL"]},
        "suggested_warning": {"type": ["STRING", "NULL"]}
    },
    "required": ["pattern", "evidence_phrases", "requested_secret", "language_detected", "suggested_warning"]
}
""",
    "app/ai/gemini_client.py": """\
import asyncio
import json
from typing import Optional, Dict, Any
from app.config import settings
from app.ai.prompts import SYSTEM_PROMPT, FEW_SHOT_EXAMPLES, RESPONSE_SCHEMA
from app.utils.logger import get_logger

log = get_logger(__name__)

async def extract_intent(text: str) -> Optional[Dict[str, Any]]:
    if not settings.gemini_enabled: return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    client = genai.Client(api_key=settings.gemini_api_key)
    examples_text = "\\n".join([f"Input: {ex['input']}\\nOutput: {ex['output']}" for ex in FEW_SHOT_EXAMPLES])
    full_prompt = f"{SYSTEM_PROMPT}\\n\\nExamples:\\n{examples_text}\\n\\nNOW ANALYZE THIS TEXT:\\n{text}\\nReturn ONLY JSON."

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model, contents=full_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RESPONSE_SCHEMA, temperature=0.1)
        )

    try:
        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=settings.gemini_timeout_seconds)
        return json.loads(response.text)
    except asyncio.TimeoutError:
        log.warning("Gemini call timed out")
        return None
    except Exception as e:
        log.warning(f"Gemini call failed: {e}")
        return None
""",
    "app/ai/fallback.py": """\
from typing import Dict, Any, Optional

PIN_KEYWORDS = ["pin", "otp", "code", "password", "wo pin", "fa wo pin"]
AUTHORITY_KEYWORDS = ["mtn", "telecel", "head office", "customer care", "regulator"]
LOSS_KEYWORDS = ["block", "blocked", "problem", "lose", "anya problem"]

def keyword_intent(text: str) -> Optional[Dict[str, Any]]:
    lower = (text or "").lower()
    requested = next((kw for kw in PIN_KEYWORDS if kw in lower), None)
    has_auth = any(kw in lower for kw in AUTHORITY_KEYWORDS)
    has_loss = any(kw in lower for kw in LOSS_KEYWORDS)
    
    if not requested and not (has_auth and has_loss): return None
    
    pattern = "Authority + Loss Aversion" if has_auth and has_loss else ("Authority" if has_auth else "Loss Aversion")
    return {
        "pattern": pattern,
        "evidence_phrases": [kw for kw in PIN_KEYWORDS + AUTHORITY_KEYWORDS + LOSS_KEYWORDS if kw in lower],
        "requested_secret": requested.upper() if requested else None,
        "language_detected": "Twi/English Code-Switch",
        "suggested_warning": "Verify before sharing any code." if requested else None
    }
""",
    "app/api/__init__.py": "",
    "app/api/routes.py": """\
from fastapi import APIRouter, HTTPException
from app.models.events import AssessRequest
from app.models.responses import AssessResponse
from app.engine.scorer import assess
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

@router.post("/assess", response_model=AssessResponse)
async def assess_event(req: AssessRequest):
    try:
        result = await assess(req.event)
        log.info(f"Assessed event {result.event_id}: score={result.risk_score} tier={result.risk_tier}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Unexpected error")
        raise HTTPException(status_code=500, detail="Internal assessment error")
""",
    "app/api/sandbox.py": """\
from fastapi import APIRouter, HTTPException
from app.engine.scorer import assess
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

@router.post("/webhook")
async def sandbox_webhook(payload: dict):
    try:
        event = payload.get("event") or payload.get("data") or payload
        result = await assess(event)
        return {"status": "processed", "event_id": result.event_id, "risk_score": result.risk_score, "risk_tier": result.risk_tier}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Sandbox webhook error")
        raise HTTPException(status_code=500, detail="Webhook processing error")
""",
    "app/utils/__init__.py": "",
    "app/utils/logger.py": """\
import logging
import sys

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
""",
    "fixtures/gh01_fake_credit.json": """\
{
  "scenario_name": "GH01 — Fabricated Credit → Fake Refund",
  "steps": [
    {
      "delay_seconds": 0,
      "event": {
        "event_id": "gh01-comm-1",
        "msisdn": "+233240000001",
        "event_type": "communication",
        "channel": "VOICE",
        "text_or_transcript": "Mepa wo kyɛw, wo MoMo account no anya problem. Fa wo PIN kɔ ma na yɛnsiesie.",
        "counterparty_msisdn": "+233500000099",
        "timestamp": "2026-11-28T10:00:00"
      }
    },
    {
      "delay_seconds": 2,
      "event": {
        "event_id": "gh01-tx-1",
        "msisdn": "+233240000001",
        "event_type": "transaction",
        "transaction_type": "CREDIT",
        "amount": 500.0,
        "ledger_verified": false,
        "timestamp": "2026-11-28T10:00:30"
      }
    },
    {
      "delay_seconds": 4,
      "event": {
        "event_id": "gh01-tx-2",
        "msisdn": "+233240000001",
        "event_type": "transaction",
        "transaction_type": "P2P_SEND",
        "amount": 500.0,
        "counterparty_msisdn": "+233500000099",
        "ledger_verified": true,
        "ussd_session_active": true,
        "timestamp": "2026-11-28T10:01:30"
      }
    }
  ]
}
""",
    "fixtures/gh18_device_takeover.json": """\
{
  "scenario_name": "GH18 — Cross-Device Wallet Takeover",
  "steps": [
    {
      "delay_seconds": 0,
      "event": {
        "event_id": "gh18-comm-1",
        "msisdn": "+233240000002",
        "event_type": "communication",
        "channel": "VOICE",
        "text_or_transcript": "Hello, this is MTN support. We need to verify your account. Please share the OTP sent to your phone.",
        "counterparty_msisdn": "+233500000088",
        "timestamp": "2026-11-28T11:00:00"
      }
    },
    {
      "delay_seconds": 3,
      "event": {
        "event_id": "gh18-dev-1",
        "msisdn": "+233240000002",
        "event_type": "device_binding",
        "new_imei": "353456789012345",
        "action": "WALLET_ENROLMENT",
        "preceded_by_otp_activity": true,
        "timestamp": "2026-11-28T11:02:00"
      }
    }
  ]
}
""",
    "fixtures/legitimate_baseline.json": """\
{
  "scenario_name": "Legitimate Baseline — Normal P2P Transfer",
  "steps": [
    {
      "delay_seconds": 0,
      "event": {
        "event_id": "legit-tx-1",
        "msisdn": "+233240000003",
        "event_type": "transaction",
        "transaction_type": "P2P_SEND",
        "amount": 50.0,
        "counterparty_msisdn": "+233240000099",
        "ledger_verified": true,
        "timestamp": "2026-11-28T12:00:00"
      }
    }
  ]
}
""",
    "tests/__init__.py": "",
    "tests/test_scorer.py": """\
import asyncio
import json
from pathlib import Path
from app.engine.scorer import assess

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())

def test_gh01_scores_high():
    fixture = _load("gh01_fake_credit.json")
    result = asyncio.run(assess(fixture["steps"][-1]["event"]))
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"
    assert result.recommended_action == "SIMULATED_HOLD"

def test_gh18_scores_high():
    fixture = _load("gh18_device_takeover.json")
    result = asyncio.run(assess(fixture["steps"][-1]["event"]))
    assert result.risk_score >= 75
    assert result.risk_tier == "HIGH"

def test_legitimate_scores_low():
    fixture = _load("legitimate_baseline.json")
    result = asyncio.run(assess(fixture["steps"][-1]["event"]))
    assert result.risk_score < 40
    assert result.risk_tier == "LOW"
    assert result.recommended_action == "SEAMLESS_APPROVE"
""",
    "tests/test_api.py": """\
import json
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_assess_endpoint_gh01():
    fixture = json.loads((FIXTURES_DIR / "gh01_fake_credit.json").read_text())
    r = client.post("/api/v1/assess", json={"event": fixture["steps"][-1]["event"]})
    assert r.status_code == 200
    body = r.json()
    assert body["risk_tier"] == "HIGH"
    assert body["recommended_action"] == "SIMULATED_HOLD"
"""
}

def build_backend():
    print("🚀 Building backend_part2/ directory...")
    
    # Create all files
    for filepath, content in FILES.items():
        full_path = BASE_DIR / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content.strip(), encoding="utf-8")
        print(f"  ✅ Created: {filepath}")
    
    print("\\n📦 Zipping backend_part2/ into backend_part2.zip...")
    import shutil
    shutil.make_archive("backend_part2", "zip", BASE_DIR.parent, BASE_DIR.name)
    print("🎉 SUCCESS! backend_part2.zip has been created in your current directory.")
    print("💡 You can now extract this zip file to your desktop and start building!")

if __name__ == "__main__":
    build_backend()