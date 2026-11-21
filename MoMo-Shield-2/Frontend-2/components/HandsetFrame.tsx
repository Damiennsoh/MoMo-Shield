'use client';

import { ShieldAlert, ShieldCheck, Volume2, Wifi, Signal, BatteryFull } from 'lucide-react';
import type { RiskLevel } from '@/lib/useStore';

export interface HandsetFrameProps { mode: RiskLevel; message: string; compact?: boolean; largerText?: boolean; onReadAloud?: () => void }
export function HandsetFrame({ mode, message, compact = false, largerText = false, onReadAloud }: HandsetFrameProps) {
  const Icon = mode === 'high' ? ShieldAlert : mode === 'medium' ? ShieldAlert : ShieldCheck;
  return (
    <div className={`handset-frame relative mx-auto w-full max-w-[266px] rounded-[32px] border-[5px] border-[#272d36] bg-[#090d12] p-2.5 shadow-[0_28px_70px_rgba(0,0,0,.45)] ${compact ? 'max-w-[220px]' : ''}`}>
      <div className="absolute left-1/2 top-[8px] z-10 h-[15px] w-[62px] -translate-x-1/2 rounded-full bg-[#050709]" />
      <div className="overflow-hidden rounded-[23px] bg-[#f4f5f1] text-slate-900">
        <div className="flex items-center justify-between px-4 pb-2 pt-3 text-[9px] font-semibold"><span>9:41</span><span className="flex items-center gap-1"><Signal size={10} /><Wifi size={10} /><BatteryFull size={12} /></span></div>
        <div className="flex items-center gap-2 border-b border-black/5 bg-white px-3 py-2.5"><span className="grid h-7 w-7 place-items-center rounded-full bg-[#ffcc00] text-[10px] font-black text-[#1d2730]">m</span><span><b className="block text-[11px]">MTN MoMo</b><small className="text-[8px] text-slate-500">Mobile Money · Official</small></span><span className="ml-auto rounded-full bg-emerald-50 px-1.5 py-1 text-[7px] font-semibold uppercase tracking-wide text-emerald-700">Verified</span></div>
        <div className="min-h-[214px] px-3 py-3">
          {mode === 'low' ? <div className="mt-5 rounded-2xl bg-white p-3 shadow-sm"><div className="mb-2 flex items-center gap-2"><span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-100 text-emerald-700"><ShieldCheck size={14} /></span><b className="text-[10px]">You’re all set</b></div><p className="text-[9px] leading-relaxed text-slate-600">Your MoMo account is protected. Never share your PIN with anyone.</p><div className="mt-3 rounded-lg bg-slate-50 p-2 font-mono text-[8px] text-slate-500">*170# · Check balance</div></div> : <div className={`rounded-2xl p-3 ${mode === 'high' ? 'bg-[#a3212e] text-white' : 'bg-[#f1c64f] text-[#272311]'}`}><div className="flex items-center gap-2"><span className={`grid h-7 w-7 place-items-center rounded-full ${mode === 'high' ? 'bg-white/15' : 'bg-black/10'}`}><Icon size={15} /></span><b className="text-[10px] font-bold">{mode === 'high' ? 'TRANSACTION BLOCKED' : 'TAKE A MOMENT'}</b></div><p className={`mt-2 leading-relaxed ${largerText ? 'text-[11px]' : 'text-[9px]'}`}>{message}</p><div className={`mt-3 rounded-lg px-2.5 py-2 text-center text-[9px] font-bold ${mode === 'high' ? 'bg-white text-[#a3212e]' : 'bg-[#292414] text-[#ffe387]'}`}>{mode === 'high' ? 'Call 100 for support' : 'Wait 30 seconds before continuing'}</div></div>}
          <div className="mt-3 rounded-2xl bg-white p-2.5 shadow-sm"><p className="text-[8px] text-slate-500">MoMo Shield · just now</p><p className={`mt-1 leading-relaxed text-slate-700 ${largerText ? 'text-[10px]' : 'text-[8px]'}`}>Mepa wo kyɛw, fa wo PIN kɔ ma. We’ll never ask for your PIN.</p></div>
        </div>
        <div className="flex items-center justify-center border-t border-black/5 bg-white py-2.5"><div className="h-1 w-14 rounded-full bg-slate-300" /></div>
      </div>
      {onReadAloud && <button type="button" onClick={onReadAloud} className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/[.04] py-2 text-[10px] font-medium text-slate-300 transition hover:bg-white/[.08]"><Volume2 size={12} />Read warning aloud</button>}
    </div>
  );
}
