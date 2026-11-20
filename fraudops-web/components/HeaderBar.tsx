"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Props {
  activeWorkspace: string;
  onNavigate: (w: string) => void;
}

export default function HeaderBar({ activeWorkspace, onNavigate }: Props) {
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
    check();
    const t = setInterval(check, 20_000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  const dot = (s: string) =>
    s === "online" ? "bg-risk-low" : s === "offline" ? "bg-risk-high" : "bg-slate-500";

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-ink-950/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <ShieldIcon />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white">
              MoMo Shield <span className="ml-1 rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">FraudOps</span>
            </h1>
            <p className="text-[11px] text-slate-500">
              Ghana mobile money · social-engineering early warning · synthetic demo
            </p>
          </div>
        </div>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Workspaces">
          {["replay", "lab", "injector", "provider"].map((w) => (
            <button
              key={w}
              onClick={() => onNavigate(w)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeWorkspace === w ? "bg-accent/15 text-accent" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {({ replay: "Scenario Replay", lab: "Live Signal Lab", injector: "Event Injector", provider: "Provider Readiness" } as Record<string, string>)[w]}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-4 text-[11px]">
          <StatusPill label="Backend" state={health} extra={version} dot={dot(health)} />
          <StatusPill label="Gemini" state={gemini} dot={dot(gemini)} />
          <a
            href="/handset"
            target="_blank"
            rel="noopener noreferrer"
            className="chip transition-colors hover:border-accent/40 hover:text-accent"
            title="Opens the second-device handset view"
          >
            <span className={dot("online")} /> Handset view ↗
          </a>
        </div>
      </div>
      <div className="border-t border-accent/20 bg-accent/[0.04] px-5 py-1.5 text-center text-[11px] text-slate-500">
        Prototype demonstration with synthetic data only — not a production fraud-prevention system. No real customer data, PINs, or OTPs.
      </div>
    </header>
  );
}

function StatusPill({ label, state, dot, extra }: { label: string; state: string; dot: string; extra?: string }) {
  return (
    <span className="flex items-center gap-1.5 text-slate-400" title={`${label}: ${state}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot} ${state === "checking" ? "animate-blink" : ""}`} />
      <span className="font-semibold uppercase tracking-wider">{label}</span>
      {extra && <span className="font-mono text-slate-600">{extra}</span>}
    </span>
  );
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
