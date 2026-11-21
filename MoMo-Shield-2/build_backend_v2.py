import os
import zipfile
from pathlib import Path

BASE_DIR = Path("momo_shield_backend")

FILES = {
    "main.py": """\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.config import settings
from app.utils.logger import setup_logging

setup_logging()

app = FastAPI(
    title="MoMo Shield Intelligence Core",
    version="2.0.0",
    description="Enterprise Fraud Middleware for InnoFemme Sandbox & Rancard Glance",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "operational", "middleware": "MoMo Shield v2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
""",
    "requirements.txt": """\
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.2
pydantic-settings==2.5.2
httpx==0.27.2
websockets==13.1
python-dotenv==1.0.1
google-genai==0.3.0
""",
    ".env.example": """\
# Rancard Glance API
GLANCE_API_KEY=your_glance_sandbox_key
GLANCE_BASE_URL=https://api.glance.rancardmobility.com/v1

# Google Gemini API
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash-exp

# InnoFemme Sandbox
SANDBOX_API_KEY=your_sandbox_key
SANDBOX_BASE_URL=https://api.innofemme-sandbox.com/v1

# System
RISK_THRESHOLD_HIGH=75
RISK_THRESHOLD_MEDIUM=40
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
    "app/__init__.py": "",
    "app/config.py": """\
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    glance_api_key: str = ""
    glance_base_url: str = "https://api.glance.rancardmobility.com/v1"
    
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    
    sandbox_api_key: str = ""
    sandbox_base_url: str = "https://api.innofemme-sandbox.com/v1"
    
    risk_threshold_high: int = 75
    risk_threshold_medium: int = 40

    @property
    def glance_enabled(self) -> bool:
        return bool(self.glance_api_key) and "your_" not in self.glance_api_key

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key) and "your_" not in self.gemini_api_key

settings = Settings()
""",
    "app/models/__init__.py": "",
    "app/models/schemas.py": """\
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class EventType(str, Enum):
    USSD = "ussd"
    SMS = "sms"
    VOICE = "voice"
    TRANSACTION = "transaction"

class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class SandboxEvent(BaseModel):
    event_id: str
    msisdn: str
    event_type: EventType
    timestamp: datetime
    payload: Dict[str, Any]

class GlanceRiskResponse(BaseModel):
    risk_level: str = "UNKNOWN"
    reports: int = 0
    threat_type: Optional[str] = None

class AssessmentResult(BaseModel):
    event_id: str
    msisdn: str
    risk_score: int
    risk_tier: RiskTier
    triggered_rules: List[str]
    glance_status: Optional[str] = None
    llm_intent: Optional[str] = None
    action_taken: str
    timestamp: datetime
""",
    "app/engine/__init__.py": "",
    "app/engine/state.py": """\
from datetime import datetime, timedelta
from typing import Dict, List, Any
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
            cutoff = datetime.utcnow() - self._retention
            self._events[msisdn] = [e for e in self._events[msisdn] if e.get('timestamp', datetime.min) >= cutoff]

    def get_history(self, msisdn: str, within_minutes: int = 10) -> List[Any]:
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(minutes=within_minutes)
            return [e for e in self._events.get(msisdn, []) if e.get('timestamp', datetime.min) >= cutoff]

global_window = EventWindow()
""",
    "app/engine/rules.py": """\
from typing import List, Tuple
from app.models.schemas import SandboxEvent

def check_gh01_fake_credit(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if event.payload.get('type') == 'transfer_out' and event.payload.get('amount', 0) > 100:
        recent_credits = [e for e in history if e.get('payload', {}).get('type') == 'sms_credit' and not e.get('payload', {}).get('ledger_verified', True)]
        if recent_credits:
            return 40, "GH01: Unverified SMS credit followed by outbound transfer"
    return 0, ""

def check_gh18_device_takeover(event: SandboxEvent, history: List) -> Tuple[int, str]:
    if event.payload.get('type') == 'new_device_binding':
        return 50, "GH18: New device binding detected"
    return 0, ""

def check_velocity(history: List) -> Tuple[int, str]:
    if len(history) > 5:
        return 20, "High velocity: Multiple events in short window"
    return 0, ""

RULES = [check_gh01_fake_credit, check_gh18_device_takeover, check_velocity]
""",
    "app/integrations/__init__.py": "",
    "app/integrations/glance.py": """\
import httpx
from app.config import settings
from app.models.schemas import GlanceRiskResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

async def check_glance_risk(msisdn: str) -> GlanceRiskResponse:
    if not settings.glance_enabled:
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)
    
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.get(
                f"{settings.glance_base_url}/risk-check",
                params={"msisdn": msisdn},
                headers={"Authorization": f"Bearer {settings.glance_api_key}"}
            )
            if resp.status_code == 200:
                data = resp.json()
                return GlanceRiskResponse(
                    risk_level=data.get("risk_level", "UNKNOWN"),
                    reports=data.get("reports", 0),
                    threat_type=data.get("threat_type")
                )
    except Exception as e:
        log.warning(f"Glance API timeout/error: {e}")
    return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)

async def report_fraud(msisdn: str, threat_type: str):
    if not settings.glance_enabled: return
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.post(
                f"{settings.glance_base_url}/fraud-report",
                json={"msisdn": msisdn, "threat_type": threat_type},
                headers={"Authorization": f"Bearer {settings.glance_api_key}"}
            )
            log.info(f"Reported {msisdn} to Glance network.")
    except Exception as e:
        log.error(f"Failed to report to Glance: {e}")
""",
    "app/integrations/sandbox.py": """\
import httpx
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

async def intervene_sandbox(event_id: str, action: str):
    # Calls Sandbox API to block transaction or push USSD warning.
    if "your_" in settings.sandbox_api_key:
        log.info(f"[MOCK] Sandbox Intervention: {event_id} -> {action}")
        return
        
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                f"{settings.sandbox_base_url}/intervene",
                json={"event_id": event_id, "action": action},
                headers={"Authorization": f"Bearer {settings.sandbox_api_key}"}
            )
    except Exception as e:
        log.error(f"Sandbox intervention failed: {e}")
""",
    "app/integrations/gemini.py": """\
import asyncio
import json
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

async def analyze_intent(text: str) -> str:
    if not settings.gemini_enabled or not text:
        return "N/A"
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.gemini_api_key)
        
        prompt = f"Analyze this MoMo message for fraud intent. Return JSON: {{'pattern': str, 'secret_requested': bool}}. Text: {text}"
        
        def _call():
            return client.models.generate_content(
                model=settings.gemini_model, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )
            
        resp = await asyncio.wait_for(asyncio.to_thread(_call), timeout=1.5)
        data = json.loads(resp.text)
        return data.get('pattern', 'Unknown')
    except Exception as e:
        log.warning(f"Gemini failed: {e}")
        return "Fallback: Keyword Match"
""",
    "app/api/__init__.py": "",
    "app/api/routes.py": """\
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models.schemas import SandboxEvent, AssessmentResult, RiskTier
from app.engine.state import global_window
from app.engine.rules import RULES
from app.integrations.glance import check_glance_risk, report_fraud
from app.integrations.sandbox import intervene_sandbox
from app.integrations.gemini import analyze_intent
from app.utils.logger import get_logger
from datetime import datetime
import json

log = get_logger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)
    async def broadcast(self, data: dict):
        for conn in self.active_connections:
            try: await conn.send_json(data)
            except: pass

manager = ConnectionManager()

@router.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.post("/webhook/sandbox", response_model=AssessmentResult)
async def receive_sandbox_event(event: SandboxEvent):
    history = global_window.get_history(event.msisdn)
    global_window.add(event.msisdn, event.dict())

    score = 0
    rules_fired = []
    for rule in RULES:
        pts, desc = rule(event, history)
        if pts > 0:
            score += pts
            rules_fired.append(desc)

    glance_data = await check_glance_risk(event.msisdn)
    if glance_data.risk_level == "HIGH": score += 40
    
    text_payload = event.payload.get('text', event.payload.get('transcript', ''))
    llm_intent = await analyze_intent(text_payload)

    tier = RiskTier.HIGH if score >= 75 else (RiskTier.MEDIUM if score >= 40 else RiskTier.LOW)
    action = "ALLOWED"
    
    if tier == RiskTier.HIGH:
        action = "BLOCKED"
        await intervene_sandbox(event.event_id, "BLOCK_USSD")
        await report_fraud(event.msisdn, "Social Engineering")
    elif tier == RiskTier.MEDIUM:
        action = "WARNED"
        await intervene_sandbox(event.event_id, "PUSH_WARNING")

    result = AssessmentResult(
        event_id=event.event_id, msisdn=event.msisdn, risk_score=min(100, score),
        risk_tier=tier, triggered_rules=rules_fired, 
        glance_status=f"{glance_data.risk_level} ({glance_data.reports} reports)",
        llm_intent=llm_intent, action_taken=action, timestamp=datetime.utcnow()
    )

    await manager.broadcast(result.dict())
    
    return result
""",
    "app/utils/__init__.py": "",
    "app/utils/logger.py": """\
import logging
import sys
def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", stream=sys.stdout)
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
""",
    "README.md": """\
# MoMo Shield Intelligence Core v2.0
Enterprise Fraud Middleware integrating InnoFemme Sandbox & Rancard Glance.

## Setup
1. `pip install -r requirements.txt`
2. `cp .env.example .env` (Add your API keys)
3. `python main.py`

## Endpoints
- `POST /api/v1/webhook/sandbox`: Ingest events from Sandbox.
- `WS /api/v1/ws/telemetry`: Real-time feed for Next.js SOC Dashboard.
"""
}

def build():
    print("🚀 Building MoMo Shield Backend v2.0...")
    for filepath, content in FILES.items():
        full_path = BASE_DIR / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content.strip(), encoding="utf-8")
        print(f"  ✅ {filepath}")
    
    import shutil
    shutil.make_archive("momo_shield_backend", "zip", BASE_DIR.parent, BASE_DIR.name)
    print("\n🎉 SUCCESS! momo_shield_backend.zip created. Extract and run!")

if __name__ == "__main__":
    build()