"""
National Identification Authority (NIA) Ghana Card Verification Client.
Implements identity integrity checks, Ghana Card format verification (GHA-XXXXXXXXX-X),
and NCA SIM Stacking rule evaluation (NCA limits: max 10 SIMs across all networks).
"""
import re
from typing import Dict, Any
from app.config import settings
from app.utils.logger import get_logger

log = get_logger("momo-shield.nia")

GHANA_CARD_REGEX = re.compile(r"^GHA-\d{9}-\d$", re.IGNORECASE)

class NIACheckResult:
    def __init__(self, is_valid_format: bool, sims_count: int, is_flagged: bool, reason: str = ""):
        self.is_valid_format = is_valid_format
        self.sims_count = sims_count
        self.is_flagged = is_flagged
        self.reason = reason

def evaluate_ghana_card(card_number: str | None, sims_count: int = 1) -> NIACheckResult:
    """
    Evaluates Ghana Card validity and SIM stacking risk.
    In Ghana, NCA limits individuals to max 10 SIMs. Syndicates often stack 5-8 SIMs in rapid succession.
    """
    if not card_number:
        return NIACheckResult(is_valid_format=False, sims_count=sims_count, is_flagged=False, reason="No Ghana Card provided")
    
    clean_card = card_number.strip().upper()
    is_valid = bool(GHANA_CARD_REGEX.match(clean_card))
    
    if not is_valid:
        return NIACheckResult(
            is_valid_format=False,
            sims_count=sims_count,
            is_flagged=True,
            reason=f"Invalid Ghana Card format: {clean_card}"
        )
    
    # Check SIM stacking: more than 4 SIMs registered on one card is high-risk threshold for fraud surveillance
    if sims_count >= 5:
        return NIACheckResult(
            is_valid_format=True,
            sims_count=sims_count,
            is_flagged=True,
            reason=f"NCA SIM Stacking Warning: {sims_count} active SIM cards linked to Ghana Card {clean_card}"
        )
        
    return NIACheckResult(
        is_valid_format=True,
        sims_count=sims_count,
        is_flagged=False,
        reason="Ghana Card verified. Registration volume normal."
    )
