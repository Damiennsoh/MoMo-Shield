# FraudOps telemetry panel: gauge, action banner, rules, event stream, intent.

import html

import streamlit as st

from components.risk_gauge import gauge_html


def _esc(s) -> str:
    return html.escape(str(s))


def _action_html(action: str) -> str:
    styles = {
        "SEAMLESS_APPROVE": ("✅ TRANSACTION APPROVED", "#22c55e",
                             "No high-risk signals in this scenario. This demo does not execute a payment."),
        "COOLING_OFF_PROMPT": ("⏳ COOLING-OFF PROMPT SENT", "#f59e0b",
                               "A simulated verification warning is shown on the handset; no real delay is applied."),
        "SIMULATED_HOLD": ("🚨 SIMULATED TRANSACTION HOLD", "#ef4444",
                           "Illustrative hold outcome for this demo. No payment is authorized or blocked."),
        "FRAUDOPS_ALERT": ("🚨 FRAUDOPS ALERT DISPATCHED", "#ef4444",
                           "Illustrative alert only; no external FraudOps queue is connected."),
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


def live_assessment_markup(ops: dict) -> str:
    """Single replaceable assessment fragment used during scripted playback."""
    score = max(0, min(100, int(ops.get("risk_score", 0))))
    tier = _esc(ops.get("risk_tier", "—"))
    action = _esc(ops.get("recommended_action", "Assessing…"))
    source = "FastAPI backend" if ops.get("source") == "backend" else "Local fallback"
    rules = ops.get("triggered_rules") or []
    rule_html = "".join(
        '<div class="rule-chip">⚡ ' + _esc(rule) + "</div>" for rule in rules
    ) or '<div class="muted">No rule triggered for this event.</div>'
    return (
        '<div class="live-assessment">'
        '<div class="live-assessment-head"><span>LIVE FRAUD ASSESSMENT</span>'
        '<span>' + source + '</span></div>'
        '<div class="live-assessment-score"><strong>' + str(score) + '</strong>'
        '<span>/ 100 · ' + tier + '</span></div>'
        '<div class="live-assessment-action">Action: <b>' + action + '</b></div>'
        '<div class="live-assessment-rules">' + rule_html + '</div>'
        '</div>'
    )


def render_fraudops(ops: dict):
    top = st.columns([1.3, 1.0, 1.0, 1.2])
    with top[0]:
        st.markdown(gauge_html(ops["risk_score"]), unsafe_allow_html=True)
    with top[1]:
        st.metric("Risk Tier", ops["risk_tier"])
        st.caption("≥75 HIGH · 40–74 MEDIUM · <40 LOW")
    with top[2]:
        lat = ops.get("latency_ms")
        st.metric("Decision ms", f"{lat:.0f}" if lat is not None else "—")
        st.caption("End-to-end API response · target < 5 s")
    with top[3]:
        st.metric("Engine", "FastAPI" if ops.get("source") == "backend"
                  else "Local fallback")
        st.caption("Communication intent: " + ("available" if ops.get("intent") else "not present"))

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
        if ops.get("intervention_message"):
            st.markdown("**Victim-facing guidance (English demo copy)**")
            st.info(ops["intervention_message"])
            st.caption("Context-aware prototype guidance; no provider alert or real transaction control is connected.")

    with tab2:
        st.markdown(_log_html(ops.get("event_log")), unsafe_allow_html=True)

    with tab3:
        intent = ops.get("intent")
        intent_source = ops.get("intent_source", "none")
        source_label = {
            "gemini": "Gemini model",
            "keyword_fallback": "Deterministic keyword fallback",
            "none": "No communication intent analysis",
        }.get(intent_source, intent_source.replace("_", " ").title())
        st.caption("Analysis source: " + source_label)
        if ops.get("llm_unavailable"):
            st.warning("Gemini was unavailable for this assessment; fallback rules were used.")
        elif intent_source == "keyword_fallback":
            st.info("Gemini was not configured for this assessment; deterministic keyword analysis was used. Set GEMINI_API_KEY and use Test Gemini API to verify live access.")
        if intent:
            evidence = intent.get("evidence_phrases") or []
            signal_text = str(ops.get("intent_text") or "")
            matched = [phrase for phrase in evidence
                       if str(phrase).casefold() in signal_text.casefold()]
            unmatched = [phrase for phrase in evidence if phrase not in matched]
            if ops.get("intent_text"):
                st.caption("Analyzed signal")
                st.code(signal_text[:500], language=None)
            if matched:
                st.markdown("**Evidence phrases found in the signal (case-insensitive exact-phrase check)**")
                st.markdown(" · ".join("`" + _esc(phrase) + "`" for phrase in matched))
            if unmatched:
                st.warning("Some analyzer evidence phrases did not match the message verbatim and are hidden.")
            elif not intent.get("pattern") and not intent.get("requested_secret"):
                st.info("No suspicious intent was returned for this message.")
            visible_intent = dict(intent)
            visible_intent["evidence_phrases"] = matched
            st.json(visible_intent)
            st.caption("Evidence is model/fallback output, not a verified fraud finding. Validate against operator policy before taking action.")
        else:
            st.markdown('<div class="muted">No text/voice intent was available for this assessment.</div>',
                        unsafe_allow_html=True)
