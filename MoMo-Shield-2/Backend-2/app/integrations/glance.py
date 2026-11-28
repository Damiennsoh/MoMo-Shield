"""Rancard Glance cross-operator fraud intelligence client.

Two API surfaces share this client:

- Developer sandbox (default): ``{base}/msisdn/aggregates`` and
  ``{base}/flagged-msisdns/reports`` under
  ``/api/v1/developer/sandbox``. It only accepts fictional ``SYN-####``
  subjects and a fixed reason enum — real MSISDNs are rejected with
  ``INVALID_SYNTHETIC_SUBJECT`` by design.
- Institutional API (production): same shapes at ``/api/v1`` with an
  institutional key, accepting real MSISDNs. Detected by the base URL
  not containing ``/developer/sandbox``.

All calls fail open: any error returns UNKNOWN / False so the plug-in
budget is never spent on Glance availability.
"""
import re
import uuid

import httpx

from app.config import settings
from app.models.schemas import GlanceRiskResponse
from app.utils.logger import get_logger

log = get_logger(__name__)

_SYNTHETIC_SUBJECT = re.compile(r"^SYN-\d{4}$")

_REASON_MAP = (
    ("phish", "PHISHING"),
    ("impersonat", "IMPERSONATION"),
    ("account", "ACCOUNT_TAKEOVER"),
    ("takeover", "ACCOUNT_TAKEOVER"),
    ("pin", "ACCOUNT_TAKEOVER"),
    ("otp", "ACCOUNT_TAKEOVER"),
    ("sim", "ACCOUNT_TAKEOVER"),
)
_DEFAULT_REASON = "PAYMENT_REDIRECTION"


def _is_sandbox() -> bool:
    return "/developer/sandbox" in settings.glance_base_url


def _map_reason(threat_type: str) -> str:
    t = (threat_type or "").lower()
    for needle, reason in _REASON_MAP:
        if needle in t:
            return reason
    return _DEFAULT_REASON


async def check_glance_risk(msisdn: str) -> GlanceRiskResponse:
    if not settings.glance_enabled:
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)
    # The developer sandbox only models fictional SYN-#### subjects;
    # skip the guaranteed-400 call for real MSISDNs. Institutional keys
    # (non-sandbox base URL) accept any number.
    if _is_sandbox() and not _SYNTHETIC_SUBJECT.match(str(msisdn).strip()):
        return GlanceRiskResponse(risk_level="UNKNOWN", reports=0, threat_type="non-synthetic-subject")

    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.get(
                f"{settings.glance_base_url}/msisdn/aggregates",
                params={"msisdn": msisdn},
                headers={"X-API-Key": settings.glance_api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = ((data.get("data") or {}).get("items")) or []
                if not items:
                    return GlanceRiskResponse(risk_level="LOW", reports=0)
                top = items[0]
                explanation = top.get("explanation") or {}
                risk_level = str(explanation.get("riskLevel") or "UNKNOWN").upper()
                return GlanceRiskResponse(
                    risk_level=risk_level if risk_level in ("LOW", "MEDIUM", "HIGH") else "UNKNOWN",
                    reports=int(top.get("timesReported") or 0),
                    threat_type=top.get("msisdn"),
                )
            log.warning("Glance risk-check returned HTTP %s", resp.status_code)
    except Exception as e:
        log.warning(f"Glance API timeout/error: {e}")
    return GlanceRiskResponse(risk_level="UNKNOWN", reports=0)


async def report_fraud(msisdn: str, threat_type: str):
    if not settings.glance_enabled:
        return
    if _is_sandbox() and not _SYNTHETIC_SUBJECT.match(str(msisdn).strip()):
        log.debug("Glance dev sandbox rejects real MSISDNs; report skipped for %s", msisdn)
        return
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.post(
                f"{settings.glance_base_url}/flagged-msisdns/reports",
                json={"msisdn": msisdn, "reason": _map_reason(threat_type)},
                headers={
                    "X-API-Key": settings.glance_api_key,
                    "Idempotency-Key": str(uuid.uuid4()),
                },
            )
            if resp.status_code in (200, 201):
                log.info(f"Reported {msisdn} to Glance network.")
            else:
                log.warning("Glance report returned HTTP %s: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        log.error(f"Failed to report to Glance: {e}")
