"use client";

import { useEffect, useRef, useState } from "react";
import type { HandsetEvent } from "@/lib/types";
import { api, demoToken, speakWarning, stopSpeaking, streamHandset } from "@/lib/api";

interface SmsItem { id: number; from: string; body: string; time: string; }
let smsId = 0;

/**
 * Second-device handset view — mobile-first page consuming the SSE stream.
 * Access via #token=<DEMO_DEVICE_TOKEN> like the original page.
 */
export default function HandsetPage() {
  const [smsList, setSmsList] = useState<SmsItem[]>([]);
  const [call, setCall] = useState<{ from: string; status: string } | null>(null);
  const [warning, setWarning] = useState<{ title: string; text: string; text_twi?: string; level: string } | null>(null);
  const [largeText, setLargeText] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [connected, setConnected] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  // token from URL fragment — sent implicitly by backend via SSE auth in this demo
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.hash.includes("token=")) {
      // Token is validated server-side on the SSE endpoint; nothing to store client-side.
      void 0;
    }
  }, []);

  const playTone = async (kind: "sms" | "ring" | "alert" | "warning_en") => {
    if (!soundOn) return;
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const token = demoToken();
      const res = await fetch(`${base}/api/v1/demo-device/audio/${kind}.mp3`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const url = URL.createObjectURL(await res.blob());
      const audio = new Audio(url);
      await audio.play().catch(() => {});
    } catch {
      /* audio cues are best-effort */
    }
  };

  useEffect(() => {
    const cleanup = streamHandset((evt: HandsetEvent) => {
      setConnected(true);
      switch (evt.type) {
        case "sms":
          setSmsList((l) => [...l.slice(-8), { id: ++smsId, from: evt.from ?? "Unknown", body: evt.body ?? "", time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);
          void playTone("sms");
          break;
        case "call":
          setCall({ from: evt.from ?? "Unknown", status: evt.status ?? "ringing" });
          void playTone("ring");
          break;
        case "call_status":
          if (evt.status === "ended" || evt.status === "declined") setCall(null);
          else setCall((c) => (c ? { ...c, status: evt.status ?? c.status } : c));
          break;
        case "warning":
          setWarning({ title: evt.title ?? "WARNING", text: evt.text ?? "", text_twi: evt.text_twi, level: evt.level ?? "HIGH" });
          speakWarning(evt.text ?? "");
          setSpeaking(true);
          if (evt.sip_hangup) setCall((c) => (c ? { ...c, status: "ended" } : c));
          void playTone("alert");
          break;
        case "reset":
          setSmsList([]); setCall(null); setWarning(null);
          break;
      }
    });
    return cleanup;
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [smsList.length]);

  const callAction = (action: "answer" | "decline" | "end") => {
    api.callAction(action).catch(() => {});
    if (action !== "answer") setCall(null);
    else setCall((c) => (c ? { ...c, status: "answered" } : c));
  };

  const textScale = largeText ? "text-base" : "text-xs";

  return (
    <div className="flex min-h-screen flex-col items-center bg-ink-950 px-4 py-6">
      <div className="flex w-full max-w-sm items-center justify-between text-[11px] text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-risk-low" : "bg-slate-600"}`} />
          {connected ? "Connected to FraudOps stream" : "Connecting…"}
        </span>
        <div className="flex items-center gap-3">
          <button onClick={() => setSoundOn((s) => !s)} className="underline underline-offset-2">
            Sound {soundOn ? "on" : "off"}
          </button>
          <button onClick={() => setLargeText((l) => !l)} className="underline underline-offset-2" aria-pressed={largeText}>
            Aa {largeText ? "large" : "normal"}
          </button>
        </div>
      </div>

      <div className="mt-4 w-full max-w-sm flex-1 rounded-[2.2rem] border border-white/10 bg-gradient-to-b from-ink-700 to-ink-900 p-2 shadow-panel">
        <div ref={listRef} className="flex h-[70vh] min-h-[420px] flex-col gap-3 overflow-y-auto scroll-slim rounded-[1.8rem] bg-black px-4 py-5">
          {smsList.length === 0 && !call && !warning && (
            <div role="status" aria-live="polite" className="flex flex-1 flex-col items-center justify-center px-5 text-center">
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-accent">MoMo Shield · Demo</p>
              <h1 className="mt-3 text-xl font-semibold text-white">Standing by</h1>
              <p className="mt-2 max-w-[240px] text-xs leading-relaxed text-slate-400">
                Simulated calls and messages from the lab will appear here.
              </p>
              <p className="mt-5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[10px] text-slate-500">
                SIP audio is handled by Linphone
              </p>
            </div>
          )}

          {call && (
            <div className="animate-fade-up rounded-2xl border border-accent/30 bg-ink-800/90 p-5 text-center">
              <p className="text-[11px] uppercase tracking-widest text-slate-500">Incoming call</p>
              <p className="mt-1 text-lg font-bold text-white">{call.from}</p>
              <p className="mt-0.5 text-xs font-bold uppercase tracking-wider text-accent">{call.status}</p>
              {call.status === "ended" || /ended|declined/.test(call.status) ? (
                <p className="mt-3 text-[11px] font-bold uppercase tracking-wider text-slate-500">Call ended</p>
              ) : call.status === "ringing" ? (
                <div className="mt-4 flex justify-center gap-4">
                  <button onClick={() => callAction("answer")} className="rounded-full bg-risk-low px-6 py-2 text-sm font-bold text-ink-950">Answer</button>
                  <button onClick={() => callAction("decline")} className="rounded-full bg-risk-high px-6 py-2 text-sm font-bold text-white">Decline</button>
                </div>
              ) : (
                <button onClick={() => callAction("end")} className="mt-4 rounded-full bg-risk-high px-6 py-2 text-sm font-bold text-white">End call</button>
              )}
            </div>
          )}

          {smsList.map((s) => (
            <div key={s.id} className="animate-fade-up rounded-2xl rounded-tl-md bg-ink-700/90 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{s.from} · {s.time}</p>
              <p className={`mt-1.5 leading-relaxed text-slate-200 ${textScale}`}>{s.body}</p>
            </div>
          ))}

          {warning && (
            <div className={`animate-fade-up rounded-2xl border p-4 ${warning.level === "HIGH" ? "border-risk-high/60 bg-risk-high/15 text-risk-high" : "border-risk-medium/60 bg-risk-medium/15 text-risk-medium"}`}>
              <p className="text-xs font-bold uppercase tracking-wider">{warning.title}</p>
              <p className={`mt-2 leading-relaxed ${textScale}`}>{warning.text}</p>
              {warning.text_twi && <p className={`mt-2 leading-relaxed text-slate-300 ${textScale}`}>{warning.text_twi}</p>}
              {speaking && (
                <button onClick={() => { stopSpeaking(); setSpeaking(false); }} className="mt-3 text-xs font-semibold underline underline-offset-2">
                  Stop spoken guidance
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <p className="mt-4 max-w-sm text-center text-[11px] leading-relaxed text-slate-500">
        Demo only: calls ring for up to 60 seconds, with a 5-minute cap after pickup. Answer the actual SIP call in Linphone; browser Answer only updates this screen, while Decline/End can hang up the local test call. This view cannot hear live calls, send carrier SMS, or control transactions.
      </p>
    </div>
  );
}
