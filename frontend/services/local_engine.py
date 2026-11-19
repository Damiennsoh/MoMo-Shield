"""Offline deterministic rule engine for the dashboard demonstration.

This is a deliberately lightweight fallback, not a fraud model. It mirrors the
backend rules needed by the bundled scenarios so the demo remains useful when
its API cannot be reached.
"""

from datetime import datetime
from services.interventions import build_intervention
from services.credential_requests import has_explicit_credential_request


def new_accumulator() -> dict:
    """Return fresh per-session score and event state."""
    return {}


def _add(score: int, rules: list, points: int, label: str) -> int:
    rules.append(label)
    return score + points


def _is_secret_request(text: str) -> bool:
    return has_explicit_credential_request(text)


def assess_local(event: dict, acc: dict):
    """Assess one event and update the session accumulator in place."""
    msisdn = event.get("msisdn", "unknown")
    state = acc.setdefault(msisdn, {"score": 0, "rules": [], "events": [], "intent": None})
    score = state["score"]
    rules = list(state["rules"])
    history = list(state["events"])
    intent = dict(state["intent"]) if state["intent"] else None
    event_type = event.get("event_type")
    points = 0

    if event_type == "transaction":
        kind = event.get("transaction_type")
        amount = float(event.get("amount") or 0)
        if kind == "CREDIT" and event.get("ledger_verified") is False:
            points = _add(points, rules, 30, "GH01: Unverified credit followed by outbound transfer")
        if kind == "P2P_SEND":
            recent_unverified_credit = any(
                e.get("event_type") == "transaction"
                and e.get("transaction_type") == "CREDIT"
                and e.get("ledger_verified") is False for e in history
            )
            if recent_unverified_credit:
                points = _add(points, rules, 30, "GH01: Unverified credit followed by outbound transfer")
            if amount >= 400:
                points = _add(points, rules, 25, "GH01: High-value outbound transfer immediately after inbound credit")
            if any(e.get("event_type") == "communication" and e.get("channel") == "VOICE" for e in history):
                points = _add(points, rules, 20, "GH01: Outbound transfer during active voice call")
            if any(e.get("event_type") == "communication" and _is_secret_request(e.get("text_or_transcript", "")) for e in history):
                points = _add(points, rules, 25, "Payment/transfer shortly after credential-harvesting communication")
        if kind == "XTRACASH_LOAN" and any(
            e.get("event_type") == "transaction" and e.get("transaction_type") == "P2P_SEND"
            and float(e.get("amount") or 0) > 100 for e in history
        ):
            points = _add(points, rules, 25, "GH17: Micro-loan activated immediately after large outbound transfer")
        if points == 0 and event.get("ledger_verified") is True and score == 0:
            points = _add(points, rules, 10, "Baseline: normal transaction telemetry")

    elif event_type == "device_binding":
        action = str(event.get("action") or "NEW_DEVICE").upper()
        points = _add(points, rules, 45 if "SIM_SWAP" in action else 40,
                      f"GH18: New device event — {action}")
        prior_credential = any(
            e.get("event_type") == "communication" and _is_secret_request(e.get("text_or_transcript", ""))
            for e in history
        )
        if event.get("preceded_by_otp_activity") or prior_credential:
            points = _add(points, rules, 25, "GH18: Device binding preceded by OTP/credential activity")

    elif event_type == "communication":
        text = (event.get("text_or_transcript") or "").lower()
        if any(phrase in text for phrase in ("send your pin", "enter your pin", "fa wo pin")) or (
            _is_secret_request(text) and any(word in text for word in ("send", "enter", "verify", "provide", "confirm", "read me"))
        ):
            points = _add(points, rules, 30, "Credential request detected in communication")
        if any(word in text for word in ("blocked", "unusual activity", "secure your account")):
            points = _add(points, rules, 20, "Authority + Loss Aversion psychological levers detected")
        if any(word in text for word in ("reverse", "reversal", "send it back", "send back", "mistaken transfer", "transaction id", "receipt")):
            points = _add(points, rules, 25, "GH02: Reversal/forge pretext detected in communication")
        has_link = any(word in text for word in ("http", "www.", ".com", ".net", ".link"))
        if has_link and _is_secret_request(text):
            points = _add(points, rules, 20, "GH15: Credential request via suspicious link/form")

        caller_ids = {
            e.get("counterparty_msisdn") for e in history
            if e.get("event_type") == "communication" and e.get("channel") == "VOICE" and e.get("counterparty_msisdn")
        }
        if event.get("channel") == "VOICE":
            if event.get("counterparty_msisdn"):
                caller_ids.add(event["counterparty_msisdn"])
            if len(caller_ids) >= 3:
                points = _add(points, rules, 20, "GH19: Multiple nuisance calls from distinct numbers detected")
            if _is_secret_request(text) and len(caller_ids) >= 3:
                points = _add(points, rules, 25, "GH19: 'Helper' credential request exploiting call fatigue")

        intent = {
            "pattern": "Authority + Loss Aversion (keyword fallback)",
            "evidence_phrases": [word for word in ("pin", "otp", "code", "blocked", "refund", "reverse", "receipt", "http") if word in text],
            "requested_secret": "PIN" if "pin" in text else ("OTP" if ("otp" in text or "code" in text) else None),
            "code_switching": "twi-english" if any(word in text for word in ("wo ", "kyew", "sika", "mepa")) else "english",
        }

    score = min(score + points, 100)
    tier = "HIGH" if score >= 75 else "MEDIUM" if score >= 40 else "LOW"
    if tier == "LOW":
        action = "SEAMLESS_APPROVE"
    elif tier == "MEDIUM":
        action = "COOLING_OFF_PROMPT"
    elif event_type == "communication":
        action = "FRAUDOPS_ALERT"
    else:
        action = "SIMULATED_HOLD"

    out = {
        "msisdn": msisdn,
        "risk_score": score,
        "risk_tier": tier,
        "triggered_rules": rules,
        "llm_extracted_intent": (intent or {}).get("pattern"),
        "intent": intent,
        "intent_source": "keyword_fallback" if event_type == "communication" else "none",
        "recommended_action": action,
        "twi_warning_message": None,
        "timestamp": event.get("timestamp") or datetime.now().isoformat(),
    }
    intervention = build_intervention(event, out, history)
    out.update({
        "english_warning_message": intervention["message"],
        "intervention_category": intervention["category"],
        "intervention_title": intervention["title"],
        "intervention_message": intervention["message"],
    })
    history.append(dict(event))
    state.update({"score": score, "rules": rules, "events": history, "intent": intent})
    return out
