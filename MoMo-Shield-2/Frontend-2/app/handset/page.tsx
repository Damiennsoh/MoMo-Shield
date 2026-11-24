'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  Languages,
  Shield,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  Volume2,
} from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { Badge } from '@/components/ui/primitives';
import { useStore, type RiskLevel } from '@/lib/useStore';
import { HandsetFrame } from '@/components/HandsetFrame';
import { playEnglishTwiWarning, stopAllSounds } from '@/lib/sound';

const states: {
  id: RiskLevel;
  title: string;
  sub: string;
  icon: typeof ShieldCheck;
  selected: string;
  iconTone: string;
}[] = [
  {
    id: 'low',
    title: 'Normal · Protected',
    sub: 'Standard MoMo user experience',
    icon: ShieldCheck,
    selected: 'border-emerald-500/40 bg-emerald-500/15 shadow-sm',
    iconTone: 'bg-emerald-500/20 text-emerald-300',
  },
  {
    id: 'medium',
    title: 'Cooling-off Prompt',
    sub: 'Gentle pause · medium risk threshold',
    icon: CircleHelp,
    selected: 'border-amber-500/40 bg-amber-500/15 shadow-sm',
    iconTone: 'bg-amber-500/20 text-amber-200',
  },
  {
    id: 'high',
    title: 'Transaction Blocked / Hold',
    sub: 'High risk · urgent dual-language intervention',
    icon: ShieldAlert,
    selected: 'border-rose-500/40 bg-rose-500/15 shadow-sm',
    iconTone: 'bg-rose-500/20 text-rose-300',
  },
];

export default function HandsetPage() {
  const mode = useStore((state) => state.handsetMode);
  const message = useStore((state) => state.handsetMessage);
  const twiMessage = useStore((state) => state.twiWarningMessage);
  const setAnalysis = useStore((state) => state.setAnalysis);
  const soundEnabled = useStore((state) => state.soundEnabled);

  const [larger, setLarger] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  const setMode = (next: RiskLevel) => {
    const score = next === 'high' ? 94 : next === 'medium' ? 57 : 8;
    const copy =
      next === 'high'
        ? 'Transaction blocked. We detected a suspicious credential request. Call 100 for support.'
        : next === 'medium'
        ? 'Take a moment before you act. We noticed unusual pressure. Never share your PIN.'
        : 'Your MoMo account is protected. Never share your PIN with anyone.';

    const twi =
      next === 'high'
        ? 'Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!'
        : next === 'medium'
        ? 'Mepa wo kyɛw, twɛn kakra ansa. Mfa wo PIN mma obiara.'
        : 'Wo MoMo sika bɔne biara nni ho. MoMo remmisa wo PIN da.';

    setAnalysis(score, copy, twi);
  };

  const readAloud = () => {
    setIsPlayingAudio(true);
    void playEnglishTwiWarning({
      englishText: message,
      twiText: twiMessage,
      onEnded: () => setIsPlayingAudio(false),
    });
  };

  const handleStopAudio = () => {
    stopAllSounds();
    setIsPlayingAudio(false);
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-[1140px]">
        {/* Header Bar */}
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
                Intervention Preview
              </span>
              <Badge variant="outline">SIMULATION</Badge>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
              Victim Handset <span className="text-[#ffcc00]">Simulator</span>
            </h1>
            <p className="mt-1.5 max-w-xl text-xs text-slate-300">
              Preview how risk decisions become clear, accessible guidance for Ghanaian subscribers across English and Twi.
            </p>
          </div>
          <Link
            href="/lab"
            className="flex items-center gap-2 rounded-lg border border-white/[.12] bg-white/[.04] px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:border-[#ffcc00] hover:text-[#ffcc00]"
          >
            Update Live Signal <ArrowRight size={14} />
          </Link>
        </div>

        {/* Casing Container */}
        <section className="overflow-hidden rounded-2xl border border-white/[.1] bg-[#0c121a]/95 shadow-2xl">
          <header className="flex items-center justify-between border-b border-white/[.08] px-5 py-3.5 md:px-7">
            <div className="flex items-center gap-2.5 text-xs font-semibold text-slate-300">
              <Shield size={15} className="text-[#ffcc00]" />
              <span>Subscriber Experience Demonstration</span>
            </div>
            <span className="flex items-center gap-2 rounded-full border border-white/[.1] bg-white/[.04] px-3 py-1 text-[9px] font-bold text-slate-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
              CLIENT DEMO · NO LIVE TELECOM DISPATCH
            </span>
          </header>

          <div className="grid md:grid-cols-[1fr_1fr]">
            {/* Left Column: Handset Frame */}
            <section className="flex flex-col items-center px-6 pb-8 pt-6 md:justify-center md:border-r md:border-white/[.08] md:px-10 md:py-10 bg-black/20">
              <div className="mb-4 flex w-full max-w-[340px] items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
                  Victim Handset · Ghana
                </span>
                <button
                  type="button"
                  aria-pressed={larger}
                  onClick={() => setLarger(!larger)}
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                    larger
                      ? 'border-[#ffcc00] bg-[#ffcc00]/15 text-[#ffcc00]'
                      : 'border-white/[.12] text-slate-300 hover:text-white'
                  }`}
                >
                  <SlidersHorizontal size={13} />
                  {larger ? 'Larger text: ON' : 'Larger text'}
                </button>
              </div>

              <div className="w-full max-w-[340px]">
                <HandsetFrame
                  mode={mode}
                  message={message}
                  twiMessage={twiMessage}
                  largerText={larger}
                  onReadAloud={readAloud}
                />
              </div>

              <p className="mt-4 max-w-[300px] text-center text-[10px] leading-relaxed text-slate-400 font-medium">
                Simulated victim handset · Displays on-screen English + Twi warning when transaction is held.
              </p>
            </section>

            {/* Right Column: State Selector & Audio Controls */}
            <section className="flex flex-col px-5 pb-8 pt-6 md:justify-center md:px-9 md:py-10">
              <div className="mx-auto w-full max-w-[400px]">
                <div className="mb-6 hidden md:block">
                  <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl border border-[#ffcc00]/25 bg-[#ffcc00]/15 text-[#ffcc00]">
                    <Shield size={20} />
                  </div>
                  <p className="text-[10px] font-bold uppercase tracking-[.2em] text-[#ffcc00]">
                    MoMo Shield · Active Intervention
                  </p>
                  <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-white leading-tight">
                    Accessible Guidance <br />
                    for Every Subscriber.
                  </h2>
                  <p className="mt-2 text-xs leading-relaxed text-slate-300">
                    Switch between normal, cooling-off, and blocked states to inspect real-time visual and voice safety warnings.
                  </p>
                </div>

                <div className="flex items-center gap-2.5 border-b border-white/[.08] pb-3.5">
                  <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#ffcc00] text-xs font-black text-slate-950">
                    m
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white">MTN MoMo Integration Mode</p>
                    <p className="text-[10px] text-slate-400">Choose a risk state to trigger</p>
                  </div>
                  <Languages size={15} className="ml-auto text-[#ffcc00]" />
                </div>

                {/* State Options */}
                <div className="mt-4 grid gap-3">
                  {states.map(({ id, title, sub, icon: Icon, selected, iconTone }) => (
                    <button
                      type="button"
                      key={id}
                      aria-pressed={mode === id}
                      onClick={() => setMode(id)}
                      className={`flex items-center gap-3.5 rounded-xl border p-3.5 text-left transition ${
                        mode === id ? selected : 'border-white/[.08] bg-white/[.02] hover:border-white/20'
                      }`}
                    >
                      <span className={`grid h-9 w-9 place-items-center rounded-lg ${iconTone}`}>
                        <Icon size={17} />
                      </span>
                      <span className="flex-1">
                        <span className="block text-xs font-bold text-white">{title}</span>
                        <span className="mt-0.5 block text-[10px] text-slate-400">{sub}</span>
                      </span>
                      {mode === id && <Check size={16} className="text-[#ffcc00]" />}
                    </button>
                  ))}
                </div>

                {/* Read aloud and audio toggle */}
                <div className="mt-5 space-y-2.5">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={readAloud}
                      disabled={isPlayingAudio}
                      className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/[.06] py-3 text-xs font-bold text-white transition hover:bg-white/[.12] disabled:opacity-50"
                    >
                      <Volume2 size={16} className="text-[#ffcc00]" />
                      {isPlayingAudio ? 'Speaking...' : 'Read Warning Aloud (Twi + EN)'}
                    </button>
                    {isPlayingAudio && (
                      <button
                        type="button"
                        onClick={handleStopAudio}
                        className="flex items-center justify-center gap-1.5 rounded-xl border border-rose-500/30 bg-rose-500/20 px-4 text-xs font-semibold text-rose-200 transition hover:bg-rose-500/30"
                      >
                        <Square size={13} />
                        Stop
                      </button>
                    )}
                  </div>

                  <p className="text-[10px] text-slate-400 text-center">
                    {soundEnabled
                      ? '🔊 Internal Sound: ACTIVE (Mute in top bar if testing with real phone)'
                      : '🔇 Internal Sound: MUTED (Phone Mode active)'}
                  </p>
                </div>

                {/* Ghanaian Inclusivity Callout */}
                <div className="mt-5 rounded-xl border border-sky-400/20 bg-sky-400/[.05] p-3.5 shadow-sm">
                  <p className="flex items-center gap-2 text-xs font-bold text-sky-200">
                    <ShieldCheck size={14} className="text-sky-300" />
                    Built for Real Ghanaian Subscribers
                  </p>
                  <p className="mt-1 text-[11px] leading-relaxed text-slate-300">
                    Blind and non-literate subscribers receive IVR spoken warnings in Twi:
                    <strong className="block text-[#ffcc00] mt-1">
                      “Mepa wo kyɛw, fa wo PIN kɔ ma” — Please never give away your PIN.
                    </strong>
                  </p>
                </div>

                <Link
                  href="/lab"
                  className="mt-5 flex items-center justify-between text-xs font-medium text-slate-400 transition hover:text-[#ffcc00]"
                >
                  <span>Test dynamic messages in Live Signal Lab</span>
                  <ChevronRight size={14} />
                </Link>
              </div>
            </section>
          </div>
        </section>

        <footer className="px-2 py-4 text-center text-[10px] text-slate-400 md:text-left font-medium">
          MoMo Shield Intelligence Core · InnoFemme Hackathon 2026 · Demonstrator Interface
        </footer>
      </div>
    </AppShell>
  );
}
