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

For a real SIP ring to one nearby softphone, use the optional Asterisk Compose stack. Docker Compose is required for this path. Copy the template, edit its LAN IPs to your laptop's Wi-Fi IPv4 address, and generate separate credentials:

```bash
python setup_demo.py
docker compose --env-file .env.demo -f docker-compose.demo.yml up --build -d
```

`setup_demo.py` detects the host's LAN address and creates `.env.demo` with fresh handset-token, SIP, and ARI credentials without printing them. Review the file and change the LAN address if detection selected the wrong network. Add `GEMINI_API_KEY` there only if you want the live Gemini integration enabled in this stack.

Install the [free Linphone softphone](https://www.linphone.org/en/download/) on a phone or laptop on the same Wi-Fi and add a SIP/UDP account with server/domain `<DEMO_LAN_IP>`, port `5060`, username and authentication ID `200`, and the `ASTERISK_SIP_PASSWORD` from `.env.demo`. Another SIP client can also be used. No Linphone cloud account or SIP trunk is needed. In the dashboard, enable **Ring local SIP softphone on incoming-call steps**, then play a single scenario such as **GH01 — Fake Credit → Refund Scam**. Its synthetic incoming-call step asks the backend to ring only `PJSIP/200`. The FraudOps call card and SIP originate both use a 3-second ring window. When the scenario emits its fraud intervention/hold, the backend hangs up that exact ARI channel and the mock/second-handset warning appears on the same event. A 12-second PBX failsafe ends orphaned calls if the dashboard disappears. No arbitrary destination or outbound/PSTN route is configured. Missed-call fixture steps are displayed as missed and do not originate a SIP call.

The SIP line intentionally stays silent after answer and is terminated at the intervention event so a long recording cannot extend it beyond the simulated hold. The warning voice plays automatically on the mock/second handset from `frontend/assets/warning_twi.wav`/`.mp3`, then uses the English recording or browser TTS fallback. No file is represented as native Twi until the team supplies a consented recording.

For dashboard/browser sound, the offline audio engine uses a supplied `frontend/assets/sms.mp3`, `ring.mp3`, or `alert.mp3` in preference to the bundled `.wav` cue of the same name. On an intervention it automatically plays the alert cue, then a human-recorded combined Twi/English `warning_twi.mp3`/`.wav`, an English-only `warning_en.mp3`/`.wav`, or browser-native English TTS, in that order. Dashboard warning playback is capped at 10 seconds. The second handset loads the same files from the backend's token-authenticated audio route; the Compose backend mount at `/app/frontend-assets` points to `./frontend/assets` read-only. The handset plays its brief alert before its recorded/TTS warning, caps warning audio at 8 seconds, and suppresses duplicate browser call audio while SIP is ringing. If SIP is unavailable, an explicit fallback event starts the handset's browser ringtone. One **Connect** tap enables its audio; later fixture cues are automatic. The SIP call is hung up at the intervention event, and the handset produces the synchronized warning. Do not pass an English voice off as Twi. Use only synthetic demo content and consented team recordings; see [`frontend/assets/README.md`](frontend/assets/README.md) for exact names and playback behavior.

Use only a private/trusted Wi-Fi network. Set `DEMO_LAN_IP` and `ASTERISK_MEDIA_IP` to the host's actual LAN IP, allow only that LAN in the host firewall, and do not forward ports from the public internet. SIP (UDP 5060) and the small RTP block (UDP 10000–10050) are published only on the configured LAN address. Asterisk's ARI port is not published to the host; only the backend can reach it on the private Compose network. `.env.demo` is ignored by Git; never commit its credentials. Stop and remove the demo stack with:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml down
```

The Compose file includes health checks, a read-only frontend audio mount, LAN-bound SIP/RTP/backend/dashboard ports, and a private backend-to-Asterisk ARI path. This sandbox does not have Docker installed, so the Compose file can be statically validated here but the Asterisk container path still must be smoke-tested on the hackathon laptop with Docker before relying on it for the live judging demo. The regular Streamlit/FastAPI path remains available without Docker or Asterisk.

To run services separately, use two terminals with the same virtual environment:

```bash
# Terminal 1 — API
cd backend
python main.py

# Terminal 2 — dashboard
cd frontend
streamlit run app.py
```

The backend works without a Gemini key; communication-intent analysis then uses the built-in keyword fallback. To enable Gemini, copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY`, then restart the backend. Gemini analysis is bounded to 7 seconds; the dashboard's assessment request timeout is 9 seconds, leaving a response margin before its local rules fallback. Never commit `.env` or real customer data. Use **Test Gemini API** in the dashboard sidebar to make a real, neutral Gemini request and verify the configured key/model; the check reports configuration or provider errors without exposing the key. `CORS_ORIGINS` is only needed for browser-based cross-origin clients; the current Streamlit API client makes server-to-server HTTP requests, so browser CORS is not what connects the dashboard to the API.

## Frontend/backend integration

The Streamlit client in `frontend/services/api_client.py` calls `POST /api/v1/assess` with `{"event": { ... }}` for each scenario event and `POST /api/v1/reset` before a replay. The launcher checks `GET /health`. The adapter supplies event IDs and timestamps when fixture payloads omit them, adds the required transaction ledger-verification default, and maps the backend response into fields used by the dashboard. The frontend uses `http://localhost:8000` by default; change **Backend API URL** in the dashboard sidebar to use another address. If an assessment request fails, the frontend falls back to local deterministic scoring.

API schemas and interactive documentation are available at `http://localhost:8000/docs` while the backend is running. Assessment scores accumulate in process-local backend state per MSISDN until reset or service restart; they are not persisted.

## Scenarios and tests

The dashboard provides seven simulated scenarios: fake credit/refund, new-device takeover, fake support/wallet drain, reversal syndicate, fake business/PIN harvest, nuisance-call swarm, and a legitimate baseline used as a false-positive control. Dashboard fixtures are in `frontend/fixtures/`; backend fixtures and tests are in `backend/`.

Use **Run all 7 scenarios** in the dashboard sidebar to replay the full suite and see live handset/telemetry updates, progress, and individual result cards. The scenario inspector lets you select any result to review its event stream and intent analysis, including whether Gemini or keyword fallback was used and which evidence phrases appear in the signal. Select **Play selected** to replay one fixture. A recorded Twi/English warning or English TTS follows intervention cues automatically. Browser autoplay policies may require one user interaction before dashboard playback works; **Connect** is the second handset's one-time sound activation. Incoming-call fixture steps retain a minimum handset ring interval so the ringtone is perceptible. No cellular call or SMS is sent. Fixture pauses are capped at 0.3 seconds per step, but live Gemini latency and the deliberate incoming-call interval affect total run time.

Run the backend and fixture tests from the repository root:

```bash
python -m pytest backend/tests frontend/tests -q
```

Tests include API health and assessment checks, scoring rules, frontend-fixture replays through the backend, and offline fallback decisions/audio-file validation. Fixture tests do not simulate a browser's audio output.

## Safety and limitations

- Use synthetic data only. Do not submit real phone numbers, payment details, PINs, OTPs, or customer communications.
- `SIMULATED_HOLD` and FraudOps alerts are demo outcomes. The software does not connect to a mobile-money ledger or enforce a real transaction hold.
- The bundled attack cases are curated synthetic demonstrations, not live operator data. No external hackathon sandbox, credentials, real-time feed, or official test-case set is included in this repository.
- Risk scoring and intent analysis are demonstration logic, not a validated fraud decision model. Security and operational hardening would be required before real deployment.
- Backend state is in memory and local to one process; it is not suitable for multi-worker production deployments.

See [`backend/README.md`](backend/README.md) for API configuration and backend tests, and [`frontend/README.md`](frontend/README.md) for dashboard behavior and scenarios.
