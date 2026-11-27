'use client';

import { ArrowUpRight, MessageSquareText, Phone, Smartphone } from 'lucide-react';
import type { SignalEvent } from '@/lib/useStore';
import { Badge } from '@/components/ui/primitives';

export interface EventRowProps {
  event: SignalEvent;
  onClick?: () => void;
}

export function EventRow({ event, onClick }: EventRowProps) {
  const Icon = event.kind === 'SMS' ? MessageSquareText : event.kind === 'VOICE' ? Phone : Smartphone;
  const isHigh = event.risk === 'high';
  const isMed = event.risk === 'medium';

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-3.5 border-b border-white/[.07] px-4 py-3 text-left transition hover:bg-white/[.05] active:bg-white/[.08]"
    >
      <span
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg border shadow-sm ${
          isHigh
            ? 'border-rose-500/30 bg-rose-500/15 text-rose-300'
            : isMed
            ? 'border-amber-500/30 bg-amber-500/15 text-amber-300'
            : 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
        }`}
      >
        <Icon size={15} />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate font-mono text-xs font-bold text-white">{event.msisdn}</span>
          <Badge variant={event.risk} title="Risk tier and numeric score from the same assessment">
            {event.risk.toUpperCase()} · {event.score}/100
          </Badge>
        </span>
        <span className="mt-0.5 flex items-center gap-1.5 truncate text-[11px] font-medium text-slate-400">
          <span className="font-bold text-slate-300">{event.kind}</span>
          <span>·</span>
          <span className="truncate text-slate-300">{event.summary}</span>
        </span>
      </span>

      <span className="hidden shrink-0 text-right sm:block">
        <span className="block font-mono text-[10px] font-semibold text-slate-400">{event.time}</span>
        <span className="mt-0.5 block font-mono text-xs font-bold text-slate-200">{event.amount}</span>
      </span>

      <ArrowUpRight size={14} className="shrink-0 text-slate-500 transition group-hover:text-[#ffcc00]" />
    </button>
  );
}
