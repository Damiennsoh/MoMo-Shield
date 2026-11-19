# MoMo Shield implementation plan

## Goal and constraints

Preserve the existing FastAPI + Streamlit application and its seven curated scenario replays. Add an honestly labelled Live Signal Lab for original synthetic text and optional, consented speech transcription; a structured synthetic event injector; contextual, accessible interventions; and a provider-feed readiness boundary. Keep all assessments demonstrative: the score is a prototype rule score, not a calibrated probability, and no real payment is authorized, delayed, intercepted, or blocked. A live provider listener remains disabled until an operator/provider supplies an authorized documented interface and test data.

Add a separate advisory case-reference view only after the live input path is working. Retrieved examples are context, not proof of fraud and never override the existing score/action pipeline. Do not enable any unreviewed Twi safety copy. Audio samples are transient, sent only after explicit consent to the configured transcription backend, and never persisted by this application; the transcript is editable and must be submitted explicitly.

## Implementation approach

1. Add a workspace selector that preserves curated replay and exposes Live Signal Lab, synthetic event injection, and provider-feed readiness without mixing their state.
2. Build communication and structured-event payloads with a fresh synthetic identity and fresh accumulator for every assessment. Display the actual backend/local response, source, latency, rules, intent, exact matching evidence, and submitted event. Keep personal data out of demo inputs and use clear synthetic labels.
3. Add a consent-gated `st.audio_input` flow and a replaceable transcription adapter. The FastAPI backend may use the already configured Gemini model to transcribe a bounded WAV payload. Show the transcript for correction; never assess the raw audio or silently submit a transcript. Handle missing credentials, unavailable model, oversized payload, and uncertainty without pretending transcription succeeded.
4. Replace generic OTP-only victim warnings with concise English messages selected from assessment context: credential harvesting, reversal/refund, suspicious link, impersonation/threat, device takeover, repeated calls, transaction/loan risk, or insufficient evidence. Keep the warning text visible, provide user-operated speech/stop controls, and avoid automatic public disclosure of sensitive details. Twi/Pidgin are evaluation labels only until fluent speakers validate the safety copy.
5. Provide a provider-feed status boundary and adapter contract, but do not connect, poll, or simulate a provider feed. Document required authorization, API/event schema, test credentials/data, security, and redaction prerequisites.
6. Add an advisory case-reference sidecar only if a real embedding/retrieval path can be implemented without weakening the primary assessment or making unsupported claims. Keep retrieved cases and benign counterexamples visibly separate from score/action.
7. Add focused tests for sample isolation, payload validation, contextual intervention selection, transcription constraints/uncertainty, and provider-feed disabled state; run existing tests and app/backend smoke checks.

## Design direction

Reuse the current high-contrast dark FraudOps shell rather than replacing the framework or resetting its visual identity. Use deep navy surfaces for calm operational context, warm yellow for attention, and blue/teal for neutral evidence. Keep text as the primary status cue; never rely on color or tone alone. Separate the operator workflow into clearly named workspaces, use short plain-language helper text, preserve keyboard order, make the warning readable at larger sizes, and include explicit speak/stop controls for blind and low-vision users. A warning must say what to do next in plain English and must not claim that an actual account or transaction was protected.

Brand essence: an explainable synthetic mobile-money risk demonstration for partners and hackathon judges. Personality: careful, accessible, evidence-led. Voice: plain, specific, honest. Example copy: “Try a new synthetic signal.” “This prototype can assess the message; it cannot block a payment.”

## Project structure

- `frontend/app.py`: Streamlit workspaces, scenario replay, Live Signal Lab, synthetic event injector, result rendering.
- `frontend/components/`: reusable handset and FraudOps presentation.
- `frontend/services/api_client.py`: FastAPI request, transcription adapter, and labelled local fallback.
- `frontend/services/local_engine.py`: deterministic offline assessment with fresh per-sample state.
- `frontend/services/interventions.py`: rule/context-aware victim-facing message selection and privacy checks.
- `frontend/services/audio.py`: existing synthetic sounds plus accessible speech/stop helpers.
- `frontend/styles/custom.css`: responsive dashboard styling and readable warning styles.
- `backend/app/api/routes.py`: assessment and bounded, optional transcription endpoints; no provider feed endpoint until authorization.
- `backend/app/ai/`: existing intent service plus optional transcription implementation.
- `backend/app/engine/`: scoring rules and event context; keep actions synthetic.
- `backend/tests/` and `frontend/tests/`: focused regression coverage.
- `docs/`: setup, privacy, feed-readiness, and honest demo limitations.

## Dependencies and serving

Keep Python 3.10+, FastAPI, and Streamlit. Reuse the existing `google-genai` dependency only for optional backend transcription/intent when `GEMINI_API_KEY` is configured. Do not add a large speech-recognition or vector database dependency without a measurable need. Keep backend and frontend deploy boundaries intact. No production partner credentials, phone numbers, audio archives, customer data, or fabricated live events are introduced.
