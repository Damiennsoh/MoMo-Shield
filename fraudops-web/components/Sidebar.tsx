"use client";

interface Props {
  active: string;
  onSelect: (w: string) => void;
}

const WORKSPACES = [
  { id: "replay", label: "Case review", desc: "Review fraud patterns and response paths", step: "01" },
  { id: "lab", label: "Signal assessment", desc: "Assess message and call signals", step: "02" },
  { id: "injector", label: "Event assessment", desc: "Assess a transaction or device event", step: "03" },
  { id: "provider", label: "Provider connections", desc: "Review integration readiness", step: "04" },
];

export default function Sidebar({ active, onSelect }: Props) {
  return (
    <aside className="w-full shrink-0 lg:w-[258px]">
      <div className="panel p-3 lg:sticky lg:top-28">
        <div className="px-2 pb-3 pt-1">
          <p className="label">Detection workflows</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">Choose an operational workspace to assess risk signals.</p>
        </div>
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:gap-1" aria-label="Fraud detection workflows">
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

        <details className="mt-4 border-t border-white/10 px-2 pb-1 pt-4">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 text-xs font-semibold text-slate-300 marker:hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
            System &amp; privacy details
            <span className="text-accent" aria-hidden="true">+</span>
          </summary>
          <div className="pb-2 pt-3">
            <p className="label">System endpoint</p>
            <p className="mt-1 break-all font-mono text-[11px] leading-relaxed text-slate-300">
              {process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"}
            </p>
            <p className="mt-4 label">Privacy safeguards</p>
            <ul className="mt-2 flex flex-col gap-2 text-[11px] leading-relaxed text-slate-400">
              <li>Act 843 · Data Protection Act</li>
              <li>Synthetic data only · never enter a real PIN or OTP</li>
              <li>Voice recording requires consent</li>
            </ul>
          </div>
        </details>
      </div>
    </aside>
  );
}
