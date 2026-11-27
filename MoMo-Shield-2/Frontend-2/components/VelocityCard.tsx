'use client';

import { useCallback, useEffect, useState } from 'react';
import { Activity, ArrowDownLeft, ArrowUpRight, Flame, Zap } from 'lucide-react';
import { Card, Badge } from '@/components/ui/primitives';
import { fetchVelocity, type VelocityParty, type VelocityStats } from '@/lib/api';

function maskMsisdn(msisdn: string): string {
  const digits = msisdn.replace(/\D/g, '');
  if (digits.length < 7) return msisdn;
  return `${digits.slice(0, 5)} ••• ${digits.slice(-4)}`;
}

function PartyList({
  heading,
  parties,
  direction,
}: {
  heading: string;
  parties: VelocityParty[];
  direction: 'source' | 'destination';
}) {
  const DirectionIcon = direction === 'source' ? ArrowUpRight : ArrowDownLeft;

  return (
    <section className="min-w-0">
      <h3 className="mb-1.5 flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider text-slate-400">
        <DirectionIcon size={11} />
        {heading}
      </h3>
      {parties.length > 0 ? (
        <div className="space-y-1.5">
          {parties.slice(0, 2).map((party) => (
            <div
              key={party.msisdn}
              className="flex min-w-0 items-center justify-between gap-1 rounded-lg border border-white/[.06] bg-white/[.02] px-2 py-1.5"
            >
              <span className="truncate font-mono text-[9px] font-semibold text-slate-300">
                {maskMsisdn(party.msisdn)}
              </span>
              <span className="shrink-0 text-right text-[9px] text-slate-500">
                {party.events} ev{party.payments > 0 ? ` · ${party.payments} pay` : ''}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-lg border border-white/[.06] px-2 py-2 text-[9px] text-slate-500">
          No flow edges observed
        </p>
      )}
    </section>
  );
}

export function VelocityCard() {
  const [stats, setStats] = useState<VelocityStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshFailed, setRefreshFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setStats(await fetchVelocity());
      setRefreshFailed(false);
    } catch {
      // Preserve the latest known sample, but label it stale if refreshing fails.
      setRefreshFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [load]);

  const maxBucket = Math.max(1, ...(stats?.buckets.map((bucket) => bucket.count) ?? [1]));
  const updatedAt = stats
    ? new Date(stats.generated_at).toLocaleTimeString('en-GB', {
        hour12: false,
        timeZone: 'UTC',
      })
    : null;

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Activity size={16} className="text-[#ffcc00]" />
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-white">Signal Velocity</h2>
            {stats?.burst_detected && (
              <Badge variant="high">
                <Flame size={9} className="mr-1" />BURST
              </Badge>
            )}
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            Observed activity · {stats?.window_minutes ?? 15}-minute rolling window
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="font-mono text-xl font-extrabold text-white">
            {stats ? stats.current_per_minute : '—'}
            <span className="ml-1 text-[10px] font-medium text-slate-500">/min</span>
          </p>
          <p className="text-[10px] text-slate-400">Events in latest minute</p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-white/[.07] bg-white/[.02] px-2.5 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">Events · last 10 min</p>
          <p className="mt-0.5 font-mono text-sm font-bold text-slate-200">{stats ? stats.events_last_10m : '—'}</p>
        </div>
        <div className="rounded-lg border border-white/[.07] bg-white/[.02] px-2.5 py-2">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-500">15-min median / min</p>
          <p className="mt-0.5 font-mono text-sm font-bold text-slate-200">{stats ? stats.median_per_minute : '—'}</p>
        </div>
      </div>

      <div
        className="mt-3.5 flex h-14 items-end gap-1 rounded-xl border border-white/[.08] bg-white/[.02] px-3 py-2"
        role="img"
        aria-label={
          stats
            ? `Observed events per minute over ${stats.window_minutes} minutes. Current ${stats.current_per_minute}; median ${stats.median_per_minute}.`
            : 'Signal velocity chart has no sample yet.'
        }
      >
        {stats?.buckets.map((bucket) => {
          const burstBucket =
            bucket.count >= 15 ||
            (bucket.count >= 8 &&
              stats.median_per_minute > 0 &&
              bucket.count >= 3 * stats.median_per_minute);
          return (
            <div
              key={bucket.minute_ago}
              title={`${bucket.label} UTC — ${bucket.count} events${burstBucket ? ' · burst threshold met' : ''}`}
              aria-hidden="true"
              className={`flex-1 rounded-sm transition-all ${
                burstBucket ? 'bg-rose-500/80' : bucket.count > 0 ? 'bg-[#ffcc00]/70' : 'bg-white/[.06]'
              }`}
              style={{ height: `${Math.max(6, (bucket.count / maxBucket) * 100)}%` }}
            />
          );
        })}
        {!stats && <span className="w-full text-center text-[10px] text-slate-500">Awaiting telemetry sample</span>}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[9px] text-slate-500">
        <span>{stats?.buckets[0]?.label ?? '—'} UTC</span>
        <span>now</span>
      </div>

      {stats && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <PartyList heading="Top flow sources · 10m" parties={stats.top_sources} direction="source" />
          <PartyList heading="Top flow destinations · 10m" parties={stats.top_destinations} direction="destination" />
        </div>
      )}

      <div className="mt-3.5 rounded-xl border border-white/[.08] bg-white/[.02] p-3 text-[10px] font-medium leading-relaxed text-slate-300">
        {stats?.burst_detected
          ? `Burst threshold met: ${stats.current_per_minute} events this minute. Rule: ≥15 events, or ≥8 and ≥3× the 15-minute median (${stats.median_per_minute}/min). This aggregate monitor is triage-only; it does not itself change an individual decision.`
          : stats
            ? `Burst rule: ≥15 events in the latest minute, or ≥8 and ≥3× the 15-minute median (${stats.median_per_minute}/min). Current activity is ${stats.current_per_minute}/min. This aggregate monitor is triage-only; it does not itself change an individual decision.`
            : refreshFailed
              ? 'Velocity sample unavailable. The dashboard is not treating missing data as zero.'
              : loading
                ? 'Loading observed event-rate data…'
                : 'Waiting for the first velocity sample.'}
      </div>

      <div className="mt-2 flex flex-wrap justify-between gap-x-2 gap-y-1 text-[9px] text-slate-500">
        <span>{stats?.scope ?? 'Scope unavailable until telemetry loads.'}</span>
        <span className="shrink-0">
          {stats
            ? `${refreshFailed ? 'Stale · last sample' : 'Updated'} ${updatedAt} UTC`
            : refreshFailed
              ? 'Feed unavailable'
              : 'Loading'}
        </span>
      </div>
    </Card>
  );
}
