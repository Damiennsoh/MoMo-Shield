"use client";

import { useCallback, useRef, useState } from "react";
import { SCENARIOS } from "@/lib/fixtures";
import type { Assessment, HandsetEvent, SandboxEvent, Scenario } from "@/lib/types";
import { api } from "@/lib/api";
import AssessmentCard from "./AssessmentCard";
import HandsetMock from "./HandsetMock";

interface RunState {
  running: boolean;
  scenarioId: string | null;
  progress: number; // 0..1
}

interface Result {
  scenarioId: string;
  assessment: Assessment | null;
  error?: string;
}

export default function ScenarioReplay() {
  const [run, setRun] = useState<RunState>({ running: false, scenarioId: null, progress: 0 });
  const [results, setResults] = useState<Record<string, Result>>({});
  const [eventLog, setEventLog] = useState<{ t: string; msg: string }[]>([]);
  const [lastAssessment, setLastAssessment] = useState<Assessment | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const cancelled = useRef(false);

  const log = (msg: string) =>
    setEventLog((l) => [...l.slice(-60), { t: new Date().toLocaleTimeString(), msg }]);

  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  const publish = (evt: HandsetEvent) => {
    // Fire-and-forget to the backend so the second-device page and the
    // dashboard handset mock (both SSE-driven) see the same events.
    void api.publishHandset(evt).catch(() => {});
  };

  const assessEvent = useCallback(async (event: SandboxEvent, scenario: Scenario): Promise<Assessment | null> => {
    try {
      const a = await api.assess(event);
      setResults((r) => ({ ...r, [scenario.id]: { scenarioId: scenario.id, assessment: a } }));
      setLastAssessment(a);
      log(`assess → ${event.event_type} · score ${a.risk_score} (${a.risk_tier}) · ${a.latency_ms}ms [${a.source}]`);
      // Mirror to victim handset
      if (event.event_type === "communication" && event.channel === "SMS") {
        publish({ type: "sms", from: "Sandbox SMS", body: event.text_or_transcript, scenario: scenario.name });
      }
      if (event.event_type === "communication" && event.channel === "VOICE") {
        publish({ type: "call", from: "Sandbox caller", status: "Incoming call", transcript: event.text_or_transcript, scenario: scenario.name });
      }
      if (a.risk_tier === "HIGH" || a.risk_tier === "MEDIUM") {
        const kill = a.recommended_action === "SIMULATED_HOLD" || a.recommended_action === "FRAUDOPS_ALERT";
        publish({
          type: "warning",
          level: a.risk_tier,
          title: a.risk_tier === "HIGH" ? "FRAUD ALERT" : "CAUTION — VERIFY",
          text: a.english_warning_message ?? a.guidance ?? "Do not share a PIN, OTP, or verification code.",
          text_twi: a.twi_warning_message ?? undefined,
          scenario: scenario.name,
          sip_hangup: kill,
        });
        log(`handset → ${a.risk_tier} warning published (sip_hangup=${kill})`);
      }
      return a;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "assessment failed";
      setResults((r) => ({ ...r, [scenario.id]: { scenarioId: scenario.id, assessment: null, error: msg } }));
      log(`ERROR · ${msg} — local fallback scoring not available in replay`);
      return null;
    }
  }, []);

  const playScenario = useCallback((scenario: Scenario) => {
    cancelled.current = false;
    clearTimers();
    setEventLog([]);
    setLastAssessment(null);
    setRun({ running: true, scenarioId: scenario.id, progress: 0 });
    log(`▶ replay started · ${scenario.name} (${scenario.steps.length} steps)`);
    publish({ type: "reset" });

    const total = scenario.steps.reduce((s, st) => s + st.delay_ms, 0) + 100;
    const start = Date.now();
    const tick = setInterval(() => {
      setRun((r) => ({ ...r, progress: Math.min(1, (Date.now() - start) / total) }));
    }, 120);

    let acc = 300;
    scenario.steps.forEach((step) => {
      acc += step.delay_ms;
      timers.current.push(
        setTimeout(() => {
          if (cancelled.current) return;
          log(`event → ${step.event.event_type}${step.note ? ` · ${step.note}` : ""}`);
          void assessEvent(step.event, scenario);
        }, acc)
      );
    });

    timers.current.push(
      setTimeout(() => {
        clearInterval(tick);
        if (!cancelled.current) {
          setRun({ running: false, scenarioId: scenario.id, progress: 1 });
          log("✓ replay complete");
        }
      }, acc + 800)
    );
  }, [assessEvent]);

  const runAll = useCallback(() => {
    cancelled.current = false;
    clearTimers();
    setEventLog([]);
    let acc = 0;
    SCENARIOS.forEach((sc) => {
      timers.current.push(setTimeout(() => playScenario(sc), acc));
      acc += sc.steps.reduce((s, st) => s + st.delay_ms, 0) + 2600;
    });
  }, [playScenario]);

  const stop = () => {
    cancelled.current = true;
    clearTimers();
    setRun({ running: false, scenarioId: null, progress: 0 });
    log("■ replay stopped by operator");
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
      {/* scenario list */}
      <div className="panel flex max-h-[560px] flex-col p-4">
        <div className="flex items-center justify-between">
          <p className="label">Scenarios</p>
          <div className="flex gap-2">
            <button className="btn btn-accent !px-3 !py-1.5 !text-xs" onClick={runAll} disabled={run.running}>Run all 7</button>
            {run.running && <button className="btn btn-danger !px-3 !py-1.5 !text-xs" onClick={stop}>Stop</button>}
          </div>
        </div>
        <div className="mt-3 space-y-2 overflow-y-auto scroll-slim">
          {SCENARIOS.map((sc) => {
            const res = results[sc.id];
            return (
              <button
                key={sc.id}
                onClick={() => !run.running && playScenario(sc)}
                disabled={run.running}
                className="panel-hover w-full rounded-xl border border-white/[0.06] bg-ink-800/60 p-3 text-left transition-all disabled:opacity-50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] font-bold text-slate-500">{sc.caseRef}</span>
                  <TierBadge tier={sc.tier} />
                </div>
                <p className="mt-1 text-[13px] font-semibold leading-snug text-slate-100">{sc.name}</p>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">{sc.steps.length} steps · ~{Math.round(sc.steps.reduce((s, x) => s + x.delay_ms, 0) / 1000)}s</span>
                  {res?.assessment && (
                    <span className="font-mono text-[11px] font-bold text-slate-300">
                      {res.assessment.risk_score}<span className="text-slate-600">/100</span>
                    </span>
                  )}
                  {res?.error && <span className="text-[11px] text-risk-high">failed</span>}
                </div>
                {run.scenarioId === sc.id && run.running && (
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-ink-700">
                    <div className="h-full bg-accent transition-all duration-150" style={{ width: `${run.progress * 100}%` }} />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* live area */}
      <div className="space-y-5">
        {lastAssessment ? (
          <AssessmentCard a={lastAssessment} title="Live assessment — latest event" />
        ) : (
          <div className="panel flex min-h-[220px] items-center justify-center p-8 text-center">
            <div>
              <p className="text-sm font-semibold text-slate-300">Standing by — choose a scenario and start a replay.</p>
              <p className="mt-1 text-xs text-slate-500">The engine correlates cross-channel telemetry in under 5 seconds per event.</p>
            </div>
          </div>
        )}

        <div className="panel p-4">
          <p className="label mb-2">Event stream</p>
          <div className="h-44 overflow-y-auto scroll-slim rounded-lg bg-black/40 p-3 font-mono text-[11px] leading-relaxed">
            {eventLog.length === 0 && <span className="text-slate-600">// awaiting events…</span>}
            {eventLog.map((e, i) => (
              <p key={i} className="text-slate-400"><span className="text-slate-600">{e.t}</span>  {e.msg}</p>
            ))}
          </div>
        </div>

        {/* scenario run results */}
        <div className="panel p-4">
          <p className="label mb-3">Scenario run results</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.values(results).map((r) => (
              <div key={r.scenarioId} className="rounded-xl border border-white/[0.06] bg-ink-800/60 p-3.5">
                <p className="text-xs font-semibold text-slate-200">{SCENARIOS.find((s) => s.id === r.scenarioId)?.name}</p>
                {r.assessment ? (
                  <>
                    <p className="mt-2 font-mono text-2xl font-bold text-slate-100">
                      {r.assessment.risk_score}<span className="text-sm text-slate-500">/100</span>
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <TierBadge tier={r.assessment.risk_tier} />
                      <span className="chip">{r.assessment.source === "backend" ? "backend" : "local"}</span>
                      <span className="font-mono text-[11px] text-slate-500">{r.assessment.latency_ms}ms</span>
                    </div>
                    <p className="mt-2 text-[11px] text-slate-500">{r.assessment.triggered_rules.length} rule(s) triggered</p>
                  </>
                ) : (
                  <p className="mt-2 text-xs text-risk-high">{r.error ?? "Pending…"}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* victim handset */}
      <HandsetMock />
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const cls =
    tier === "HIGH"
      ? "border-risk-high/40 bg-risk-high/10 text-risk-high"
      : tier === "MEDIUM"
        ? "border-risk-medium/40 bg-risk-medium/10 text-risk-medium"
        : "border-risk-low/40 bg-risk-low/10 text-risk-low";
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${cls}`}>{tier}</span>;
}
