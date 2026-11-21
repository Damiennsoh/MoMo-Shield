'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Check, ChevronRight, CircleHelp, Languages, Shield, ShieldAlert, ShieldCheck, SlidersHorizontal, Volume2 } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { Badge } from '@/components/ui/primitives';
import { useStore, type RiskLevel } from '@/lib/useStore';
import { HandsetFrame } from '@/components/HandsetFrame';

const states: { id: RiskLevel; title: string; sub: string; icon: typeof ShieldCheck; selected: string; iconTone: string }[] = [
  { id: 'low', title: 'Normal · protected', sub: 'Standard MoMo experience', icon: ShieldCheck, selected: 'border-emerald-300/25 bg-emerald-300/[.055]', iconTone: 'bg-emerald-300/[.09] text-emerald-300' },
  { id: 'medium', title: 'Cooling-off prompt', sub: 'Gentle pause · medium risk', icon: CircleHelp, selected: 'border-amber-300/25 bg-amber-300/[.055]', iconTone: 'bg-amber-300/[.09] text-amber-200' },
  { id: 'high', title: 'Transaction blocked', sub: 'High risk · urgent warning', icon: ShieldAlert, selected: 'border-rose-300/25 bg-rose-300/[.055]', iconTone: 'bg-rose-300/[.09] text-rose-300' },
];

export default function HandsetPage() {
  const mode = useStore((state) => state.handsetMode);
  const message = useStore((state) => state.handsetMessage);
  const setAnalysis = useStore((state) => state.setAnalysis);
  const [larger, setLarger] = useState(false);

  const setMode = (next: RiskLevel) => {
    const score = next === 'high' ? 94 : next === 'medium' ? 57 : 8;
    const copy = next === 'high'
      ? 'Transaction blocked. We detected a suspicious request. Call 100 if you need help.'
      : next === 'medium'
        ? 'Take a moment before you act. Never share your PIN.'
        : 'Your MoMo account is protected. Never share your PIN with anyone.';
    setAnalysis(score, copy);
  };

  const readAloud = () => {
    if (!('speechSynthesis' in window)) return;
    const phrase = mode === 'high' ? 'Transaction blocked. Do not share your PIN. Call 100 for support.' : mode === 'medium' ? 'Take a moment. Never share your PIN with anyone.' : 'Your MoMo account is protected.';
    window.speechSynthesis.cancel();
    const twi = new SpeechSynthesisUtterance('Mepa wo kyɛw, fa wo PIN kɔ ma.');
    twi.lang = 'en-GH';
    const english = new SpeechSynthesisUtterance(phrase);
    english.lang = 'en-GH';
    window.speechSynthesis.speak(twi);
    window.speechSynthesis.speak(english);
  };

  return <AppShell>
    <div className="mx-auto max-w-[1100px]">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[9px] font-semibold uppercase tracking-[.18em] text-slate-600">Intervention preview</span>
            <Badge variant="outline">DEMO</Badge>
          </div>
          <h1 className="text-[24px] font-semibold tracking-tight text-white sm:text-[28px]">Handset <span className="text-[#ffcc00]">Simulator</span></h1>
          <p className="mt-1.5 max-w-xl text-[11px] text-slate-500">Preview how a risk decision becomes clear, accessible guidance for a customer.</p>
        </div>
        <Link href="/lab" className="flex items-center gap-1.5 rounded-lg border border-white/[.08] bg-white/[.025] px-3 py-2 text-[10px] font-medium text-slate-400 transition hover:border-[#ffcc00]/20 hover:text-[#ffcc00]">Update the signal <ArrowRight size={13}/></Link>
      </div>

      <section className="overflow-hidden rounded-2xl border border-white/[.07] bg-[#0c1219]">
        <header className="flex items-center justify-between border-b border-white/[.06] px-4 py-3.5 md:px-6">
          <div className="flex items-center gap-2 text-[10px] text-slate-400"><Shield size={13} className="text-[#ffcc00]"/><span>Customer experience preview</span></div>
          <span className="flex items-center gap-2 rounded-full border border-white/[.07] bg-white/[.025] px-2.5 py-1 text-[8px] font-medium text-slate-500"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400"/>SIMULATED · NO MESSAGE SENT</span>
        </header>
        <div className="grid md:grid-cols-[1fr_1fr]">
          <section className="flex flex-col items-center px-5 pb-6 pt-5 md:justify-center md:border-r md:border-white/[.06] md:px-10 md:py-9">
            <div className="mb-4 flex w-full max-w-[360px] items-center justify-between">
              <span className="text-[9px] font-semibold uppercase tracking-[.17em] text-slate-600">Victim view · Ghana</span>
              <button type="button" aria-pressed={larger} onClick={() => setLarger(!larger)} className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[9px] transition ${larger ? 'border-[#ffcc00]/30 bg-[#ffcc00]/[.07] text-[#ffe071]' : 'border-white/[.08] text-slate-500 hover:text-slate-200'}`}><SlidersHorizontal size={11}/>{larger ? 'Larger text on' : 'Larger text'}</button>
            </div>
            <div className="w-full max-w-[360px]"><HandsetFrame mode={mode} message={message} largerText={larger} onReadAloud={readAloud}/></div>
            <p className="mt-4 max-w-[300px] text-center text-[9px] leading-relaxed text-slate-600">Simulated customer experience · no message is sent to a real device</p>
          </section>

          <section className="flex flex-col px-4 pb-7 pt-5 md:justify-center md:px-9 md:py-9">
            <div className="mx-auto w-full max-w-[380px]">
              <div className="mb-5 hidden md:block">
                <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl border border-[#ffcc00]/15 bg-[#ffcc00]/[.08] text-[#ffcc00]"><Shield size={19}/></div>
                <p className="text-[9px] font-semibold uppercase tracking-[.18em] text-[#ffcc00]">MoMo Shield · intervention preview</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">A safer moment<br/>for every customer.</h2>
                <p className="mt-2 max-w-[320px] text-[10px] leading-relaxed text-slate-500">Choose a risk state and see the guidance rendered on the customer handset.</p>
              </div>
              <div className="flex items-center gap-2 border-b border-white/[.06] pb-3"><div className="grid h-7 w-7 place-items-center rounded-lg bg-[#ffcc00] text-[9px] font-black text-slate-900">m</div><div><p className="text-[11px] font-semibold text-slate-200">MTN MoMo</p><p className="mt-0.5 text-[8px] text-slate-600">Choose a state to preview</p></div><Languages size={13} className="ml-auto text-slate-600"/></div>
              <div className="mt-4 grid gap-2.5">{states.map(({ id, title, sub, icon: Icon, selected, iconTone }) => <button type="button" key={id} aria-pressed={mode === id} onClick={() => setMode(id)} className={`flex items-center gap-3 rounded-xl border p-3.5 text-left transition ${mode === id ? selected : 'border-white/[.065] bg-white/[.015] hover:border-white/[.12]'}`}><span className={`grid h-8 w-8 place-items-center rounded-lg ${iconTone}`}><Icon size={15}/></span><span className="flex-1"><span className="block text-[10px] font-semibold text-slate-200">{title}</span><span className="mt-1 block text-[9px] text-slate-600">{sub}</span></span>{mode === id && <Check size={14} className="text-[#ffcc00]"/>}</button>)}</div>
              <button type="button" onClick={readAloud} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-white/[.09] bg-white/[.025] py-3 text-[10px] font-semibold text-slate-300 transition hover:bg-white/[.06]"><Volume2 size={14} className="text-[#ffcc00]"/>Read warning aloud<span className="ml-1 text-[8px] font-normal text-slate-600">Twi + English</span></button>
              <div className="mt-5 rounded-xl border border-sky-300/10 bg-sky-300/[.025] p-3"><p className="flex items-center gap-1.5 text-[9px] font-semibold text-sky-200"><ShieldCheck size={11}/>Designed for Ghanaian customers</p><p className="mt-1.5 text-[9px] leading-relaxed text-slate-500">Warnings are direct and actionable. Twi safety copy: “Mepa wo kyɛw, fa wo PIN kɔ ma” — please, don’t share your PIN.</p></div>
              <Link href="/lab" className="mt-5 flex items-center justify-between text-[9px] text-slate-600 transition hover:text-slate-300"><span>Change the test message in Live Signal Lab</span><ChevronRight size={12}/></Link>
            </div>
          </section>
        </div>
      </section>
      <footer className="px-1 py-3 text-center text-[8px] text-slate-700 md:text-left">MoMo Shield · Synthetic interface demonstration · Not affiliated with MTN MoMo</footer>
    </div>
  </AppShell>;
}
