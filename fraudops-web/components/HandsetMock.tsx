"use client";

import { useEffect, useRef, useState } from "react";
import type { HandsetEvent } from "@/lib/types";
import { api, speakWarning, stopSpeaking, streamHandset } from "@/lib/api";

interface Props {
  externalEvents?: HandsetEvent[];
}

interface SmsItem {
  id: number;
  from: string;
  body: string;
  time: string;
}

let smsId = 0;

export default function HandsetMock({ externalEvents }: Props) {
  const [smsList, setSmsList] = useState<SmsItem[]>([]);
  const [call, setCall] = useState<{ from: string; status: string } | null>(null);
  const [warning, setWarning] = useState<{ title: string; text: string; level: string } | null>(null);
  const [now, setNow] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const upd = () => setNow(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    upd();
    const t = setInterval(upd, 30_000);
    return () => clearInterval(t);
  }, []);

  const handle = (evt: HandsetEvent) => {
    switch (evt.type) {
      case "sms":
        setSmsList((l) => [...l.slice(-4), { id: ++smsId, from: evt.from ?? "Unknown", body: evt.body ?? "", time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]);
        break;
      case "call":
        setCall({ from: evt.from ?? "Unknown", status: evt.status ?? "ringing" });
        break;
      case "call_status":
        if (evt.status === "ended" || evt.status === "declined") setCall(null);
        else if (call) setCall({ ...call, status: evt.status ?? call.status });
        break;
      case "warning":
        setWarning({ title: evt.title ?? "WARNING", text: evt.text ?? "", level: evt.level ?? "HIGH" });
        speakWarning(evt.text ?? "");
        setSpeaking(true);
        if (evt.sip_hangup) setCall((c) => (c ? { ...c, status: "ended" } : c));
        break;
      case "reset":
        setSmsList([]);
        setCall(null);
        setWarning(null);
        break;
    }
  };

  useEffect(() => streamHandset(handle), []);

  useEffect(() => {
    if (externalEvents?.length) handle(externalEvents[externalEvents.length - 1]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalEvents?.length]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [smsList.length]);

  const callAction = (action: "answer" | "decline" | "end") => {
    api.callAction(action).catch(() => {});
    if (action !== "answer") setCall(null);
    else setCall((c) => (c ? { ...c, status: "answered" } : c));
  };

  const warnColor = warning?.level === "HIGH" ? "border-risk-high/60 bg-risk-high/15 text-risk-high" : "border-risk-medium/60 bg-risk-medium/15 text-risk-medium";

  return (
    <div className="mx-auto w-[270px] select-none">
      <div className="relative rounded-[2.4rem] border border-white/10 bg-gradient-to-b from-ink-700 to-ink-900 p-2 shadow-panel">
        <div className="relative overflow-hidden rounded-[1.9rem] bg-black">
          {/* status bar */}
          <div className="flex items-center justify-between px-5 pt-3 text-[10px] text-slate-400">
            <span>MTN · Ghana</span>
            <div className="flex items-center gap-1.5">
              <span className="font-mono">{now}</span>
              <span className="inline-block h-2 w-3 rounded-[2px] bg-risk-low/80" title="battery" />
            </div>
          </div>
          {/* notch */}
          <div className="absolute left-1/2 top-1.5 h-4 w-20 -translate-x-1/2 rounded-full bg-ink-900" />

          <div ref={listRef} className="h-[340px] space-y-2 overflow-y-auto scroll-slim px-3 py-3">
            {smsList.length === 0 && !call && !warning && (
              <div className="flex h-full items-center justify-center text-center text-xs text-slate-600">
                Awaiting sandbox events…
              </div>
            )}

            {call && (
              <div className="animate-fade-up rounded-2xl border border-accent/30 bg-ink-800/90 p-4 text-center">
                <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-accent/15 text-accent">
                  <PhoneRing />
                </div>
                <p className="text-sm font-semibold text-white">{call.from}</p>
                <p className="mt-0.5 text-[11px] uppercase tracking-wider text-accent">{call.status}</p>
                {call.status === "ringing" && (
                  <div className="mt-3 flex justify-center gap-3">
                    <button onClick={() => callAction("answer")} className="rounded-full bg-risk-low/20 px-4 py-1.5 text-xs font-semibold text-risk-low">Answer</button>
                    <button onClick={() => callAction("decline")} className="rounded-full bg-risk-high/20 px-4 py-1.5 text-xs font-semibold text-risk-high">Decline</button>
                  </div>
                )}
                {call.status === "answered" && (
                  <button onClick={() => callAction("end")} className="mt-3 rounded-full bg-risk-high/20 px-4 py-1.5 text-xs font-semibold text-risk-high">End call</button>
                )}
              </div>
            )}

            {smsList.map((s) => (
              <div key={s.id} className="animate-fade-up rounded-2xl rounded-tl-md bg-ink-700/90 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{s.from} · {s.time}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-200">{s.body}</p>
              </div>
            ))}

            {warning && (
              <div className={`animate-fade-up rounded-2xl border p-3.5 ${warnColor}`}>
                <p className="text-[11px] font-bold uppercase tracking-wider">{warning.title}</p>
                <p className="mt-1.5 text-xs leading-relaxed">{warning.text}</p>
                {speaking && (
                  <button onClick={() => { stopSpeaking(); setSpeaking(false); }} className="mt-2 text-[11px] font-semibold underline underline-offset-2">
                    Stop spoken guidance
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <p className="mt-3 text-center text-[11px] text-slate-600">
        Victim handset (simulated — what the customer sees, in real time)
      </p>
    </div>
  );
}

function PhoneRing() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  );
}
