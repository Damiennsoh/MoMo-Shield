# MoMo Shield Backend

FastAPI service for the MoMo Shield synthetic demonstration. It validates event payloads, applies deterministic risk rules, accumulates risk by identity in process memory, and optionally analyzes communication text with Gemini. Without Gemini credentials, communication intent uses the built-in keyword fallback. This is a prototype, not a production payment-control or fraud-detection system.

## Requirements and start

Use Python 3.10 or newer. From the repository root, install `backend/requirements.txt`, or install it from this directory:

```bash
python -m pip install -r requirements.txt
python main.py
```

The API listens at `http://localhost:8000`. OpenAPI documentation is at `/docs`; `GET /health` is the basic health check. From the repository root, `python run_demo.py` starts this API and the Streamlit dashboard together.

## Configuration

Copy `.env.example` to `.env` in this directory if needed. Set `GEMINI_API_KEY` only to enable optional Gemini intent analysis, transcription, and case-reference retrieval. Without it, typed-text assessment and local rules remain available; optional transcription and case-reference requests report that they are not configured. `GEMINI_MODEL` and `GEMINI_TIMEOUT_SECONDS` configure intent requests. Use `POST /api/v1/gemini/healthcheck` or the dashboard's **Test Gemini API** button to make a real, neutral model request and verify access. Errors are reported without exposing the key. `BACKEND_HOST`, `BACKEND_PORT`, risk thresholds, and `CORS_ORIGINS` configure runtime behavior.

Keep `.env` private. Use fictional, synthetic test material only. Do not submit real phone numbers, payment details, PINs, OTPs, customer communications, or live call audio. Audio submitted for transcription is forwarded to the configured Gemini service; its processing is subject to that provider's terms. This application does not intentionally persist raw audio.

## API surface

- `GET /health` — basic service status.
- `POST /api/v1/assess` — assesses one transaction, device-binding, or communication event. The result includes a prototype risk score/tier, triggered rules, source/provenance, recommendation, and contextual warning. A score is not a calibrated probability or proof of fraud.
- `POST /api/v1/reset` — clears the in-memory risk window.
- `POST /api/v1/gemini/healthcheck` — makes a real minimal Gemini request only when configured; it does not test a provider/payment feed.
- `POST /api/v1/transcribe` — accepts a consented WAV sample up to 8 MiB when Gemini is configured and returns an editable transcript draft, not an assessment. The request body is size-limited while streaming; raw bytes are not intentionally logged or persisted.
- `POST /api/v1/case-reference` — optional Gemini-backed retrieval from the versioned synthetic case library. Its advisory response is separate from and cannot change the assessment score or action.
- `/api/v1/demo-device` — optional token-protected synthetic second-screen handset stream and publisher for the local demonstration. It is not a feature-phone SMS service or provider integration.

There is no provider listener, webhook, ledger connection, transaction hold, cellular SMS/USSD delivery, smartphone-wallet observation, or production call-interception capability in this repository. Provider Feed Readiness is a status/documentation workspace only. A future listener requires written authorization, a documented sandbox interface, test credentials and data, an agreed schema, and approved security/privacy/retention rules.

The optional Asterisk/SIP path is a test-lab simulation limited to the configured local softphone endpoint. It is not connected to an operator, cellular network, PSTN trunk, customer call, or call-interception system.

## Frontend connection and tests

The Streamlit adapter in `../frontend/services/api_client.py` calls the assessment and reset endpoints and labels backend versus local-fallback results. Synthetic event identities are generated separately for each sample. From the repository root, run the backend and frontend regression suites with:

```bash
python -m pytest backend/tests frontend/tests -q
```

State is held in a single process and is lost on restart. It is not durable or a multi-worker-safe production architecture. All actions and outcomes such as `SIMULATED_HOLD` are illustrative only; no payment is authorized, delayed, or blocked.
