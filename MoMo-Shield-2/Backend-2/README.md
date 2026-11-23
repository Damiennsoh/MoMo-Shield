# MoMo Shield Intelligence Core v2.0
Enterprise Fraud Middleware integrating InnoFemme Sandbox & Rancard Glance.

## Setup
1. `pip install -r requirements.txt`
2. `cp .env.example .env` (Add only credentials you have been issued)
3. `python main.py` (defaults to port 8000; honors `PORT`)

## Endpoints
- `POST /api/v1/plugin`: InnoFemme plug-in envelope (`point`, `institution`, `world`, `at`, `data`); five named points are mapped.
- `POST /api/v1/webhook/sandbox`: Separate internal `SandboxEvent` ingestion path; it is not interchangeable with the plug-in contract.
- `WS /api/v1/ws/telemetry`: Real-time feed for the Next.js SOC dashboard.
- `GET /api/v1/integrations/mtn-momo/status`: Reports whether MTN sandbox credentials are configured.
- `POST /api/v1/integrations/mtn-momo/collection/request-to-pay`: Explicitly initiates a sandbox RequestToPay. Requires `Authorization: Bearer <MTN_MOMO_REQUEST_API_KEY>` and a client-generated UUID `Idempotency-Key`.
- `GET /api/v1/integrations/mtn-momo/collection/request-to-pay/{reference_id}`: Checks the provider's authoritative transaction status; requires the same API key.
- `POST /api/v1/integrations/mtn-momo/callback`: Receives the provider callback and verifies final state with MTN before acknowledging it. Configure this public HTTPS URL in the MTN sandbox portal.

MTN MoMo Collection is a payment API, not an SMS/USSD/voice event feed. It is kept separate from fraud-signal ingestion. Configure `MTN_MOMO_API_USER`, `MTN_MOMO_API_KEY`, `MTN_MOMO_SUBSCRIPTION_KEY` and `MTN_MOMO_REQUEST_API_KEY` on the backend; never put these values in the browser or commit them. The adapter pins the target environment to `sandbox`. Callback delivery should be treated as a notification only: the backend checks the transaction status with MTN before accepting it. Actual MNO network signals still require a separate authorized signal-feed product/API.
