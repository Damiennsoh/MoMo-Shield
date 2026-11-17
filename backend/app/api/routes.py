from fastapi import APIRouter, HTTPException
from app.models.events import AssessRequest
from app.models.responses import AssessResponse
from app.engine.scorer import assess
from app.engine.state import global_window
from app.config import settings
from app.ai.gemini_client import extract_intent
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

@router.post("/gemini/healthcheck")
async def gemini_healthcheck():
    """Make a real, minimal Gemini request to verify configured credentials/model."""
    if not settings.gemini_enabled:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_configured", "message": "Set GEMINI_API_KEY in backend/.env and restart the backend."},
        )
    try:
        result = await extract_intent("Connectivity test: the meeting starts at noon.")
        if not isinstance(result, dict) or "evidence_phrases" not in result:
            raise RuntimeError("Gemini returned an unexpected response shape")
        return {"status": "ok", "model": settings.gemini_model, "message": "Gemini API request succeeded."}
    except Exception as exc:
        log.warning("Gemini connectivity check failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"status": "error", "model": settings.gemini_model,
                    "message": "Gemini request failed. Check the API key, model access, network, and backend logs."},
        ) from exc

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

@router.post("/reset")
async def reset_state():
    global_window.reset()
    return {"status": "ok"}
