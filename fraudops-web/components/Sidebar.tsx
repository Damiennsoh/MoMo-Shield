"use client";

interface Props {
  active: string;
  onSelect: (w: string) => void;
}

const WORKSPACES = [
  { id: "replay", label: "Curated Scenario Replay", desc: "7 fixture scenarios, timed replay" },
  { id: "lab", label: "Live Signal Lab", desc: "SMS / voice transcript assessment" },
  { id: "injector", label: "Synthetic Event Injector", desc: "Single transaction / device event" },
  { id: "provider", label: "Provider Feed Readiness", desc: "Honest integration status" },
];

export default function Sidebar({ active, onSelect }: Props) {
  return (
    <aside className="w-full shrink-0 lg:w-64">
      <div className="panel p-3">
        <p className="label px-2 pb-2 pt-1">Workspace</p>
        <div className="space-y-1" role="tablist" aria-label="FraudOps workspaces">
          {WORKSPACES.map((w) => (
            <button
              key={w.id}
              role="tab"
              aria-selected={active === w.id}
              onClick={() => onSelect(w.id)}
              className={`w-full rounded-xl px-3 py-2.5 text-left transition-colors ${
                active === w.id
                  ? "border border-accent/30 bg-accent/[0.08]"
                  : "border border-transparent hover:bg-ink-800"
              }`}
            >
              <p className={`text-[13px] font-semibold ${active === w.id ? "text-accent" : "text-slate-200"}`}>
                {w.label}
              </p>
              <p className="text-[11px] text-slate-500">{w.desc}</p>
            </button>
          ))}
        </div>

        <div className="mt-4 border-t border-white/[0.06] px-2 pb-1 pt-3">
          <p className="label">Backend API URL</p>
          <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
            {process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}
          </p>
          <p className="mt-3 label">Compliance</p>
          <ul className="mt-1.5 space-y-1 text-[11px] leading-snug text-slate-500">
            <li>· Act 843 (Data Protection, 2012)</li>
            <li>· Synthetic data only — no real PIN/OTP</li>
            <li>· Consent-gated recording in Live Lab</li>
          </ul>
        </div>
      </div>
    </aside>
  );
}
