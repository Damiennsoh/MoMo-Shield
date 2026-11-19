# MoMo Shield Backend

FastAPI service for the MoMo Shield demonstration. It validates event payloads, applies deterministic risk rules, accumulates risk by MSISDN in process memory, and optionally analyzes communication text with Gemini. Without Gemini credentials, it uses the built-in keyword-intent fallback.

## Requirements and start

Use Python 3.10 or newer. From the repository root, activate a virtual environment and install `backend/requirements.txt`, or install it from this directory:

```bash
python -m pip install -r requirements.txt
python main.py
```

The API listens on `http://localhost:8000`. Interactive OpenAPI docs are at `/docs`; the health check is `GET /health`. The repository-root launcher `python run_demo.py` starts this service together with the Streamlit dashboard.

## Configuration

Copy `.env.example` to `.env` in this directory if you need to configure the service. Set `GEMINI_API_KEY` to enable Gemini intent extraction; leave it unset to use the keyword fallback. The default model is `gemini-3.5-flash-lite`; `GEMINI_MODEL` and `GEMINI_TIMEOUT_SECONDS` configure that integration (the demo defaults to 7 seconds). The dashboard assessment request allows 9 seconds before using local rules. Use `POST /api/v1/gemini/healthcheck` or the dashboard's **Test Gemini API** button to make a real, neutral model request and verify access. A missing key returns `not_configured`; an invalid key, unavailable model, timeout, or provider error returns a clear failure without exposing the key. `BACKEND_HOST`, `BACKEND_PORT`, `RISK_THRESHOLD_MEDIUM`, and `RISK_THRESHOLD_HIGH` set runtime options. `CORS_ORIGINS` configures FastAPI CORS for browser-based clients; the current Streamlit client is server-to-server and does not require browser CORS.

Keep `.env` private. All supplied fixtures are synthetic. Do not use production customer, payment, PIN, or OTP data.

## API contract

- `GET /health` returns a basic service status.
- `POST /api/v1/gemini/healthcheck` makes a real Gemini request when credentials are configured and reports whether the integration works.
- `GET /api/v1/demo-device` serves the synthetic second-device handset page. Its stream at `GET /api/v1/demo-device/stream`, publisher at `POST /api/v1/demo-device/publish`, and allowlisted audio assets at `GET /api/v1/demo-device/audio/{filename}` require the per-demo `DEMO_DEVICE_TOKEN` bearer token. Set `DEMO_DEVICE_AUDIO_DIR` when assets are mounted outside the default repository path.
- When the publisher receives a `call` event with `trigger_sip=true`, it asks Asterisk to ring only the code-fixed `PJSIP/200` local endpoint for the same three-second window shown in FraudOps. It retains the generated ARI channel ID and hangs up only that call when the warning/intervention or reset event is published. The handset suppresses its duplicate browser ringtone when ARI accepts the request; if SIP is unavailable, a follow-up stream event enables browser ringing. The Compose setup has no PSTN trunk or arbitrary-number route; ARI is private to the Compose network.
- `POST /api/v1/assess` accepts `{"event": { ... }, "context": ...}`. `event_type` must be `transaction`, `device_binding`, or `communication`, with required fields for that event type. The response includes `risk_score` (0–100), `risk_tier`, `triggered_rules`, optional `llm_extracted_intent`, `intent_source` (`gemini`, `keyword_fallback`, or `none`), `recommended_action`, and warning text. The source identifies the method used; it is not a confidence score or proof of fraud.
- `POST /api/v1/reset` clears the demo's in-memory event window and risk accumulators.
- `POST /api/v1/sandbox/webhook` accepts a sandbox event directly or nested under `event` or `data`.

The frontend adapter in `../frontend/services/api_client.py` adds event IDs and timestamps when omitted by scenario fixtures and supplies `ledger_verified` for transaction events. The API schema and exact field definitions are also available from `/docs` at runtime.

## Tests

From the repository root, install the backend dependencies and run:

```bash
python -m pytest backend/tests -q
```

The suite covers health and assessment endpoints, scoring rules, and all frontend scenario fixtures. The fixture replays call the scoring engine directly after applying the same event defaults as the frontend adapter; they do not launch Streamlit.

## Demo limitations

State is held in memory in a single process. It is reset by `/api/v1/reset` and lost when the process restarts. It is not a durable store or a multi-worker-safe production architecture. Risk actions such as `SIMULATED_HOLD` are illustrative only; this service is not connected to a payment ledger.
