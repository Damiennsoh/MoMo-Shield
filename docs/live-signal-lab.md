# Live Signal Lab and safe-demo boundaries

## What judges can test

The dashboard keeps its seven curated replays and adds separate workspaces for Live Signal Lab, Synthetic Event Injector, and Provider Feed Readiness. In Live Signal Lab, a judge can submit an unfamiliar synthetic SMS or voice transcript without choosing a scenario class. Each assessment gets a new fake identity and a fresh local accumulator. When the backend is reachable, the request runs through FastAPI; otherwise the deterministic local fallback is labelled. The returned score, tier, action, exact intent evidence, triggered rules, source, latency, event payload, and context-aware English guidance are displayed. A low score is not proof of safety, and the rule score is not a calibrated probability.

The sample buttons include a benign message, an ambiguous support message, and an attack-like example. Judges can edit them or type their own fictional signal. The UI blocks apparent phone numbers and numeric PIN/OTP values; replace them with `[PHONE]` and `[CODE]`. A confirmation is required before sending typed content. The language control is an evaluation label, not a guarantee of recognition. Twi/Akan, Ghanaian Pidgin, accents, and code-switching need evaluation with fluent speakers.

## Microphone and transcription

Microphone access is opt-in. Before recording, the user is told that the browser sends audio to the Streamlit demo server and that transcription forwards it to the configured backend/Gemini service. This application does not intentionally persist raw audio. The external service may process the sample under its own terms; use synthetic speech only and never record a real caller or customer. The API accepts WAV only and caps uploads at 8 MB.

Transcription returns a draft, may mark it uncertain, and never directly invokes assessment. The judge must review and edit the transcript in the text field, confirm it is synthetic, and explicitly press Analyze. The model is asked to preserve the language and mark unclear speech; that does not validate performance in Twi, Pidgin, accents, or code-switching. A missing key, unavailable model, or timeout leaves typed input and the local assessment fallback available.

To enable transcription, configure `GEMINI_API_KEY` for the backend and use a Gemini model that accepts audio. Do not store audio files in the repository or logs. The app uses a memory-only audio transfer for the request and then retains only the transcript draft in Streamlit session state.

## Context-aware warnings and access

Victim-facing guidance is selected from evidence such as credential requests, reversal/refund pressure, suspicious links, impersonation or threats, device/SIM changes, repeated calls, and transaction signals. A call burst alone is explicitly described as inconclusive. Warnings are short and action-oriented; all are shown as text. English speech can be started and stopped by the user through browser-native speech controls. The mock handset has a large-text option, screen-reader status announcements, and reduced-motion behavior.

Twi safety copy is intentionally withheld until a fluent-speaker review. Do not present an unreviewed translation as an instruction that a customer should follow. Browser speech depends on the device’s installed voices and is not guaranteed to sound like a local Ghanaian speaker. The dashboard cannot deliver SMS or USSD to a feature phone. That requires a provider-approved route. A smartphone demo cannot silently observe or intercept another app’s wallet session.

## Synthetic event injector

The injector creates one transaction or device-binding event using a new impossible-number-namespace identity and synthetic device identifier. It accepts only the project’s event types and bounded amount values; the backend model validates event shape. It cannot reach a ledger, handset, operator, or payment provider. A separate event sample starts with a fresh score context.

## Advisory case reference

The Live Signal Lab offers a user-triggered case-reference panel. It retrieves from `backend/app/knowledge/case_library.py`, a small versioned library of synthetic attack patterns, benign lookalikes, and safe responses. If Gemini is configured, the backend computes the corpus embeddings once per process, retrieves the top three examples, and asks Gemini for a cautious, schema-constrained advisory. Retrieved examples and the generated text are visibly separate from the primary rules score and cannot alter its tier or action. Similarity is a retrieval distance, not a probability. The case set is not exhaustive, not operator-sourced, and not validated against production traffic. The first query after a backend restart may take longer while the embeddings are created; later requests reuse the in-memory vectors.

The sidecar requires `GEMINI_API_KEY` and the configured embedding model (`GEMINI_EMBEDDING_MODEL`, default `gemini-embedding-001`). If Gemini or embedding retrieval is unavailable, the primary rules assessment remains unchanged. Do not claim coverage of all known attacks, calibrated similarity thresholds, or real-world performance.

## Provider feed readiness

The Provider Feed Readiness workspace states that no provider is connected. A live listener must not be enabled until the project receives written authorization, a documented sandbox API/webhook/stream, provider-issued test credentials, representative test data, a schema, and approved privacy/security/retention rules. A future feed adapter should expose source, event ID, timestamp, connection state, and redacted payload. Fixture replay and random-generated traffic must never be labelled live. There is no sandbox endpoint or partner feed included in this repository.

## Funding-stage description

A credible description for judges or funders is:

> “MoMo Shield is a prototype for detecting social-engineering risk around mobile-money events and delivering accessible, risk-appropriate interventions. Today we demonstrate the assessment pipeline on synthetic communication, device, and transaction events, with explainable rules and optional AI-assisted intent extraction and case references. We are not connected to an operator and do not block real transactions. We are seeking a partner and funding to connect to an authorized sandbox, validate performance on representative events, and co-design interventions for smartphone and feature-phone users, blind customers, and people with limited literacy before any production deployment.”

A funded pilot should establish a sanctioned sandbox, event/API integration and security, fluent-speaker and accessibility co-design, and evaluation against a reviewed test set. Report latency distributions, false-positive/false-negative rates on the evaluated set, benign-lookalike outcomes, and comprehension results only after measuring them. Do not invent a case count, accuracy rate, operator endorsement, or funding budget.
