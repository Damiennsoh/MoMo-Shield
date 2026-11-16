# MoMo Shield — InnoFemme Hackathon (Track 1)

Early detection of social-engineering fraud in mobile money. A telco-side
engine scores SMS / voice / device-binding signals in real time and injects
interventions **before** the victim enters their PIN — zero customer friction,
works on feature phones and smartphones alike.

## Architecture

```
Hackathon_Build/
├── run_demo.py / start_demo.bat   # one-command launcher (both services)
├── backend_part2/                 # FastAPI fraud engine (the "telco side")
│   ├── main.py                    #   app entrypoint, /health
│   ├── app/
│   │   ├── api/routes.py          #   POST /api/v1/assess, POST /api/v1/reset
│   │   ├── engine/                #   scorer, rules, per-MSIDN event window
│   │   ├── ai/                    #   Gemini intent layer + keyword fallback
│   │   └── models/                #   event & response schemas
│   ├── fixtures/                  #   GH01 / GH18 / legit scenarios
│   └── tests/                     #   pytest — 5 tests, all passing
└── frontend_part1/                # Streamlit FraudOps Command Center
    ├── app.py                     #   split-screen demo player
    ├── components/                #   mock handset + telemetry panel
    ├── services/
    │   ├── api_client.py          #   backend client + contract adapter
    │   └── local_engine.py        #   offline deterministic fallback
    └── fixtures/                  #   scripted victim-handset scenarios
```

**Partition rationale:** the engine and the dashboard are separate deployable
services — exactly how a real MNO would run them (decision engine behind
webhooks, ops console on top). The frontend degrades gracefully to its local
rule engine if the backend is unreachable, so the demo survives bad Wi-Fi.

## Run it

One-time setup (standard venv, no Docker):

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r backend_part2/requirements.txt -r frontend_part1/requirements.txt
```

Then run the two services in **two separate terminals**:

```bash
# terminal 1 — fraud engine
cd backend_part2
python main.py                  # FastAPI on http://localhost:8000

# terminal 2 — dashboard
cd frontend_part1
streamlit run app.py            # dashboard on http://localhost:8501
```

Or use `start_demo.bat` / `python run_demo.py` from an activated venv to
launch both at once and open the dashboard automatically.

## Wire contract

- `POST /api/v1/assess` — body `{"event": {...}}`; returns `AssessResponse`
  (risk_score accumulates per MSISDN across a scenario).
- `POST /api/v1/reset` — clears the event window and score accumulators;
  called automatically by the dashboard before each scenario replay.
- The frontend (`services/api_client.py`) adapts sandbox fixture events to the
  backend schema (injects `event_id`, `timestamp`, `ledger_verified`) and
  normalizes the response for the panel.

## Tests

```bash
cd backend_part2 && python -m pytest tests/ -q
```

Expected: GH01 → 100/100 HIGH (SIMULATED_HOLD), GH18 → 95/100 HIGH,
legitimate baseline → 10/100 LOW (SEAMLESS_APPROVE).
