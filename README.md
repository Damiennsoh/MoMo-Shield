# MoMo Shield

MoMo Shield is a demonstration platform for early detection of social-engineering fraud in mobile-money activity. It pairs a FastAPI risk-scoring service with a Streamlit FraudOps dashboard that replays simulated handset and transaction scenarios. All records and interventions in this repository are for demonstration only; this is not a production payment-control system.

## Architecture

```text
MoMo-Shield/
├── backend/                 # FastAPI assessment API and scoring engine
├── frontend/                # Streamlit dashboard and offline fallback engine
├── run_demo.py              # Starts both services for a local demo
├── start_demo.bat           # Windows launcher
└── README.md
```

Keep `backend/` and `frontend/` separate. They have different runtime roles, entry points, dependencies, and deployment needs. The dashboard communicates with the backend over HTTP; they do not need to be merged into one application. The frontend can also run without the API by using its deterministic local rules engine.

## Technology stack

| Tool | Role in MoMo Shield |
|---|---|
| **Python 3.12** | Runtime for both services; all demo logic is Python. |
| **FastAPI + Uvicorn** | Backend HTTP API (`/api/v1/assess`, `/demo-device/*`) serving risk assessments, the second-handset event stream, audio assets, and SIP/SIP-MESSAGE bridging. |
| **Pydantic / pydantic-settings** | Request/response schemas for events and assessments; typed configuration from `.env` files. |
| **Streamlit** | FraudOps dashboard — scenario replay, Live Signal Lab, event injector, provider-readiness page, and the simulated victim handset view. |
| **httpx** | Async HTTP client used by the backend to call the Asterisk ARI and by the frontend to call the backend. |
| **Google GenAI SDK (Gemini `gemini-3.5-flash-lite`)** | Optional intent extraction (authority/loss-aversion levers, requested-secret detection), audio transcription for the mic flow, and the healthcheck. Deterministic rules remain the primary scorer; Gemini is advisory and time-bounded. |
| **pytest** | Backend and frontend suites covering scoring rules, API contracts, fixtures, and safety guards. |
| **Docker Compose** | Three-service demo stack: `asterisk`, `backend`, `dashboard` — LAN-bound ports, health checks, private ARI networking. |
| **Asterisk (PJSIP/ARI)** | Local-only SIP PBX. Originates calls to the fixed demo endpoint `PJSIP/200`, reports channel state, accepts hangup requests, and delivers SIP `MESSAGE` text notifications. No PSTN/trunk connectivity. |
| **Linphone** | Optional softphone on a second device that registers to Asterisk as extension `200` — the "real phone" that rings and receives SIP text messages during the demo. |
| **Server-Sent Events (SSE)** | Streams handset events (`sms`, `call`, `warning`, `screen`, `reset`) from the backend to the token-protected second-device browser page. |
| **Browser Web Audio + Web Speech API** | Handset/dashboard sound effects (ring, SMS, alert tones) and English text-to-speech warnings; Twi safety wording stays disabled pending fluent-speaker review. |
| **numpy / pandas / pyarrow** | Data handling for the Streamlit dashboard (pinned for compatibility). |

## Requirements and setup

Use Python 3.10 or newer. From the repository root, create and activate a virtual environment, then install both services' dependencies. The frontend pins NumPy 2.x and a compatible PyArrow range to avoid Streamlit dataframe import failures seen with mixed NumPy/PyArrow installs:

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r frontend/requirements.txt
```

Start the complete demo from the repository root:

```bash
python run_demo.py
```

The launcher starts the API at `http://localhost:8000`, waits for its health endpoint, and starts the dashboard at `http://localhost:8501`. It opens the dashboard in a browser when possible. Stop both processes with Ctrl+C. On Windows, `start_demo.bat` invokes the same launcher.

## Second-device SMS and local SIP call demo

The ordinary `python run_demo.py` launch now creates a fresh random bearer token for a mobile-size **simulated handset** served by the FastAPI backend. Use **Open second-device handset simulator** in the dashboard sidebar on another phone/tablet on the same trusted Wi-Fi, then tap **Connect this demo handset and enable sound**. Fixture SMS, missed/incoming-call screens, and intervention warnings stream to that page. Stable per-scenario card keys update a ringing call in place when it becomes connected and replace a repeated warning rather than displaying duplicate cards; different caller identities remain separate. The token stays in the link fragment and is sent to the backend in an Authorization header; it is regenerated each launch. The handset page makes no cellular SMS/PSTN calls.

For a SIP ring to your own local lab softphone, use the optional Asterisk Compose stack. Docker Compose is required for this path. Copy the template, edit its LAN IPs to your laptop's Wi-Fi IPv4 address, and generate separate credentials:

```bash
python setup_demo.py
docker compose --env-file .env.demo -f docker-compose.demo.yml up --build -d
```

`setup_demo.py` detects the host's LAN address and creates `.env.demo` with fresh handset-token, SIP, and ARI credentials without printing them. Review the file and change the LAN address if detection selected the wrong network. Add `GEMINI_API_KEY` there only if you want the live Gemini integration enabled in this stack.

Install the [free Linphone softphone](https://www.linphone.org/en/download/) on a phone or laptop on the same Wi-Fi and add a SIP/UDP account with server/domain `<DEMO_LAN_IP>`, port `5060`, username and authentication ID `200`, and the `ASTERISK_SIP_PASSWORD` from `.env.demo`. Another SIP client can also be used. No Linphone cloud account or SIP trunk is needed. In the dashboard, enable **Ring local SIP softphone on incoming-call steps**, then play a single scenario such as **GH01 — Fake Credit → Refund Scam**. Its synthetic incoming-call step asks the backend to ring only `PJSIP/200`; the recipient must answer in Linphone. The SIP call rings for up to 60 seconds. Once answered, it can remain open for up to 5 minutes as a PBX failsafe. The engine assesses the transcript submitted in the lab before pickup; it does not listen to the live Linphone call. For HIGH-risk voice evidence, the demo waits until answer, then disconnects that exact local SIP leg and sends the warning. A reported-number match alone is not enough to auto-disconnect: caller ID can be spoofed; an immediate ring interruption requires both a reported-number match and a HIGH assessment. MEDIUM warnings leave the call connected; LOW-risk calls continue until manually ended or the 5-minute failsafe. This test-only local simulation does not intercept, monitor, or control customer, carrier, cellular, or PSTN calls and does not block a real transaction. No arbitrary destination or outbound/PSTN route is configured. Missed-call fixture steps are displayed as missed and do not originate a SIP call.

SMS examples are assessed when submitted in the lab; they are not intercepted or scanned in the background. An explicit PIN/OTP request can be flagged before the recipient enters a code. The engine does not observe typing or spoken codes; a later synthetic transaction/device event can be correlated only when it uses the same account identity and falls within the rule window. The demo may send a SIP `MESSAGE` to Linphone, which is a local SIP text—not carrier SMS. None of these actions blocks an actual wallet transaction.

The optional local SIP test call intentionally stays silent after answer and may be terminated by the demo harness at a synthetic warning event; this is not call interception or a production control. Warning guidance is context-specific English demo copy and may use browser-native speech; the on-screen text remains available. The dashboard does not use unreviewed Twi recordings as safety guidance.

For dashboard/browser sound, the offline audio engine uses bundled SMS, ring, and alert cues. Contextual warning speech uses browser-native English TTS rather than a generic prerecorded OTP warning. The Live Signal Lab offers explicit **Read this guidance aloud** and **Stop spoken guidance** controls; the curated replay has a **Stop spoken warning** control. The mock handset keeps warning text available to screen readers, offers a larger-text setting, and respects reduced-motion preferences. Do not pass an English voice off as Twi. The second handset has its own local playback behavior; no live customer audio is routed to it.

Use only a private/trusted Wi-Fi network. Set `DEMO_LAN_IP` and `ASTERISK_MEDIA_IP` to the host's actual LAN IP, allow only that LAN in the host firewall, and do not forward ports from the public internet. SIP (UDP 5060) and the small RTP block (UDP 10000–10050) are published only on the configured LAN address. Asterisk's ARI port is not published to the host; only the backend can reach it on the private Compose network. `.env.demo` is ignored by Git; never commit its credentials. Stop and remove the demo stack with:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml down
```

The Compose file includes health checks, a read-only frontend audio mount, LAN-bound SIP/RTP/backend/dashboard ports, and a private backend-to-Asterisk ARI path. The dashboard is also bound to `127.0.0.1:8501` so the laptop browser treats it as a secure context and allows microphone access for Live Signal Lab transcription; use `http://localhost:8501` on the demo machine and the LAN URL for other devices. The regular Streamlit/FastAPI path remains available without Docker or Asterisk.

To run services separately, use two terminals with the same virtual environment:

```bash
# Terminal 1 — API
cd backend
python main.py

# Terminal 2 — dashboard
cd frontend
streamlit run app.py
```

The backend works without a Gemini key; communication-intent analysis then uses the built-in keyword fallback. To enable Gemini, copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY`, then restart the backend. Gemini analysis is bounded by `GEMINI_TIMEOUT_SECONDS` (15s in the demo stack); the dashboard's assessment request timeout is 18 seconds so slow-but-successful Gemini responses are not abandoned. Never commit `.env` or real customer data. Use **Test Gemini API** in the dashboard sidebar to make a real, neutral Gemini request and verify the configured key/model; the check reports configuration or provider errors without exposing the key. `CORS_ORIGINS` is only needed for browser-based cross-origin clients; the current Streamlit API client makes server-to-server HTTP requests, so browser CORS is not what connects the dashboard to the API.

## Frontend/backend integration

The Streamlit client in `frontend/services/api_client.py` calls `POST /api/v1/assess` with `{"event": { ... }}` for each scenario event and `POST /api/v1/reset` before a replay. The launcher checks `GET /health`. The adapter supplies event IDs and timestamps when fixture payloads omit them, adds the required transaction ledger-verification default, and maps the backend response into fields used by the dashboard. The frontend uses `http://localhost:8000` by default; change **Backend API URL** in the dashboard sidebar to use another address. If an assessment request fails, the frontend falls back to local deterministic scoring.

API schemas and interactive documentation are available at `http://localhost:8000/docs` while the backend is running. Assessment scores accumulate in process-local backend state per MSISDN until reset or service restart; they are not persisted.

## Live Signal Lab, accessibility, and provider readiness

Choose **Live Signal Lab** to assess a new synthetic SMS or voice transcript with the existing FastAPI/local-fallback pipeline. Each sample gets a fresh synthetic identity, so prior samples do not affect its score. The workspace displays the actual engine result, provenance, latency, intent evidence, triggered rules, and contextual guidance. Optional microphone transcription is consent-gated, WAV-only, capped at 8 MB, and returns an editable draft; the app does not intentionally persist raw audio. Browser microphone access requires a secure context, so use `http://localhost:8501` on the machine running the dashboard (plain HTTP on a LAN IP is blocked by browsers). Gemini must be configured for transcription and the optional case-reference panel. Use fictional content only; the UI asks you to replace apparent phone numbers and numeric PIN/OTP values with placeholders.

The **Synthetic Event Injector** validates one transaction or device-binding event at a time and uses an isolated identity. The **Provider Feed Readiness** workspace explicitly reports **NOT CONNECTED**. It does not simulate a “live” feed. A real listener requires written provider authorization, a documented sandbox interface, test credentials and data, schema details, and approved security/privacy rules. Feature-phone SMS/USSD delivery and smartphone-app observation are not present.

The optional case-reference panel is a separate advisory sidecar. It retrieves from the small synthetic case library, shows benign lookalikes, and does not alter the rules score or recommended action. Retrieval similarity is not a fraud probability, and the case library is neither exhaustive nor validated against production traffic. See [`docs/live-signal-lab.md`](docs/live-signal-lab.md) for details and a funding-stage description.

## Scenarios and tests

The dashboard provides seven simulated scenarios: fake credit/refund, new-device takeover, fake support/wallet drain, reversal syndicate, fake business/PIN harvest, nuisance-call swarm, and a legitimate baseline used as a false-positive control. Dashboard fixtures are in `frontend/fixtures/`; backend fixtures and tests are in `backend/`.

Use **Run all 7 scenarios** in the dashboard sidebar to replay the full suite and see live handset/telemetry updates, progress, and individual result cards. The scenario inspector lets you select any result to review its event stream and intent analysis, including whether Gemini or keyword fallback was used and which evidence phrases appear in the signal. Select **Play selected** to replay one fixture. Contextual English guidance follows intervention cues as visible text and optional browser speech. The handset offers read-aloud, stop-speech, and larger-text controls; browser speech may require its one-time **Connect** gesture. Incoming-call fixture steps retain a minimum handset ring interval so the ringtone is perceptible. No cellular call or SMS is sent. Fixture pauses are capped at 0.3 seconds per step, but live Gemini latency and the deliberate incoming-call interval affect total run time.

Run the backend and fixture tests from the repository root:

```bash
python -m pytest backend/tests frontend/tests -q
```

Tests include API health and assessment checks, scoring rules, frontend-fixture replays through the backend, offline fallback decisions/audio-file validation, and focused safety checks for synthetic input and the optional advisory sidecar. Fixture tests do not simulate a browser's audio output.

## Safety and limitations

- Use synthetic data only. Do not submit real phone numbers, payment details, PINs, OTPs, or customer communications.
- `SIMULATED_HOLD` and FraudOps alerts are demo outcomes. The software does not connect to a mobile-money ledger or enforce a real transaction hold.
- The bundled attack cases are curated synthetic demonstrations, not live operator data. No external hackathon sandbox, credentials, real-time feed, or official test-case set is included in this repository.
- Risk scoring and intent analysis are demonstration logic, not a validated fraud decision model. Security and operational hardening would be required before real deployment.
- Backend state is in memory and local to one process; it is not suitable for multi-worker production deployments.

See [`backend/README.md`](backend/README.md) for API configuration and backend tests, and [`frontend/README.md`](frontend/README.md) for dashboard behavior and scenarios.
