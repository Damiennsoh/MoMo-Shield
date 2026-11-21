'use client';

import { motion } from 'framer-motion';

export interface RiskGaugeProps {
  value: number;
  size?: number;
  compact?: boolean;
  label?: string;
}

export function RiskGauge({ value, size = 176, compact = false, label }: RiskGaugeProps) {
  const safeValue = Math.max(0, Math.min(100, Math.round(value)));
  const tone = safeValue >= 75 ? '#ef4444' : safeValue >= 40 ? '#f59e0b' : '#10b981';
  const radius = 68;
  const circumference = 2 * Math.PI * radius;
  const progress = (circumference * safeValue) / 100;

  return (
    <div
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Risk score ${safeValue} out of 100`}
    >
      <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90 overflow-visible">
        {/* Background track: adaptive to theme */}
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke="currentColor"
          className="text-slate-700/40 dark:text-white/10"
          strokeWidth="9"
        />
        {/* Progress Arc with glow */}
        <circle
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          stroke={tone}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={`${progress} ${circumference - progress}`}
          className="gauge-track"
          style={{ filter: `drop-shadow(0 0 10px ${tone}77)` }}
        />
        <circle
          cx="80"
          cy="80"
          r="54"
          fill="none"
          stroke="currentColor"
          className="text-slate-700/20 dark:text-white/5"
          strokeWidth="1"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          key={safeValue}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className={`font-extrabold tracking-tight font-mono ${compact ? 'text-3xl' : 'text-4xl'}`}
          style={{ color: tone }}
        >
          {safeValue}
          <span className="ml-0.5 text-xs font-semibold text-slate-400">/100</span>
        </motion.span>
        <span className="mt-1 text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
          {label ?? 'Risk Score'}
        </span>
      </div>
    </div>
  );
}
