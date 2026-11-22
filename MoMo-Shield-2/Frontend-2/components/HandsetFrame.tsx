'use client';

import { ShieldAlert, ShieldCheck, Volume2, Wifi, Signal, BatteryFull } from 'lucide-react';
import type { RiskLevel } from '@/lib/useStore';
import { useStore } from '@/lib/useStore';

export interface HandsetFrameProps {
  mode: RiskLevel;
  message: string;
  twiMessage?: string;
  compact?: boolean;
  largerText?: boolean;
  onReadAloud?: () => void;
}

export function HandsetFrame({
  mode,
  message,
  twiMessage,
  compact = false,
  largerText = false,
  onReadAloud,
}: HandsetFrameProps) {
  const storeTwi = useStore((state) => state.twiWarningMessage);
  const effectiveTwi = twiMessage || storeTwi || 'Mepa wo kyɛw, fa wo PIN kɔ ma. We’ll never ask for your PIN.';
  const Icon = mode === 'high' ? ShieldAlert : mode === 'medium' ? ShieldAlert : ShieldCheck;

  return (
    <div
      className={`handset-frame relative mx-auto w-full rounded-[36px] border-[6px] border-[#202732] bg-[#070b10] p-2.5 shadow-[0_24px_60px_rgba(0,0,0,.6)] transition-all ${
        compact ? 'max-w-[240px]' : 'max-w-[280px]'
      }`}
    >
      {/* Dynamic island notch */}
      <div className="absolute left-1/2 top-[10px] z-10 h-[16px] w-[68px] -translate-x-1/2 rounded-full bg-[#050709] border border-black/40" />

      {/* Handset screen */}
      <div className="overflow-hidden rounded-[24px] bg-[#f8fafc] text-slate-900 shadow-inner">
        {/* Status bar */}
        <div className="flex items-center justify-between px-4 pb-2 pt-3.5 text-[10px] font-bold text-slate-800">
          <span>9:41</span>
          <span className="flex items-center gap-1.5">
            <Signal size={11} />
            <Wifi size={11} />
            <BatteryFull size={13} />
          </span>
        </div>

        {/* MTN MoMo Official header */}
        <div className="flex items-center gap-2.5 border-b border-slate-200 bg-white px-3.5 py-2.5 shadow-sm">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-[#ffcc00] text-xs font-black text-[#0f172a] shadow-sm">
            m
          </span>
          <div>
            <b className="block text-xs font-extrabold text-slate-950">MTN MoMo</b>
            <small className="text-[9px] font-bold text-slate-500">Official · Bank of Ghana Lic.</small>
          </div>
          <span className="ml-auto rounded-full bg-emerald-100 border border-emerald-300 px-2 py-0.5 text-[8px] font-bold uppercase tracking-wider text-emerald-800">
            Verified
          </span>
        </div>

        {/* Screen content */}
        <div className="min-h-[230px] px-3.5 py-3.5 space-y-3">
          {mode === 'low' ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-100 text-emerald-700">
                  <ShieldCheck size={16} />
                </span>
                <b className="text-xs font-bold text-slate-900">Wallet Protected</b>
              </div>
              <p className="text-[10px] leading-relaxed font-medium text-slate-600">
                Your MTN MoMo wallet is secure. Standby for incoming transactions, calls, or USSD prompts.
              </p>
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2 font-mono text-[9px] font-bold text-slate-700 text-center">
                *170# · Check Balance
              </div>
            </div>
          ) : (
            <div
              className={`rounded-2xl p-3.5 shadow-md ${
                mode === 'high' ? 'bg-[#991b1b] text-white' : 'bg-[#f59e0b] text-[#1c1917]'
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`grid h-7 w-7 place-items-center rounded-full ${
                    mode === 'high' ? 'bg-white/20' : 'bg-black/15'
                  }`}
                >
                  <Icon size={16} />
                </span>
                <b className="text-xs font-extrabold tracking-wide">
                  {mode === 'high' ? 'TRANSACTION BLOCKED' : 'TAKE A MOMENT'}
                </b>
              </div>
              <p className={`mt-2 font-medium leading-relaxed ${largerText ? 'text-xs' : 'text-[10px]'}`}>
                {message}
              </p>
              <div
                className={`mt-3 rounded-lg px-3 py-2 text-center text-[10px] font-extrabold shadow-sm ${
                  mode === 'high' ? 'bg-white text-[#991b1b]' : 'bg-[#1c1917] text-[#fef3c7]'
                }`}
              >
                {mode === 'high' ? 'Call 100 for Support' : 'Wait 30s before proceeding'}
              </div>
            </div>
          )}

          {/* Localized Twi Warning notification card: ONLY displayed during active threat / intervention */}
          {mode !== 'low' ? (
            <div className="rounded-2xl border border-amber-300 bg-amber-50 p-3 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="flex items-center justify-between text-[9px] font-bold text-amber-800">
                <span className="flex items-center gap-1 text-[#b45309]">
                  <ShieldAlert size={11} />
                  MoMo Shield Active Warning
                </span>
                <span className="text-amber-700">Just now</span>
              </div>
              <p className={`mt-1 font-semibold leading-relaxed text-slate-900 ${largerText ? 'text-xs' : 'text-[10px]'}`}>
                {effectiveTwi}
              </p>
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-white/70 p-3 shadow-xs">
              <div className="flex items-center justify-between text-[9px] font-semibold text-slate-400">
                <span>Recent System Notice</span>
                <span>Standby</span>
              </div>
              <p className="mt-1 text-[10px] font-medium leading-relaxed text-slate-500">
                No active threat detected. MoMo Shield monitoring Hook 12, 13 & 15.
              </p>
            </div>
          )}
        </div>

        {/* Home gesture bar */}
        <div className="flex items-center justify-center border-t border-slate-200 bg-white py-2.5">
          <div className="h-1.5 w-16 rounded-full bg-slate-300" />
        </div>
      </div>

      {/* External read aloud button */}
      {onReadAloud && (
        <button
          type="button"
          onClick={onReadAloud}
          className="mt-2.5 flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[.07] py-2 text-xs font-semibold text-slate-200 transition hover:bg-white/[.12] hover:text-white"
        >
          <Volume2 size={14} className="text-[#ffcc00]" />
          Read Warning Aloud (Twi + EN)
        </button>
      )}
    </div>
  );
}
