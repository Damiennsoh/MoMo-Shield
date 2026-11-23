"""Transparent keyword features for short, time-linked mobile-money messages."""

import re
from typing import Tuple

import pandas as pd


_PRIZE_RE = re.compile(r"\b(prize|won|winner|congratulations|promo|promotion)\b", re.I)
_URGENT_RE = re.compile(r"\b(urgent|urgently|now|immediately|asap)\b", re.I)
_CREDENTIAL_RE = re.compile(r"\b(pin|password|otp|verification code|secret code)\b", re.I)
_CREDIT_RE = re.compile(r"\b(received|credited|payment received|deposit)\b", re.I)
_AMOUNT_RE = re.compile(r"\b(?:GHS|GHC|GH¢)\s*([\d,]+(?:\.\d{1,2})?)", re.I)


def message_flags(body: object) -> Tuple[int, int, int, int, float]:
    """Return suspicious-language flags and any explicitly claimed GHS amount."""
    text = "" if pd.isna(body) else str(body)
    prize = bool(_PRIZE_RE.search(text))
    urgent = bool(_URGENT_RE.search(text))
    credential = bool(_CREDENTIAL_RE.search(text))
    amount_match = _AMOUNT_RE.search(text)
    claimed_amount = (
        float(amount_match.group(1).replace(",", "")) if amount_match else 0.0
    )
    return (
        int(prize or urgent or credential),
        int(prize),
        int(urgent),
        int(bool(_CREDIT_RE.search(text))),
        claimed_amount,
    )
