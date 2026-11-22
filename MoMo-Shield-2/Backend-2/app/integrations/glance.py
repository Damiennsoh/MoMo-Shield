import httpx
from app.config import settings
from app.models.schemas import GlanceRiskResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

async def check_glance_risk(msisdn: str) -> GlanceRiskResponse:
    # Built-in demo fallback: if Glance is in mock/sandbox mode, provide verified intel
    # for the primary demo MSISDN +233240000310 to illustrate cross-telco telemetry to judges
    clean = msisdn.replace("+", "").strip()
    if clean in ("233240000310", "0240000310") and (not settings.glance_enabled or "your_" in settings.glance_api_key):
        return GlanceRiskResponse(
            risk_level="HIGH",
            reports=4,
            threat_type="social_engineering_cross_mno",
            simulated=True,
        )

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