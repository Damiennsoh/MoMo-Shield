'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  AudioLines,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  ExternalLink,
  Filter,
  Gauge,
  Search,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Sparkles,
  TrendingDown,
  Volume2,
  Zap,
} from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { AlertCard } from '@/components/AlertCard';
import { EventRow } from '@/components/EventRow';
import { FraudGraph } from '@/components/FraudGraph';
import { TrendChart } from '@/components/TrendChart';
import { RiskGauge } from '@/components/RiskGauge';
import { useStore, type FraudAlert, type SignalEvent } from '@/lib/useStore';
import { useTelemetry } from '@/lib/useTelemetry';
import {
  Badge,
  Button,
  Card,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  Input,
} from '@/components/ui/primitives';
import { playAlertTone, playEnglishTwiWarning, stopAllSounds } from '@/lib/sound';

function MetricCard({
  title,
  value,
  delta,
  icon: Icon,
  tone,
}: {
  title: string;
  value: string;
  delta: string;
  icon: typeof ShieldCheck;
  tone: 'yellow' | 'green' | 'blue' | 'rose';
}) {
  const tones = {
    yellow: 'border-[#ffcc00]/30 bg-[#ffcc00]/15 text-[#ffcc00]',
    green: 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300',
    blue: 'border-sky-500/30 bg-sky-500/15 text-sky-300',
    rose: 'border-rose-500/30 bg-rose-500/15 text-rose-300',
  };
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between">
        <span className={`grid h-9 w-9 place-items-center rounded-xl border ${tones[tone]} shadow-sm`}>
          <Icon size={18} />
        </span>
        <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400">
          <ArrowDownRight size={13} />
          {delta}
        </span>
      </div>
      <p className="mt-4 text-xs font-bold text-slate-400">{title}</p>
      <p className="mt-1 font-mono text-2xl font-extrabold tracking-tight text-white">{value}</p>
    </Card>
  );
}

export default function DashboardPage() {
  const events = useStore((state) => state.events);
  const alerts = useStore((state) => state.alerts);
  const resolveAlert = useStore((state) => state.resolveAlert);
  const connected = useStore((state) => state.connected);
  const backendReachable = useStore((state) => state.backendReachable);
  const avgLatencyMs = useStore((state) => state.avgLatencyMs);
  const soundEnabled = useStore((state) => state.soundEnabled);

  useTelemetry();

  const [selected, setSelected] = useState<FraudAlert | null>(null);
  const [filter, setFilter] = useState('');
  const [eventType, setEventType] = useState('ALL SIGNALS');
  const [actionDone, setActionDone] = useState('');

  const filtered = useMemo(
    () =>
      events.filter(
        (event) =>
          `${event.msisdn} ${event.kind} ${event.summary}`.toLowerCase().includes(filter.toLowerCase()) &&
          (eventType === 'ALL SIGNALS' || event.kind === eventType)
      ),
    [events, filter, eventType]
  );

  const activeAlerts = alerts.filter((alert) => alert.status === 'active');
  const blockedCount = alerts.filter((alert) => alert.status === 'blocked').length;
  const reviewedCount = alerts.filter((alert) => alert.status !== 'active').length;

  const handleAction = (action: NonNullable<FraudAlert['status']>) => {
    if (selected) {
      resolveAlert(selected.id, action);
      setActionDone(action);

      // If blocked, trigger warning audio & real-phone notification
      if (action === 'blocked') {
        void playAlertTone();
        if (soundEnabled) {
          void playEnglishTwiWarning({
            englishText: `Transaction blocked for ${selected.msisdn}. High fraud risk confirmed.`,
            twiText: `Kɔkɔbɔ! Yɛn hu sɛ obi rehyɛ wo. Mepa wo kyɛw, mfa wo PIN mma obiara!`,
          });
        }
        try {
          const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
          void fetch(`${backendUrl}/api/v1/demo/real-phone-action?action=warn`, { method: 'POST' }).catch(() => {});
        } catch {
          // ignore
        }
      }

      window.setTimeout(() => {
        setSelected(null);
        setActionDone('');
      }, 1200);
    }
  };

  const menuOptions = ['ALL SIGNALS', 'SMS', 'USSD', 'VOICE'];

  return (
    <AppShell>
      {/* Top Banner */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
              Live Sandbox Session
            </span>
            <span className="h-px w-6 bg-slate-700" />
            <Badge variant={connected ? 'success' : 'medium'}>
              <span
                className={`mr-1.5 inline-block h-2 w-2 rounded-full ${
                  connected ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : 'bg-amber-400'
                }`}
              />
              {connected ? 'Telemetry Live' : backendReachable ? 'Reconnecting' : 'Backend Offline'}
            </Badge>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            FraudOps <span className="text-[#ffcc00]">Command Center</span>
          </h1>
          <p className="mt-1 text-xs text-slate-300">
            Every transaction scored. Every subscriber protected in real-time.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-lg border border-white/[.12] bg-white/[.04] px-3.5 py-2 text-xs font-semibold text-slate-300 sm:flex">
            <span className={connected ? 'live-dot' : 'h-2 w-2 rounded-full bg-amber-400'} />
            {connected ? 'Sandbox Telemetry Connected' : backendReachable ? 'Reconnecting...' : 'Offline'}
          </div>
          <Link href="/lab">
            <Button size="sm" className="font-bold">
              <Zap size={14} />
              Run Signal Test
            </Button>
          </Link>
        </div>
      </div>

      {/* 4 KPIs */}
      <div className="mb-6 grid grid-cols-2 gap-3.5 xl:grid-cols-4">
        <MetricCard
          title="Sessions Blocked"
          value={String(blockedCount)}
          delta="Active Interventions"
          icon={ShieldCheck}
          tone="yellow"
        />
        <MetricCard
          title="Alerts Reviewed"
          value={String(reviewedCount)}
          delta="Analyst Triaged"
          icon={Check}
          tone="green"
        />
        <MetricCard
          title="Decision Latency"
          value={avgLatencyMs != null ? `${avgLatencyMs}ms` : '42ms'}
          delta="FastAPI SLA"
          icon={Zap}
          tone="blue"
        />
        <MetricCard
          title="Active Fraud Alerts"
          value={String(activeAlerts.length).padStart(2, '0')}
          delta="Requires Review"
          icon={Siren}
          tone="rose"
        />
      </div>

      {/* 3 Columns Layout */}
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(260px,1fr)_minmax(420px,1.65fr)_minmax(280px,1.05fr)]">
        {/* Col 1: Live Telemetry Feed */}
        <Card className="min-w-0 overflow-hidden" id="telemetry">
          <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="live-dot" />
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">Live Telemetry</h2>
              </div>
              <p className="mt-0.5 text-[10px] text-slate-400">
                Inbound signals <span className="text-slate-300 font-semibold">· {events.length} received</span>
              </p>
            </div>
            <button
              aria-label="Filter telemetry"
              className="grid h-7 w-7 place-items-center rounded-md border border-white/[.12] text-slate-300 transition hover:bg-white/[.08] hover:text-white"
            >
              <Filter size={13} />
            </button>
          </div>

          <div className="flex gap-1.5 border-b border-white/[.08] px-3.5 py-2.5 bg-black/20">
            {menuOptions.map((item) => (
              <button
                key={item}
                onClick={() => setEventType(item)}
                className={`rounded-lg px-2.5 py-1 text-[10px] font-bold transition ${
                  eventType === item
                    ? 'border border-[#ffcc00]/30 bg-[#ffcc00]/15 text-[#ffcc00]'
                    : 'text-slate-400 hover:text-white hover:bg-white/[.04]'
                }`}
              >
                {item}
              </button>
            ))}
          </div>

          <div className="border-b border-white/[.08] px-3.5 py-2.5">
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="h-8 pl-8 text-xs font-medium"
                placeholder="Search phone number or summary…"
              />
            </div>
          </div>

          <div className="scrollbar-thin max-h-[600px] overflow-y-auto divide-y divide-white/[.05]">
            {filtered.map((event) => (
              <EventRow
                key={event.id}
                event={event}
                onClick={() => {
                  const match = alerts.find((alert) => alert.id === event.id);
                  if (match) setSelected(match);
                }}
              />
            ))}
          </div>

          <div className="flex items-center justify-between border-t border-white/[.08] px-4 py-3 bg-black/10">
            <span className="text-[10px] text-slate-400 font-medium">
              {connected ? 'WebSocket Stream Active' : 'Connecting to Core…'}
            </span>
            <span
              className={`flex items-center gap-1.5 text-[10px] font-bold ${
                connected ? 'text-emerald-300' : 'text-amber-300'
              }`}
            >
              <span className={connected ? 'live-dot' : 'h-1.5 w-1.5 rounded-full bg-amber-400'} />
              {connected ? 'Streaming' : backendReachable ? 'Reconnecting' : 'Offline'}
            </span>
          </div>
        </Card>

        {/* Col 2: Fraud Network Map & Velocity */}
        <div className="min-w-0 space-y-5">
          <FraudGraph />

          <Card className="p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Activity size={16} className="text-[#ffcc00]" />
                  <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">Signal Velocity</h2>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">Transaction burst detection · sliding window</p>
              </div>
              <div className="text-right">
                <p className="font-mono text-xl font-extrabold text-white">{events.length}</p>
                <p className="text-[10px] text-slate-400">Events in state cache</p>
              </div>
            </div>
            <div className="mt-3.5 rounded-xl border border-white/[.08] bg-white/[.02] p-4 text-xs font-medium text-slate-300 leading-relaxed">
              Temporal window tracking: Rapid multi-hop transfers following SMS credits are prioritized under rule <strong>GH01 (Reversal Scam)</strong>.
            </div>
          </Card>

          <Card className="flex items-center justify-between gap-4 p-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-emerald-500/30 bg-emerald-500/15 text-emerald-300">
                <AudioLines size={20} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white">Hybrid Decision Engine</p>
                <p className="mt-0.5 truncate text-[11px] text-slate-400">
                  Deterministic Rules + Gemini 2.0 + Rancard Threat Feed
                </p>
              </div>
            </div>
            <span className="flex shrink-0 items-center gap-1.5 text-xs font-bold text-emerald-300">
              <CircleDot size={12} />
              Operational
            </span>
          </Card>
        </div>

        {/* Col 3: Active Alerts & Threat Feed */}
        <div className="space-y-5">
          <Card className="overflow-hidden" id="alerts">
            <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldAlert size={16} className="text-rose-400" />
                  <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">Active Alerts</h2>
                  <Badge variant="high">{activeAlerts.length}</Badge>
                </div>
                <p className="mt-0.5 text-[10px] text-slate-400">Priority security review queue</p>
              </div>
              <span className="text-[10px] font-bold text-slate-400">Real-time</span>
            </div>

            <div className="space-y-3 p-4">
              {activeAlerts.slice(0, 4).map((alert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onClick={() => {
                    setActionDone('');
                    setSelected(alert);
                  }}
                />
              ))}
            </div>

            <div className="border-t border-white/[.08] px-4 py-3 bg-black/10">
              <p className="text-[10px] text-slate-400 text-center font-medium">
                Tap any alert to inspect triggered rules, Rancard Glance status, and initiate intervention.
              </p>
            </div>
          </Card>

          {/* External Intelligence Card */}
          <Card className="overflow-hidden" id="threat-feed">
            <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-3.5">
              <div>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-[#ffcc00] shadow-[0_0_8px_#ffcc00]" />
                  <h2 className="text-xs font-bold text-white">External Intelligence</h2>
                </div>
                <p className="mt-0.5 text-[10px] text-slate-400">Rancard Glance Cross-Telco Feed</p>
              </div>
              <Badge variant="medium">READY / SANDBOX</Badge>
            </div>
            <div className="p-4 space-y-2">
              <p className="text-xs font-medium text-slate-300 leading-relaxed">
                Connects directly to the Rancard Glance API for known syndicate numbers and automated fraud reporting.
              </p>
              <div className="rounded-lg border border-white/[.08] bg-white/[.03] p-2.5 text-[10px] text-slate-400 font-mono">
                API Endpoint: /api/v1/integrations/glance
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Alert Triage Slide-over Modal */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="overflow-y-auto p-0">
          <div className="border-b border-white/[.1] px-6 py-6 bg-black/20">
            <div className="mb-3 flex items-center gap-2">
              <Badge variant={selected && selected.score >= 75 ? 'high' : 'medium'}>
                {selected && selected.score >= 75 ? 'HIGH RISK DETECTED' : 'ELEVATED RISK'}
              </Badge>
              <span className="flex items-center gap-1 text-xs text-slate-400 font-mono">
                <Clock3 size={13} />
                {selected?.time} GMT
              </span>
            </div>
            <DialogTitle className="pr-10 text-xl font-extrabold tracking-tight text-white">
              {selected?.summary}
            </DialogTitle>
            <DialogDescription className="mt-1.5 text-xs text-slate-300 font-medium">
              Flagged Transaction · MSISDN: <strong className="text-white font-mono">{selected?.msisdn}</strong>
            </DialogDescription>
          </div>

          <div className="space-y-6 px-6 py-6">
            {/* Risk Value Box */}
            <div className="flex items-center gap-5 rounded-2xl border border-white/[.1] bg-white/[.03] p-4 shadow-sm">
              <RiskGauge value={selected?.score ?? 0} size={120} compact />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[.15em] text-slate-400">
                  Transaction Amount
                </p>
                <p className="mt-1 font-mono text-2xl font-extrabold text-white">{selected?.amount}</p>
                <p className="mt-2 text-xs text-slate-300">
                  Engine Assessment:{' '}
                  <b className={selected && selected.score >= 75 ? 'text-rose-300 font-bold' : 'text-amber-300 font-bold'}>
                    {selected && selected.score >= 75 ? 'CRITICAL - HOLD REQUIRED' : 'REVIEW'}
                  </b>
                </p>
              </div>
            </div>

            {/* Triggered Rules */}
            <section>
              <h3 className="mb-2.5 text-xs font-bold uppercase tracking-wider text-slate-300">
                Triggered Fraud Rules
              </h3>
              <div className="space-y-2">
                {(selected?.rules ?? []).map((rule) => (
                  <div
                    key={rule}
                    className="flex items-center gap-2.5 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3.5 py-2.5"
                  >
                    <ShieldAlert size={15} className="text-rose-400 shrink-0" />
                    <span className="text-xs font-semibold text-rose-100">{rule}</span>
                    <span className="ml-auto text-[9px] font-extrabold text-rose-300 bg-rose-500/20 px-1.5 py-0.5 rounded">
                      MATCH
                    </span>
                  </div>
                ))}
              </div>
            </section>

            {/* On-screen Warning Message Display */}
            <section className="rounded-xl border border-amber-400/30 bg-amber-400/[.07] p-4">
              <h4 className="text-xs font-bold text-amber-200 flex items-center gap-2">
                <Volume2 size={15} className="text-amber-400" />
                Intervention Guidance (English + Twi)
              </h4>
              <p className="mt-2 text-xs text-slate-200 leading-relaxed">
                <strong>English: </strong> Transaction placed on hold. Do not share your PIN. Call 100 for support.
              </p>
              <p className="mt-1.5 text-xs text-slate-200 leading-relaxed border-t border-amber-400/20 pt-1.5">
                <strong className="text-[#ffcc00]">Twi: </strong> Kɔkɔbɔ! Yɛn hu sɛ obi rehyɛ wo. Mepa wo kyɛw, mfa wo PIN mma obiara!
              </p>
            </section>

            {/* Analyst Decision Controls */}
            <section>
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-300">
                Analyst Intervention Action
              </h3>
              <p className="mb-3 text-xs text-slate-400">
                Take action on this event. Blocking dispatches USSD cancellation and audio warnings to the handset.
              </p>
              <div className="grid grid-cols-3 gap-2.5">
                <Button variant="secondary" size="sm" onClick={() => handleAction('released')}>
                  <Check size={14} />
                  Release
                </Button>
                <Button variant="destructive" size="sm" onClick={() => handleAction('blocked')}>
                  <ShieldAlert size={14} />
                  Block &amp; Warn
                </Button>
                <Button variant="outline" size="sm" onClick={() => handleAction('escalated')}>
                  <ExternalLink size={14} />
                  Escalate
                </Button>
              </div>
              {actionDone && (
                <p className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 p-3 text-xs font-bold text-emerald-300">
                  <Check size={14} />
                  Analyst action recorded: {actionDone.toUpperCase()}. Intervention dispatched.
                </p>
              )}
            </section>

            <Link
              href="/handset"
              className="flex items-center justify-between rounded-xl border border-white/[.12] bg-white/[.04] p-3.5 text-xs font-semibold text-slate-200 transition hover:border-[#ffcc00] hover:text-[#ffcc00]"
            >
              <span className="flex items-center gap-2">
                <ExternalLink size={14} />
                Open Victim Handset View
              </span>
              <ChevronRight size={14} />
            </Link>
          </div>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
