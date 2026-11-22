from src.risk_engine import calculate_risk


def explain_decision(user_id: str, transaction_id: str, indicators: dict) -> dict:
    risk = calculate_risk(indicators)
    behaviours = indicators.get("detected_behaviours", [])
    reasons = []
    if "authority_impersonation" in behaviours:
        reasons.append("The communication claimed to represent a telecom or customer-support organisation.")
    if "threats" in behaviours or "account_suspension_threat" in behaviours:
        reasons.append("The communication threatened account suspension or loss of access.")
    if "credential_request" in behaviours or "otp_request" in indicators:
        reasons.append("An OTP or PIN request was detected.")
    if indicators.get("is_new_recipient"):
        reasons.append("The transfer was directed to an unfamiliar recipient.")
    if indicators.get("new_device"):
        reasons.append("The account showed a recently registered or changed device.")

    if not reasons:
        reasons.append("No strong suspicious indicators were identified.")

    return {
        "user_id": user_id,
        "transaction_id": transaction_id,
        **risk,
        "detected_behaviours": behaviours,
        "explanation": " ".join(reasons),
    }
