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

# Ghana numbering plan → carrier, used to pick which network API to call.
_CARRIER_BY_PREFIX = {
    "024": "mtn", "025": "mtn", "053": "mtn", "054": "mtn", "055": "mtn", "059": "mtn",
    "020": "telecel", "050": "telecel",
    "026": "at", "027": "at", "056": "at", "057": "at",
}


def _carrier_for_msisdn(msisdn: str) -> str:
    digits = "".join(ch for ch in str(msisdn) if ch.isdigit())
    if digits.startswith("233"):
        digits = "0" + digits[3:]
    return _CARRIER_BY_PREFIX.get(digits[:3], "mtn")


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
        """GET network/v1/subscribers/{number} — name, status, hasWallet."""
        carrier = _carrier_for_msisdn(msisdn)
        if not self.enabled:
            return {"msisdn": msisdn, "status": "UNCONFIGURED"}
        phone_number = str(msisdn).replace("+", "").strip()
        endpoint = f"{self.base_url}/network/{carrier}/v1/subscribers/{phone_number}"
        try:
            async with httpx.AsyncClient(timeout=0.75) as client:
                response = await client.get(endpoint, auth=(self.client_id, self.api_key))
                if response.status_code == 200:
                    data = response.json()
                    return {"msisdn": msisdn, "status": "OK", "profile": data,
                            "source": "innofemme_network_api"}
                log.warning("Subscriber lookup returned HTTP %s", response.status_code)
        except Exception as exc:
            log.warning("Subscriber lookup failed: %s", exc)
        return {"msisdn": msisdn, "status": "UNKNOWN"}

    async def send_ussd_push(self, msisdn: str, message: str, carrier: str | None = None) -> bool:
        """Proactive warning to a subscriber.

        The sandbox has no USSD-push primitive; the network SMS API
        (Hackathon Environment §3, same Basic credentials) is the real
        channel. Kept under the legacy name for existing callers.
        """
        carrier = (carrier or _carrier_for_msisdn(msisdn)).strip().lower()
        if carrier not in _ALLOWED_CARRIERS:
            return False
        if not self.enabled:
            log.info("[WARNING SMS NOT SENT — no network credentials] %s: %s", msisdn, message)
            return False
        phone_number = str(msisdn).replace("+", "").strip()
        endpoint = f"{self.base_url}/network/{carrier}/v1/sms/messages"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    endpoint,
                    json={"to": phone_number, "text": message[:160]},
                    auth=(self.client_id, self.api_key),
                )
                if response.status_code in (200, 201, 202):
                    return True
                log.warning("Warning SMS returned HTTP %s", response.status_code)
        except Exception as exc:
            log.warning("Warning SMS failed: %s", exc)
        return False


infofemme_client = InnoFemmeNetworkClient()
