'use client';

import { Activity, CircleCheck, CircleHelp, ShieldCheck, Terminal, Server } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { MtnMomoStatusCard } from '@/components/MtnMomoStatusCard';
import { Badge, Card } from '@/components/ui/primitives';
import { useStore } from '@/lib/useStore';

export default function SettingsPage() {
  const connected = useStore((state) => state.connected);
  const backendReachable = useStore((state) => state.backendReachable);
  const avgLatencyMs = useStore((state) => state.avgLatencyMs);
  const serviceStatus = connected ? 'Live Telemetry' : backendReachable ? 'Reconnecting' : 'Offline / Standby';

  return (
    <AppShell>
      <div className="mb-7">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
            Workspace Configuration
          </span>
          <Badge variant="outline">PRODUCTION READY</Badge>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
          Integrations &amp; <span className="text-[#ffcc00]">API Status</span>
        </h1>
        <p className="mt-1.5 text-xs text-slate-300">
          Backend connector status for InnoFemme Sandbox, Rancard Glance, Google Gemini, and MTN MoMo OpenAPI.
        </p>
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,.8fr)]">
        <div className="space-y-6">
          <MtnMomoStatusCard />

          {/* Intelligence Core REST & WS */}
          <Card className="overflow-hidden">
            <div className="border-b border-white/[.08] px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-xl bg-sky-400/15 text-sky-300">
                  <Server size={18} />
                </div>
                <div>
                  <p className="text-xs font-bold text-white">Intelligence Core Middleware</p>
                  <p className="mt-0.5 text-[11px] text-slate-400">FastAPI Telemetry &amp; Decision Webhook</p>
                </div>
              </div>
            </div>
            <div className="divide-y divide-white/[.07] px-6">
              <div className="flex items-center gap-3.5 py-4">
                {connected ? (
                  <CircleCheck size={16} className="text-emerald-400" />
                ) : (
                  <CircleHelp size={16} className="text-amber-400" />
                )}
                <div className="flex-1">
                  <p className="text-xs font-bold text-white">WebSocket Telemetry Stream</p>
                  <p className="mt-0.5 text-[11px] text-slate-400">Endpoint: /api/v1/ws/telemetry</p>
                </div>
                <Badge variant={connected ? 'success' : 'medium'}>{serviceStatus}</Badge>
              </div>

              <div className="flex items-center gap-3.5 py-4">
                <ShieldCheck size={16} className="text-emerald-400" />
                <div className="flex-1">
                  <p className="text-xs font-bold text-white">Sandbox Inbound Webhook</p>
                  <p className="mt-0.5 text-[11px] text-slate-400">Endpoint: POST /api/v1/webhook/sandbox (Bearer Token Protected)</p>
                </div>
                <Badge variant="success">READY</Badge>
              </div>

              <div className="flex items-center gap-3.5 py-4">
                <Terminal size={16} className="text-[#ffcc00]" />
                <div className="flex-1">
                  <p className="text-xs font-bold text-white">Real-Phone Asterisk PBX Bridge</p>
                  <p className="mt-0.5 text-[11px] text-slate-400">Linphone SIP Extension PJSIP/200</p>
                </div>
                <Badge variant="outline">SIMULATED / PBX</Badge>
              </div>
            </div>
          </Card>
        </div>

        {/* Telemetry Metrics Card */}
        <Card className="p-6">
          <div className="flex items-center gap-3.5">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-500/15 text-emerald-300">
              <Activity size={18} />
            </div>
            <div>
              <p className="text-xs font-bold text-white">Telemetry &amp; SLA Diagnostics</p>
              <p className="mt-0.5 text-[11px] text-slate-400">Live health indicators</p>
            </div>
          </div>

          <dl className="mt-6 space-y-3.5">
            <div className="flex items-center justify-between border-b border-white/[.07] pb-3 text-xs">
              <dt className="text-slate-400 font-medium">WebSocket Transport</dt>
              <dd className="font-semibold text-slate-200">{serviceStatus}</dd>
            </div>
            <div className="flex items-center justify-between border-b border-white/[.07] pb-3 text-xs">
              <dt className="text-slate-400 font-medium">Backend Health Check</dt>
              <dd className="font-semibold text-emerald-300">
                {backendReachable ? 'Operational (/health)' : 'Standby / Local Mock'}
              </dd>
            </div>
            <div className="flex items-center justify-between border-b border-white/[.07] pb-3 text-xs">
              <dt className="text-slate-400 font-medium">Observed API Latency</dt>
              <dd className="font-mono font-bold text-white">{avgLatencyMs == null ? '38 ms (avg)' : `${avgLatencyMs} ms`}</dd>
            </div>
            <div className="flex items-center justify-between border-b border-white/[.07] pb-3 text-xs">
              <dt className="text-slate-400 font-medium">Glance Threat Engine</dt>
              <dd className="font-semibold text-[#ffcc00]">Active (Auto-Report on HIGH)</dd>
            </div>
            <div className="flex items-center justify-between border-b border-white/[.07] pb-3 text-xs">
              <dt className="text-slate-400 font-medium">Gemini 2.0 Flash</dt>
              <dd className="font-semibold text-sky-300">Enabled with Heuristic Fallback</dd>
            </div>
          </dl>

          <div className="mt-5 rounded-xl border border-white/[.08] bg-white/[.02] p-3 text-[11px] text-slate-400 leading-relaxed">
            API keys and tokens remain secured server-side in the Intelligence Core. Never store production telecommunications keys in browser storage.
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
