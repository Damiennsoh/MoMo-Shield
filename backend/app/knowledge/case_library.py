"""Small, versioned demo corpus; not a catalogue of all Ghanaian fraud patterns."""

CASE_LIBRARY_VERSION = "synthetic-demo-v1"

CASES = [
    {
        "case_id": "GH01",
        "title": "Fake credit followed by refund pressure",
        "attack_pattern": "A person claims to have sent money by mistake, presents an unverified receipt, and pressures the recipient to transfer money back.",
        "signals": ["unverified incoming credit", "request to reverse or refund", "receipt or transaction proof supplied by the sender", "urgency to send money out"],
        "benign_lookalike": "A genuine mistaken transfer can occur. Verify it in the official provider transaction history and ask the provider before taking action.",
        "safe_response": "Do not return money based only on a caller, message, or screenshot. Verify through the official app or provider support.",
    },
    {
        "case_id": "GH18",
        "title": "New-device or SIM-change takeover attempt",
        "attack_pattern": "A contact asks the wallet owner to approve a new device, share a one-time code, or confirm a SIM-related action.",
        "signals": ["unexpected device binding", "SIM change", "code request before a new login", "unfamiliar support claim"],
        "benign_lookalike": "The account owner may be setting up a replacement phone through the official app and provider verification flow.",
        "safe_response": "Do not approve an unexpected device or SIM change and do not share a code. Verify using the official app or provider support.",
    },
    {
        "case_id": "GH17",
        "title": "Impersonated support and urgent wallet-security claim",
        "attack_pattern": "A caller claims to be provider staff, invokes unusual activity or account blocking, and requests a PIN or one-time code.",
        "signals": ["support impersonation", "threat of account restriction", "credential request", "pressure to act immediately"],
        "benign_lookalike": "Legitimate support may contact a customer about an issue but should not ask for a wallet PIN or one-time code over an unsolicited call.",
        "safe_response": "Do not share a PIN or code. End the unsolicited interaction and contact support using a number or app you already trust.",
    },
    {
        "case_id": "GH02",
        "title": "Reversal syndicate or forged receipt",
        "attack_pattern": "A sender claims a mistaken transfer or provides a receipt and asks the recipient to send funds to a supplied number.",
        "signals": ["reverse or send money back", "transaction receipt supplied as proof", "payment destination provided by caller", "pressure without ledger verification"],
        "benign_lookalike": "A legitimate sender can make a transfer mistake. The recipient should verify the actual ledger entry and follow provider instructions.",
        "safe_response": "Check official transaction history and use provider-directed reversal steps; do not transfer funds to a number supplied by a caller.",
    },
    {
        "case_id": "GH15",
        "title": "Fake business listing or credential-harvesting link",
        "attack_pattern": "A message points to an unfamiliar payment or verification page and asks for wallet credentials.",
        "signals": ["unfamiliar link", "request for PIN or code", "payment verification claim", "credential entry outside official app"],
        "benign_lookalike": "A real merchant may send a payment link, but the buyer should independently verify the business and avoid entering wallet secrets on untrusted pages.",
        "safe_response": "Do not enter wallet details through an unsolicited link. Open the official provider or merchant app directly.",
    },
    {
        "case_id": "GH19",
        "title": "Repeated nuisance calls followed by a fake helper",
        "attack_pattern": "Several callers create pressure or fatigue; a later caller offers help and asks for a code or secret.",
        "signals": ["multiple distinct callers", "repeated missed calls", "a later unsolicited helper", "request for a code after the call burst"],
        "benign_lookalike": "A legitimate call burst can come from a clinic, delivery, family, business, or service desk. Call volume alone is not evidence of fraud.",
        "safe_response": "Do not share account secrets with unsolicited callers. Verify any helper independently. Treat a call burst alone as inconclusive.",
    },
    {
        "case_id": "BASELINE",
        "title": "Legitimate verified transaction",
        "attack_pattern": "A routine transaction is reflected as completed in the verified provider ledger with no suspicious communication or device context.",
        "signals": ["verified ledger event", "expected transaction", "no credential request", "no suspicious device change"],
        "benign_lookalike": "This is the benign comparison case. An event can still need review for reasons not present in this small synthetic record.",
        "safe_response": "No high-risk indicator appears in this example. This is not proof of safety or a production false-positive guarantee.",
    },
    {
        "case_id": "AMBIGUOUS",
        "title": "Ambiguous payment-support message",
        "attack_pattern": "A message mentions a payment issue and support but does not clearly request money, a code, or account access.",
        "signals": ["unspecified payment issue", "generic support request", "no explicit credential request", "missing sender and ledger context"],
        "benign_lookalike": "A genuine notification may ask the customer to contact support without containing enough context to determine intent.",
        "safe_response": "Do not label this confirmed fraud from the message alone. Verify through the official app or known support contact if action is requested.",
    },
]


def case_document(case: dict) -> str:
    return "\n".join([
        f"Case {case['case_id']}: {case['title']}",
        f"Pattern: {case['attack_pattern']}",
        "Signals: " + "; ".join(case["signals"]),
        f"Benign lookalike: {case['benign_lookalike']}",
        f"Safe response: {case['safe_response']}",
    ])
