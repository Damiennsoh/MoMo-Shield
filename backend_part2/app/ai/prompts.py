SYSTEM_PROMPT = """You are a fraud-intent classifier for mobile money social engineering in Ghana.
Analyze SMS texts and voice-call transcripts to detect scam patterns. Scammers mix Twi/Akan and English.
Common phrases: "wo MoMo account no anya problem", "fa wo PIN kɔ ma", "E-Levy refund", "account will be blocked".
Return STRICT JSON matching the schema. If benign, return null values."""

FEW_SHOT_EXAMPLES = [
    {"input": "Mepa wo kyɛw, wo MoMo account no anya problem. Fa wo PIN kɔ ma na yɛnsiesie.",
     "output": {"pattern": "Authority + Loss Aversion", "evidence_phrases": ["wo MoMo account no anya problem", "fa wo pin kɔ ma"], "requested_secret": "PIN", "language_detected": "Twi/English Code-Switch", "suggested_warning": "Wɔrehyɛ wo sɛ fa wo PIN kɔ ma!"}},
    {"input": "Hello, this is MTN head office. Your account will be blocked. Send your OTP now.",
     "output": {"pattern": "Authority + Loss Aversion", "evidence_phrases": ["mtn head office", "account will be blocked", "send your otp"], "requested_secret": "OTP", "language_detected": "English", "suggested_warning": "MTN will never ask for your OTP."}},
    {"input": "Hey, are we still meeting at the market tomorrow?",
     "output": {"pattern": None, "evidence_phrases": [], "requested_secret": None, "language_detected": "English", "suggested_warning": None}}
]

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pattern": {"type": ["STRING", "NULL"]},
        "evidence_phrases": {"type": "ARRAY", "items": {"type": "STRING"}},
        "requested_secret": {"type": ["STRING", "NULL"]},
        "language_detected": {"type": ["STRING", "NULL"]},
        "suggested_warning": {"type": ["STRING", "NULL"]}
    },
    "required": ["pattern", "evidence_phrases", "requested_secret", "language_detected", "suggested_warning"]
}