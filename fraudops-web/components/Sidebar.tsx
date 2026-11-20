"use client";

interface Props {
  active: string;
  onSelect: (w: string) => void;
}

const WORKSPACES = [
  { id: "replay", label: "Scenario replay", desc: "Guided fraud simulations", step: "01" },
  { id: "lab", label: "Signal lab", desc: "Test SMS and call signals", step: "02" },
  { id: "injector", label: "Event injector", desc: "Submit a synthetic event", step: "03" },
  { id: "provider", label: "Provider readiness", desc: "Integration status", step: "04" },
];

export default function Sidebar({ active, onSelect }: Props) {
  return (
    <aside className="w-full shrink-0 lg:w-[258px]">
      <div className="panel p-3 lg:sticky lg:top-28">
        <div className="px-2 pb-3 pt-1">
          <p className="label">Demo workflow</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">Choose a workspace to explore the protection flow.</p>
        </div>
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:gap-1" aria-label="FraudOps workspaces">
          {WORKSPACES.map((w) => (
            <button
              key={w.id}
              type="button"
              aria-current={active === w.id ? "page" : undefined}
              onClick={() => onSelect(w.id)}
              className={`min-w-[190px] flex-1 rounded-xl border px-3 py-3 text-left transition-colors lg:min-w-0 lg:flex-none ${
                active === w.id
                  ? "border-accent/35 bg-accent/[0.09]"
                  : "border-transparent bg-ink-800/60 hover:border-white/10 hover:bg-ink-800"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <span className={`font-mono text-[10px] font-bold ${active === w.id ? "text-accent" : "text-slate-500"}`}>{w.step}</span>
                <span className={`text-[13px] font-bold ${active === w.id ? "text-white" : "text-slate-200"}`}>{w.label}</span>
              </span>
              <span className="mt-1 block pl-6 text-[11px] text-slate-400">{w.desc}</span>
            </button>
          ))}
        </nav>

        <div className="mt-4 border-t border-white/10 px-2 pb-1 pt-4">
          <p className="label">System endpoint</p>
          <p className="mt-1 break-all font-mono text-[11px] leading-relaxed text-slate-300">
            {process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}
          </p>
          <p className="mt-4 label">Responsible demo</p>
          <ul className="mt-2 flex flex-col gap-2 text-[11px] leading-relaxed text-slate-400">
            <li>Act 843 · Data Protection Act</li>
            <li>Synthetic data only · never enter a real PIN or OTP</li>
            <li>Voice recording requires consent</li>
          </ul>
        </div>
      </div>
    </aside>
  );
}
