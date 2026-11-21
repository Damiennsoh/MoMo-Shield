'use client';

import { create } from 'zustand';
import type { AssessmentResult } from './api';
import { assessmentToAlert, assessmentToSignalEvent } from './mappers';

export type RiskLevel = 'low' | 'medium' | 'high';
export type EventKind = 'SMS' | 'USSD' | 'VOICE';
export interface SignalEvent {
  id: string;
  time: string;
  kind: EventKind;
  msisdn: string;
  amount: string;
  risk: RiskLevel;
  score: number;
  summary: string;
}
export interface FraudAlert extends SignalEvent {
  rules: string[];
  glance: string;
  status?: 'active' | 'released' | 'blocked' | 'escalated';
}
interface ShieldStore {
  events: SignalEvent[];
  alerts: FraudAlert[];
  currentRisk: number;
  handsetMode: RiskLevel;
  handsetMessage: string;
  twiWarningMessage: string;
  englishWarningMessage: string;
  soundEnabled: boolean;
  connected: boolean;
  backendReachable: boolean;
  avgLatencyMs: number | null;
  addEvent: (event: SignalEvent, alert?: FraudAlert) => void;
  ingestAssessment: (result: AssessmentResult) => void;
  hydrateAssessments: (results: AssessmentResult[]) => void;
  setConnection: (connected: boolean, reachable?: boolean) => void;
  setAnalysis: (score: number, message: string, twiMessage?: string) => void;
  resolveAlert: (id: string, status: NonNullable<FraudAlert['status']>) => void;
  toggleSound: () => void;
}

const getInitialSoundPreference = (): boolean => {
  if (typeof window === 'undefined') return true;
  const stored = window.localStorage.getItem('momo-shield-sound');
  return stored !== 'false';
};

export const useStore = create<ShieldStore>((set) => ({
  events: [],
  alerts: [],
  currentRisk: 0,
  handsetMode: 'low',
  handsetMessage: 'Your MoMo account is protected. Never share your PIN with anyone.',
  twiWarningMessage: 'Mepa wo kyɛw, fa wo PIN kɔ ma. We’ll never ask for your PIN.',
  englishWarningMessage: 'Your MoMo account is protected. Never share your PIN with anyone.',
  soundEnabled: getInitialSoundPreference(),
  connected: false,
  backendReachable: false,
  avgLatencyMs: null,
  toggleSound: () =>
    set((state) => {
      const next = !state.soundEnabled;
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('momo-shield-sound', String(next));
      }
      return { soundEnabled: next };
    }),
  addEvent: (event, alert) => set((state) => ({ events: [event, ...state.events].slice(0, 12), alerts: alert ? [alert, ...state.alerts].slice(0, 8) : state.alerts })),
  ingestAssessment: (result) =>
    set((state) => {
      const event = assessmentToSignalEvent(result);
      const alert = assessmentToAlert(result);
      return {
        events: [event, ...state.events].slice(0, 12),
        alerts: alert ? [alert, ...state.alerts].slice(0, 8) : state.alerts,
        currentRisk: result.risk_score,
        handsetMode: result.risk_tier === 'HIGH' ? 'high' : result.risk_tier === 'MEDIUM' ? 'medium' : 'low',
        handsetMessage:
          result.risk_tier === 'HIGH'
            ? 'Transaction blocked. This request may be a scam. Never share your MoMo PIN. Call 100 for help.'
            : result.risk_tier === 'MEDIUM'
              ? 'Take a moment before you act. We noticed unusual activity. Never share your PIN.'
              : 'This activity looks safe. Remember: MoMo will never ask for your PIN.',
        avgLatencyMs: result.latency_ms,
      };
    }),
  hydrateAssessments: (results) =>
    set(() => {
      const events: SignalEvent[] = [];
      const alerts: FraudAlert[] = [];
      let latest: AssessmentResult | null = null;
      for (const result of results.slice().reverse()) {
        events.push(assessmentToSignalEvent(result));
        const alert = assessmentToAlert(result);
        if (alert) alerts.push(alert);
        if (!latest) latest = result;
      }
      return {
        events: events.slice(0, 12),
        alerts: alerts.slice(0, 8),
        backendReachable: true,
        avgLatencyMs: latest?.latency_ms ?? null,
        ...(latest
          ? {
              currentRisk: latest.risk_score,
              handsetMode: (latest.risk_tier === 'HIGH' ? 'high' : latest.risk_tier === 'MEDIUM' ? 'medium' : 'low') as RiskLevel,
            }
          : {}),
      };
    }),
  setConnection: (connected, reachable) =>
    set((state) => ({ connected, backendReachable: reachable ?? state.backendReachable })),
  setAnalysis: (score, message, twiMessage) =>
    set({
      currentRisk: score,
      handsetMode: score >= 75 ? 'high' : score >= 40 ? 'medium' : 'low',
      handsetMessage: message,
      englishWarningMessage: message,
      ...(twiMessage ? { twiWarningMessage: twiMessage } : {}),
    }),
  resolveAlert: (id, status) => set((state) => ({ alerts: state.alerts.map((alert) => alert.id === id ? { ...alert, status } : alert) })),
}));
