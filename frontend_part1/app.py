"""
MoMo Shield - FraudOps Command Center (Track 1, InnoFemme Hackathon)
====================================================================
Streamlit frontend: split-screen dashboard.
  LEFT  -> Mock victim handset (SMS / USSD / call screens + Twi alerts)
  RIGHT -> FraudOps telemetry (risk gauge, triggered rules, event stream)

Talks to the FastAPI backend (Part 2). If the backend is unreachable,
it automatically falls back to a built-in deterministic rule engine so
the demo never dies on hackathon Wi-Fi.

Run:  streamlit run app.py
"""

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


def reset():
    st.session_state.phone = {"screen": "home"}
    st.session_state.ops = None
    st.session_state.accumulator = new_accumulator()
    st.session_state.event_log = []
    st.session_state.alert_played = False


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
    play = c1.button("▶ Play", use_container_width=True)
    if c2.button("⟲ Reset", use_container_width=True):
        reset()
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
    with phone_ph.container():
        render_phone(st.session_state.phone)
    with ops_ph.container():
        if st.session_state.ops:
            render_fraudops(st.session_state.ops)
        else:
            st.info("Standing by… Press ▶ Play to stream a sandbox scenario.")


draw()

# ------------------------------------------------------------- scenario play
if play:
    scenario = load_scenario(SCENARIOS[scenario_label])
    reset()
    reset_backend(backend_url)
    draw()
    for step in scenario["steps"]:
        time.sleep(step.get("delay", 1.5))
        if step.get("phone_ui"):
            st.session_state.phone.update(step["phone_ui"])
        if "event" in step:
            ev = step["event"]
            ev.setdefault("timestamp", datetime.now().isoformat())
            t0 = time.perf_counter()
            assessment, source = assess_event(ev, backend_url, st.session_state.accumulator)
            assessment["latency_ms"] = (time.perf_counter() - t0) * 1000
            assessment["source"] = source
            assessment["event_log"] = list(st.session_state.event_log)
            st.session_state.ops = assessment
            log_event(
                ev["event_type"].upper(),
                f'{ev.get("transaction_type") or ev.get("action") or ev.get("channel", "")} '
                f'→ risk {assessment["risk_score"]}/100 ({source})',
            )
            # ---- engine-driven intervention on the handset -----------------
            # The engine's recommended_action picks the screen — not a script.
            action = assessment.get("recommended_action")
            if action == "SIMULATED_HOLD":
                st.session_state.phone["screen"] = "ussd"
                st.session_state.phone["ussd_lines"] = [
                    "*170#",
                    "⛔ TRANSACTION ON HOLD",
                    "Suspicious activity flagged by MoMo Shield.",
                    "FraudOps has been alerted.",
                    "Call 100 for assistance.",
                ]
                st.session_state.phone["warning"] = {
                    "title": "FRAUD ALERT — SIKA AFONO AKENKAN",
                    "body": f'{assessment["twi_warning_message"]} '
                            f'Do NOT share your PIN. MTN will never ask for it. Call 100.',
                }
            elif action == "FRAUDOPS_ALERT":
                # No transaction exists to hold (e.g. GH19) — keep the call
                # screen and raise an amber watch/cooling-off banner instead.
                st.session_state.phone["warning"] = {
                    "variant": "watch",
                    "title": "ACCOUNT ON WATCH — FA KASA",
                    "body": "No money was moved — we paused before the code prompt. "
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
                st.audio(alert_tone_bytes(), format="audio/wav", autoplay=True)
        else:
            log_event(step.get("kind", "UI").upper(), step.get("log", "phone update"))
        draw()
