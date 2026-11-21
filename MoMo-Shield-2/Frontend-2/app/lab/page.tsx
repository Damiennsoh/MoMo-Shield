'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, ArrowRight, AudioLines, CheckCircle2, Clipboard, Code2, Languages, Mic, Radio, RotateCcw, ShieldAlert, ShieldCheck, Sparkles, Volume2, Waves } from 'lucide-react';
import { motion } from 'framer-motion';
import { AppShell } from '@/components/AppShell';
import { RiskGauge } from '@/components/RiskGauge';
import { HandsetFrame } from '@/components/HandsetFrame';
import { useStore, type RiskLevel } from '@/lib/useStore';
import { submitSandboxEvent, type AssessmentResult } from '@/lib/api';
import { assessmentToAlert, assessmentToSignalEvent, buildLabEvent } from '@/lib/mappers';
import { Badge, Button, Card, CardDescription, CardHeader, CardTitle, Input, Textarea } from '@/components/ui/primitives';

const example = 'Congratulations! Your MoMo wallet has been suspended. Verify your account immediately to avoid losing GH₵ 2,500. Reply with your PIN or call this number now.';
const safeExample = 'You received GH₵ 50.00 from Ama Mensah. Your new balance is GH₵ 1,247.80. Thank you for using MTN MoMo.';
export default function SignalLabPage() {
  const [text, setText] = useState(example);
  const [language, setLanguage] = useState('English');
  const [voice, setVoice] = useState(false);
  const [result, setResult] = useState<{ score: number; rules: string[]; intent: string; decision: string; mode: RiskLevel; message: string } | null>(null);
  const [isRinging, setIsRinging] = useState(false);
  const [msisdn, setMsisdn] = useState('+233240000310');
  const [busy, setBusy] = useState(false);
  const [assessment, setAssessment] = useState<AssessmentResult | null>(null);
  const [error, setError] = useState('');
  const addEvent = useStore((state) => state.addEvent);
  const setAnalysis = useStore((state) => state.setAnalysis);
  const currentRisk = useStore((state) => state.currentRisk);
  const handsetMode = useStore((state) => state.handsetMode);
  const handsetMessage = useStore((state) => state.handsetMessage);
  const analyze = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      const channel = voice ? 'voice' : 'sms';
      const sandboxEvent = buildLabEvent({ msisdn, channel, text: text.trim() });
      const result = await submitSandboxEvent(sandboxEvent);
      setAssessment(result);
      const mode: RiskLevel = result.risk_tier === 'HIGH' ? 'high' : result.risk_tier === 'MEDIUM' ? 'medium' : 'low';
      const message =
        result.action_taken === 'BLOCKED'
          ? 'Transaction blocked. This request may be a scam. Never share your MoMo PIN. Call 100 for help.'
          : mode === 'medium'
            ? 'Take a moment before you act. We noticed unusual language. Never share your PIN.'
            : 'This message looks safe. Remember: MoMo will never ask for your PIN.';
      setResult({ score: result.risk_score, rules: result.triggered_rules, intent: result.llm_intent ?? 'pending', decision: result.action_taken === 'BLOCKED' ? 'SIMULATED HOLD' : result.action_taken === 'WARNED' ? 'COOLING-OFF PROMPT' : 'ALLOW - LOW RISK', mode, message });
      setAnalysis(result.risk_score, message);
      const event = assessmentToSignalEvent(result);
      const alert = assessmentToAlert(result);
      addEvent(event, alert ? { ...alert, summary: 'Signal Lab - live assessment' } : undefined);
      if (voice) {
        setIsRinging(true);
        try {
          const context = new window.AudioContext();
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.type = 'sine'; oscillator.frequency.value = 440;
          gain.gain.setValueAtTime(0, context.currentTime);
          gain.gain.setValueAtTime(0.045, context.currentTime + 0.1);
          gain.gain.setValueAtTime(0, context.currentTime + 0.34);
          gain.gain.setValueAtTime(0.045, context.currentTime + 0.48);
          gain.gain.setValueAtTime(0, context.currentTime + 0.78);
          oscillator.connect(gain); gain.connect(context.destination);
          oscillator.start(); oscillator.stop(context.currentTime + 0.8);
          oscillator.onended = () => { void context.close(); };
        } catch { /* Audio may be unavailable in a muted or restricted browser. */ }
        window.setTimeout(() => setIsRinging(false), 1800);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed - is the Intelligence Core running?');
    } finally {
      setBusy(false);
    }
  };
  const reset = () => { setText(''); setResult(null); setAssessment(null); setError(''); setAnalysis(0, 'Your MoMo account is protected. Never share your PIN with anyone.'); };
  const readAloud = () => { if ('speechSynthesis' in window) { const utterance = new SpeechSynthesisUtterance(result?.message ?? handsetMessage); utterance.lang = language === 'Twi' ? 'en-GH' : 'en-US'; window.speechSynthesis.speak(utterance); } };
  const mode = result?.mode ?? handsetMode;
  const score = result?.score ?? currentRisk;
  return <AppShell><div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><div className="mb-2 flex items-center gap-2"><span className="text-[9px] font-semibold uppercase tracking-[.18em] text-slate-600">Evaluation workspace</span><Badge variant="medium">SANDBOX</Badge></div><h1 className="text-[24px] font-semibold tracking-tight text-white sm:text-[28px]">Live Signal <span className="text-[#ffcc00]">Lab</span></h1><p className="mt-1.5 max-w-xl text-[11px] text-slate-500">Challenge the engine. See the intervention. Every result here is simulated for this demo.</p></div><Link href="/handset" className="flex items-center gap-1.5 text-[10px] text-slate-500 transition hover:text-[#ffcc00]">Open handset simulator <ArrowRight size={13}/></Link></div>
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(330px,.83fr)]"><Card className="overflow-hidden"><div className="border-b border-white/[.06] px-5 py-4"><div className="flex items-center gap-2"><div className="grid h-7 w-7 place-items-center rounded-lg bg-[#ffcc00]/[.09] text-[#ffcc00]"><Radio size={14}/></div><div><h2 className="text-[12px] font-semibold text-slate-100">Synthetic signal input</h2><p className="mt-1 text-[9px] text-slate-600">Paste any SMS or transcript to simulate a risk analysis</p></div></div></div><div className="space-y-5 p-5"><div><div className="mb-2 flex items-center justify-between"><label htmlFor="signal-text" className="text-[10px] font-semibold text-slate-300">Message or transcript</label><span className="font-mono text-[9px] text-slate-600">{text.length} chars</span></div><Textarea id="signal-text" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste or type an SMS or voice transcript…" className="min-h-[160px] font-mono text-[11px] leading-[1.85]"/><div className="mt-2 flex flex-wrap gap-2"><button type="button" onClick={() => setText(example)} className="rounded-md border border-white/[.07] px-2.5 py-1.5 text-[9px] text-slate-500 transition hover:border-rose-400/20 hover:text-rose-200">Load scam sample</button><button type="button" onClick={() => setText(safeExample)} className="rounded-md border border-white/[.07] px-2.5 py-1.5 text-[9px] text-slate-500 transition hover:border-emerald-400/20 hover:text-emerald-200">Load safe sample</button><button type="button" onClick={reset} className="ml-auto flex items-center gap-1 text-[9px] text-slate-600 hover:text-slate-300"><RotateCcw size={10}/>Clear</button></div></div>
    <div><label htmlFor="msisdn" className="mb-2 block text-[10px] font-semibold text-slate-300">Subscriber MSISDN (sandbox)</label><Input id="msisdn" value={msisdn} onChange={(event) => setMsisdn(event.target.value)} placeholder="+233XXXXXXXXX" className="h-10 font-mono text-[11px]"/></div>
    <div className="grid gap-4 sm:grid-cols-2"><div><label htmlFor="language" className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold text-slate-300"><Languages size={12} className="text-slate-500"/>Input language</label><select id="language" value={language} onChange={(event) => setLanguage(event.target.value)} className="h-10 w-full rounded-lg border border-white/10 bg-[#090e14] px-3 text-[11px] text-slate-200 outline-none focus:border-[#ffcc00]/40"><option>English</option><option>Twi</option><option>Pidgin</option></select></div><div className="flex items-end"><label className="flex h-10 w-full cursor-pointer items-center gap-3 rounded-lg border border-white/10 bg-[#090e14] px-3 transition hover:border-white/20"><input type="checkbox" checked={voice} onChange={(event) => setVoice(event.target.checked)} className="h-3.5 w-3.5 accent-[#ffcc00]"/><span className="grid h-6 w-6 place-items-center rounded-md bg-white/[.05] text-slate-400"><Mic size={12}/></span><span className="flex-1 text-[10px] text-slate-300">Simulate voice call</span><span className="text-[8px] text-slate-600">{voice ? 'VOICE' : 'OFF'}</span></label></div></div>
    {voice && <div className={`flex items-center gap-3 rounded-xl border border-amber-300/15 bg-amber-300/[.04] p-3 ${isRinging ? 'ringing' : ''}`}><div className="grid h-8 w-8 place-items-center rounded-full bg-amber-300/[.1] text-amber-200"><AudioLines size={15}/></div><div className="flex-1"><p className="text-[10px] font-semibold text-amber-100">Voice-channel simulation enabled</p><p className="mt-1 text-[9px] text-slate-500">Audio event patterns will be added to the risk score.</p></div><Waves size={16} className="text-amber-300"/></div>}
    <Button onClick={analyze} disabled={busy || !text.trim()} size="lg" className="w-full text-[11px] font-bold tracking-wide"><Sparkles size={15}/>{busy ? 'Assessing...' : 'Analyze signal'}<ArrowRight size={14}/></Button>{error && <p className="rounded-lg border border-rose-400/20 bg-rose-400/[.06] px-3 py-2 text-center text-[9px] text-rose-200">{error}</p>}<p className="text-center text-[8px] text-slate-700">Live assessment via Intelligence Core - latency {assessment ? assessment.latency_ms + 'ms' : 'pending'}</p></div></Card>
    <div className="space-y-4"><Card className="overflow-hidden"><CardHeader className="border-b border-white/[.06] px-5 py-4"><div className="flex items-center justify-between"><div><CardTitle className="text-[12px]">Engine response</CardTitle><CardDescription className="mt-1 text-[9px]">{result ? 'Analysis complete · mock ruleset v2.4.1' : 'Waiting for a signal to analyze'}</CardDescription></div><Badge variant={result ? result.mode : 'outline'}>{result ? result.mode === 'high' ? 'HIGH RISK' : result.mode === 'medium' ? 'MEDIUM RISK' : 'LOW RISK' : 'STANDBY'}</Badge></div></CardHeader><div className="flex flex-col items-center gap-2 py-5"><motion.div key={score} initial={{ opacity: .6, scale: .96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .35 }}><RiskGauge value={score} size={166} label="Risk score"/></motion.div><div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${result?.mode === 'high' ? 'border-rose-400/20 bg-rose-400/[.06] text-rose-200' : result?.mode === 'medium' ? 'border-amber-300/20 bg-amber-300/[.06] text-amber-100' : result?.mode === 'low' ? 'border-emerald-300/20 bg-emerald-300/[.06] text-emerald-200' : 'border-white/[.07] bg-white/[.02] text-slate-500'}`}>{result?.mode === 'low' ? <ShieldCheck size={13}/> : <ShieldAlert size={13}/>}<span className="text-[10px] font-bold tracking-[.08em]">{result?.decision ?? 'AWAITING INPUT'}</span></div></div><div className="border-t border-white/[.06] px-5 py-4"><div className="mb-3 flex items-center gap-2"><Code2 size={13} className="text-slate-500"/><span className="text-[10px] font-semibold text-slate-300">Intent analysis</span><Badge variant="outline" className="ml-auto">JSON · MOCK</Badge></div><pre className="scrollbar-thin overflow-x-auto rounded-lg border border-white/[.05] bg-[#090e14] p-3 font-mono text-[9px] leading-[1.8] text-slate-400">{JSON.stringify({ intent_pattern: result?.intent ?? 'pending', triggered_rules: result?.rules ?? [], language, channel: voice ? 'voice' : 'sms', intervention: result?.decision ?? 'pending', engine: 'MoMo Shield Hybrid v2.4.1' }, null, 2)}</pre></div><div className="flex items-start gap-2 border-t border-white/[.06] px-5 py-3.5"><AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-300"/><p className="text-[9px] leading-relaxed text-slate-500">This interactive demo applies local mock heuristics. It does not call a live LLM, Rancard Glance, or telecom sandbox.</p></div></Card>
    <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-white/[.06] px-4 py-3"><div><p className="text-[10px] font-semibold text-slate-200">Victim handset preview</p><p className="mt-1 text-[8px] text-slate-600">Intervention as it appears to the customer</p></div><Link href="/handset" className="text-slate-600 hover:text-slate-300"><ArrowRight size={13}/></Link></div><div className="bg-[radial-gradient(ellipse_at_center,rgba(61,78,88,.18),transparent_70%)] px-3 py-4"><HandsetFrame mode={mode} message={result?.message ?? handsetMessage} compact onReadAloud={readAloud}/></div></Card></div></div>
    <Card className="mt-5 flex flex-wrap items-center justify-between gap-3 p-4"><div className="flex items-center gap-3"><div className="grid h-8 w-8 place-items-center rounded-lg bg-sky-300/[.07] text-sky-300"><Clipboard size={14}/></div><div><p className="text-[10px] font-semibold text-slate-300">Judge-in-the-loop</p><p className="mt-1 text-[9px] text-slate-600">Try the scam sample, then swap to a legitimate notification and compare outcomes.</p></div></div><span className="flex items-center gap-1.5 text-[9px] text-emerald-300"><CheckCircle2 size={12}/>Results stream to the Command Center</span></Card>
  </AppShell>;
}
