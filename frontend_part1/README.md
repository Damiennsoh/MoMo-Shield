# MoMo Shield — Part 1: FraudOps Frontend (Streamlit)

Split-screen "FraudOps Command Center" for **Track 1: Early Detection of
Social Engineering Signals** — InnoFemme Mobile Money Fraud Hackathon, KNUST.

- **LEFT:** a simulated victim handset (SMS messenger, USSD `*170#` screens,
  incoming-call view with live transcript, Twi/English fraud-warning banner).
- **RIGHT:** FraudOps telemetry — 0–100 risk gauge, decision latency,
  triggered detection rules, live event stream, and LLM intent analysis.

The engine is **telco-side**: zero customer action required. It plugs into
the MNO's existing webhook/event infrastructure — the same protection works
whether the customer carries a 2005 Nokia or an iPhone 15.

---

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

No backend required. If the FastAPI backend (Part 2) is not running at
`http://localhost:8000`, the dashboard **automatically falls back** to the
built-in deterministic rule engine — the demo never dies on hackathon Wi-Fi.

## Connect the backend (Part 2)

```bash
# from the repo root — starts BOTH services and opens the dashboard
python run_demo.py

# or manually:
# terminal 1
cd backend_part2 && uvicorn main:app --port 8000
# terminal 2
cd frontend_part1 && streamlit run app.py
```

Set the backend URL in the sidebar (default `http://localhost:8000`).

## Scenarios (fixtures/)

| Scenario                      | File                    | Expected result                                  |
|-------------------------------|-------------------------|--------------------------------------------------|
| GH01 Fake Credit → Refund     | `gh01_fake_credit.json` | 100/100 HIGH → SIMULATED HOLD + Twi warning      |
| GH18 Device Takeover          | `gh18_device_takeover.json` | 85/100 HIGH → SIMULATED HOLD on new-device binding |
| Legitimate Baseline           | `legit_baseline.json`   | 10/100 LOW → SEAMLESS_APPROVE (false-positive control) |

Each fixture is a timed sequence of `phone_ui` steps (what the victim sees)
plus sandbox `event` payloads (what the engine scores). Scores accumulate
per MSISDN across the scenario, mirroring backend state.

## Project structure

```
frontend_part1/
├── app.py                     # Entry point, layout, scenario player
├── components/
│   ├── mock_phone.py          # Handset renderer (SMS / call / USSD)
│   ├── fraudops_panel.py      # Gauge, actions, rules, event stream, intent
│   └── risk_gauge.py          # SVG 0-100 semicircular gauge
├── services/
│   ├── api_client.py          # POST /api/v1/assess + offline fallback
│   ├── local_engine.py        # Deterministic rules (mirrors backend)
│   └── audio.py               # Self-contained alert tone (WAV, no TTS)
├── fixtures/                  # GH01 / GH18 / legit-baseline scenarios
├── styles/custom.css          # Phone frame, bubbles, banners, gauge
├── .streamlit/config.toml     # Dark MoMo-branded theme
└── requirements.txt
```

## Compliance (Act 843 / hackathon rules)

- All data is simulated sandbox data. No real MSISDNs, PINs or OTPs.
- Interventions are explicitly labelled "SIMULATED HOLD" / "FraudOps alert".
- The UI never solicits credentials from judges or testers.

## Pitch line

> "Victims will never download a new app to avoid fraud. MoMo Shield lives
> on the telco side: it correlates SMS, voice-intent and device signals
> before the PIN is entered, and it protects every handset on the network —
> feature phone or smartphone — in under 5 seconds."
