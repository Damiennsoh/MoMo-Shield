# MoMo Shield — FraudOps Command Center (Next.js frontend)

A polished, fintech-grade frontend for the MoMo Shield fraud-detection backend
(FastAPI). Dark security-console aesthetic: deep navy/charcoal, electric-yellow
accent, risk-tier colors, Inter + JetBrains Mono typography.

> Prototype demonstration with synthetic data only — not a production
> fraud-prevention system.

## Stack

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS (custom design tokens, no component library)
- SSE via native `EventSource` for the second-device handset stream
- No state library — plain React state; assessments are short-lived

## Quick start

```bash
cp .env.example .env.local   # adjust if needed
npm install
npm run dev                  # http://localhost:3000
```

Run alongside the backend demo stack:

```bash
docker compose --env-file .env.demo -f docker-compose.demo.yml up -d
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | FastAPI base URL |
| `NEXT_PUBLIC_DEMO_DEVICE_TOKEN` | — | Bearer token for `/demo-device/*` endpoints |
| `NEXT_PUBLIC_MOCK_SSE` | `false` | `true` = built-in mock handset stream for offline UI testing |

## Routes

- `/` — FraudOps Command Center with four workspaces:
  - **Curated Scenario Replay** — 7 fixture scenarios (GH01, GH18, GH17, GH02,
    GH15, GH19 + legitimate baseline), timed step replay, live victim-handset
    mock, event stream log, per-scenario result cards, "Run all" mode.
  - **Live Signal Lab** — SMS/voice transcript assessment, language hint,
    consent-gated mic recording (MediaRecorder → `/transcribe`), synthetic-content
    confirmation, example chips, advisory case-reference panel, Linphone toggles.
  - **Synthetic Event Injector** — single transaction/device-binding event form.
  - **Provider Feed Readiness** — honest "NOT CONNECTED" status page.
- `/handset` — second-device handset view (SSE; access with `#token=<token>`).

## Backend contract

Matches the FastAPI backend under `/api/v1`: `/health`, `/assess`, `/reset`,
`/transcribe`, `/case-reference`, `/gemini/healthcheck`, and the
`/demo-device/*` publish/stream/call-action/audio bridge (18s assess timeout,
local deterministic fallback clearly labelled "local rules").

## Behavior rules honored

- Persistent honest synthetic-data disclaimer
- 18s assessment timeout with clearly-labelled local fallback
- No real phone numbers/PINs rendered; synthetic-identity pattern throughout
- Keyboard accessible; respects `prefers-reduced-motion`; handset view readable at 360px

## Integration notes

- This frontend does not modify the existing `backend/` or Streamlit `frontend/` code.
- The backend must send CORS headers for the dev origin (or run behind the same
  Compose network / reverse proxy in production).
