"""Ghana Card checks: local format/SIM heuristics plus an optional live
NIA registry verify against the InnoFemme sandbox (Hackathon Environment §6).
The live call fails open — a NIA outage must never block a plug-in decision."""
import re

import httpx

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

GHANA_CARD_REGEX = re.compile(r"^GHA-\d{9}-\d$", re.IGNORECASE)


class NIACheckResult:
    def __init__(self, is_valid_format: bool, sims_count: int, is_flagged: bool, reason: str = ""):
        self.is_valid_format = is_valid_format
        self.sims_count = sims_count
        self.is_flagged = is_flagged
        self.reason = reason


def evaluate_ghana_card(card_number: str | None, sims_count: int = 1) -> NIACheckResult:
    """Evaluate provided card formatting and local SIM-count heuristics only."""
    try:
        safe_sims_count = max(0, int(sims_count))
    except (TypeError, ValueError, OverflowError):
        safe_sims_count = 0

    clean_card = str(card_number or "").strip().upper()
    is_valid = bool(clean_card and GHANA_CARD_REGEX.fullmatch(clean_card))

    # Do not let missing card data hide a supplied high SIM count.
    if safe_sims_count >= 5:
        reason = f"NCA SIM Stacking Warning: {safe_sims_count} active SIM cards"
        if is_valid:
            reason += f" linked to Ghana Card {clean_card}"
        else:
            reason += " linked to supplied identity data"
        return NIACheckResult(is_valid, safe_sims_count, True, reason)

    if clean_card and not is_valid:
        return NIACheckResult(
            False, safe_sims_count, True, f"Invalid Ghana Card format: {clean_card}"
        )

    if not clean_card:
        return NIACheckResult(
            False, safe_sims_count, False, "No Ghana Card provided; format not checked"
        )

    return NIACheckResult(
        True,
        safe_sims_count,
        False,
        "Ghana Card format valid; no live NIA registry verification performed",
    )


async def verify_card_live(
    card_number: str | None,
    fingerprint: str | None = None,
    purpose: str = "fraud_check",
    timeout: float = 0.8,
) -> dict | None:
    """POST {sandbox}/nia/v1/verify — live NIA registry check.

    Returns the NIA response dict ({valid, biometricMatch?, person?}) or None
    when unconfigured/unreachable. Never raises: callers treat None as
    "no live verification available" and fall back to local heuristics.
    """
    clean_card = str(card_number or "").strip()
    if not clean_card or not settings.sandbox_team_key:
        return None
    payload: dict = {"cardNumber": clean_card}
    if fingerprint:
        payload["fingerprint"] = fingerprint
        payload["purpose"] = purpose
    endpoint = f"{settings.sandbox_base_url.rstrip('/')}/nia/v1/verify"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                endpoint, json=payload, headers={"x-team-key": settings.sandbox_team_key}
            )
            if response.status_code == 200:
                return response.json()
            log.warning("NIA verify returned HTTP %s", response.status_code)
    except Exception as exc:
        log.warning("NIA verify failed (fail-open): %s", exc)
    return None
