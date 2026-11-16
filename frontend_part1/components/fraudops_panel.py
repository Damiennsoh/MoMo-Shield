# FraudOps telemetry panel: gauge, action banner, rules, event stream, intent.

import html

import streamlit as st

from components.risk_gauge import gauge_html


def _esc(s) -> str:
    return html.escape(str(s))


def _action_html(action: str) -> str:
    styles = {
        "SEAMLESS_APPROVE": ("✅ TRANSACTION APPROVED", "#22c55e",
                             "No fraud signals. Zero friction for the customer — funds move normally."),
        "COOLING_OFF_PROMPT": ("⏳ COOLING-OFF PROMPT SENT", "#f59e0b",
                               "Soft warning in Twi & English shown on handset; 60-second cooling-off delay applied."),
        "SIMULATED_HOLD": ("🚨 SIMULATED TRANSACTION HOLD", "#ef4444",
                           "Pre-authorisation hold injected BEFORE PIN verification. FraudOps alerted. "
                           "Twi audio warning dispatched to the handset."),
        "FRAUDOPS_ALERT": ("🚨 FRAUDOPS ALERT DISPATCHED", "#ef4444",
                           "Case routed to telco FraudOps queue with the full multi-channel signal bundle."),
    }
    title, color, desc = styles.get(action, (action, "#94a3b8", ""))
    banner = '<div class="action-banner" style="border-left:6px solid ' + color + ';">'
    banner += '<div class="action-title" style="color:' + color + ';">' + title + "</div>"
    banner += '<div class="action-desc">' + desc + "</div></div>"
    return banner


def _log_html(log) -> str:
    if not log:
        return '<div class="muted">No events yet.</div>'
    rows = ""
    for e in reversed(log):
        rows += ('<div class="log-row"><span class="log-time">' + _esc(e["time"]) + "</span>"
                 '<span class="log-kind">' + _esc(e["kind"]) + "</span>"
                 '<span class="log-summary">' + _esc(e["summary"]) + "</span></div>")
    return '<div class="event-log">' + rows + "</div>"


def render_fraudops(ops: dict):
    top = st.columns([1.4, 0.8, 0.8, 0.9])
    with top[0]:
        st.markdown(gauge_html(ops["risk_score"]), unsafe_allow_html=True)
    with top[1]:
        st.metric("Risk Tier", ops["risk_tier"])
        st.caption(">=75 HIGH ‚Ä¢ 40-74 MEDIUM ‚Ä¢ <40 LOW")
    with top[2]:
        lat = ops.get("latency_ms")
        st.metric("Decision Latency", f"{lat:.0f} ms" if lat is not None else "—")
        st.caption("Track 1 SLA: < 5,000 ms")
    with top[3]:
        st.metric("Scoring Engine", "FastAPI Backend" if ops.get("source") == "backend"
                  else "Local Rules (offline fallback)")
        st.caption("Gemini intent layer: " + ("active" if ops.get("intent") else "not required"))

    tab1, tab2, tab3 = st.tabs(["🚨 Live Assessment", "📡 Event Stream", "🧠 Intent Analysis"])

    with tab1:
        st.markdown(_action_html(ops.get("recommended_action")), unsafe_allow_html=True)
        st.markdown("**Triggered detection rules**")
        rules = ops.get("triggered_rules") or []
        if rules:
            chips = "".join('<div class="rule-chip">⚡ ' + _esc(r) + "</div>" for r in rules)
            st.markdown(chips, unsafe_allow_html=True)
        else:
            st.markdown('<div class="muted">No rules triggered — transaction profile is normal.</div>',
                        unsafe_allow_html=True)
        if ops.get("twi_warning_message"):
            st.warning('📢 Handset alert (Twi): *' + ops["twi_warning_message"] + '* — '
                       "“MTN will never ask for your PIN or OTP. Call 100 to verify any request.”")

    with tab2:
        st.markdown(_log_html(ops.get("event_log")), unsafe_allow_html=True)

    with tab3:
        intent = ops.get("intent")
        if intent:
            if ops.get("intent_text"):
                st.caption("Analyzed signal: *" + _esc(str(ops["intent_text"])[:300]) + "*")
            st.json(intent)
            st.caption("Structured JSON from Gemini Flash (code-switched Twi/English intent). "
                       "Keyword fallback shown automatically when the API is unavailable.")
        else:
            st.markdown('<div class="muted">No text/voice signal in this scenario.</div>',
                        unsafe_allow_html=True)
