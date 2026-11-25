'use client';

import { useCallback, useEffect, useState } from 'react';
import { Activity, Flame, Zap } from 'lucide-react';
import { Card, Badge } from '@/components/ui/primitives';
import { fetchVelocity, type VelocityStats } from '@/lib/api';

function maskMsisdn(msisdn: string): string {
  const digits = msisdn.replace(/\D/g, '');
  if (digits.length < 7) return msisdn;
  return `${digits.slice(0, 5)} ••• ${digits.slice(-4)}`;
}

export function VelocityCard() {
  const [stats, setStats] = useState<VelocityStats | null>(null);

  const load = useCallback(async () => {
    try {
      setStats(await fetchVelocity());
    } catch {
      /* backend unreachable — keep last snapshot */
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const maxBucket = Math.max(1, ...(stats?.buckets.map((b) => b.count) ?? [1]));

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Activity size={16} className="text-[#ffcc00]" />
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">Signal Velocity</h2>
            {stats?.burst_detected && <Badge variant="high"><Flame size={9} className="mr-1" />BURST</Badge>}
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            Observed event rate · {stats?.window_minutes ?? 15}-min sliding window
          </p>
        </div>
        <div className="text-right">
          <p className="font-mono text-xl font-extrabold text-white">
            {stats?.current_per_minute ?? 0}
            <span className="ml-1 text-[10px] font-medium text-slate-500">/min</span>
          </p>
          <p className="text-[10px] text-slate-400">Current rate</p>
        </div>
      </div>

      {/* 15-minute sparkline */}
      <div className="mt-3.5 flex h-14 items-end gap-1 rounded-xl border border-white/[.08] bg-white/[.02] px-3 py-2">
        {(stats?.buckets ?? []).map((b) => (
          <div
            key={b.minute_ago}
            title={`${b.label} — ${b.count} events`}
            className={`flex-1 rounded-sm transition-all ${
              b.count >= maxBucket * 0.7 ? 'bg-rose-500/80' : b.count > 0 ? 'bg-[#ffcc00]/70' : 'bg-white/[.06]'
            }`}
            style={{ height: `${Math.max(6, (b.count / maxBucket) * 100)}%` }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[9px] text-slate-500">
        <span>{stats?.buckets[0]?.label ?? '—'}</span>
        <span>now</span>
      </div>

      {/* Top talkers */}
      {stats && stats.top_sources.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {stats.top_sources.slice(0, 3).map((p) => (
            <div
              key={p.msisdn}
              className="flex items-center justify-between rounded-lg border border-white/[.06] bg-white/[.02] px-2.5 py-1.5"
            >
              <span className="font-mono text-[10px] font-semibold text-slate-300">
                {maskMsisdn(p.msisdn)}
              </span>
              <span className="flex items-center gap-2 text-[9px] text-slate-500">
                <span className="flex items-center gap-0.5">
                  <Zap size={9} className="text-[#ffcc00]" />
                  {p.events} ev
                </span>
                {p.payments > 0 && <span>{p.payments} pmts</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3.5 rounded-xl border border-white/[.08] bg-white/[.02] p-4 text-xs font-medium text-slate-300 leading-relaxed">
        {stats?.burst_detected
          ? 'Velocity burst: current minute is ≥3× the window median — correlated with fan-out and blast signals under probabilistic scoring.'
          : 'Temporal window tracking: rapid multi-hop transfers following SMS credits are prioritized under rule GH01 (Reversal Scam). Rates reflect observed plug-in events only.'}
      </div>
    </Card>
  );
}
