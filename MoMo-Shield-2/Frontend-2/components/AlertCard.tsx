import { ArrowUpRight, Clock3, ShieldAlert } from 'lucide-react';
import type { FraudAlert } from '@/lib/useStore';
import { Badge } from '@/components/ui/primitives';

export interface AlertCardProps { alert: FraudAlert; onClick: () => void }
export function AlertCard({ alert, onClick }: AlertCardProps) {
  if (alert.status !== 'active') return null;
  const highRisk = alert.risk === 'high';
  const accent = highRisk
    ? 'border-rose-400/15 bg-rose-400/[.09] text-rose-300'
    : 'border-amber-300/15 bg-amber-300/[.08] text-amber-200';
  const hover = highRisk
    ? 'hover:border-rose-400/25 hover:bg-rose-400/[.035] group-hover:text-rose-300'
    : 'hover:border-amber-300/25 hover:bg-amber-300/[.035] group-hover:text-amber-200';
  return (
    <button type="button" onClick={onClick} className={`group w-full rounded-xl border border-white/[.07] bg-white/[.018] p-3.5 text-left transition ${hover}`}>
      <span className="flex items-start gap-2.5">
        <span className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border ${accent}`}><ShieldAlert size={14}/></span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-2"><span className="truncate text-[11px] font-semibold text-slate-100">{alert.summary}</span><ArrowUpRight size={13} className="shrink-0 text-slate-600 transition"/></span>
          <span className="mt-1.5 block truncate font-mono text-[10px] text-slate-500">{alert.msisdn}</span>
          <span className="mt-2.5 flex items-center justify-between"><span className="flex items-center gap-1 text-[9px] text-slate-500"><Clock3 size={10}/>{alert.time}</span><Badge variant={alert.risk}>Risk {alert.score}</Badge></span>
        </span>
      </span>
    </button>
  );
}
