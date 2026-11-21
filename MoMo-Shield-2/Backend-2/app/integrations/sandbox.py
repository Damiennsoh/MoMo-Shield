import httpx
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

async def intervene_sandbox(event_id: str, action: str):
    # Calls Sandbox API to block transaction or push USSD warning.
    if not settings.sandbox_api_key or "your_" in settings.sandbox_api_key:
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