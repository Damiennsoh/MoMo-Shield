"""
MoMo Shield - FraudOps Command Center (Track 1, InnoFemme Hackathon)
====================================================================
Streamlit frontend: split-screen dashboard.
  LEFT  -> Mock victim handset (SMS / USSD / call screens + Twi alerts)
  RIGHT -> FraudOps telemetry (risk gauge, triggered rules, event stream)

Talks to the FastAPI backend. If the backend is unreachable,
it automatically falls back to a built-in deterministic rule engine so
the demo never dies on hackathon Wi-Fi.

Run:  streamlit run app.py
"""

import io
import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from components.mock_phone import render_phone
from components.fraudops_panel import render_fraudops
from services.api_client import assess_event, reset_backend
from services.local_engine import new_accumulator
from services.audio import alert_tone_bytes

BASE_DIR = Path(__file__).parent

st.set_page_config(
    page_title="MoMo Shield | FraudOps Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCENARIOS = {
    "GH01 — Fake Credit → Refund Scam": "gh01_fake_credit",
    "GH18 — New Device Takeover": "gh18_device_takeover",
    "GH17 — Fake Support → Wallet Drain": "gh17_fake_support",
    "GH02 — Reversal Syndicate & Forged Receipt": "gh02_reversal_syndicate",
    "GH15 — Fake Business Listing & PIN Harvest": "gh15_fake_business_listing",
    "GH19 — Nuisance Call Swarm → Fake Helper": "gh19_nuisance_calls",
    "Legitimate Baseline (False-Positive Control)": "legit_baseline",
}


def load_css():
    css = (BASE_DIR / "styles" / "custom.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def load_scenario(key: str) -> dict:
    return json.loads((BASE_DIR / "fixtures" / f"{key}.json").read_text(encoding="utf-8"))


def init_state():
    st.session_state.setdefault("phone", {"screen": "home"})
    st.session_state.setdefault("ops", None)
    st.session_state.setdefault("accumulator", new_accumulator())
    st.session_state.setdefault("event_log", [])
    st.session_state.setdefault("alert_played", False)
    st.session_state.setdefault("intent", None)
    st.session_state.setdefault("intent_text", None)
    st.session_state.setdefault("intent_source", "none")
    st.session_state.setdefault("intent_model_unavailable", False)
    st.session_state.setdefault("alert_tone", None)
    st.session_state.setdefault("scenario_results", [])
    st.session_state.setdefault("scenario_records", [])


def reset():
    st.session_state.phone = {"screen": "home"}
    st.session_state.ops = None
    st.session_state.accumulator = new_accumulator()
    st.session_state.event_log = []
    st.session_state.alert_played = False
    st.session_state.intent = None
    st.session_state.intent_text = None
    st.session_state.intent_source = "none"
    st.session_state.intent_model_unavailable = False


def log_event(kind, summary):
    st.session_state.event_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "kind": kind,
        "summary": summary,
    })


load_css()
init_state()

# ------------------------------------------------------------------ header
st.markdown("""
<div class="app-header">
  <div class="app-title">🛡️ MoMo Shield
    <span class="app-subtitle">FraudOps Command Center</span>
  </div>
  <div class="app-tagline">TRACK 1 — Early Detection of Social Engineering Signals
    • Telco-side decision engine • Zero customer friction • &lt;5s latency SLA</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Demo Controls")
    scenario_label = st.selectbox("Attack Scenario", list(SCENARIOS.keys()))
    backend_url = st.text_input("Backend API URL", value="http://localhost:8000")
    c1, c2 = st.columns(2)
    play = c1.button("▶ Play selected", use_container_width=True)
    run_all = st.button("▶ Run all 7 scenarios", use_container_width=True)
    if c2.button("⟲ Reset", use_container_width=True):
        reset()
        st.session_state.alert_tone = None
        st.session_state.scenario_results = []
        st.session_state.scenario_records = []
        reset_backend(backend_url)
        st.rerun()
    st.divider()
    st.caption("If the backend is unreachable, the dashboard automatically falls "
               "back to the built-in deterministic rule engine — the demo never dies.")
    st.divider()
    st.caption("🛡️ SIMULATED SANDBOX DATA ONLY")
    st.caption("Act 843 compliant demo. No real customer data, no real PINs/OTPs.")

# ------------------------------------------------------- split-screen layout
left_col, right_col = st.columns([1, 1.35], gap="large")
phone_ph = left_col.empty()
ops_ph = right_col.empty()


def draw():
    # Repeated container writes can leave dynamic child widgets behind on
    # some Streamlit reruns. Clear both panes before rendering current state.
    phone_ph.empty()
    ops_ph.empty()
    with phone_ph.container():
        render_phone(st.session_state.phone)
    with ops_ph.container():
        if st.session_state.ops:
            render_fraudops(st.session_state.ops)
        else:
            st.info("Standing by… Press ▶ Play to stream a sandbox scenario.")


draw()

# ------------------------------------------------------------- scenario play
if play or run_all:
    scenario_items = list(SCENARIOS.items()) if run_all else [(scenario_label, SCENARIOS[scenario_label])]
    results = []
    records = []
    st.session_state.alert_tone = None
    for label, key in scenario_items:
        scenario = load_scenario(key)
        reset()
        reset_backend(backend_url)
        for step in scenario["steps"]:
            delay = step.get("delay", 1.5)
            time.sleep(min(delay, 0.2) if run_all else delay)
            if step.get("phone_ui"):
                st.session_state.phone.update(step["phone_ui"])
            if "event" in step:
                ev = dict(step["event"])
                ev.setdefault("timestamp", datetime.now().isoformat())
                t0 = time.perf_counter()
                assessment, source = assess_event(ev, backend_url, st.session_state.accumulator)
                assessment["latency_ms"] = (time.perf_counter() - t0) * 1000
                assessment["source"] = source
                if ev.get("event_type") == "communication":
                    st.session_state.intent = assessment.get("intent")
                    st.session_state.intent_text = ev.get("text_or_transcript")
                    st.session_state.intent_source = assessment.get("intent_source", "none")
                    st.session_state.intent_model_unavailable = assessment.get("llm_unavailable", False)
                assessment["intent"] = assessment.get("intent") or st.session_state.intent
                assessment["intent_text"] = st.session_state.intent_text
                assessment["intent_source"] = st.session_state.intent_source
                assessment["llm_unavailable"] = st.session_state.intent_model_unavailable
                log_event(
                    ev["event_type"].upper(),
                    f'{ev.get("transaction_type") or ev.get("action") or ev.get("channel", "")} '
                    f'→ risk {assessment["risk_score"]}/100 ({source})',
                )
                # The event log copy must be made after appending this event.
                assessment["event_log"] = list(st.session_state.event_log)
                st.session_state.ops = assessment

                action = assessment.get("recommended_action")
                if action == "SIMULATED_HOLD":
                    st.session_state.phone["screen"] = "ussd"
                    st.session_state.phone["ussd_lines"] = [
                        "*170#", "⛔ SIMULATED TRANSACTION HOLD",
                        "Suspicious activity flagged by MoMo Shield.",
                        "FraudOps has been alerted.", "Call 100 for assistance.",
                    ]
                    st.session_state.phone["warning"] = {
                        "title": "FRAUD ALERT — SIKA AFONO AKENKAN",
                        "body": f'{assessment.get("twi_warning_message") or "Suspected scam activity."} '
                                'Do NOT share your PIN. MTN will never ask for it. Call 100.',
                    }
                elif action == "FRAUDOPS_ALERT":
                    st.session_state.phone["warning"] = {
                        "variant": "watch",
                        "title": "ACCOUNT ON WATCH — FA KASA",
                        "body": "No transaction was executed in this simulation. "
                                f'{assessment.get("twi_warning_message") or "Call MTN 100 to verify any request."}',
                    }
                elif action == "COOLING_OFF_PROMPT":
                    st.session_state.phone["warning"] = {
                        "title": "SUSPECTED SIKA AFONO — VERIFY FIRST",
                        "body": "Slow down. Verify this request through the official "
                                "MoMo app or by calling 100 before entering any code.",
                    }
                if action in ("SIMULATED_HOLD", "FRAUDOPS_ALERT") and not st.session_state.alert_played:
                    st.session_state.alert_played = True
                    st.session_state.alert_tone = alert_tone_bytes()
            else:
                log_event(step.get("kind", "UI").upper(), step.get("log", "phone update"))
        if st.session_state.ops:
            last = st.session_state.ops
            # Include trailing UI-only fixture steps in the scenario's event view.
            last["event_log"] = list(st.session_state.event_log)
            results.append({
                "Scenario": label,
                "Risk": f'{last["risk_score"]}/100',
                "Tier": last["risk_tier"],
                "Recommended action": last["recommended_action"],
                "Source": last["source"],
            })
            records.append({"Scenario": label, "assessment": dict(last)})
    st.session_state.scenario_results = results
    st.session_state.scenario_records = records
    draw()

if st.session_state.get("alert_tone"):
    st.caption("Alert tone — press play to hear it. Some browsers block automatic audio playback.")
    st.audio(io.BytesIO(st.session_state.alert_tone), format="audio/wav")

if st.session_state.get("scenario_results"):
    st.subheader("Scenario run results")
    st.dataframe(st.session_state.scenario_results, hide_index=True, use_container_width=True)
    labels = [record["Scenario"] for record in st.session_state.scenario_records]
    selected_label = st.selectbox(
        "Inspect event stream and intent for",
        labels,
        key="scenario_inspector",
    )
    selected_record = next(record for record in st.session_state.scenario_records
                           if record["Scenario"] == selected_label)
    with st.expander(f"{selected_label} — assessment details", expanded=True):
        render_fraudops(selected_record["assessment"])
