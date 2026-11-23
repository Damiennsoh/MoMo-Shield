# InnoFemme Sandbox API, Bridge & Plug-in Architecture
### Official Developer Integration Guide for MoMo Shield (Track 1)

> **Source:** Extracted directly from [https://hackathon.innofemme.org/docs](https://hackathon.innofemme.org/docs)  
> **Status:** Repository integration guide. A live sandbox registration and end-to-end round trip still require rehearsal; this document alone does not prove those outcomes.

---

## 1. Sandbox Architecture Overview

The InnoFemme sandbox is an end-to-end simulation of Ghana's mobile financial infrastructure. It simulates three Mobile Network Operators (MTN MoMo, Telecel Cash, AT Money), commercial banks, the national switch (GhIPSS), the National Identification Authority (NIA), and individual subscriber handsets.

### Two Ways to Integrate
1. **Plug-in API (Carrier Middleware — Route 1 — Preferred for MoMo Shield):**  
   Your API is plugged directly into the internal steps of an institution (MTN, Telecel, AT). Every time an event occurs (e.g. text arrives, call rings, payment authorized), the network core sends a `POST` request to your API, pauses execution for up to 2 seconds, and acts on your decision (`allow`, `warn`, `reject`, `delay`).
2. **Standalone Application (Route 2):**  
   Your application interacts with the sandbox using REST endpoints (querying subscriber profiles, initiating USSD push, checking SIM swap status, and receiving the Fraud Simulator stream).

---

## 2. The Bridge: Connecting Localhost to the Cloud Sandbox

The sandbox runs on the internet and cannot directly reach your local backend. To bridge this gap, run `bridge.py` (included in `Backend-2/`). The backend defaults to port `8000`.

### How It Operates
1. `bridge.py` establishes an outbound HTTP long-polling connection to the sandbox using your Team Key.
2. When the sandbox needs a decision for `bridge://laptop/...`, it forwards the payload through the open bridge connection.
3. The bridge relays the request to your local backend (`http://localhost:8000` by default), captures the response, and sends it back to the sandbox.

### Running the Bridge
From the `MoMo-Shield-2/Backend-2` directory:
```bash
python bridge.py \
  --sandbox https://hackathon.innofemme.org/api/w/YOUR-TEAM \
  --key YOUR-TEAM-KEY \
  --to http://localhost:8000 \
  --name laptop
```

### Configuring the Sandbox
In the institution console (e.g., MTN Back Office > **Plug-ins** > **Plug in an API**):
- **Address:** `bridge://laptop/api/v1/plugin`
- **Plug-in Steps:** Select `sms.deliver`, `call.connect`, `payment.authorize`, `menu.open`, `sim.swap`.

---

## 3. Plug-in Interception Points Specification

Every time a plugged-in step executes, the institution sends a `POST` request with the following JSON envelope:

### Request Envelope
```json
{
  "point": "sms.deliver",
  "institution": "mtn",
  "world": "YOUR-TEAM",
  "at": "2026-11-26T10:15:00.000Z",
  "data": { ... }
}
```

### Permitted Response Decisions (HTTP 200)
```json
// Allow the action unconditionally
{ "decision": "allow" }

// Reject immediately and display reason on victim's screen (<= 150 chars)
{ "decision": "reject", "message": "MoMo Shield Alert: Fraudulent prompt detected. Transaction blocked." }

// Interpose an interactive warning prompt on handset: 1) Continue  2) Cancel
{ "decision": "warn", "message": "MoMo Shield Warning: Potential scam. Never disclose your PIN." }

// Enforce a mandatory cooling-off period (payments only)
{ "decision": "delay", "minutes": 10, "message": "Transfer held for 10-minute cooling period." }
```

---

## 4. Plug-in Step Payloads Relevant to Track 1

### A. `sms.deliver` (Pre-SMS Delivery Warning/Interception)
Fired before an incoming SMS is delivered to a subscriber's handset.
```json
{
  "from": "0209876543",
  "fromType": "person",
  "fromNetwork": "telecel",
  "to": "0241234567",
  "toNetwork": "mtn",
  "text": "Congratulations! Your wallet is suspended. Reply with PIN to reactivate.",
  "textsBetweenThemBefore": 0
}
```
- **MoMo Shield Intervention:** Evaluates text for credential solicitation (`_SECRET_RE`), authority impersonation (`_AUTHORITY_RE`), urgency pressure, phishing links (`GH15`), and approve-to-receive tricks (`GH16`). Returns `warn` or `reject`.

### B. `call.connect` (Pre-Ring Interception)
Fired before the victim's phone rings.
```json
{
  "from": "0209876543",
  "fromNetwork": "telecel",
  "callerSimRegisteredAt": "2026-11-20T16:31:00.000Z",
  "to": "0241234567",
  "toNetwork": "mtn",
  "callsBetweenThemBefore": 0,
  "numbersTheCallerHasRungToday": 42
}
```
- **MoMo Shield Intervention:** If `numbersTheCallerHasRungToday > 20`, `callsBetweenThemBefore == 0`, and `callerSimRegisteredAt` is less than 48 hours old, flags Robocall / Scam Preconditioning (`GH19`) and returns `warn`.

### C. `payment.authorize` (Transaction Level Interception)
Fired before money leaves the victim's wallet.
```json
{
  "type": "p2p",
  "channel": "ussd",
  "amount": 500,
  "fee": 3.75,
  "reference": "refund fee",
  "payer": {
    "msisdn": "0241234567",
    "name": "Ama Mensah",
    "network": "mtn",
    "walletType": "person",
    "kycTier": "medium",
    "walletOpenedAt": "2026-11-02T09:14:00.000Z",
    "balance": 1250.5,
    "lastSimSwapAt": "2026-11-21T08:00:00.000Z",
    "onCallWith": "0209876543",
    "paymentsInLast24Hours": 1,
    "amountSentInLast24Hours": 40
  },
  "payee": {
    "msisdn": "0209876543",
    "name": "Kojo Boateng",
    "network": "telecel",
    "walletType": "person",
    "kycTier": "minimum",
    "walletOpenedAt": "2026-11-21T16:40:00.000Z"
  },
  "paymentsToThisPayeeBefore": 0,
  "afterDelay": false
}
```
- **Critical Composite Signal:** `payer.onCallWith != null` while executing USSD payment = Active Social Engineering Coercion (+50 score).
- **SIM Swap Signal:** `payer.lastSimSwapAt` within 48h = Device Takeover / Mule (+45 score).
- **Action:** If score >= 75, returns `reject` or `delay`.

### D. `menu.open` (Handset USSD Menu Interception)
Fired when subscriber dials `*170#` or `*110#`.
```json
{
  "msisdn": "0241234567",
  "network": "mtn",
  "hasWallet": true,
  "lastSimSwapAt": null,
  "onCallWith": "0209876543"
}
```
- **Intervention:** If `onCallWith` is active, displays warning banner before menu opens: `"MoMo Shield: You are currently on a call. Never follow payment instructions given over the phone."`

The implementation has named mappings for the five selected points above. It does not claim support for all 16 advertised sandbox hooks. NIA checks are local format/count heuristics over event-supplied values, not registry verification. Gemini and semantic RAG enrichment run after the plug-in decision and do not determine its verdict. Optional Glance/SIM-swap checks fail open and are bounded; configure only their separately verified credentials.

---

## 5. Network Edge API Endpoints (Direct Pull)

Each carrier exposes REST APIs protected by HTTP Basic Auth (`CLIENT_ID:API_KEY`):
- MTN: `https://hackathon.innofemme.org/api/w/YOUR-TEAM/network/mtn`
- Telecel: `https://hackathon.innofemme.org/api/w/YOUR-TEAM/network/telecel`
- AT: `https://hackathon.innofemme.org/api/w/YOUR-TEAM/network/at`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `v1/sim-swap/check` | Check if SIM was swapped: `{"phoneNumber": "0241234567", "maxAge": 48}` → `{"swapped": true}` |
| `POST` | `v1/sim-swap/retrieve-date` | Retrieve timestamp of last SIM change |
| `GET` | `v1/subscribers/{number}` | Fetch subscriber KYC name, SIM status, and wallet association |
| `POST` | `v1/sms/messages` | Send network SMS warning from official sender name (e.g. `MoMoShield`) |
| `POST` | `v1/kyc-match` | Cross-check ID and personal details against registry |

---

## 6. Automated Fraud Simulator Benchmark (Section 13)

The sandbox includes an automated benchmark runner that streams live fraud scenarios alongside benign traffic to evaluate your system's True Positive / False Positive rates.

### Available Fraud Typologies in Benchmark
1. `reversal_scam` (Fake SMS credit followed by call demanding refund)
2. `pin_phishing` (Impersonation of telecom care agent harvesting credentials)
3. `sim_swap` (SIM replacement followed by account drain)
4. `agent_fraud` (Float diversion via fake head-office instructions)
5. `mule_chain` (Multi-hop wallet transfer sequence to cash-out)
6. `fake_promo` (Prize winning notification with advance fee requirement)
7. `rtp_abuse` (Request-to-pay approve-to-receive trick)
8. `fake_merchant` (Phantom goods storefront)
9. `relative_impersonation` ("Relative on new number" emergency distress story)
10. `limit_splitting` (Structuring transactions below daily caps)
11. `pin_guessing` (Brute force PIN attempts)

### Triggering an Evaluation Batch
```bash
# Test 40 targeted fraud incidents alongside 40 honest transactions
curl -X POST https://hackathon.innofemme.org/api/w/YOUR-TEAM/fraud-simulator \
  -H "x-team-key: YOUR-TEAM-KEY" \
  -H "content-type: application/json" \
  -d '{"kinds":["reversal_scam","pin_phishing","sim_swap","relative_impersonation"],"incidents":40,"ordinary":40}'
```

The results are computed automatically in the sandbox **Fraud Console** under **Fraud API Results**, reporting:
- **Stopped:** Victim lost zero funds.
- **Held before cash-out:** Caught before cash conversion.
- **Got through:** Fraud succeeded.
- **False positives:** Legitimate transactions wrongly blocked.

---

## 7. MoMo Shield Integration Checklist

1. Download `bridge.py` (already at `MoMo-Shield-2/Backend-2/bridge.py`).
2. Run bridge pointing to the backend's default port `8000`:
   ```bash
   python bridge.py --sandbox https://hackathon.innofemme.org/api/w/YOUR-TEAM --key YOUR-TEAM-KEY --to http://localhost:8000
   ```
3. In the sandbox web UI:
   - Go to **MTN MoMo Console** > **Plug-ins** > **Plug in an API**.
   - Set Address: `bridge://laptop/api/v1/plugin`.
   - Enable points: `sms.deliver`, `call.connect`, `payment.authorize`, `menu.open`.
4. Trigger the Fraud Simulator to prove live mitigation live to judges!
