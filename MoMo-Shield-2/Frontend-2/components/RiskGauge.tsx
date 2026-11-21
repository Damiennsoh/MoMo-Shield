'use client';

import { motion } from 'framer-motion';

export interface RiskGaugeProps { value: number; size?: number; compact?: boolean; label?: string }
export function RiskGauge({ value, size = 176, compact = false, label }: RiskGaugeProps) {
  const safeValue = Math.max(0, Math.min(100, Math.round(value)));
  const tone = safeValue >= 75 ? '#fb5263' : safeValue >= 40 ? '#f5b942' : '#31d49a';
  const radius = 68;
  const circumference = 2 * Math.PI * radius;
  const progress = circumference * safeValue / 100;
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }} role="img" aria-label={`Risk score ${safeValue} out of 100`}>
      <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90 overflow-visible">
        <circle cx="80" cy="80" r={radius} fill="none" stroke="rgba(255,255,255,.07)" strokeWidth="8" />
        <circle cx="80" cy="80" r={radius} fill="none" stroke={tone} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${progress} ${circumference - progress}`} className="gauge-track" style={{ filter: `drop-shadow(0 0 8px ${tone}66)` }} />
        <circle cx="80" cy="80" r="54" fill="rgba(255,255,255,.018)" stroke="rgba(255,255,255,.055)" strokeWidth="1" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span key={safeValue} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={`font-semibold tracking-tight ${compact ? 'text-3xl' : 'text-4xl'}`} style={{ color: tone }}>{safeValue}<span className="ml-0.5 text-sm font-medium text-slate-500">/100</span></motion.span>
        <span className="mt-1 text-[10px] font-semibold uppercase tracking-[.2em] text-slate-500">{label ?? 'Risk score'}</span>
      </div>
    </div>
  );
}
