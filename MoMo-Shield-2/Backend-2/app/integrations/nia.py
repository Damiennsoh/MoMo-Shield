"""Local Ghana Card format and SIM-stacking heuristics (not a live NIA query)."""
import re

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
