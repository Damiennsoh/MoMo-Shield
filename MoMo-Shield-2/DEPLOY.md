# MoMo Shield v2 — Deployment Guide

Production topology: **Intelligence Core** (FastAPI, `Backend-2/`) + **FraudOps frontend** (Next.js, `Frontend-2/`).
The MNO/sandbox calls the backend webhook directly; the frontend is display-only.

```
MNO Sandbox ──HTTPS──> Intelligence Core (Railway/Render) ──WS──> FraudOps (Vercel)
                            │
                            ├──> Rancard Glance (threat intel)
                            ├──> Gemini (intent analysis)
                            └──> Sandbox intervene API (blocks/warns)
```

## 1. Deploy the Intelligence Core (Backend-2)

Recommended: **Railway** or **Render** (both support WebSockets + Docker).

1. Push this repo to GitHub (already done).
2. Create a new service → deploy from repo → set **root directory** to `MoMo-Shield-2/Backend-2`.
3. Railway auto-detects `Dockerfile`. Render: New → Web Service → Docker runtime.
4. Set environment variables:

   | Variable | Value |
   |---|---|
   | `GLANCE_API_KEY` | Rancard Glance credential |
   | `GLANCE_BASE_URL` | e.g. `https://api.glance.rancardmobility.com/v1` |
   | `GEMINI_API_KEY` | Google AI Studio key |
   | `GEMINI_MODEL` | e.g. `gemini-2.0-flash-exp` |
   | `SANDBOX_API_KEY` | InnoFemme/MNO sandbox key |
   | `SANDBOX_BASE_URL` | e.g. `https://api.innofemme-sandbox.com/v1` |
   | `WEBHOOK_API_KEY` | **Generate a strong random secret** — the MNO must send it |
   | `CORS_ORIGINS` | `https://your-app.vercel.app` (comma-separate if multiple) |

   Leave `GLANCE_API_KEY`/`SANDBOX_API_KEY` empty or prefixed `your_` to keep mock mode.
5. Note the public URL, e.g. `https://momo-shield-core.up.railway.app`.
6. Verify: `GET https://<host>/health` → `{"status":"operational"}`.

## 2. Deploy the FraudOps frontend (Frontend-2)

1. Vercel → New Project → import repo → **Root Directory**: `MoMo-Shield-2/Frontend-2`.
   Framework preset: Next.js (auto-detected). Build command `npm run build`, output default.
2. Environment variables:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<your-backend-domain>` (no trailing slash) |

3. Deploy. Open the URL — dashboard hydrates from `GET /api/v1/events` and streams via `WS /api/v1/ws/telemetry`.

## 3. Connect the MNO / sandbox

Give the MNO this contract:

```
POST https://<backend>/api/v1/webhook/sandbox
Authorization: Bearer <WEBHOOK_API_KEY>
Content-Type: application/json

{
  "event_id": "unique-event-id",
  "msisdn": "+233XXXXXXXXX",
  "event_type": "sms | ussd | voice | transaction",
  "timestamp": "2026-11-21T10:00:00Z",
  "payload": { "text": "...", "amount": 500, "type": "transfer_out" }
}
```

Response: `AssessmentResult` — `risk_score`, `risk_tier` (LOW/MEDIUM/HIGH),
`triggered_rules`, `glance_status`, `llm_intent`, `action_taken`
(ALLOWED/WARNED/BLOCKED), `latency_ms`.

HIGH → backend calls `POST {SANDBOX_BASE_URL}/intervene` with `BLOCK_USSD` and
reports the MSISDN to Glance. MEDIUM → `PUSH_WARNING`.

## 4. Local development

```bash
# Terminal 1 — Intelligence Core
cd MoMo-Shield-2/Backend-2
pip install -r requirements.txt pytest
uvicorn main:app --port 8001

# Terminal 2 — FraudOps
cd MoMo-Shield-2/Frontend-2
npm install
npm run dev   # serves on :3000, reads NEXT_PUBLIC_API_URL from .env.local
```

`.env.local` (gitignored): `NEXT_PUBLIC_API_URL=http://localhost:8001`

## 5. Tests

```bash
cd MoMo-Shield-2/Backend-2 && python -m pytest -q   # 24 tests
cd MoMo-Shield-2/Frontend-2 && npm test             # node:test mapper tests
cd MoMo-Shield-2/Frontend-2 && npm run typecheck    # tsc --noEmit
```

## Production checklist

- [ ] `WEBHOOK_API_KEY` set (rejects unauthenticated event injection)
- [ ] `CORS_ORIGINS` restricted to the Vercel domain (no `*`)
- [ ] Real Glance + Sandbox credentials configured
- [ ] `NEXT_PUBLIC_API_URL` points at the deployed backend, not localhost
- [ ] HTTPS everywhere (Railway/Render/Vercel provide it automatically)
