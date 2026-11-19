"""MoMo Shield FraudOps Command Center.

Split-screen Streamlit demo: a simulated customer handset alongside risk,
rule, event-stream, and intent telemetry. The dashboard uses the FastAPI
backend when reachable and deterministic local rules when it is not.
"""

import html
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

from components.fraudops_panel import live_assessment_markup, render_fraudops
from components.live_lab import (
    render_live_signal_lab,
    render_provider_feed_readiness,
    render_synthetic_event_injector,
)
from components.mock_phone import render_phone
from services.api_client import (assess_event, check_gemini, demo_device_event_key,
                                 publish_demo_device_event, reset_backend)
from services.audio import alert_tone_bytes, play_sfx, play_warning_audio, stop_spoken_warning
from services.interventions import build_intervention
from services.local_engine import new_accumulator

BASE_DIR = Path(__file__).parent
SCENARIOS = {
    "GH01 — Fake Credit → Refund Scam": "gh01_fake_credit",
    "GH18 — New Device Takeover": "gh18_device_takeover",
    "GH17 — Fake Support → Wallet Drain": "gh17_fake_support",
    "GH02 — Reversal Syndicate & Forged Receipt": "gh02_reversal_syndicate",
    "GH15 — Fake Business Listing & PIN Harvest": "gh15_fake_business_listing",
    "GH19 — Nuisance Call Swarm → Fake Helper": "gh19_nuisance_calls",
    "Legitimate Baseline (False-Positive Control)": "legit_baseline",
}
DEMO_DEVICE_TOKEN = os.environ.get("DEMO_DEVICE_TOKEN", "")
DEMO_DEVICE_URL = os.environ.get("DEMO_DEVICE_URL", "")
CALL_RING_MIN_SECONDS = 3.0
WARNING_AUDIO_HOLD_SECONDS = 8.2

st.set_page_config(
    page_title="MoMo Shield | FraudOps Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css():
    css = (BASE_DIR / "styles" / "custom.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def load_scenario(key: str) -> dict:
    return json.loads((BASE_DIR / "fixtures" / f"{key}.json").read_text(encoding="utf-8"))


def init_state():
    defaults = {
        "phone": {"screen": "home"},
        "ops": None,
        "accumulator": new_accumulator(),
        "event_log": [],
        "assessment_history": [],
        "alert_played": False,
        "intent": None,
        "intent_text": None,
        "intent_source": "none",
        "intent_model_unavailable": False,
        "alert_tone": None,
        "alert_count": 0,
        "scenario_results": [],
        "scenario_records": [],
        "sip_audio_managed": False,
        "sip_warning_audio_managed": False,
        "victim_call_active": False,
        "victim_call_interrupted": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_scenario_state():
    st.session_state.phone = {"screen": "home"}
    st.session_state.ops = None
    st.session_state.accumulator = new_accumulator()
    st.session_state.event_log = []
    st.session_state.assessment_history = []
    st.session_state.alert_played = False
    st.session_state.intent = None
    st.session_state.intent_text = None
    st.session_state.intent_source = "none"
    st.session_state.intent_model_unavailable = False
    st.session_state.sip_audio_managed = False
    st.session_state.sip_warning_audio_managed = False
    st.session_state.victim_call_active = False
    st.session_state.victim_call_interrupted = False


def log_event(kind, summary):
    st.session_state.event_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "kind": kind,
        "summary": summary,
    })


load_css()
init_state()

st.markdown("""
<div class="app-header">
  <div class="app-title">🛡️ MoMo Shield
    <span class="app-subtitle">FraudOps Command Center</span>
  </div>
  <div class="app-tagline">GHANA MOBILE MONEY · SOCIAL-ENGINEERING EARLY WARNING · SYNTHETIC DEMO</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Demo Controls")
    workspace = st.radio(
        "Workspace",
        ("Curated scenario replay", "Live Signal Lab", "Synthetic Event Injector", "Provider Feed Readiness"),
        key="workspace_select",
    )
    backend_url = st.text_input(
        "Backend API URL",
        value=os.environ.get("BACKEND_API_URL", "http://localhost:8000"),
        key="backend_api_url",
        help="The dashboard process calls this FastAPI URL. For hosted demos, use the reachable API base URL.",
    )
    if workspace == "Curated scenario replay":
        scenario_label = st.selectbox("Scenario", list(SCENARIOS.keys()), key="scenario_select")
        c1, c2 = st.columns(2)
        play = c1.button("▶ Play selected", use_container_width=True, key="play_selected")
        reset_clicked = c2.button("⟲ Reset", use_container_width=True, key="reset_demo")
        run_all = st.button("▶ Run all 7 scenarios", use_container_width=True, key="run_all")
        sip_call_enabled = st.checkbox(
            "Ring local SIP softphone on incoming-call steps",
            value=False,
            help="Optional local demo only. Calls the fixed local PJSIP/200 endpoint for the incoming ring; the handset/browser provides warning speech. SIP is single-scenario only.",
            key="sip_call_enabled",
        )
        dashboard_audio_enabled = st.checkbox(
            "Also play demo sounds in the FraudOps browser",
            value=not bool(DEMO_DEVICE_TOKEN),
            help="Use this only when you want a local dashboard speaker as well. It is muted automatically when SIP is managing the call audio.",
            key="dashboard_audio_enabled",
        )
        large_warning_text = st.checkbox(
            "Use larger handset warning text",
            value=False,
            key="large_warning_text",
        )
        if st.button("Stop spoken warning", use_container_width=True, key="stop_replay_speech"):
            stop_spoken_warning()
        if sip_call_enabled and run_all:
            st.info("SIP calls are limited to Play selected. The seven-case replay uses the browser handset audio path.")
    else:
        scenario_label = list(SCENARIOS.keys())[0]
        play = False
        reset_clicked = False
        run_all = False
        sip_call_enabled = False
        dashboard_audio_enabled = False
        large_warning_text = False
    gemini_check_clicked = st.button("Test Gemini API", use_container_width=True, key="test_gemini")
    st.divider()
    st.caption("Backend unreachable? MoMo Shield switches to deterministic local rules and labels the engine source.")
    if DEMO_DEVICE_URL:
        st.markdown(
            f'<a href="{html.escape(DEMO_DEVICE_URL, quote=True)}" target="_blank" rel="noopener noreferrer">'
            "Open second-device handset simulator</a>",
            unsafe_allow_html=True,
        )
        st.caption("Open on a phone/tablet on the same trusted Wi-Fi, then tap Connect to enable sound.")
    else:
        st.caption("Launch with `python run_demo.py` to create a temporary, protected second-device link.")
    st.caption("Synthetic demonstration only. No payment is authorized, delayed, or blocked.")
    if st.session_state.get("demo_sip_result"):
        st.caption("SIP demo: " + st.session_state["demo_sip_result"])
    if st.session_state.get("demo_device_error"):
        st.sidebar.warning("Second-device bridge unavailable: " + st.session_state["demo_device_error"])

if reset_clicked:
    reset_scenario_state()
    st.session_state.sip_audio_managed = False
    st.session_state.alert_tone = None
    st.session_state.scenario_results = []
    st.session_state.scenario_records = []
    reset_backend(backend_url)
    if DEMO_DEVICE_TOKEN:
        try:
            publish_demo_device_event(backend_url, DEMO_DEVICE_TOKEN, {"type": "reset"})
        except Exception as exc:
            st.session_state["demo_device_error"] = str(exc)
    st.rerun()

if gemini_check_clicked:
    try:
        gemini_status = check_gemini(backend_url)
        st.sidebar.success(f"{gemini_status['message']} Model: {gemini_status['model']}.")
    except Exception as exc:
        st.sidebar.error(f"Gemini check failed: {exc}")

if workspace == "Live Signal Lab":
    render_live_signal_lab(backend_url)
    st.stop()
if workspace == "Synthetic Event Injector":
    render_synthetic_event_injector(backend_url)
    st.stop()
if workspace == "Provider Feed Readiness":
    render_provider_feed_readiness()
    st.stop()

left_col, right_col = st.columns([1, 1.35], gap="large")
phone_ph = left_col.empty()
ops_ph = right_col.empty()
progress_ph = st.empty()
audio_ph = st.empty()


def draw():
    phone_ph.empty()
    ops_ph.empty()
    with phone_ph.container():
        render_phone(st.session_state.phone)
    with ops_ph.container():
        if st.session_state.ops:
            render_fraudops(st.session_state.ops)
        else:
            st.info("Standing by — choose a scenario and start a replay.")


def draw_live():
    """Update one phone fragment and one assessment fragment during replay."""
    render_phone(st.session_state.phone, target=phone_ph)
    if st.session_state.ops:
        ops_ph.markdown(
            live_assessment_markup(st.session_state.ops),
            unsafe_allow_html=True,
        )
    else:
        ops_ph.info("Scenario starting — waiting for the first assessment event.")


def show_alert_tone(tone: bytes, alert_number: int):
    """Try browser autoplay at the intervention, retaining a manual fallback."""
    audio_ph.empty()
    with audio_ph.container():
        st.markdown(f"**🔔 Fraud intervention alert · event {alert_number}**")
        st.caption("Automatic playback is requested; browser policy may require pressing play once.")
        if not play_sfx("alert.wav"):
            st.audio(
                io.BytesIO(tone),
                format="audio/wav",
                autoplay=True,
                alt=f"Automatic fraud intervention warning tone, event {alert_number}",
                width="stretch",
            )


def render_results(records):
    st.subheader("Scenario run results")
    st.caption("Select a scenario below to inspect its event timeline and intent evidence.")
    for offset in range(0, len(records), 2):
        group = records[offset:offset + 2]
        cards = st.columns(len(group))
        for card, record in zip(cards, group):
            assessment = record["assessment"]
            with card:
                with st.container(border=True):
                    st.markdown(f"**{record['Scenario']}**")
                    st.metric("Risk", f"{assessment['risk_score']}/100", assessment["risk_tier"])
                    st.markdown(f"**Action:** `{assessment['recommended_action']}`")
                    st.caption(f"Engine: {assessment.get('source', 'unknown')} · {len(assessment.get('event_log', []))} timeline events")
    labels = [record["Scenario"] for record in records]
    selected_label = st.selectbox(
        "Inspect event stream and intent for",
        labels,
        key="scenario_inspector",
    )
    selected_record = next(record for record in records if record["Scenario"] == selected_label)
    with st.expander(f"{selected_label} — event stream and intent analysis", expanded=True):
        render_fraudops(selected_record["assessment"])


if not (play or run_all):
    draw()

if play or run_all:
    scenario_items = list(SCENARIOS.items()) if run_all else [(scenario_label, SCENARIOS[scenario_label])]
    total_steps = sum(len(load_scenario(key)["steps"]) for _, key in scenario_items)
    results = []
    records = []
    completed_steps = 0
    st.session_state.alert_tone = None
    progress_ph.progress(0.0, text="Preparing scenario replay…")

    for scenario_index, (label, key) in enumerate(scenario_items, start=1):
        scenario = load_scenario(key)
        reset_scenario_state()
        st.session_state.sip_audio_managed = False
        st.session_state.sip_warning_audio_managed = False
        reset_backend(backend_url)
        scenario_warning_audio_pending = False
        pending_call_started_at = None
        if DEMO_DEVICE_TOKEN:
            try:
                publish_demo_device_event(backend_url, DEMO_DEVICE_TOKEN, {"type": "reset", "scenario": label})
            except Exception as exc:
                st.session_state["demo_device_error"] = str(exc)
        draw_live()
        progress_ph.progress(
            completed_steps / total_steps,
            text=f"Scenario {scenario_index}/{len(scenario_items)} · {label}",
        )

        for step_index, step in enumerate(scenario["steps"], start=1):
            upcoming_phone = step.get("phone_ui", {})
            if pending_call_started_at is not None and upcoming_phone.get("screen") == "call":
                upcoming_status = str(upcoming_phone.get("call_status", "")).casefold()
                if "incoming" not in upcoming_status and "ringing" not in upcoming_status:
                    ring_remaining = CALL_RING_MIN_SECONDS - (time.monotonic() - pending_call_started_at)
                    if ring_remaining > 0:
                        time.sleep(ring_remaining)
                    pending_call_started_at = None
            # Retain the narrated timeline feel without 6–16 second fixture sleeps.
            time.sleep(min(float(step.get("delay", 0.15)), 0.20 if run_all else 0.30))
            if step.get("phone_ui"):
                st.session_state.phone.update(step["phone_ui"])
                phone_screen = st.session_state.phone.get("screen", "home")
                step_kind = str(step.get("kind", "")).upper()
                if phone_screen == "sms":
                    sms_items = st.session_state.phone.get("sms", [])
                    latest = sms_items[-1] if sms_items else {}
                    device_event = {
                        "type": "sms",
                        "scenario": label,
                        "event_key": demo_device_event_key(
                            label, "sms", f"{latest.get('from', 'MoMo')}|{latest.get('text', '')}"
                        ),
                        "caller": latest.get("from", "MoMo"),
                        "message": latest.get("text", ""),
                    }
                    if dashboard_audio_enabled and not st.session_state.sip_audio_managed:
                        play_sfx("sms.wav", max_duration_seconds=1.8)
                elif phone_screen == "call":
                    call_status = st.session_state.phone.get("call_status", "Incoming call")
                    incoming_call = "incoming" in str(call_status).casefold() or "ringing" in str(call_status).casefold()
                    call_status_lower = str(call_status).casefold()
                    st.session_state.victim_call_active = (
                        not any(word in call_status_lower for word in ("missed", "ended", "declined"))
                        and (incoming_call or "on call" in call_status_lower or "connected" in call_status_lower)
                    )
                    device_event = {
                        "type": "call",
                        "scenario": label,
                        # Fixture call-state updates (ringing -> connected) are
                        # one handset call, not a second incoming call card.
                        "event_key": demo_device_event_key(
                            label, "call", st.session_state.phone.get("caller", "Unknown caller")
                        ),
                        "caller": st.session_state.phone.get("caller", "Unknown caller"),
                        "status": call_status,
                        "transcript": st.session_state.phone.get("transcript", ""),
                        "trigger_sip": bool(sip_call_enabled and not run_all and step_kind == "CALL" and incoming_call),
                    }
                    if step_kind == "CALL" and incoming_call:
                        pending_call_started_at = time.monotonic()
                else:
                    device_event = {"type": "screen", "scenario": label,
                                    "event_key": demo_device_event_key(label, "screen"),
                                    "message": " · ".join(st.session_state.phone.get("ussd_lines", []))}
                if DEMO_DEVICE_TOKEN:
                    try:
                        device_result = publish_demo_device_event(backend_url, DEMO_DEVICE_TOKEN, device_event)
                        if device_event.get("trigger_sip") and device_result.get("status") == "published":
                            sip_result = device_result.get("sip") or {}
                            st.session_state.sip_audio_managed = sip_result.get("status") == "requested"
                            # Let the victim handset/browser play the warning
                            # at the exact intervention event. Asterisk's
                            # safety dialplan waits silently until this event
                            # hangs up the active local call.
                            st.session_state.sip_warning_audio_managed = False
                            st.session_state["demo_sip_result"] = sip_result.get("message", "SIP request completed.")
                            if not st.session_state.sip_audio_managed and dashboard_audio_enabled:
                                play_sfx("ring.wav", max_duration_seconds=6)
                        elif (device_event.get("type") == "call" and "incoming" in str(device_event.get("status", "")).casefold()
                              and dashboard_audio_enabled and not st.session_state.sip_audio_managed):
                            play_sfx("ring.wav", max_duration_seconds=6)
                    except Exception as exc:
                        st.session_state["demo_device_error"] = str(exc)
                        st.session_state.sip_audio_managed = False
                        st.session_state.sip_warning_audio_managed = False
                        if device_event.get("trigger_sip") and dashboard_audio_enabled:
                            play_sfx("ring.wav", max_duration_seconds=6)
                elif dashboard_audio_enabled and device_event.get("type") == "call":
                    if device_event.get("trigger_sip") or "incoming" in str(device_event.get("status", "")).casefold():
                        play_sfx("ring.wav", max_duration_seconds=6)

            if "event" in step:
                event = dict(step["event"])
                event.setdefault("timestamp", datetime.now().isoformat())
                start = time.perf_counter()
                assessment, source = assess_event(event, backend_url, st.session_state.accumulator)
                assessment["latency_ms"] = (time.perf_counter() - start) * 1000
                assessment["source"] = source

                if event.get("event_type") == "communication":
                    st.session_state.intent = assessment.get("intent")
                    st.session_state.intent_text = event.get("text_or_transcript")
                    st.session_state.intent_source = assessment.get("intent_source", "none")
                    st.session_state.intent_model_unavailable = assessment.get("llm_unavailable", False)

                assessment["intent"] = assessment.get("intent") or st.session_state.intent
                assessment["intent_text"] = st.session_state.intent_text
                assessment["intent_source"] = st.session_state.intent_source
                assessment["llm_unavailable"] = st.session_state.intent_model_unavailable
                intervention = build_intervention(
                    event, assessment, st.session_state.assessment_history
                )
                assessment["intervention_category"] = intervention["category"]
                assessment["intervention_title"] = intervention["title"]
                assessment["intervention_message"] = intervention["message"]
                assessment["victim_intervention"] = intervention
                st.session_state.assessment_history.append(dict(event))
                event_kind = event.get("event_type", "event").upper()
                event_summary = (
                    f"{event.get('transaction_type') or event.get('action') or event.get('channel', '')} "
                    f"→ risk {assessment['risk_score']}/100 ({source})"
                )
                log_event(event_kind, event_summary)

                action = assessment.get("recommended_action")
                call_ended_at_intervention = bool(
                    st.session_state.victim_call_active or st.session_state.victim_call_interrupted
                )
                if action == "SIMULATED_HOLD":
                    st.session_state.phone["screen"] = "ussd"
                    st.session_state.phone["ussd_lines"] = [
                        "*170#", "SIMULATED RISK NOTICE",
                        "No real transaction was held.",
                        "Verify through the official provider channel.",
                    ]
                    st.session_state.phone["warning"] = {
                        "title": intervention["title"],
                        "body": intervention["message"],
                        "severity": intervention["severity"],
                        "large_text": large_warning_text,
                        "call_ended": call_ended_at_intervention,
                    }
                    st.session_state.victim_call_interrupted = call_ended_at_intervention
                    st.session_state.victim_call_active = False
                elif action == "FRAUDOPS_ALERT":
                    st.session_state.phone["warning"] = {
                        "variant": "watch",
                        "title": intervention["title"],
                        "body": intervention["message"],
                        "severity": intervention["severity"],
                        "large_text": large_warning_text,
                        "call_ended": call_ended_at_intervention,
                    }
                    st.session_state.victim_call_interrupted = call_ended_at_intervention
                    st.session_state.victim_call_active = False
                elif action == "COOLING_OFF_PROMPT":
                    st.session_state.phone["warning"] = {
                        "variant": "watch",
                        "title": intervention["title"],
                        "body": intervention["message"],
                        "severity": intervention["severity"],
                        "large_text": large_warning_text,
                        "call_ended": call_ended_at_intervention,
                    }
                    st.session_state.victim_call_interrupted = call_ended_at_intervention
                    st.session_state.victim_call_active = False

                if action in ("SIMULATED_HOLD", "FRAUDOPS_ALERT", "COOLING_OFF_PROMPT"):
                    st.session_state.alert_played = True
                    st.session_state.alert_count += 1
                    tone = alert_tone_bytes(variant=st.session_state.alert_count)
                    st.session_state.alert_tone = tone
                    if dashboard_audio_enabled and not st.session_state.sip_warning_audio_managed:
                        show_alert_tone(tone, st.session_state.alert_count)
                        play_warning_audio("", intervention["message"])
                    if DEMO_DEVICE_TOKEN:
                        try:
                            publish_demo_device_event(backend_url, DEMO_DEVICE_TOKEN, {
                                "type": "warning",
                                "scenario": label,
                                "event_key": demo_device_event_key(label, "warning"),
                                "warning": intervention["message"],
                                "warning_english": intervention["message"],
                                "sip_hangup": action in ("SIMULATED_HOLD", "FRAUDOPS_ALERT"),
                                "suppress_audio": bool(st.session_state.sip_warning_audio_managed),
                            })
                            scenario_warning_audio_pending = not st.session_state.sip_warning_audio_managed
                        except Exception as exc:
                            st.session_state["demo_device_error"] = str(exc)

                assessment["event_log"] = list(st.session_state.event_log)
                st.session_state.ops = assessment
            else:
                log_event(step.get("kind", "UI").upper(), step.get("log", "phone update"))

            # Replace only one-fragment live views to prevent stale nested tabs.
            if st.session_state.ops:
                st.session_state.ops["event_log"] = list(st.session_state.event_log)
            draw_live()
            completed_steps += 1
            step_kind = step.get("event", {}).get("event_type", step.get("kind", "HANDSET")).upper()
            progress_ph.progress(
                completed_steps / total_steps,
                text=(f"Scenario {scenario_index}/{len(scenario_items)} · {label} · "
                      f"step {step_index}/{len(scenario['steps'])}: {step_kind}"),
            )

        if scenario_warning_audio_pending and run_all:
            # The handset defers the next reset until its bounded warning
            # playback ends, so its warning remains beside the scenario that
            # triggered it instead of being cleared mid-sentence.
            time.sleep(WARNING_AUDIO_HOLD_SECONDS)

        if st.session_state.ops:
            final_assessment = dict(st.session_state.ops)
            final_assessment["event_log"] = list(st.session_state.event_log)
            results.append({
                "Scenario": label,
                "Risk": f"{final_assessment['risk_score']}/100",
                "Tier": final_assessment["risk_tier"],
                "Recommended action": final_assessment["recommended_action"],
                "Source": final_assessment["source"],
            })
            records.append({"Scenario": label, "assessment": final_assessment})

    st.session_state.scenario_results = results
    st.session_state.scenario_records = records
    progress_ph.progress(1.0, text=f"Replay complete · {len(records)} scenario(s) assessed")
    draw()

if st.session_state.get("scenario_records"):
    render_results(st.session_state.scenario_records)
