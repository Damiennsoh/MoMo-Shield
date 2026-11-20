"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  score: number | null;
  tier: string;
  size?: number;
}

const TIER_COLOR: Record<string, string> = {
  HIGH: "#EF4444",
  MEDIUM: "#F59E0B",
  LOW: "#22C55E",
};

export default function RiskGauge({ score, tier, size = 150 }: Props) {
  const [animated, setAnimated] = useState(0);
  const raf = useRef<number>();
  const target = score ?? 0;

  useEffect(() => {
    const start = performance.now();
    const from = animated;
    const dur = 700;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setAnimated(Math.round(from + (target - from) * eased));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current!);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const color = TIER_COLOR[tier] ?? "#64748B";
  const stroke = 10;
  const r = (size - stroke * 2) / 2;
  const cx = size / 2;
  const circ = 2 * Math.PI * r;
  const frac = Math.min(1, animated / 100);
  // 240° arc, opening at bottom
  const arcFrac = 240 / 360;
  const dash = circ * arcFrac * frac;
  const gap = circ * arcFrac - dash;

  return (
    <div className="relative inline-flex flex-col items-center" role="img" aria-label={`Risk score ${score ?? "—"} of 100, tier ${tier}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-[210deg]">
        <circle
          cx={cx} cy={cx} r={r} fill="none" stroke="#1F2D4A" strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${circ * arcFrac} ${circ}`}
        />
        <circle
          cx={cx} cy={cx} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${gap}`}
          style={{ filter: `drop-shadow(0 0 8px ${color}66)`, transition: "stroke 300ms" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-4xl font-bold tabular-nums" style={{ color }}>
          {score === null ? "—" : animated}
        </span>
        <span className="label mt-1">risk / 100</span>
      </div>
    </div>
  );
}
