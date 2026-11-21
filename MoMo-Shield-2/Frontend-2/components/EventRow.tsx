import { ArrowUpRight, MessageSquareText, Phone, Smartphone } from 'lucide-react';
import type { SignalEvent } from '@/lib/useStore';
import { Badge } from '@/components/ui/primitives';

export interface EventRowProps { event: SignalEvent; onClick?: () => void }
export function EventRow({ event, onClick }: EventRowProps) {
  const Icon = event.kind === 'SMS' ? MessageSquareText : event.kind === 'VOICE' ? Phone : Smartphone;
  return (
    <button type="button" onClick={onClick} className="group flex w-full items-center gap-3 border-b border-white/[.045] px-3 py-3 text-left transition hover:bg-white/[.035]">
      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg border ${event.risk === 'high' ? 'border-rose-400/15 bg-rose-400/[.08] text-rose-300' : event.risk === 'medium' ? 'border-amber-300/15 bg-amber-300/[.08] text-amber-200' : 'border-emerald-300/15 bg-emerald-300/[.08] text-emerald-300'}`}><Icon size={14} /></span>
      <span className="min-w-0 flex-1"><span className="flex items-center justify-between gap-2"><span className="truncate text-[11px] font-semibold text-slate-200">{event.msisdn}</span><Badge variant={event.risk}>{event.risk}</Badge></span><span className="mt-1 flex items-center gap-1.5 truncate text-[10px] text-slate-500">{event.kind}<span className="text-slate-700">·</span>{event.summary}</span></span>
      <span className="hidden shrink-0 text-right sm:block"><span className="block font-mono text-[10px] text-slate-500">{event.time}</span><span className="mt-1 block text-[10px] text-slate-600">{event.amount}</span></span>
      <ArrowUpRight size={13} className="shrink-0 text-slate-700 transition group-hover:text-slate-300" />
    </button>
  );
}
