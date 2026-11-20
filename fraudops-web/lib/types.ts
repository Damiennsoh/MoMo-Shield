export type RiskTier = "LOW" | "MEDIUM" | "HIGH";
export type RecommendedAction =
  | "SEAMLESS_APPROVE"
  | "COOLING_OFF_PROMPT"
  | "SIMULATED_HOLD"
  | "FRAUDOPS_ALERT";

export interface CommunicationEvent {
  event_id: string;
  msisdn: string;
  event_type: "communication";
  channel: "SMS" | "VOICE";
  text_or_transcript: string;
  timestamp: string;
  language_hint?: string;
  input_source?: string;
  counterparty_msisdn?: string | null;
}

export interface TransactionEvent {
  event_id: string;
  msisdn: string;
  event_type: "transaction";
  transaction_type: string;
  amount: number;
  counterparty_msisdn?: string | null;
  timestamp: string;
  ledger_verified: boolean;
  ussd_session_active?: boolean;
}

export interface DeviceBindingEvent {
  event_id: string;
  msisdn: string;
  event_type: "device_binding";
  new_imei: string;
  action: string;
  preceded_by_otp_activity?: boolean;
  timestamp: string;
}

export type SandboxEvent = CommunicationEvent | TransactionEvent | DeviceBindingEvent;

export interface IntentEvidence {
  lever?: string;
  requested_secret?: string | null;
  evidence?: string[];
  language_detected?: string;
  suggested_warning?: string;
}

export interface Assessment {
  msisdn: string;
  risk_score: number;
  risk_tier: RiskTier;
  /** Human-readable rule descriptions after normalization. */
  triggered_rules: string[];
  llm_extracted_intent?: IntentEvidence | null;
  llm_unavailable?: boolean;
  intent_source?: string;
  recommended_action: RecommendedAction;
  twi_warning_message?: string | null;
  english_warning_message?: string | null;
  intervention_title?: string | null;
  intervention_message?: string | null;
  reported_number_match?: boolean;
  /** Convenience: intervention_message ?? english_warning_message ?? twi. */
  guidance?: string;
  source: "backend" | "local";
  latency_ms: number;
  engine?: string;
  timestamp?: string;
}

export interface HealthResponse {
  status: string;
  engine: string;
  version: string;
}

export type HandsetEventType =
  | "sms"
  | "call"
  | "call_status"
  | "screen"
  | "warning"
  | "reset"
  | "status";

export interface HandsetEvent {
  type: HandsetEventType;
  /** UI-facing aliases (mapped to backend caller/message/etc. in api.ts). */
  from?: string;
  caller?: string;
  body?: string;
  message?: string;
  direction?: string;
  status?: string;
  title?: string;
  text?: string;
  text_twi?: string;
  transcript?: string;
  level?: "HIGH" | "MEDIUM" | "LOW";
  timestamp?: string;
  scenario?: string;
  event_key?: string;
  /** SIP control flags passed through to the backend publish schema. */
  trigger_sip?: boolean;
  sip_message?: boolean;
  sip_hangup?: boolean;
  interrupt_now?: boolean;
  suppress_audio?: boolean;
  sip_managed?: boolean;
  force_browser_ring?: boolean;
  [key: string]: unknown;
}

export interface ScenarioStep {
  delay_ms: number;
  event: SandboxEvent;
  note?: string;
}

export interface Scenario {
  id: string;
  name: string;
  caseRef: string;
  description: string;
  tier: RiskTier;
  expectedScore: number;
  steps: ScenarioStep[];
}
