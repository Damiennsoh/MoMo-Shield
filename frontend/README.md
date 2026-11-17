# MoMo Shield Frontend

Streamlit FraudOps Command Center for replaying synthetic mobile-money fraud scenarios. The dashboard pairs a simulated customer handset view with risk scores, triggered rules, engine source, latency, event history, and communication-intent details.

## Requirements and start

Use Python 3.10 or newer. From the repository root, activate a virtual environment and install both sets of dependencies to run the complete demonstration. The frontend requirements explicitly install NumPy 2.x and a compatible PyArrow version for Streamlit's compiled components:

```bash
python -m pip install -r backend/requirements.txt -r frontend/requirements.txt
python run_demo.py
```

The dashboard is served at `http://localhost:8501`. To run the dashboard alone, install `frontend/requirements.txt`, change to this directory, and run:

```bash
streamlit run app.py
```

The API is optional for standalone use. If it is unreachable, assessment requests use the deterministic local rules engine in `services/local_engine.py`. For the full demo, start the API separately with `cd ../backend && python main.py`, or use `python run_demo.py` at the repository root.

## Backend connection

The **Backend API URL** sidebar field defaults to `http://localhost:8000`. For each event, `services/api_client.py` posts `{"event": {...}}` to `/api/v1/assess`. Before a replay, it sends `/api/v1/reset` to clear backend in-memory scenario state. It supplies IDs, timestamps, and a default `ledger_verified` value for transaction fixture events. It then normalizes the backend response for the dashboard panel. Failed assessment requests fall back locally; the dashboard labels the source as backend or local rules.

Because Streamlit runs the Python client on the server side, this is ordinary HTTP service-to-service communication. Browser CORS settings are not required for this integration.

## Scenarios

Scenario files in `fixtures/` contain timed handset UI steps and optional event payloads:

- `gh01_fake_credit.json` — fake credit followed by refund pressure.
- `gh18_device_takeover.json` — new-device/account takeover signals.
- `gh17_fake_support.json` — fake support and wallet-drain sequence.
- `gh02_reversal_syndicate.json` — reversal pressure and forged-receipt signals.
- `gh15_fake_business_listing.json` — fake listing and credential-harvest signals.
- `gh19_nuisance_calls.json` — nuisance calls followed by a fake helper.
- `legit_baseline.json` — legitimate activity used as a false-positive control.

Fixtures are synthetic and intended for local demonstrations only. The UI's “SIMULATED HOLD” and alerts do not execute payment actions.

Use **Play selected** for one scenario or **Run all 7 scenarios** for a visible, progress-tracked replay. The dashboard updates the handset and FraudOps pane as the fixture advances. It then displays result cards and an **Inspect event stream and intent for** selector; choose any scenario to inspect its timeline, communication signal, intent output, and engine source. The intent tab distinguishes Gemini from deterministic keyword fallback, filters evidence phrases to those appearing in the signal, and does not display a fabricated confidence score. A warning tone is requested automatically when an intervention is raised. A playable audio control remains as a fallback because browser autoplay policies can block sound until a visitor interacts with the page.

When launched with `python run_demo.py`, the sidebar includes a random-token link to `/api/v1/demo-device`. Open it on a second device on the same Wi-Fi and tap **Connect** to enable its local Web Audio cues. The dashboard publishes only synthetic fixture phone events to this token-protected page. The optional **Ring local SIP softphone** checkbox sends an Asterisk ARI request only at a scenario step explicitly marked as an incoming call; missed-call fixture steps do not ring. See the repository root README for the Compose setup, SIP account settings, local-network firewall requirements, and optional recorded Twi/English call warning. The second-screen webpage is a simulation; an actual softphone only rings when the separate Asterisk container is configured and the local SIP account is registered.

## Project layout

```text
frontend/
├── app.py                    # Streamlit entry point and scenario player
├── components/               # Mock handset, FraudOps panel, risk gauge
├── services/
│   ├── api_client.py         # HTTP API adapter and local fallback selection
│   ├── local_engine.py       # Deterministic offline demonstration rules
│   ├── audio.py              # Offline local sound cues and warning voice fallback
├── fixtures/                 # Seven scenario sequences
├── styles/custom.css         # Dashboard styles
└── .streamlit/config.toml    # Streamlit theme configuration
```

Backend endpoint and scoring tests are documented in [`../backend/README.md`](../backend/README.md). From the repository root, run all backend and offline fallback tests with `python -m pytest backend/tests frontend/tests -q`.
