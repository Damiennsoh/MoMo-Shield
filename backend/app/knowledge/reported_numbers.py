"""Demo 'previously reported scam number' blocklist.

These are SYNTHETIC numbers reserved for the demo (the +233 700 xxx xxx
range is not allocated for real subscribers). In production this list would
be fed by operator fraud reports, honeypots, and crowd-sourced flags — not
hand-written. A match is a strong signal, not proof of guilt.
"""

REPORTED_SCAM_MSISDNS = frozenset({
    "+233700000101",  # 'MTN Head Office' refund scammer
    "+233700000102",  # fake job/recruitment scammer
    "+233700000103",  # fake delivery/customs-fee scammer
    "+233700000104",  # romance-investment scammer
    "+233700000105",  # impersonated MoMo agent drain script
})


def normalize_msisdn(value: str | None) -> str | None:
    """Reduce a phone number to '+<country><subscriber>' digits for matching."""
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    # Ghana local format: 0XXXXXXXXX -> +233XXXXXXXXX
    if digits.startswith("0") and len(digits) == 10:
        digits = "233" + digits[1:]
    if len(digits) == 9:  # bare subscriber digits, assume Ghana
        digits = "233" + digits
    return "+" + digits if digits else None


def is_reported_number(value: str | None) -> bool:
    normalized = normalize_msisdn(value)
    return normalized in REPORTED_SCAM_MSISDNS if normalized else False
