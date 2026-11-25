'use client';

import { useCallback, useEffect, useState } from 'react';
import { Database, ShieldCheck } from 'lucide-react';
import { Badge, Card } from '@/components/ui/primitives';
import { fetchThreatLedger, removeThreatLedgerEntry, type ThreatLedgerEntry } from '@/lib/api';

function maskMsisdn(msisdn: string): string {
  const digits = msisdn.replace(/\D/g, '');
  if (digits.length < 7) return msisdn;
  return `${digits.slice(0, 5)} ••• ${digits.slice(-4)}`;
}

export function ThreatLedgerCard() {
  const [entries, setEntries] = useState<ThreatLedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setEntries(await fetchThreatLedger(25));
    } catch {
      /* backend unreachable — leave stale/empty */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  const exonerate = async (msisdn: string) => {
    try {
      await removeThreatLedgerEntry(msisdn);
      setEntries((prev) => prev.filter((e) => e.msisdn !== msisdn));
    } catch {
      /* 404 = already gone */
    }
  };

  return (
    <Card className="overflow-hidden" id="threat-ledger">
      <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-3.5">
        <div>
          <div className="flex items-center gap-2">
            <Database size={14} className="text-sky-400" />
            <h2 className="text-xs font-bold text-white">Local Threat Ledger</h2>
          </div>
          <p className="mt-0.5 text-[10px] text-slate-400">Proprietary flagged-number intelligence</p>
        </div>
        <Badge variant={entries.length ? 'high' : 'low'}>{entries.length}</Badge>
      </div>
      <div className="max-h-56 space-y-1.5 overflow-y-auto p-3">
        {loading && entries.length === 0 && (
          <p className="px-2 py-3 text-center text-[10px] text-slate-500">Loading ledger…</p>
        )}
        {!loading && entries.length === 0 && (
          <p className="px-2 py-3 text-center text-[10px] text-slate-500">
            No confirmed threats yet — confirmed fraud numbers appear here automatically.
          </p>
        )}
        {entries.map((entry) => (
          <div
            key={entry.msisdn}
            className="flex items-center justify-between gap-2 rounded-lg border border-white/[.06] bg-white/[.02] px-2.5 py-1.5"
          >
            <div className="min-w-0">
              <p className="truncate font-mono text-[11px] font-semibold text-slate-200">
                {maskMsisdn(entry.msisdn)}
              </p>
              <p className="truncate text-[9px] text-slate-500">
                {entry.threat_type} · {entry.effective_reports} eff. reports · {entry.age_days}d ago
              </p>
            </div>
            <button
              type="button"
              onClick={() => void exonerate(entry.msisdn)}
              title="Exonerate — remove from ledger"
              className="grid h-6 w-6 shrink-0 place-items-center rounded-md border border-white/[.1] text-slate-500 transition hover:border-emerald-500/40 hover:text-emerald-400"
            >
              <ShieldCheck size={11} />
            </button>
          </div>
        ))}
      </div>
      <div className="border-t border-white/[.08] px-4 py-2">
        <p className="text-center text-[9px] text-slate-600">
          Entries decay after 14d dormant · expire at 30d · shield icon exonerates
        </p>
      </div>
    </Card>
  );
}
