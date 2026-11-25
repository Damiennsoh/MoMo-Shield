export interface SandboxEventPayload {
  event_id: string;
  msisdn: string;
  event_type: 'ussd' | 'sms' | 'voice' | 'transaction';
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface KBMatchData {
  case_id: string;
  title: string;
  typology: string;
  similarity: number;
  is_benign: boolean;
  psychological_levers: string[];
  source: string;
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
  kb_match?: KBMatchData | null;
  action_taken: 'ALLOWED' | 'WARNED' | 'BLOCKED' | string;
  latency_ms: number;
  timestamp: string;
}

export interface EventsResponse {
  events: AssessmentResult[];
}

export interface ThreatLedgerEntry {
  msisdn: string;
  threat_type: string;
  reports: number;
  effective_reports: number;
  age_days: number;
}

export interface ThreatLedgerResponse {
  entries: ThreatLedgerEntry[];
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

export async function fetchThreatLedger(limit = 50): Promise<ThreatLedgerEntry[]> {
  const res = await fetch(`${API_BASE}/api/v1/threat-ledger?limit=${limit}`);
  if (!res.ok) throw new Error(`Threat ledger fetch failed: ${res.status}`);
  const data = (await res.json()) as ThreatLedgerResponse;
  return data.entries ?? [];
}

export async function removeThreatLedgerEntry(msisdn: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/v1/threat-ledger/${encodeURIComponent(msisdn)}`,
    { method: 'DELETE' },
  );
  if (!res.ok) throw new Error(`Exoneration failed: ${res.status}`);
}

export async function resetDemoSession(): Promise<void> {
  await fetch(`${API_BASE}/api/v1/demo/reset`, { method: 'POST' }).catch(() => {});
}

export interface BenchmarkSummary {
  total_incidents: number;
  fraud_scenarios: number;
  legitimate_scenarios: number;
  stopped_count: number;
  held_before_cashout: number;
  got_through: number;
  false_positives: number;
  precision: string;
  recall: string;
  avg_latency_ms: number;
  ghc_protected: number;
  benchmark_time_ms: number;
  status: string;
  measurement_scope: string;
}

export interface BenchmarkIncident {
  id: string;
  name: string;
  typology: string;
  msisdn: string;
  is_fraud: boolean;
  score: number;
  tier: 'LOW' | 'MEDIUM' | 'HIGH';
  decision: 'BLOCKED' | 'WARNED' | 'ALLOWED';
  rules_fired: string[];
  latency_ms: number;
  estimated_loss_ghc: number;
}

export interface BenchmarkResponse {
  summary: BenchmarkSummary;
  results: BenchmarkIncident[];
  scope: string;
}

export async function runFraudBenchmark(): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_BASE}/api/v1/demo/benchmark`, { method: 'POST' });
  if (!res.ok) throw new Error(`Benchmark run failed: ${res.status}`);
  return res.json() as Promise<BenchmarkResponse>;
}

export interface FundFlowNode {
  id: string;
  role: 'suspect' | 'mule' | 'collector' | 'caller' | 'payer' | 'node' | string;
  flagged: boolean;
  in_count: number;
  out_count: number;
  pay_in: number;
  pay_out: number;
  volume: number;
  kinds: string[];
  ledger_reports: number;
}

export interface FundFlowEdge {
  from: string;
  to: string;
  kind: 'sms' | 'call' | 'payment' | 'payment_request' | 'switch' | 'bank_transfer' | string;
  point: string;
  amount: number | null;
  decision: string;
  ts: string;
  event_id: string;
}

export interface FundFlowGraph {
  nodes: FundFlowNode[];
  edges: FundFlowEdge[];
  edge_count: number;
  node_count: number;
  generated_at: string;
  scope: string;
}

export async function fetchFundFlow(limit = 400): Promise<FundFlowGraph> {
  const res = await fetch(`${API_BASE}/api/v1/fund-flow?limit=${limit}`);
  if (!res.ok) throw new Error(`Fund-flow fetch failed: ${res.status}`);
  return res.json() as Promise<FundFlowGraph>;
}

export interface EvidencePack {
  generated_at: string;
  subject: { msisdn: string; ledger: ThreatLedgerEntry | null };
  incident_summary: {
    observed_edges: number;
    blocked_or_delayed: number;
    observed_value_ghs: number;
    first_seen: string | null;
    last_seen: string | null;
    edge_kinds: string[];
  };
  fund_trail: Array<{
    ts: string;
    kind: string;
    point: string;
    direction: 'inbound' | 'outbound';
    counterparty: string;
    amount: number | null;
    decision: string;
    event_id: string;
  }>;
  related_assessments: AssessmentResult[];
  identity_provenance: Record<string, unknown> & { note?: string };
  scope: string;
}

export async function fetchEvidencePack(msisdn: string): Promise<EvidencePack> {
  const res = await fetch(`${API_BASE}/api/v1/evidence-pack/${encodeURIComponent(msisdn)}`);
  if (!res.ok) throw new Error(`Evidence pack failed: ${res.status}`);
  return res.json() as Promise<EvidencePack>;
}

export interface VelocityBucket {
  minute_ago: number;
  label: string;
  count: number;
}

export interface VelocityParty {
  msisdn: string;
  events: number;
  payments: number;
  kinds: string[];
}

export interface VelocityStats {
  window_minutes: number;
  buckets: VelocityBucket[];
  events_last_10m: number;
  current_per_minute: number;
  median_per_minute: number;
  burst_detected: boolean;
  top_sources: VelocityParty[];
  top_destinations: VelocityParty[];
  generated_at: string;
  scope: string;
}

export async function fetchVelocity(): Promise<VelocityStats> {
  const res = await fetch(`${API_BASE}/api/v1/velocity`);
  if (!res.ok) throw new Error(`Velocity fetch failed: ${res.status}`);
  return res.json() as Promise<VelocityStats>;
}
