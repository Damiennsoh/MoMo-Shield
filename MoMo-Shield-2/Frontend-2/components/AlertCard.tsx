'use client';

import { ArrowUpRight, Clock3, ShieldAlert } from 'lucide-react';
import type { FraudAlert } from '@/lib/useStore';
import { Badge } from '@/components/ui/primitives';

export interface AlertCardProps {
  alert: FraudAlert;
  onClick: () => void;
}

export function AlertCard({ alert, onClick }: AlertCardProps) {
  if (alert.status !== 'active') return null;

  const isHigh = alert.risk === 'high';
  const borderTone = isHigh
    ? 'border-rose-500/35 bg-rose-500/[.07] hover:border-rose-500/60 hover:bg-rose-500/[.12]'
    : 'border-amber-500/35 bg-amber-500/[.07] hover:border-amber-500/60 hover:bg-amber-500/[.12]';

  const iconTone = isHigh
    ? 'border-rose-500/40 bg-rose-500/20 text-rose-300'
    : 'border-amber-500/40 bg-amber-500/20 text-amber-200';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`group w-full rounded-xl border p-4 text-left transition shadow-sm ${borderTone}`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border shadow-sm ${iconTone}`}>
          <ShieldAlert size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-xs font-bold text-white leading-tight">{alert.summary}</span>
            <ArrowUpRight size={14} className="shrink-0 text-slate-400 transition group-hover:text-white" />
          </div>
          <span className="mt-1 block truncate font-mono text-[11px] font-semibold text-slate-300">
            {alert.msisdn}
          </span>
          <div className="mt-2.5 flex items-center justify-between border-t border-white/[.08] pt-2">
            <span className="flex items-center gap-1 font-mono text-[10px] text-slate-400 font-medium">
              <Clock3 size={11} />
              {alert.time} GMT
            </span>
            <Badge variant={alert.risk}>Risk Score {alert.score}</Badge>
          </div>
        </div>
      </div>
    </button>
  );
}
