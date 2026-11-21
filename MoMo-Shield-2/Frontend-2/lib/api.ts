export interface SandboxEventPayload {
  event_id: string;
  msisdn: string;
  event_type: 'ussd' | 'sms' | 'voice' | 'transaction';
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface AssessmentResult {
  event_id: string;
  msisdn: string;
  event_type: 'ussd' | 'sms' | 'voice' | 'transaction';
  risk_score: number;
  risk_tier: 'LOW' | 'MEDIUM' | 'HIGH';
  triggered_rules: string[];
  glance_status?: string | null;
  llm_intent?: string | null;
  action_taken: 'ALLOWED' | 'WARNED' | 'BLOCKED' | string;
  latency_ms: number;
  timestamp: string;
}

export interface EventsResponse {
  events: AssessmentResult[];
}

export interface MtnMomoStatus {
  provider: string;
  environment: 'sandbox';
  configured: boolean;
  requestApiEnabled: boolean;
  ready: boolean;
  operations: string[];
  webhook: string;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000';

export function apiBase(): string {
  return API_BASE;
}

export function telemetryWsUrl(): string {
  const base = API_BASE.replace(/^http/, 'ws');
  return `${base}/api/v1/ws/telemetry`;
}

export async function submitSandboxEvent(
  event: SandboxEventPayload,
): Promise<AssessmentResult> {
  const res = await fetch(`${API_BASE}/api/v1/webhook/sandbox`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(event),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`Sandbox webhook ${res.status}: ${detail || res.statusText}`);
  }
  return res.json() as Promise<AssessmentResult>;
}

export async function fetchRecentEvents(limit = 50): Promise<AssessmentResult[]> {
  const res = await fetch(`${API_BASE}/api/v1/events?limit=${limit}`);
  if (!res.ok) throw new Error(`Events fetch failed: ${res.status}`);
  const data = (await res.json()) as EventsResponse;
  return data.events ?? [];
}
