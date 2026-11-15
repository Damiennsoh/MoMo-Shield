from fastapi import APIRouter, HTTPException
from app.models.events import AssessRequest
from app.models.responses import AssessResponse
from app.engine.scorer import assess
from app.engine.state import global_window
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

@router.post("/reset")
async def reset_state():
    global_window.reset()
    return {"status": "ok"}