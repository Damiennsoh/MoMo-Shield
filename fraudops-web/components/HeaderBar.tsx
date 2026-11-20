"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function HeaderBar() {
  const [health, setHealth] = useState<"online" | "offline" | "checking">("checking");
  const [gemini, setGemini] = useState<"online" | "offline" | "unknown">("unknown");
  const [version, setVersion] = useState("");

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const h = await api.health();
        if (!mounted) return;
        setHealth("online");
        setVersion(h.version ?? "");
      } catch {
        if (mounted) setHealth("offline");
      }
      try {
        const g = await api.geminiHealth();
        if (mounted) setGemini(g.ok ? "online" : "offline");
      } catch {
        if (mounted) setGemini("unknown");
      }
    };
    void check();
    const timer = setInterval(check, 20_000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-ink-950/95">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent"><ShieldIcon /></div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-[15px] font-extrabold tracking-tight text-white">MoMo Shield</h1>
              <span className="rounded-md border border-accent/30 bg-accent/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-accent">FraudOps</span>
            </div>
            <p className="mt-0.5 text-[11px] font-medium text-slate-400">Ghana mobile money protection · interactive prototype</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] sm:gap-5">
          <StatusPill label="API" state={health} extra={version} />
          <StatusPill label="AI signals" state={gemini} />
          <a href="/handset" target="_blank" rel="noopener noreferrer" className="chip min-h-10 transition-colors hover:border-accent/50 hover:text-accent" title="Opens the second-device handset view">
            <span className={`size-1.5 rounded-full ${stateDot("online")}`} /> Handset demo <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
      <div className="border-t border-white/[0.06] bg-ink-900 px-4 py-2 text-center text-[11px] font-medium leading-relaxed text-slate-300 sm:px-6">
        <span className="mr-1.5 font-bold text-accent">DEMO MODE</span>
        Synthetic scenarios only. No live provider feed, real customer data, PINs, or OTPs are used.
      </div>
    </header>
  );
}

function stateDot(state: string) {
  return state === "online" ? "bg-risk-low" : state === "offline" ? "bg-risk-high" : "bg-slate-400";
}

function StatusPill({ label, state, extra }: { label: string; state: string; extra?: string }) {
  const stateLabel = state === "online" ? "Connected" : state === "offline" ? "Offline" : state === "checking" ? "Checking" : "Not checked";
  return (
    <span className="flex items-center gap-2 text-slate-300" title={`${label}: ${stateLabel}`}>
      <span className={`size-2 rounded-full ${stateDot(state)} ${state === "checking" ? "animate-blink" : ""}`} />
      <span className="font-bold">{label}</span>
      <span className="text-slate-400">{stateLabel}</span>
      {extra && <span className="hidden font-mono text-slate-500 sm:inline">{extra}</span>}
    </span>
  );
}

function ShieldIcon() {
  return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></svg>;
}
