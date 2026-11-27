'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  AudioLines,
  Award,
  Check,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  ExternalLink,
  Filter,
  Lock,
  Gauge,
  Play,
  Radio,
  RefreshCw,
  Search,
  Server,
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
import { ThreatLedgerCard } from '@/components/ThreatLedgerCard';
import { EventRow } from '@/components/EventRow';
import { FraudGraph } from '@/components/FraudGraph';
import { VelocityCard } from '@/components/VelocityCard';
import { TrendChart } from '@/components/TrendChart';
import { RiskGauge } from '@/components/RiskGauge';
import { useStore, type FraudAlert, type SignalEvent } from '@/lib/useStore';
import { useTelemetry } from '@/lib/useTelemetry';
import { apiBase, runFraudBenchmark, type BenchmarkResponse } from '@/lib/api';
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
      <p className="mt-1 font-mono text-2xl font-extrabold tracking-tight text-slate-100">{value}</p>
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
  const [carrierFilter, setCarrierFilter] = useState<'ALL' | 'MTN' | 'TELECEL' | 'AT'>('ALL');
  const [carrierMenuOpen, setCarrierMenuOpen] = useState(false);
  const CARRIER_TABS = [
    { id: 'ALL', label: 'All Ghana MNOs (Unified)' },
    { id: 'MTN', label: 'MTN MoMo (65% share)' },
    { id: 'TELECEL', label: 'Telecel Cash (22% share)' },
    { id: 'AT', label: 'AT Money (13% share)' },
  ] as const;
  const [benchmarkOpen, setBenchmarkOpen] = useState(false);
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkResponse | null>(null);
  const [isPlayingWarning, setIsPlayingWarning] = useState(false);
  const [glanceDetailsOpen, setGlanceDetailsOpen] = useState(false);

  const handleRunBenchmark = async () => {
    setBenchmarkOpen(true);
    setBenchmarkRunning(true);
    try {
      const res = await runFraudBenchmark();
      setBenchmarkData(res);
    } catch (e) {
      console.error('Benchmark execution error:', e);
    } finally {
      setBenchmarkRunning(false);
    }
  };

  const handlePlayWarning = () => {
    if (!selected) return;
    setIsPlayingWarning(true);
    void playEnglishTwiWarning({
      englishText: `Transaction blocked for subscriber ${selected.msisdn}. High fraud risk confirmed.`,
      twiText: `Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!`,
    });
    setTimeout(() => setIsPlayingWarning(false), 3800);
  };

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

  // Calculate actual intercepted Cedi amount based on blocked alerts
  const ghcProtected = useMemo(() => {
    const blockedAlerts = alerts.filter((a) => a.status === 'blocked');
    if (blockedAlerts.length === 0) return 0;
    return blockedAlerts.reduce((sum, a) => {
      const match = a.amount.match(/[0-9,.]+/);
      const val = match ? parseFloat(match[0].replace(/,/g, '')) : 850;
      return sum + (isNaN(val) ? 850 : val);
    }, 0);
  }, [alerts]);

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
            twiText: `Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!`,
          });
        }
        try {
          void fetch(`${apiBase()}/api/v1/demo/real-phone-action?action=warn`, { method: 'POST' }).catch(() => {});
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
  <div className="dashboard-content">
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
            <span
              className="flex items-center gap-1 text-[10px] font-semibold text-slate-500"
              title="Demo processes synthetic sandbox data only. Production path: PII-redacted enrichment, OTP exclusion, local-first decision engine (Act 843-aware)."
            >
              <Lock size={10} />
              Synthetic Data · Privacy-First
            </span>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            FraudOps <span className="text-[#ffcc00]">Command Centre</span>
          </h1>
          <p className="mt-1 text-xs text-slate-300">
            Every transaction scored. Every subscriber protected in real-time.
          </p>
        </div>

<div className="flex flex-wrap items-center gap-3">
  <Button
  size="sm"
  onClick={handleRunBenchmark}
            className="border border-[#ffcc00]/40 bg-[#ffcc00]/15 text-[#ffcc00] hover:bg-[#ffcc00]/25 font-bold flex items-center gap-1.5"
          >
            <Award size={14} />
            <span>InnoFemme Benchmark</span>
          </Button>
          <div className="hidden items-center gap-2 rounded-lg border border-white/[.12] bg-white/[.04] px-3.5 py-2 text-xs font-semibold text-slate-300 sm:flex">
            <span className={connected ? 'live-dot' : 'h-2 w-2 rounded-full bg-amber-400'} />
            {connected ? 'Sandbox Telemetry Connected' : backendReachable ? 'Reconnecting...' : 'Offline'}
          </div>
          <Link href="/lab">
            <Button size="sm" className="font-bold flex items-center gap-1.5">
              <Zap size={14} />
              Run Signal Test
            </Button>
          </Link>
        </div>
      </div>

      <details className="group mb-4 rounded-xl border border-white/[.12] bg-[#0c131d]/90 shadow-sm backdrop-blur-md">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-xl px-4 py-3.5 outline-none transition hover:bg-white/[.03] focus-visible:ring-2 focus-visible:ring-[#ffcc00] [&::-webkit-details-marker]:hidden">
          <span className="flex min-w-0 items-center gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-emerald-500/10 text-emerald-400">
              <ShieldCheck size={17} />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-bold text-white">Protection integrations</span>
              <span className="mt-0.5 block text-xs text-slate-400">
                Messages, calls, payments, and in-app actions are monitored.
              </span>
            </span>
          </span>
          <span className="flex shrink-0 items-center gap-3">
            <span className="hidden items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-300 sm:inline-flex">
              <span className="live-dot" />4 protections active
            </span>
            <span className="hidden text-xs font-semibold text-slate-300 sm:inline group-open:hidden">View details</span>
            <span className="hidden text-xs font-semibold text-slate-300 sm:group-open:inline">Hide details</span>
            <ChevronDown size={16} className="shrink-0 text-slate-400 transition-transform group-open:rotate-180" />
          </span>
        </summary>

        <div className="border-t border-white/[.08] px-4 pb-4 pt-3">
          <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            <Server size={13} />
            InnoFemme integration details
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: 'SMS screening', hook: 'Hook 12 · sms.deliver' },
              { label: 'Call screening', hook: 'Hook 13 · call.connect' },
              { label: 'Payment checks', hook: 'Hook 15 · payment.authorize' },
              { label: 'In-app actions', hook: 'Hook 7 · menu.open' },
            ].map(({ label, hook }) => (
              <div key={hook} className="flex min-w-0 items-center justify-between gap-2 rounded-lg border border-white/[.08] bg-white/[.03] px-3 py-2">
                <span className="min-w-0">
                  <span className="block text-xs font-semibold text-slate-200">{label}</span>
                  <code className="mt-0.5 block truncate text-[10px] text-slate-400">{hook}</code>
                </span>
                <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">Active</span>
              </div>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
            <span>Bridge endpoint</span>
            <code className="rounded border border-white/[.08] bg-white/[.04] px-2 py-1 font-mono text-[#ffcc00]">bridge://laptop/api/v1/plugin</code>
          </div>
        </div>
      </details>

      {/* Carrier Multi-Tenant Selector — folded by default to keep the
          header clean; expands horizontally on click */}
      <div className="mb-5 border-b border-white/[.08] pb-3 text-xs">
        <button
          onClick={() => setCarrierMenuOpen((open) => !open)}
          className="flex items-center gap-2 rounded-lg border border-white/[.12] bg-white/[.04] px-3 py-1.5 font-bold text-slate-300 transition hover:bg-white/[.07]"
        >
          <span className="uppercase tracking-wider text-[10px] text-slate-500">Carrier Tenant:</span>
          <span className={carrierFilter === 'ALL' ? 'text-white' : 'text-[#ffcc00]'}>
            {CARRIER_TABS.find((t) => t.id === carrierFilter)?.label}
          </span>
          <ChevronDown
            size={14}
            className={`text-slate-400 transition-transform ${carrierMenuOpen ? 'rotate-180' : ''}`}
          />
        </button>
        {carrierMenuOpen && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {CARRIER_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setCarrierFilter(tab.id);
                  setCarrierMenuOpen(false);
                }}
                className={`rounded-lg px-3 py-1.5 font-bold transition text-xs ${
                  carrierFilter === tab.id
                    ? 'border border-[#ffcc00]/40 bg-[#ffcc00]/15 text-[#ffcc00] shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/[.04]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 4 KPIs */}
      <div className="mb-6 grid grid-cols-2 gap-3.5 xl:grid-cols-4">
        <MetricCard
          title="GH₵ Protected"
          value={ghcProtected > 0 ? `GH₵ ${ghcProtected.toLocaleString()}` : 'GH₵ 0.00'}
          delta={ghcProtected > 0 ? 'Direct Loss Prevented' : 'Awaiting Interventions'}
          icon={ShieldCheck}
          tone="yellow"
        />
        <MetricCard
          title="Sessions Intercepted"
          value={String(blockedCount + reviewedCount)}
          delta={`${blockedCount} Auto-Blocked`}
          icon={Check}
          tone="green"
        />
        <MetricCard
          title="Decision Latency"
          value={avgLatencyMs != null ? `${avgLatencyMs}ms` : '—'}
          delta="Observed events only; not p95"
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
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(240px,0.95fr)_minmax(390px,1.5fr)_minmax(245px,0.95fr)]">
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

          <VelocityCard />

          <Card className="flex items-center justify-between gap-4 p-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-emerald-500/30 bg-emerald-500/15 text-emerald-300">
                <AudioLines size={20} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-white">Hybrid Decision Engine</p>
                <p className="mt-0.5 truncate text-[11px] text-slate-400">
                  Rules + optional ML/RAG/Glance/ledger signals (where configured)
                </p>
              </div>
            </div>
            <span
              className={`flex shrink-0 items-center gap-1.5 text-[10px] font-bold ${
                backendReachable ? 'text-emerald-300' : 'text-slate-400'
              }`}
            >
              <CircleDot size={12} />
              {backendReachable ? 'Core reachable' : 'Offline / unverified'}
            </span>
          </Card>
        </div>

        {/* Col 3: Active Alerts & Threat Feed */}
<div className="min-w-0 space-y-5">
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
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 shrink-0 rounded-full bg-slate-500" />
                  <h2 id="glance-title" className="truncate text-xs font-bold text-white">External Intelligence</h2>
                </div>
                <p className="mt-0.5 truncate pl-4 text-[10px] text-slate-400">Rancard Glance · optional provider feed</p>
              </div>
              <button
                type="button"
                aria-expanded={glanceDetailsOpen}
                aria-controls="glance-details"
                onClick={() => setGlanceDetailsOpen((open) => !open)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-white/[.1] px-2.5 py-1.5 text-[10px] font-bold text-slate-300 transition hover:border-white/20 hover:bg-white/[.05] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ffcc00]"
              >
                {glanceDetailsOpen ? 'Hide details' : 'Show details'}
                <ChevronDown
                  size={13}
                  aria-hidden="true"
                  className={`transition-transform ${glanceDetailsOpen ? 'rotate-180' : ''}`}
                />
              </button>
            </div>
            <div
              id="glance-details"
              role="region"
              aria-labelledby="glance-title"
              hidden={!glanceDetailsOpen}
              className="space-y-2 border-t border-white/[.08] p-4"
            >
              <Badge variant="medium">CONFIGURATION-DEPENDENT</Badge>
              <p className="text-xs font-medium leading-relaxed text-slate-300">
                The backend adapter can query Rancard Glance when provider credentials are configured. Live connectivity is not confirmed by this dashboard; no dedicated Glance status endpoint is implemented.
              </p>
              <div className="rounded-lg border border-white/[.08] bg-white/[.03] p-2.5 text-[10px] font-mono text-slate-400">
                Optional server-side integration · credentials required
              </div>
            </div>
          </Card>

          {/* Proprietary Threat Ledger Card */}
          <ThreatLedgerCard />
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
              <p className="mb-2 text-[10px] text-slate-500">
                Signal inputs — external ratings (e.g. Glance HIGH) are sources, not the verdict tier shown above.
              </p>
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
                <strong className="text-[#ffcc00]">Twi: </strong> Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!
              </p>

              {/* Play English + Twi Audio Warning Button */}
              <div className="mt-3 pt-3 border-t border-amber-400/20 flex items-center justify-between">
                <span className="text-[11px] text-amber-200/80 font-medium">Broadcast to Handset:</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handlePlayWarning}
                  disabled={isPlayingWarning}
                  className="border-amber-400/40 bg-amber-400/10 text-amber-200 hover:bg-amber-400/20 font-bold text-xs"
                >
                  <Volume2 size={13} className={isPlayingWarning ? 'animate-bounce text-[#ffcc00]' : ''} />
                  <span>{isPlayingWarning ? 'Broadcasting...' : 'Play Twi+English Warning'}</span>
                </Button>
              </div>
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

      {/* Local deterministic rule-fixture dialog */}
      <Dialog open={benchmarkOpen} onOpenChange={(open) => !benchmarkRunning && setBenchmarkOpen(open)}>
        <DialogContent className="max-w-3xl overflow-y-auto max-h-[85vh] p-0">
          <div className="border-b border-white/[.1] px-6 py-5 bg-gradient-to-r from-[#111927] to-[#070b10]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#ffcc00]/15 text-[#ffcc00] border border-[#ffcc00]/30">
                  <Award size={18} />
                </div>
                <div>
                  <DialogTitle className="text-lg font-extrabold text-white">
                    Local Fraud Rule <span className="text-[#ffcc00]">Fixtures</span>
                  </DialogTitle>
                  <DialogDescription className="text-xs text-slate-400">
                    Local rule-only regression fixtures; not the live InnoFemme simulator
                  </DialogDescription>
                </div>
              </div>
              <Badge variant={benchmarkRunning ? 'medium' : 'success'}>
                {benchmarkRunning ? 'RUNNING TEST BATCH...' : 'BENCHMARK COMPLETE'}
              </Badge>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {benchmarkRunning ? (
              <div className="py-12 text-center space-y-4">
                <RefreshCw size={32} className="animate-spin mx-auto text-[#ffcc00]" />
                <p className="text-sm font-bold text-white">Running local deterministic regression fixtures...</p>
                <p className="text-xs text-slate-400">No sandbox calls, external lookups, or end-to-end timing are included.</p>
              </div>
            ) : benchmarkData ? (
              <>
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                  {benchmarkData.scope}
                </div>
                {/* 4 Scorecard Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Fraud fixtures flagged</p>
                    <p className="mt-1 font-mono text-2xl font-extrabold text-white">
                      {benchmarkData.summary.stopped_count}/{benchmarkData.summary.fraud_scenarios}
                    </p>
                    <p className="text-[10px] font-bold text-emerald-300 mt-1">Synthetic fixture result</p>
                  </div>
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Benign fixtures blocked</p>
                    <p className="mt-1 font-mono text-2xl font-extrabold text-white">
                      {benchmarkData.summary.false_positives}
                    </p>
                    <p className="text-[10px] font-bold text-emerald-300 mt-1">Small fixed fixture set only</p>
                  </div>
                  <div className="rounded-xl border border-[#ffcc00]/30 bg-[#ffcc00]/10 p-3.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-[#ffcc00]">GH₵ Protected</p>
                    <p className="mt-1 font-mono text-xl font-extrabold text-white">
                      GH₵ {benchmarkData.summary.ghc_protected.toLocaleString()}
                    </p>
                    <p className="text-[10px] font-bold text-[#ffcc00] mt-1">Fixture-based estimate only</p>
                  </div>
                  <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-3.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-sky-400">Avg rule-fixture time</p>
                    <p className="mt-1 font-mono text-2xl font-extrabold text-white">
                      {benchmarkData.summary.avg_latency_ms}ms
                    </p>
                    <p className="text-[10px] font-bold text-sky-300 mt-1">Not end-to-end plug-in latency</p>
                  </div>
                </div>

                {/* Detailed Table */}
                <div className="rounded-xl border border-white/[.1] overflow-hidden">
                  <div className="bg-black/30 px-4 py-2.5 text-xs font-bold text-slate-300 border-b border-white/[.08]">
                    Scenario-by-Scenario Mitigation Breakdown
                  </div>
                  <div className="max-h-64 overflow-y-auto divide-y divide-white/[.06]">
                    {benchmarkData.results.map((r) => (
                      <div key={r.id} className="p-3 text-xs flex items-center justify-between hover:bg-white/[.02]">
                        <div className="min-w-0 pr-3">
                          <p className="font-bold text-white truncate">{r.name}</p>
                          <p className="text-[10px] font-mono text-slate-400">
                            {r.typology} • Score: {r.score}/100 • Latency: {r.latency_ms}ms
                          </p>
                        </div>
                        <Badge variant={r.decision === 'BLOCKED' ? 'high' : r.decision === 'WARNED' ? 'medium' : 'success'}>
                          {r.decision}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : null}

            <div className="flex justify-end gap-2 border-t border-white/[.08] pt-4">
              <Button variant="secondary" size="sm" onClick={() => setBenchmarkOpen(false)}>
                Close Scorecard
              </Button>
              <Button size="sm" onClick={handleRunBenchmark} disabled={benchmarkRunning}>
                <RefreshCw size={13} className={benchmarkRunning ? 'animate-spin' : ''} />
                Re-Run Benchmark
              </Button>
            </div>
          </div>
        </DialogContent>
  </Dialog>
  </div>
  </AppShell>
  );
}
