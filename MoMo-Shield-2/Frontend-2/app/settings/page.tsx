'use client';

import { Activity, CircleCheck, CircleHelp, ShieldCheck } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { MtnMomoStatusCard } from '@/components/MtnMomoStatusCard';
import { Badge, Card } from '@/components/ui/primitives';
import { useStore } from '@/lib/useStore';

export default function SettingsPage() {
  const connected = useStore((state) => state.connected);
  const backendReachable = useStore((state) => state.backendReachable);
  const avgLatencyMs = useStore((state) => state.avgLatencyMs);
  const serviceStatus = connected ? 'Streaming' : backendReachable ? 'Reachable · reconnecting' : 'Unavailable';

  return (
    <AppShell>
      <div className="mb-7">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[9px] font-semibold uppercase tracking-[.18em] text-slate-600">Workspace configuration</span>
          <Badge variant="outline">SANDBOX</Badge>
        </div>
        <h1 className="text-[25px] font-semibold tracking-tight text-white">Settings <span className="text-slate-500">&amp; integrations</span></h1>
        <p className="mt-1.5 text-[11px] text-slate-500">Live backend readiness and provider configuration. Credentials remain server-side.</p>
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(290px,.8fr)]">
        <div className="space-y-5">
          <MtnMomoStatusCard />
          <Card className="overflow-hidden">
            <div className="border-b border-white/[.06] px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="grid h-8 w-8 place-items-center rounded-lg bg-sky-300/[.08] text-sky-300"><Activity size={15} /></div>
                <div><p className="text-[11px] font-semibold text-slate-200">Intelligence Core</p><p className="mt-1 text-[9px] text-slate-600">Current REST and WebSocket telemetry connection</p></div>
              </div>
            </div>
            <div className="divide-y divide-white/[.05] px-5">
              <div className="flex items-center gap-3 py-4">
                {connected ? <CircleCheck size={14} className="text-emerald-400" /> : <CircleHelp size={14} className="text-amber-400" />}
                <div className="flex-1"><p className="text-[10px] font-semibold text-slate-300">Telemetry stream</p><p className="mt-1 text-[9px] text-slate-600">Status is read from the active browser connection</p></div>
                <span className="text-right text-[9px] text-slate-400">{serviceStatus}</span>
              </div>
              <div className="flex items-center gap-3 py-4">
                <ShieldCheck size={14} className="text-slate-500" />
                <div className="flex-1"><p className="text-[10px] font-semibold text-slate-300">MNO fraud signals</p><p className="mt-1 text-[9px] text-slate-600">SMS, USSD, and voice streams require a separate authorized network feed.</p></div>
                <Badge variant="outline">NOT CONFIGURED</Badge>
              </div>
            </div>
          </Card>
        </div>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-400/[.08] text-emerald-300"><Activity size={16} /></div>
            <div><p className="text-[11px] font-semibold text-slate-200">Backend connection</p><p className="mt-1 text-[9px] text-slate-600">Measured from live telemetry</p></div>
          </div>
          <dl className="mt-5 space-y-3">
            <div className="flex items-center justify-between border-b border-white/[.05] pb-2.5 text-[9px]"><dt className="text-slate-500">WebSocket</dt><dd className="text-slate-300">{serviceStatus}</dd></div>
            <div className="flex items-center justify-between border-b border-white/[.05] pb-2.5 text-[9px]"><dt className="text-slate-500">Backend reachability</dt><dd className="text-slate-300">{backendReachable ? 'Reachable' : 'Unavailable'}</dd></div>
            <div className="flex items-center justify-between border-b border-white/[.05] pb-2.5 text-[9px]"><dt className="text-slate-500">Recent measured latency</dt><dd className="font-mono text-slate-300">{avgLatencyMs == null ? 'Not available' : `${avgLatencyMs} ms`}</dd></div>
          </dl>
          <p className="mt-4 text-[9px] leading-relaxed text-slate-500">No API keys are displayed or copied from this page. Configure provider secrets in the backend environment, not in browser storage.</p>
        </Card>
      </div>
    </AppShell>
  );
}
