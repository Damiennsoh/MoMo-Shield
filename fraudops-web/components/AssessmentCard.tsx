"use client";

import type { Assessment } from "@/lib/types";
import { tierBar, tierColor } from "@/lib/api";

const ACTION_LABEL: Record<string, string> = {
  SEAMLESS_APPROVE: "Seamless approval",
  COOLING_OFF_PROMPT: "Cooling-off prompt",
  SIMULATED_HOLD: "Simulated transaction hold",
  FRAUDOPS_ALERT: "FraudOps alert dispatched",
};

export default function AssessmentCard({ a, title }: { a: Assessment; title?: string }) {
  return (
    <div className="panel animate-fade-up p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="label">{title ?? "Live assessment"}</p>
          <p className={`mt-1 font-mono text-3xl font-bold tabular-nums ${tierColor(a.risk_tier)}`}>
            {a.risk_score}
            <span className="text-base text-slate-500">/100</span>
          </p>
          <p className={`mt-1 text-xs font-bold uppercase tracking-[0.2em] ${tierColor(a.risk_tier)}`}>
            {a.risk_tier} risk
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 text-right">
          <span className={`chip ${a.risk_tier === "HIGH" ? "border-risk-high/40 text-risk-high" : a.risk_tier === "MEDIUM" ? "border-risk-medium/40 text-risk-medium" : "border-risk-low/40 text-risk-low"}`}>
            {ACTION_LABEL[a.recommended_action] ?? a.recommended_action}
          </span>
          <span className="chip">
            {a.source === "backend" ? "FastAPI engine" : "Local rules fallback"}
          </span>
          <span className="font-mono text-xs text-slate-500">{a.latency_ms} ms</span>
        </div>
      </div>

      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
        <div className={`h-full rounded-full ${tierBar(a.risk_tier)} transition-all duration-700`} style={{ width: `${a.risk_score}%` }} />
      </div>

      {a.triggered_rules?.length > 0 && (
        <div className="mt-4">
          <p className="label mb-2">Triggered detection rules</p>
          <ul className="space-y-1.5">
            {a.triggered_rules.map((r, i) => (
              <li key={i} className="flex items-start gap-2 rounded-lg bg-ink-800/70 px-3 py-2 text-xs text-slate-300">
                <span className="mt-0.5 text-accent">⚡</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {a.llm_extracted_intent && typeof a.llm_extracted_intent === "object" && (
        <div className="mt-4 rounded-lg border border-white/[0.06] bg-ink-800/50 p-3">
          <p className="label mb-1.5">
            Intent evidence{a.intent_source ? ` · ${a.intent_source}` : ""}
            {a.llm_unavailable ? " · fallback" : ""}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {a.llm_extracted_intent.lever && <span className="chip">{a.llm_extracted_intent.lever}</span>}
            {a.llm_extracted_intent.requested_secret && <span className="chip border-risk-high/40 text-risk-high">requests: {a.llm_extracted_intent.requested_secret}</span>}
            {a.llm_extracted_intent.language_detected && <span className="chip">lang: {a.llm_extracted_intent.language_detected}</span>}
            {(a.llm_extracted_intent.evidence ?? []).map((e, i) => (
              <span key={i} className="chip">“{e}”</span>
            ))}
          </div>
        </div>
      )}

      {a.guidance && (
        <div className="mt-4 rounded-lg border border-accent/20 bg-accent/[0.06] p-3 text-xs leading-relaxed text-slate-300">
          <span className="font-semibold text-accent">Victim-facing guidance · </span>{a.guidance}
          <p className="mt-1.5 text-[11px] text-slate-500">Context-aware prototype guidance; no provider alert or real transaction control is connected.</p>
        </div>
      )}
    </div>
  );
}
