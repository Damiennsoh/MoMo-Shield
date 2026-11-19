# MoMo Shield Frontend

Streamlit FraudOps dashboard for the synthetic MoMo Shield prototype. It preserves curated scenario replay and adds a Live Signal Lab, Synthetic Event Injector, and Provider Feed Readiness workspace. The FastAPI backend is used when reachable; otherwise the deterministic local rules engine is identified as the result source.

## Requirements and start

Use Python 3.10 or newer. From the repository root, install both dependency sets and launch the demo:

```bash
python -m pip install -r backend/requirements.txt -r frontend/requirements.txt
python run_demo.py
```

The dashboard is served at `http://localhost:8501`; the API is served at `http://localhost:8000`. To run only the dashboard, install `frontend/requirements.txt`, change to this directory, and run `streamlit run app.py`. In standalone mode, assessments use the local deterministic engine if the API is unavailable.

## Workspaces

- **Curated scenario replay** presents seven visibly synthetic scenarios, including a legitimate baseline used as a false-positive control. Scores are prototype rule scores, not calibrated fraud probabilities.
- **Live Signal Lab** accepts fictional SMS text or a transcript, displays assessment source, latency, evidence, rules, and attack-context guidance, and isolates each sample with a fresh synthetic identity. The UI checks apparent phone numbers and numeric codes and asks for confirmation before assessment.
- **Synthetic Event Injector** submits one constrained transaction or device-binding event using a generated synthetic identity. The amount field is bounded in the UI and backend schema.
- **Provider Feed Readiness** is explicitly **NOT CONNECTED**. It neither opens a listener nor invents live events. A real feed requires written provider authorization, a documented sandbox interface, test credentials/data, schema, and approved privacy/security rules.

## Audio, accessibility, and privacy

Microphone recording is opt-in and appears only after a consent step. A supported WAV sample is sent through the dashboard server to the configured backend for transcription, is capped at 8 MiB, and returns an editable draft. Transcription does not assess audio: the user must review the draft and separately submit text for analysis. The app does not intentionally persist raw audio; external processing is subject to the configured provider's terms. Use synthetic speech only.

Warnings are visible as plain English text and selected for the detected context. The Live Signal Lab provides user-operated read-aloud and stop-speech controls; the handset provides screen-reader status announcements, larger text, visible warnings, and reduced-motion styling. Browser speech depends on installed voices and user interaction. Twi/Pidgin language selection is an evaluation label, not validated language recognition or safety guidance; no unreviewed localized warning audio is played.

## Integration and limitations

The dashboard posts assessments to `/api/v1/assess` and uses `/api/v1/reset` before curated replay. Set **Backend API URL** in the sidebar when the API is hosted elsewhere. Gemini is optional and requires backend configuration; it is not verified by this offline demo unless the explicit API check is run with valid credentials. Transcription and case-reference retrieval are unavailable without Gemini configuration.

The optional second-screen handset displays synthetic fixture events over a token-protected local demo stream. It does not send cellular SMS or USSD and cannot observe or intercept another wallet app. An optional Asterisk configuration can ring only a fixed local test softphone endpoint; it is a lab-only simulation, not a carrier/operator connection or call-interception capability. `SIMULATED_HOLD` is a visible demo label only: the dashboard does not connect to a payment ledger or hold a real transaction.

No real customer data, payment details, PINs, OTPs, phone numbers, or communications should be entered. Risk rules and intent analysis are demonstration logic, not validated production performance. For privacy, authorization, and future-pilot boundaries, see [`../docs/live-signal-lab.md`](../docs/live-signal-lab.md). From the repository root, run all regression tests with `python -m pytest backend/tests frontend/tests -q`.
