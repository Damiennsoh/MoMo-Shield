import re

FRAUD_PATTERNS = {
    "authority_impersonation": [
        r"\bmtn agent\b", r"\bcustomer support\b",
        r"\bnetwork representative\b", r"\bbank staff\b"
    ],
    "urgency": [r"\bimmediately\b", r"\bright now\b", r"\burgent\b", r"\bwithin 5 minutes\b"],
    "threats": [r"\baccount (?:will be )?(?:blocked|suspended)\b", r"\blose access\b"],
    "credential_request": [
        r"\bsend (?:your )?otp\b", r"\bprovide (?:your )?pin\b",
        r"\bshare (?:your )?(?:otp|pin|verification code)\b",
        r"\bconfirm (?:the )?(?:otp|pin|code)\b"
    ],
    "financial_manipulation": [
        r"\byou have won\b", r"\bclaim your prize\b",
        r"\bunexpected payment\b", r"\bunclaimed refund\b"
    ],
    "financial_instruction": [
        r"\btransfer money\b", r"\bsend (?:your )?(?:money|funds)\b",
        r"\bdial (?:a )?code\b"
    ],
}


def detect_behaviours(text: str) -> list[str]:
    text = (text or "").lower()
    detected = []
    for behaviour, patterns in FRAUD_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            detected.append(behaviour)
    return detected
