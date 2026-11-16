# Offline deterministic rule engine - mirrors the backend scoring matrix.
# Used automatically when the FastAPI backend is unreachable (demo-day resilience).

from datetime import datetime


def new_accumulator() -> dict:
    # Per-session risk accumulator, keyed by MSISDN (mirrors backend state).
    return {}


def _add(score, rules, points, label):
    if label not in rules:
        rules.append(label)
    return score + points


def assess_local(event: dict, acc: dict):
    msisdn = event.get("msisdn", "unknown")
    prev = acc.get(msisdn, {"score": 0, "rules": [], "intent": None})
    score, rules = prev["score"], list(prev["rules"])
    intent = dict(prev["intent"]) if prev["intent"] else None

    et = event.get("event_type")

    if et == "transaction":
        if event.get("transaction_type") == "CREDIT" and event.get("ledger_verified") is False:
            score = _add(score, rules, 30,
                         "GH01: Unverified credit - core-ledger mismatch (fabricated credit SMS)")
        if event.get("transaction_type") == "P2P_SEND" and event.get("amount", 0) >= 400:
            score = _add(score, rules, 25,
                         "GH01: High-value outbound transfer immediately after inbound credit")
        if event.get("transaction_type") == "P2P_SEND" and event.get("counterparty_first_time"):
            score = _add(score, rules, 15, "First-time counterparty (watchlist)")
        if event.get("transaction_type") == "XTRACASH_LOAN":
            score = _add(score, rules, 25, "GH17: Overdraft/micro-loan activation draining wallet")
        # Trust baseline: a ledger-verified credit with no anomalies keeps
        # legitimate users friction-free (false-positive control).
        if score == 0 and event.get("ledger_verified") is True:
            score = 10
            rules = ["Baseline: ledger-verified credit - session trust established (no anomaly)"]

    elif et == "device_binding":
        action = (event.get("action") or "NEW_DEVICE").upper()
        pts = 45 if "SIM_SWAP" in action else 40
        score = _add(score, rules, pts,
                     "GH18: " + str(event.get("action", "new device binding")) + " - device-takeover pattern")

    elif et == "communication":
        txt = (event.get("text_or_transcript") or "").lower()
        for kw, pts, label in [
            ("pin", 30, "Language intent: credential request (MoMo PIN)"),
            ("otp", 20, "Language intent: OTP/code request"),
            ("code", 15, "Language intent: verification code request"),
            ("blocked", 20, "Language intent: loss-aversion threat (account blocked)"),
            ("refund", 15, "Language intent: refund/reversal pretext"),
            ("reverse", 20, "Language intent: reversal/forge pretext"),
            ("receipt", 15, "Language intent: forged receipt presented"),
            ("http", 15, "Language intent: suspicious link in message"),
            (".com", 10, "Language intent: external link domain"),
        ]:
            if kw in txt:
                score = _add(score, rules, pts, label)
        intent = {
            "pattern": "Authority + Loss Aversion (keyword fallback)",
            "evidence_phrases": [kw for kw in ("pin", "otp", "code", "blocked", "refund", "reverse", "receipt", "http") if kw in txt],
            "requested_secret": "PIN" if "pin" in txt else (
                "OTP" if ("otp" in txt or "code" in txt) else None),
            "code_switching": "twi-english" if any(w in txt for w in ("wo ", "kyew", "sika", "mepa")) else "english",
        }

    score = min(score, 100)
    tier = "HIGH" if score >= 75 else "MEDIUM" if score >= 40 else "LOW"
    # Mirrors backend _action_from_tier: a HIGH communication event has no
    # in-flight transaction to hold -> FraudOps alert instead of a fake hold.
    if tier == "LOW":
        action_out = "SEAMLESS_APPROVE"
    elif tier == "MEDIUM":
        action_out = "COOLING_OFF_PROMPT"
    elif et == "communication":
        action_out = "FRAUDOPS_ALERT"
    else:
        action_out = "SIMULATED_HOLD"

    out = {
        "msisdn": msisdn,
        "risk_score": score,
        "risk_tier": tier,
        "triggered_rules": rules,
        "llm_extracted_intent": (intent or {}).get("pattern"),
        "intent": intent,
        "recommended_action": action_out,
        "twi_warning_message": "Wɔrehyɛ wo sɛ fa wo PIN kɔ ma!" if tier == "HIGH" else None,
        "timestamp": datetime.now().isoformat(),
    }
    acc[msisdn] = {"score": score, "rules": rules, "intent": intent}
    return out
