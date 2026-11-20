const PREREQS = [
  { title: "Written provider authorization", detail: "Formal agreement with the MNO / wallet operator permitting ingestion of SMSC, call-detail, and device-binding telemetry." },
  { title: "Provider endpoint & credentials", detail: "Configure an approved provider interface with scoped credentials before enabling event ingestion." },
  { title: "Event schema & dictionary", detail: "Field-level documentation for transaction, device-binding, and communication events (Pydantic schemas align already)." },
  { title: "Security & privacy review", detail: "Act 843 (Data Protection Act, 2012) compliance sign-off, DPIA, and data-minimization audit before any real traffic." },
  { title: "Latency SLA", detail: "End-to-end decision in <5s at p95, including provider round-trip. Deterministic rules run in ~0.1s locally." },
];

export default function ProviderReadiness() {
  return (
    <div className="panel max-w-3xl p-6">
      <div className="flex items-center gap-3">
        <span className="rounded-full border border-risk-high/40 bg-risk-high/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-risk-high">
          Not connected
        </span>
        <p className="text-sm text-slate-400">Provider connection readiness</p>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-slate-300">
        Provider events are currently <strong className="text-white">not connected</strong>. Complete the prerequisites below and
        obtain the required approvals before enabling live ingestion. Feature-phone SMS/USSD delivery and smartphone-app
        observation require separate provider integrations.
      </p>
      <ul className="mt-6 space-y-3">
        {PREREQS.map((p, i) => (
          <li key={i} className="flex gap-3 rounded-xl border border-white/[0.06] bg-ink-800/60 p-4">
            <span className="font-mono text-xs font-bold text-accent">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <p className="text-sm font-semibold text-slate-100">{p.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-500">{p.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
