import type { AssessmentResult, SandboxEventPayload } from './api';
import type { FraudAlert, RiskLevel, SignalEvent } from './useStore';

const KIND_BY_TYPE: Record<string, SignalEvent['kind']> = {
  sms: 'SMS',
  ussd: 'USSD',
  voice: 'VOICE',
  transaction: 'USSD',
};

function maskMsisdn(msisdn: string): string {
  const digits = msisdn.replace(/\D/g, '');
  if (digits.length < 7) return msisdn;
  const prefix = msisdn.startsWith('+') ? '+' : '';
  return `${prefix}${digits.slice(0, 5)} ••• ${digits.slice(-4)}`;
}

function tierToRisk(tier: AssessmentResult['risk_tier']): RiskLevel {
  return tier === 'HIGH' ? 'high' : tier === 'MEDIUM' ? 'medium' : 'low';
}

function actionToStatus(action: string): FraudAlert['status'] {
  if (action === 'BLOCKED') return 'blocked';
  if (action === 'WARNED') return 'active';
  return 'released';
}

export function assessmentToSignalEvent(result: AssessmentResult): SignalEvent {
  const time = new Date(result.timestamp).toLocaleTimeString('en-GB', { hour12: false });
  const kind = KIND_BY_TYPE[result.event_type] ?? 'SMS';
  return {
    id: result.event_id,
    time,
    kind,
    msisdn: maskMsisdn(result.msisdn),
    amount: '—',
    risk: tierToRisk(result.risk_tier),
    score: result.risk_score,
    summary:
      result.triggered_rules[0] ??
      (result.risk_tier === 'LOW' ? 'Standard MoMo activity' : 'Reviewed signal'),
  };
}

export function assessmentToAlert(result: AssessmentResult): FraudAlert | undefined {
  if (result.risk_tier === 'LOW') return undefined;
  return {
    ...assessmentToSignalEvent(result),
    rules: result.triggered_rules,
    glance: result.glance_status ?? 'No external reports',
    status: actionToStatus(result.action_taken),
  };
}

export function buildLabEvent(input: {
  msisdn: string;
  channel: 'sms' | 'voice' | 'ussd';
  text: string;
  amount?: number;
}): SandboxEventPayload {
  const eventType = input.channel === 'voice' ? 'voice' : input.channel === 'ussd' ? 'ussd' : 'sms';
  return {
    event_id: `lab-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    msisdn: input.msisdn,
    event_type: eventType,
    timestamp: new Date().toISOString(),
    payload: {
      text: input.text,
      ...(input.amount ? { amount: input.amount, type: 'transfer_out' } : {}),
    },
  };
}
