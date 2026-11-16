from typing import Dict, Any, Optional

PIN_KEYWORDS = ["pin", "otp", "code", "password", "wo pin", "fa wo pin"]
AUTHORITY_KEYWORDS = ["mtn", "telecel", "head office", "customer care", "regulator"]
LOSS_KEYWORDS = ["block", "blocked", "problem", "lose", "anya problem"]

def keyword_intent(text: str) -> Optional[Dict[str, Any]]:
    lower = (text or "").lower()
    requested = next((kw for kw in PIN_KEYWORDS if kw in lower), None)
    has_auth = any(kw in lower for kw in AUTHORITY_KEYWORDS)
    has_loss = any(kw in lower for kw in LOSS_KEYWORDS)
    
    if not requested and not (has_auth and has_loss): return None
    
    pattern = "Authority + Loss Aversion" if has_auth and has_loss else ("Authority" if has_auth else "Loss Aversion")
    return {
        "pattern": pattern,
        "evidence_phrases": [kw for kw in PIN_KEYWORDS + AUTHORITY_KEYWORDS + LOSS_KEYWORDS if kw in lower],
        "requested_secret": requested.upper() if requested else None,
        "language_detected": "Twi/English Code-Switch",
        "suggested_warning": "Verify before sharing any code." if requested else None
    }