WEIGHTS = {
    "authority_impersonation": 25,
    "urgency": 10,
    "threats": 15,
    "account_suspension_threat": 15,
    "credential_request": 25,
    "otp_request": 25,
    "suspicious_transaction_context": 15,
    "unusual_transaction": 25,
    "new_device": 10,
    "known_fraud_match": 10,
}


def classify_risk(score: int) -> tuple[str, str]:
    if score >= 80:
        return "CRITICAL", "HOLD_FOR_VERIFICATION"
    if score >= 40:
        return "HIGH", "ADDITIONAL_VERIFICATION"
    if score >= 25:
        return "MEDIUM", "WARN"
    return "LOW", "ALLOW"


def calculate_risk(indicators: dict) -> dict:
    behaviours = set(indicators.get("detected_behaviours", []))
    score = sum(weight for name, weight in WEIGHTS.items() if indicators.get(name) or name in behaviours)

    if indicators.get("is_new_recipient"):
        score += WEIGHTS["suspicious_transaction_context"]
    if indicators.get("new_device"):
        score += WEIGHTS["new_device"]
    if indicators.get("known_fraud_match"):
        score += WEIGHTS["known_fraud_match"]

    score = min(100, score)
    level, action = classify_risk(score)
    return {
        "risk_score": score,
        "risk_level": level,
        "recommended_action": action,
    }
