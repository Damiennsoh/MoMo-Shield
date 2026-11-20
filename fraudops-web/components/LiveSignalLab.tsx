"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { blobToWav } from "@/lib/wav";
import { EN_WARNING, EXAMPLE_MESSAGES } from "@/lib/fixtures";
import type { Assessment } from "@/lib/types";
import AssessmentCard from "./AssessmentCard";

export default function LiveSignalLab() {
  const [channel, setChannel] = useState<"SMS" | "VOICE">("SMS");
  const [language, setLanguage] = useState("twi-en");
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [syntheticConfirmed, setSyntheticConfirmed] = useState(false);
  const [ringLinphone, setRingLinphone] = useState(false);
  const [smsToLinphone, setSmsToLinphone] = useState(false);
  const [assessing, setAssessing] = useState(false);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cases, setCases] = useState<{ title?: string; similarity?: number; note?: string }[] | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const msisdn = "233240000001";

  const canAssess = text.trim().length > 3 && syntheticConfirmed && !assessing;

  const assess = async () => {
    if (!canAssess) return;
    setAssessing(true);
    setError(null);
    setAssessment(null);
    setCases(null);
    const started = performance.now();
    try {
      if (channel === "SMS") {
        await api.publishHandset({
          type: "sms", from: "Live Signal Lab", body: text,
          scenario: "Live Signal Lab", sip_message: smsToLinphone,
        }).catch(() => {});
      } else {
        await api.publishHandset({
          type: "call", from: "Unknown caller", status: "Incoming call",
          transcript: text, scenario: "Live Signal Lab",
          trigger_sip: ringLinphone,
        }).catch(() => {});
      }

      const a = await api.assess({
        event_id: `lab-${Date.now()}`,
        msisdn,
        event_type: "communication",
        channel,
        text_or_transcript: text,
        timestamp: new Date().toISOString(),
        language_hint: language,
        input_source: "live_signal_lab",
      });
      // fallback local scoring if backend unreachable
      if (!a || typeof a.risk_score !== "number") throw new Error("invalid assessment");
      setAssessment(a);

      const killCall = a.recommended_action === "SIMULATED_HOLD" || a.recommended_action === "FRAUDOPS_ALERT";
      if (a.risk_tier === "HIGH" || a.risk_tier === "MEDIUM") {
        await api
          .publishHandset({
            type: "warning",
            level: a.risk_tier,
            title: a.risk_tier === "HIGH" ? "FRAUD ALERT — LIVE SIGNAL" : "CAUTION — VERIFY",
            text: a.english_warning_message ?? a.guidance ?? EN_WARNING,
            text_twi: a.twi_warning_message ?? undefined,
            scenario: "Live Signal Lab",
            // HIGH kills the call only after the victim answers; MEDIUM warns
            // but lets the call continue until the user ends it manually.
            sip_hangup: killCall,
          })
          .catch(() => {});
      }
      if (channel === "VOICE") {
        await api.publishHandset({
          type: "call_status",
          status: killCall ? "Call ended · fraud intervention"
                          : a.risk_tier === "MEDIUM" ? "Call in progress · cooling-off notice"
                          : "Call in progress · no intervention",
          scenario: "Live Signal Lab",
        }).catch(() => {});
      }

      try {
        const ref = await api.caseReference(text, language);
        setCases((ref.cases as typeof cases) ?? []);
      } catch {
        setCases([]);
      }
      void started;
    } catch (e) {
      // local deterministic fallback, clearly labelled
      const lower = text.toLowerCase();
      let score = 12;
      const rules: string[] = ["Baseline: normal transaction telemetry"];
      if (/\b(pin|otp|verification code|code)\b/i.test(text)) { score += 34; rules.push("Communication requests a secret (PIN/OTP)"); }
      if (/(block|suspend|limit|locked)/i.test(text)) { score += 20; rules.push("Loss-aversion / account-blocking threat"); }
      if (/(head office|mtn|telecel|support|fraud desk)/i.test(text)) { score += 18; rules.push("Authority impersonation claim"); }
      if (/(urgent|immediately|24 ?hrs|today)/i.test(text)) { score += 12; rules.push("Urgency / task-momentum pressure"); }
      if (/http:\/\//i.test(text)) { score += 12; rules.push("Off-channel link (phishing vector)"); }
      score = Math.min(100, score);
      const tier = score >= 75 ? "HIGH" : score >= 40 ? "MEDIUM" : "LOW";
      setAssessment({
        msisdn,
        risk_score: score,
        risk_tier: tier,
        triggered_rules: rules,
        recommended_action: tier === "HIGH" ? "SIMULATED_HOLD" : tier === "MEDIUM" ? "COOLING_OFF_PROMPT" : "SEAMLESS_APPROVE",
        source: "local",
        latency_ms: Math.round(performance.now() - started),
        guidance: EN_WARNING,
        english_warning_message: EN_WARNING,
        intent_source: "local",
        llm_unavailable: true,
      });
    } finally {
      setAssessing(false);
    }
  };

  const startRecording = async () => {
    if (!consent) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      recorder.current = rec;
      chunks.current = [];
      rec.ondataavailable = (e) => chunks.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
        setTranscribing(true);
        try {
          const wav = await blobToWav(blob);
          const r = await api.transcribe(wav, language);
          setText((t) => (t ? `${t}\n${r.transcript}` : r.transcript));
        } catch {
          setError("Transcription unavailable — backend offline or mic blocked. Type the transcript instead.");
        } finally {
          setTranscribing(false);
        }
      };
      rec.start();
      setRecording(true);
    } catch {
      setError("Microphone access denied. Browser requires a secure context (HTTPS or localhost).");
    }
  };

  const stopRecording = () => {
    recorder.current?.stop();
    setRecording(false);
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="panel p-5">
        <p className="label">Live Signal Lab</p>
        <p className="mt-1 text-sm text-slate-400">
          Assess a synthetic SMS or voice transcript against the FastAPI scoring engine. Each sample uses a fresh
          synthetic identity — prior samples do not affect its score.
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          {(["SMS", "VOICE"] as const).map((c) => (
            <button
              key={c}
              onClick={() => setChannel(c)}
              className={`rounded-lg px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors ${
                channel === c ? "bg-accent/15 text-accent" : "bg-ink-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {c === "SMS" ? "SMS signal" : "Voice transcript"}
            </button>
          ))}
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className="input !w-auto !py-2 text-xs" aria-label="Language hint">
            <option value="twi-en">Twi / English code-switch</option>
            <option value="twi">Twi</option>
            <option value="en">English</option>
            <option value="pidgin">Ghanaian Pidgin</option>
          </select>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          placeholder={channel === "SMS" ? "Paste or type the synthetic SMS content…" : "Paste a transcript, or record below and edit the draft…"}
          className="input mt-4 resize-y font-mono text-[13px] leading-relaxed"
        />
        {channel === "VOICE" && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-400">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="accent-[#FACC15]" />
              I consent to microphone recording (Act 843)
            </label>
            {!recording ? (
              <button className="btn !py-1.5 !text-xs" onClick={startRecording} disabled={!consent || transcribing}>
                ● Record
              </button>
            ) : (
              <button className="btn btn-danger !py-1.5 !text-xs animate-pulse-ring" onClick={stopRecording}>■ Stop & transcribe</button>
            )}
            {transcribing && <span className="text-xs text-slate-500">Transcribing…</span>}
          </div>
        )}

        <div className="mt-4">
          <p className="label mb-2">Example signals</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_MESSAGES.map((m) => (
              <button key={m.label} onClick={() => { setText(m.text); setChannel(m.channel); }} className="chip transition-colors hover:border-accent/40 hover:text-accent">
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 space-y-2 border-t border-white/[0.06] pt-4 text-xs text-slate-400">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={syntheticConfirmed} onChange={(e) => setSyntheticConfirmed(e.target.checked)} className="accent-[#FACC15]" />
            I confirm this content is synthetic / fictional (required)
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={ringLinphone} onChange={(e) => setRingLinphone(e.target.checked)} className="accent-[#FACC15]" />
            Ring Linphone softphone for voice signals
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={smsToLinphone} onChange={(e) => setSmsToLinphone(e.target.checked)} className="accent-[#FACC15]" />
            Send SMS signals to Linphone as SIP text
          </label>
        </div>

        <div className="mt-5 flex gap-3">
          <button className="btn btn-accent" onClick={assess} disabled={!canAssess}>
            {assessing ? "Assessing…" : "Assess signal"}
          </button>
          <button className="btn" onClick={() => { setText(""); setAssessment(null); setError(null); }}>
            Clear
          </button>
        </div>
        {error && <p className="mt-3 text-xs text-risk-high">{error}</p>}
      </div>

      <div className="space-y-5">
        {assessment ? (
          <AssessmentCard a={assessment} title="Live Signal Lab — result" />
        ) : (
          <div className="panel flex min-h-[180px] items-center justify-center p-6 text-center text-sm text-slate-500">
            Result appears here — tier color, triggered rules, intent evidence, latency, and source badge.
          </div>
        )}

        <div className="panel p-4">
          <p className="label mb-2">Advisory case-reference</p>
          {cases === null ? (
            <p className="text-xs text-slate-500">Submit a signal to retrieve similar synthetic cases. Retrieval similarity is not a fraud probability.</p>
          ) : cases.length === 0 ? (
            <p className="text-xs text-slate-500">No similar cases in the synthetic library.</p>
          ) : (
            <ul className="space-y-2">
              {cases.map((c, i) => (
                <li key={i} className="rounded-lg bg-ink-800/70 px-3 py-2 text-xs text-slate-300">
                  {c.title ?? `Case ${i + 1}`}
                  {typeof c.similarity === "number" && <span className="ml-2 font-mono text-slate-500">{Math.round(c.similarity * 100)}%</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
