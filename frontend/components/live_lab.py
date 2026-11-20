"""Live synthetic-signal, event-injection, and provider-readiness workspaces."""

from __future__ import annotations

import copy
import os
import time

import streamlit as st

from components.fraudops_panel import render_fraudops
from services.api_client import (assess_event, demo_device_event_key, find_case_reference,
                                 publish_demo_device_event, transcribe_audio)
from services.audio import speak_english_warning, stop_spoken_warning
from services.interventions import build_intervention
from services.live_signal import (
    EXAMPLE_MESSAGES,
    LANGUAGE_OPTIONS,
    build_communication_event,
    build_device_event,
    build_transaction_event,
    identity_label_for_event,
    validate_synthetic_text,
)
from services.local_engine import new_accumulator


MAX_AUDIO_BYTES = 8 * 1024 * 1024


def _assess(event: dict, backend_url: str, identity_label: str) -> dict:
    start = time.perf_counter()
    assessment, source = assess_event(event, backend_url, new_accumulator())
    assessment = dict(assessment)
    assessment["latency_ms"] = (time.perf_counter() - start) * 1000
    assessment["source"] = source
    assessment.setdefault("intent_text", event.get("text_or_transcript"))
    assessment.setdefault("intent_source", "none")
    assessment.setdefault("llm_unavailable", False)
    assessment["synthetic_identity_label"] = identity_label
    assessment["submitted_event"] = copy.deepcopy(event)
    return assessment




DEMO_DEVICE_TOKEN = os.environ.get("DEMO_DEVICE_TOKEN", "")
_WARNING_ACTIONS = ("SIMULATED_HOLD", "FRAUDOPS_ALERT", "COOLING_OFF_PROMPT")


def _publish_live_event(backend_url: str, payload: dict) -> None:
    """Best-effort mirror to the token-protected second-device handset."""
    if not DEMO_DEVICE_TOKEN:
        return
    try:
        publish_demo_device_event(backend_url, DEMO_DEVICE_TOKEN, payload)
    except Exception:
        pass


def _publish_incoming_signal(event: dict, backend_url: str, sip_voice: bool, sip_sms: bool) -> None:
    """Show the judge-submitted signal on the simulated handset (and Linphone for voice)."""
    if event.get("event_type") != "communication":
        return
    label = str(event.get("event_id", "live"))
    if event.get("channel") == "VOICE":
        _publish_live_event(backend_url, {
            "type": "call", "scenario": "Live Signal Lab",
            "event_key": demo_device_event_key("Live Signal Lab", "call", label),
            "caller": caller_id or "Unknown caller", "status": "Incoming call",
            "transcript": event.get("text_or_transcript", ""),
            "trigger_sip": bool(sip_voice),
        })
        st.session_state.phone = {
            "screen": "call", "caller": "Unknown caller",
            "call_status": "Incoming call…", "call_type": "voice",
        }
    else:
        text = event.get("text_or_transcript", "")
        _publish_live_event(backend_url, {
            "type": "sms", "scenario": "Live Signal Lab",
            "event_key": demo_device_event_key("Live Signal Lab", "sms", label),
            "caller": caller_id or "Unknown sender", "message": text,
            "sip_message": bool(sip_sms),
        })
        st.session_state.phone = {
            "screen": "sms",
            "sms": [{"dir": "in", "from": "Unknown sender", "text": text}],
        }


def _publish_intervention(event: dict, assessment: dict, backend_url: str) -> None:
    """Raise the fraud warning on the handset when the engine intervenes.
    For SIP-managed calls the backend also hangs up the Linphone leg here."""
    action = assessment.get("recommended_action")
    if action not in _WARNING_ACTIONS:
        return
    _publish_live_event(backend_url, {
        "type": "warning", "scenario": "Live Signal Lab",
        "event_key": demo_device_event_key("Live Signal Lab", "warning"),
        "warning": "Do not share your PIN or OTP. Verify through official support.",
        "warning_twi": assessment.get("twi_warning_message") or "",
        "warning_english": assessment.get("english_warning_message")
                          or "Do not share your PIN or OTP. Verify through official support.",
        # HIGH-tier interventions end the call without consent; MEDIUM cooling-off
        # warns but lets the call continue until the victim ends it manually.
        "sip_hangup": action in ("SIMULATED_HOLD", "FRAUDOPS_ALERT"),
        "interrupt_now": bool(assessment.get("reported_number_match")),
    })
    st.session_state.phone["warning"] = {
        "title": "FRAUD ALERT — LIVE SIGNAL",
        "body": (assessment.get("twi_warning_message")
                 or "Suspected scam activity. Do NOT share your PIN. Call 100."),
        "call_ended": True,
    }


def _render_intervention(event: dict, assessment: dict) -> None:
    warning = {
        "category": assessment.get("intervention_category"),
        "title": assessment.get("intervention_title"),
        "message": assessment.get("intervention_message") or assessment.get("english_warning_message"),
    }
    if not warning["title"] or not warning["message"]:
        warning = build_intervention(event, assessment)
    st.markdown("#### Victim-facing guidance")
    st.caption("English safety copy only. Twi/Pidgin wording remains disabled until fluent-speaker review.")
    severity = str(assessment.get("risk_tier", "LOW")).upper()
    if severity == "HIGH":
        st.error(f"**{warning['title']}**\n\n{warning['message']}")
    elif severity == "MEDIUM":
        st.warning(f"**{warning['title']}**\n\n{warning['message']}")
    else:
        st.info(f"**{warning['title']}**\n\n{warning['message']}")
    st.caption("This is prototype guidance. It does not contact a provider or protect, delay, or block a real transaction.")
    speak_col, stop_col = st.columns(2)
    with speak_col:
        if st.button("Read this guidance aloud", key="speak_live_guidance", use_container_width=True):
            speak_english_warning(warning["message"], delay_ms=0, max_duration_seconds=18)
    with stop_col:
        if st.button("Stop spoken guidance", key="stop_live_guidance", use_container_width=True):
            stop_spoken_warning()
    st.caption("Speech uses the browser’s available English voice. The text remains visible if audio is unavailable.")


def _render_case_reference(event: dict, assessment: dict, backend_url: str) -> None:
    if event.get("event_type") != "communication":
        return
    event_key = str(event.get("event_id", "case"))
    result_key = f"case_reference_result_{event_key}"
    st.markdown("#### Known-case reference (advisory sidecar)")
    st.caption("This optional RAG result is separate from the rules assessment and cannot change its score or action.")
    if st.button("Retrieve related synthetic cases", key=f"retrieve_cases_{event_key}"):
        try:
            result = find_case_reference(
                backend_url,
                event.get("text_or_transcript", ""),
                event.get("language_hint", "English"),
            )
            st.session_state[result_key] = result
        except Exception as exc:
            st.session_state[result_key] = {"error": str(exc)}
    result = st.session_state.get(result_key)
    if not result:
        return
    if result.get("error"):
        st.info(f"Case reference unavailable: {result['error']} The primary assessment above is unchanged.")
        return
    st.caption(
        f"Corpus {result.get('case_library_version')} · embedding {result.get('embedding_model')} · "
        f"advisory model {result.get('generation_model')} · no impact on the rule score."
    )
    status = result.get("status", "uncertain")
    if status == "possible_match":
        st.warning("The advisory model found a possible match in the small synthetic library. This is not proof of fraud.")
    elif status == "no_match":
        st.info("The advisory model did not find a useful match in this small synthetic library. That is not proof of safety.")
    else:
        st.info("The advisory model is uncertain. Do not treat the result as a fraud finding.")
    st.write(result.get("summary", ""))
    if result.get("evidence_phrases"):
        st.markdown("**Exact evidence phrases from the submitted text**")
        st.write(" · ".join(f"`{phrase}`" for phrase in result["evidence_phrases"]))
    if result.get("benign_counterexample"):
        st.markdown("**Benign lookalike to consider**")
        st.write(result["benign_counterexample"])
    if result.get("safe_next_step"):
        st.markdown("**Safe next step**")
        st.write(result["safe_next_step"])
    with st.expander("Retrieved synthetic case records", expanded=False):
        for item in result.get("retrieved_cases", []):
            st.markdown(f"**{item.get('case_id')} — {item.get('title')}**")
            st.caption(
                f"Embedding similarity {item.get('retrieval_similarity', 0):.3f} "
                "(retrieval distance only; not a fraud probability or confidence score)."
            )
            st.write(item.get("attack_pattern", ""))
            st.markdown("**Signals:** " + "; ".join(item.get("signals", [])))
            st.markdown("**Benign lookalike:** " + item.get("benign_lookalike", ""))
            st.markdown("**Safe response:** " + item.get("safe_response", ""))
            st.divider()


def _render_assessment(record: dict, backend_url: str) -> None:
    event = record["event"]
    assessment = record["assessment"]
    st.divider()
    st.subheader("Assessment result")
    st.caption(
        f"Identity {record['identity']} · {assessment.get('source', 'unknown')} · "
        f"{assessment.get('latency_ms', 0):.0f} ms · one fresh synthetic assessment"
    )
    st.warning(
        "Risk scores are prototype rule outputs, not calibrated probabilities of fraud. "
        "A low score is not proof that an event is safe."
    )
    _render_intervention(event, assessment)
    render_fraudops(assessment)
    safe_event = copy.deepcopy(event)
    safe_event["msisdn"] = record["identity"]
    safe_assessment = copy.deepcopy(assessment)
    safe_assessment.pop("submitted_event", None)
    if "msisdn" in safe_assessment:
        safe_assessment["msisdn"] = record["identity"]
    with st.expander("Submitted event and returned assessment (display-sanitized)", expanded=False):
        st.caption("The actual API request uses a reserved fake identity. No customer phone number is requested.")
        st.markdown("**Submitted event**")
        st.json(safe_event)
        st.markdown("**Assessment returned by the selected engine**")
        st.json(safe_assessment)
    _render_case_reference(event, assessment, backend_url)


def render_live_signal_lab(backend_url: str) -> None:
    st.header("Live Signal Lab")
    st.caption("Try a new synthetic SMS or call transcript. This is live input to the prototype pipeline—not a live carrier feed.")
    st.info(
        "Use fictional content only. Never enter a real PIN, OTP, phone number, balance, account detail, "
        "or customer conversation. The score is a prototype rule score, not a fraud probability."
    )
    col_ring, col_msg = st.columns(2)
    with col_ring:
        sip_voice_enabled = st.checkbox(
            "Ring Linphone for voice signals",
            value=True, key="live_sip_voice",
            help="Voice submissions originate a local SIP call to PJSIP/200. If the softphone is not registered, the browser handset rings instead.",
        )
    with col_msg:
        sip_sms_enabled = st.checkbox(
            "Send SMS signals to Linphone as SIP text",
            value=True, key="live_sip_sms",
            help="SMS submissions deliver a SIP MESSAGE to the registered softphone so it shows a real text notification. No call is placed.",
        )

    channel_label = st.radio(
        "Signal channel",
        ("SMS text", "Voice-call transcript"),
        horizontal=True,
        key="live_signal_channel",
        help="Voice-call input is a transcript; this dashboard does not listen to or intercept live calls.",
    )
    caller_id = st.text_input(
        "Caller ID / sender number (optional, synthetic only)",
        key="live_caller_id",
        placeholder="e.g. +233700000101 — try a reported demo scam number",
        help="For voice calls this is the caller's number; for SMS it is the sender. "
             "Reported demo numbers (+233700000101–105) trigger an immediate blocklist interrupt.",
    )
    language_hint = st.selectbox(
        "Input language / evaluation label",
        LANGUAGE_OPTIONS,
        key="live_signal_language",
        help="This selector labels the test only. Automatic Twi, Pidgin, accent, or code-switching performance is not validated.",
    )

    st.markdown("**Optional microphone transcription**")
    st.caption(
        "Recording is opt-in. If enabled, audio moves from your browser to this demo server and then to the configured "
        "Gemini backend for a transcript draft. This app does not intentionally store the audio; external service "
        "processing is subject to that provider’s terms. Use a synthetic voice only."
    )
    consent = st.checkbox(
        "I consent to send a short synthetic recording to the configured backend for transcription.",
        key="live_audio_consent",
    )
    if "live_audio_nonce" not in st.session_state:
        st.session_state.live_audio_nonce = 0
    if "live_audio_consent_previous" not in st.session_state:
        st.session_state.live_audio_consent_previous = False
    if not consent and st.session_state.live_audio_consent_previous:
        st.session_state.live_audio_nonce += 1
    st.session_state.live_audio_consent_previous = consent
    if consent:
        recording = st.audio_input(
            "Record a synthetic example (short clip only)",
            sample_rate=16000,
            key=f"live_audio_{st.session_state.live_audio_nonce}",
        )
        if recording:
            audio_bytes = recording.getvalue()
            st.caption(f"Recording captured: {len(audio_bytes) / 1024:.0f} KB. It is not assessed until you review and submit text.")
            if st.button("Transcribe to an editable draft", key="transcribe_live_audio"):
                if len(audio_bytes) > MAX_AUDIO_BYTES:
                    st.error("Recording exceeds the 8 MB demo limit. Record a shorter sample or type the text.")
                else:
                    try:
                        draft = transcribe_audio(backend_url, audio_bytes, language_hint)
                        transcript = str(draft.get("transcript", ""))
                        if not transcript.strip():
                            st.warning("No clear words were returned. Type a synthetic example instead.")
                        else:
                            st.session_state.live_signal_text = transcript
                            st.session_state.live_signal_input_source = "transcribed_then_edited"
                            st.session_state.live_transcript_uncertain = bool(draft.get("uncertain", True))
                            st.session_state.live_transcription_note = str(draft.get("note", "Review this draft."))
                            st.session_state.live_audio_nonce += 1
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Transcription unavailable: {exc}")
    else:
        st.caption("Microphone access is off until you provide consent above.")

    if st.session_state.get("live_transcription_note"):
        if st.session_state.get("live_transcript_uncertain"):
            st.warning("The speech recognizer marked this transcript as uncertain. Correct it before assessment.")
        else:
            st.info("Transcript draft ready. Review and edit the text below before assessment.")
        st.caption(st.session_state.live_transcription_note)

    st.markdown("**Optional fictional examples**")
    example_cols = st.columns(3)
    for col, (label, message) in zip(example_cols, EXAMPLE_MESSAGES.items()):
        with col:
            if st.button(f"Insert {label}", key=f"example_{label}", use_container_width=True):
                st.session_state.live_signal_text = message
                st.session_state.live_signal_input_source = "typed"
                st.session_state.live_transcript_uncertain = False
                st.session_state.live_transcription_note = ""

    with st.form("live_signal_assessment_form", clear_on_submit=False):
        text = st.text_area(
            "Synthetic message or corrected transcript",
            key="live_signal_text",
            height=190,
            max_chars=5000,
            help="No scenario category is required. Use placeholders such as [PHONE] and [CODE].",
        )
        synthetic_confirmed = st.checkbox(
            "I confirm this is fictional and contains no real customer, PIN/OTP, phone, account, or balance details.",
            key="live_signal_synthetic_confirmed",
        )
        submitted = st.form_submit_button("Analyze synthetic signal", type="primary", use_container_width=True)

    if submitted:
        if not synthetic_confirmed:
            st.error("Confirm the sample is synthetic before sending it to the assessment engine.")
        else:
            issues = validate_synthetic_text(text)
            if issues:
                for issue in issues:
                    st.error(issue)
            else:
                input_source = st.session_state.get("live_signal_input_source", "typed")
                try:
                    event = build_communication_event(
                        text,
                        "SMS" if channel_label == "SMS text" else "VOICE",
                        language_hint,
                        input_source,
                        counterparty_msisdn=caller_id,
                    )
                    _publish_incoming_signal(event, backend_url, sip_voice_enabled, sip_sms_enabled)
                    identity = identity_label_for_event(event)
                    assessment = _assess(event, backend_url, identity)
                    _publish_intervention(event, assessment, backend_url)
                    if event.get("channel") == "VOICE":
                        action = assessment.get("recommended_action")
                        if action in ("SIMULATED_HOLD", "FRAUDOPS_ALERT"):
                            call_status = "Call ended · fraud intervention"
                            sip_hangup = True
                        elif action == "COOLING_OFF_PROMPT":
                            call_status = "Call in progress · cooling-off notice"
                            sip_hangup = False
                        else:
                            call_status = "Call in progress · no intervention"
                            sip_hangup = False
                        _publish_live_event(backend_url, {
                            "type": "call", "scenario": "Live Signal Lab",
                            "event_key": demo_device_event_key("Live Signal Lab", "call",
                                str(event.get("event_id", "live"))),
                            "caller": caller_id or "Unknown caller", "status": call_status,
                            "sip_hangup": sip_hangup,
                        })
                        st.session_state.phone["call_status"] = call_status
                    assessment["intervention"] = build_intervention(event, assessment)
                    st.session_state.live_signal_result = {
                        "event": event,
                        "assessment": assessment,
                        "identity": identity,
                    }
                    st.session_state.live_signal_input_source = "typed"
                    st.session_state.live_transcription_note = ""
                except Exception as exc:
                    st.error(f"Could not assess this sample: {exc}")

    result = st.session_state.get("live_signal_result")
    if result:
        _render_assessment(result, backend_url)


def render_synthetic_event_injector(backend_url: str) -> None:
    st.header("Synthetic Event Injector")
    st.caption("Build one schema-shaped transaction or device event using a fresh isolated synthetic identity.")
    st.warning("This injector sends only synthetic events to the demo assessment API. It does not connect to a ledger, wallet, handset, or provider sandbox.")
    kind = st.radio(
        "Synthetic event type",
        ("Transaction", "Device binding"),
        horizontal=True,
        key="injector_event_type",
    )
    with st.form("synthetic_event_form"):
        if kind == "Transaction":
            transaction_type = st.selectbox(
                "Transaction type",
                ("P2P_SEND", "CREDIT", "XTRACASH_LOAN", "USSD_SESSION"),
                format_func=lambda value: {
                    "P2P_SEND": "Person-to-person send",
                    "CREDIT": "Incoming credit",
                    "XTRACASH_LOAN": "XtraCash loan",
                    "USSD_SESSION": "USSD session event",
                }[value],
            )
            amount = st.number_input("Synthetic amount (GHS)", min_value=0.0, max_value=100000.0, value=50.0, step=10.0)
            ledger_verified = st.checkbox("Ledger entry marked verified (synthetic input)", value=False)
            device_action = None
            preceded_by_otp = False
        else:
            device_action = st.selectbox(
                "Device action",
                ("NEW_DEVICE_LOGIN", "APP_INSTALL", "SIM_SWAP", "WALLET_ENROLMENT"),
                format_func=lambda value: value.replace("_", " ").title(),
            )
            preceded_by_otp = st.checkbox("Synthetic OTP activity preceded this event", value=False)
            transaction_type = None
            amount = 0.0
            ledger_verified = False
        synthetic_confirmed = st.checkbox(
            "I confirm this event is fictional and contains no real account or device identifiers.",
            key="injector_synthetic_confirmed",
        )
        submitted = st.form_submit_button("Assess synthetic event", type="primary", use_container_width=True)

    if submitted:
        if not synthetic_confirmed:
            st.error("Confirm the event is synthetic before assessment.")
        else:
            try:
                if kind == "Transaction":
                    event = build_transaction_event(transaction_type, amount, ledger_verified)
                else:
                    event = build_device_event(device_action, preceded_by_otp)
                identity = identity_label_for_event(event)
                assessment = _assess(event, backend_url, identity)
                _publish_intervention(event, assessment, backend_url)
                assessment["intervention"] = build_intervention(event, assessment)
                st.session_state.synthetic_event_result = {
                    "event": event,
                    "assessment": assessment,
                    "identity": identity,
                }
            except Exception as exc:
                st.error(f"Event validation or assessment failed: {exc}")

    result = st.session_state.get("synthetic_event_result")
    if result:
        _render_assessment(result, backend_url)


def render_provider_feed_readiness() -> None:
    st.header("Provider Sandbox Readiness")
    st.caption("No operator, payment-provider, telco, or ledger feed is connected in this build.")
    st.error("Feed status: NOT CONNECTED — no authorized provider endpoint or test credentials were supplied.")
    st.markdown("### What is required before a listener can be enabled")
    st.markdown(
        "1. Written authorization and a documented sandbox API, webhook, or stream.\n"
        "2. Provider-issued test credentials and representative synthetic test data.\n"
        "3. A documented event schema, delivery guarantees, rate limits, and permitted response actions.\n"
        "4. Security, redaction, retention, consent, and incident-handling requirements.\n"
        "5. A test plan that proves event IDs, source, timestamps, and connection state without exposing customer data."
    )
    st.info("Until those prerequisites exist, fixture replays, Live Signal Lab samples, and injected events remain synthetic. A simulated feed or random generator will not be shown as live.")
    st.markdown("### Feature-phone and smartphone boundary")
    st.write(
        "Feature phones can receive SMS, but this browser dashboard cannot push a USSD prompt or SMS to a handset. "
        "That requires an approved operator or service-provider route. A smartphone demo cannot automatically observe or intercept another app’s MoMo transaction."
    )
