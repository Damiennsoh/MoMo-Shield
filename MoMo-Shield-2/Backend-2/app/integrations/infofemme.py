"""Optional InnoFemme network-edge client.

SIM-swap checks follow the carrier-scoped Basic-auth contract documented in
``docs/InnoFemme_Sandbox_API_and_Bridge_Guide.md``. This client fails open and
never labels locally seeded data as live network intelligence.
"""
from typing import Any, Dict

import httpx

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)
_ALLOWED_CARRIERS = {"mtn", "telecel", "at"}


class InnoFemmeNetworkClient:
    def __init__(self):
        self.base_url = settings.sandbox_base_url.rstrip("/")
        self.client_id = settings.sandbox_network_client_id
        self.api_key = settings.sandbox_network_api_key
        self.enabled = bool(self.client_id and self.api_key)

    async def get_sim_swap_history(self, msisdn: str, carrier: str = "mtn") -> Dict[str, Any]:
        """Query the carrier-scoped SIM-swap check endpoint."""
        normalized_carrier = str(carrier or "mtn").strip().lower()
        if normalized_carrier not in _ALLOWED_CARRIERS:
            return {"msisdn": msisdn, "status": "UNKNOWN", "risk_boost": 0}
        if not self.enabled:
            return {"msisdn": msisdn, "status": "UNCONFIGURED", "risk_boost": 0}

        phone_number = str(msisdn).replace("+", "").strip()
        endpoint = f"{self.base_url}/network/{normalized_carrier}/v1/sim-swap/check"
        try:
            async with httpx.AsyncClient(timeout=0.75) as client:
                response = await client.post(
                    endpoint,
                    json={"phoneNumber": phone_number, "maxAge": 48},
                    auth=(self.client_id, self.api_key),
                )
                if response.status_code == 200:
                    data = response.json()
                    swapped = bool(data.get("swapped", False))
                    return {
                        "msisdn": msisdn,
                        "sim_swapped": swapped,
                        "status": "SWAP_WITHIN_48H" if swapped else "CLEAN",
                        "risk_boost": 45 if swapped else 0,
                        "source": "innofemme_network_api",
                    }
                log.warning("InnoFemme SIM-swap check returned HTTP %s", response.status_code)
        except Exception as exc:
            log.warning("InnoFemme SIM-swap check failed: %s", exc)

        return {"msisdn": msisdn, "status": "UNKNOWN", "risk_boost": 0}

    async def get_subscriber_profile(self, msisdn: str) -> Dict[str, Any]:
        """Profile lookup is unavailable until its contract is verified."""
        return {"msisdn": msisdn, "status": "UNIMPLEMENTED"}

    async def send_ussd_push(self, msisdn: str, message: str) -> bool:
        """USSD push is outside this verified plug-in integration contract."""
        log.info("[USSD PUSH NOT SENT] %s: %s", msisdn, message)
        return False


infofemme_client = InnoFemmeNetworkClient()
