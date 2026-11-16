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