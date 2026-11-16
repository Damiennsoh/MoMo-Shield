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

Use Python 3.10 or newer. From the repository root, create and activate a virtual environment, then install both services' dependencies:

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

To run services separately, use two terminals with the same virtual environment:

```bash
# Terminal 1 — API
cd backend
python main.py

# Terminal 2 — dashboard
cd frontend
streamlit run app.py
```

The backend works without a Gemini key; communication-intent analysis then uses the built-in keyword fallback. To enable Gemini, copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY`. Never commit `.env` or real customer data. `CORS_ORIGINS` is only needed for browser-based cross-origin clients; the current Streamlit API client makes server-to-server HTTP requests, so browser CORS is not what connects the dashboard to the API.

## Frontend/backend integration

The Streamlit client in `frontend/services/api_client.py` calls `POST /api/v1/assess` with `{"event": { ... }}` for each scenario event and `POST /api/v1/reset` before a replay. The launcher checks `GET /health`. The adapter supplies event IDs and timestamps when fixture payloads omit them, adds the required transaction ledger-verification default, and maps the backend response into fields used by the dashboard. The frontend uses `http://localhost:8000` by default; change **Backend API URL** in the dashboard sidebar to use another address. If an assessment request fails, the frontend falls back to local deterministic scoring.

API schemas and interactive documentation are available at `http://localhost:8000/docs` while the backend is running. Assessment scores accumulate in process-local backend state per MSISDN until reset or service restart; they are not persisted.

## Scenarios and tests

The dashboard provides seven simulated scenarios: fake credit/refund, new-device takeover, fake support/wallet drain, reversal syndicate, fake business/PIN harvest, nuisance-call swarm, and a legitimate baseline used as a false-positive control. Dashboard fixtures are in `frontend/fixtures/`; backend fixtures and tests are in `backend/`.

Use **Run all 7 scenarios** in the dashboard sidebar to replay the full suite and see a table of risk tier, recommended action, and scoring source for each scenario. The scenario inspector lets you select any result to review its event stream and intent analysis, including whether Gemini or keyword fallback was used and which evidence phrases match the signal verbatim. Select **Play selected** to replay one fixture. The alert tone is presented as a playable audio control because browsers may block automatic playback.

Run the backend and fixture tests from the repository root:

```bash
python -m pytest backend/tests frontend/tests -q
```

Tests include API health and assessment checks, scoring rules, frontend-fixture replays through the backend, and offline fallback decisions/audio-file validation. Fixture tests do not simulate a browser's audio output.

## Safety and limitations

- Use synthetic data only. Do not submit real phone numbers, payment details, PINs, OTPs, or customer communications.
- `SIMULATED_HOLD` and FraudOps alerts are demo outcomes. The software does not connect to a mobile-money ledger or enforce a real transaction hold.
- Risk scoring and intent analysis are demonstration logic, not a validated fraud decision model. Security and operational hardening would be required before real deployment.
- Backend state is in memory and local to one process; it is not suitable for multi-worker production deployments.

See [`backend/README.md`](backend/README.md) for API configuration and backend tests, and [`frontend/README.md`](frontend/README.md) for dashboard behavior and scenarios.
