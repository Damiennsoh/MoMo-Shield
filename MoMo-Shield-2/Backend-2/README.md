# MoMo Shield Intelligence Core v2.0
Enterprise Fraud Middleware integrating InnoFemme Sandbox & Rancard Glance.

## Setup
1. `pip install -r requirements.txt`
2. `cp .env.example .env` (Add your API keys)
3. `python main.py`

## Endpoints
- `POST /api/v1/webhook/sandbox`: Ingest events from Sandbox.
- `WS /api/v1/ws/telemetry`: Real-time feed for Next.js SOC Dashboard.