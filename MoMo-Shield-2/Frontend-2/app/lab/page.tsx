'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowRight,
  AudioLines,
  CheckCircle2,
  Clipboard,
  Code2,
  Cpu,
  Flame,
  KeyRound,
  Languages,
  Layers,
  Lock,
  Mic,
  Radio,
  RotateCcw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
  Waves,
  Zap,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { AppShell } from '@/components/AppShell';
import { RiskGauge } from '@/components/RiskGauge';
import { HandsetFrame } from '@/components/HandsetFrame';
import { useStore, type RiskLevel } from '@/lib/useStore';
import { apiBase, submitSandboxEvent, type AssessmentResult, type KBMatchData } from '@/lib/api';
import { assessmentToAlert, assessmentToSignalEvent, buildLabEvent } from '@/lib/mappers';
import {
  Badge,
  Button,
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Textarea,
} from '@/components/ui/primitives';
import {
  playAlertTone,
  playEnglishTwiWarning,
  playRingSound,
  playSmsSound,
  stopAllSounds,
} from '@/lib/sound';

const example =
  'Congratulations! Your MoMo wallet has been suspended. Verify your account immediately to avoid losing GH₵ 2,500. Reply with your PIN or call this number now.';
const safeExample =
  'You received GH₵ 50.00 from Ama Mensah. Your new balance is GH₵ 1,247.80. Thank you for using MTN MoMo.';

const CASE_STUDY_PRESETS = [
  {
    id: 'GH01',
    label: 'GH01: Reversal Scam',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000310',
    text: 'Payment received: GH₵ 800.00 from Kofi Mensah. Current balance GH₵ 2,150.00. (Followed by call: Please send back the GH₵ 800 sent by mistake)',
    tag: 'Reversal Trick',
  },
  {
    id: 'GH15',
    label: 'GH15: Phishing Link',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000311',
    text: 'MTN Ghana Alert: Your MoMo account has pending verification. Visit http://mtn-gh-update.net/login and enter your secret PIN to reactivate immediately.',
    tag: 'PIN Harvesting',
  },
  {
    id: 'GH18',
    label: 'GH18: SIM Swap Drain',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000312',
    text: 'New SIM registration notice: Your MSISDN is being paired with replacement SIM. Reply with PIN to authorize wallet transfer of GH₵ 3,500.',
    tag: 'Device Takeover',
  },
  {
    id: 'GH19',
    label: 'GH19: Authority Helper',
    channel: 'voice',
    voice: true,
    msisdn: '+233240000313',
    text: 'Hello, this is the official MTN head office security department calling to assist on your behalf. We detected an unauthorized login, reply with your PIN to protect your float.',
    tag: 'Nuisance Preconditioning',
  },
  {
    id: 'GH16',
    label: 'GH16: Approve-to-Receive',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000316',
    text: 'You have a pending refund of GH₵ 450.00 from Telecel. Please approve the prompt on your phone right now to receive your refund credit.',
    tag: 'RTP Abuse',
  },
  {
    id: 'GH19B',
    label: 'GH19B: Relative Emergency',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000317',
    text: 'Mum, this is Kwame on my new number. I had an accident near Kumasi and am in hospital, please send emergency money and PIN immediately.',
    tag: 'Distress Coercion',
  },
  {
    id: 'GH22',
    label: 'GH22: Structuring',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000318',
    text: 'Transfer GH₵ 950.00 to agent float wallet 0551122334. Reference: split payment 1 of 4.',
    tag: 'Sub-limit Evading',
  },
  {
    id: 'SAFE',
    label: 'Safe: School Fees',
    channel: 'sms',
    voice: false,
    msisdn: '+233240000350',
    text: 'You sent GH₵ 1,200.00 to Achimota School Accounts. Fee GH₵ 0.00. Balance GH₵ 4,820.00. Reference: Term 1 Fees Kwesi.',
    tag: '0% Friction Control',
  },
];

const twiWarningDefault =
  'Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!';
const englishWarningDefault =
  'Transaction blocked. We detected suspicious credential pressure. Never share your MoMo PIN with anyone. Call 100 for support.';

export default function SignalLabPage() {
  const [text, setText] = useState(example);
  const [language, setLanguage] = useState('English');
  const [voice, setVoice] = useState(false);
  const [result, setResult] = useState<{
    score: number;
    rules: string[];
    intent: string;
    decision: string;
    mode: RiskLevel;
    message: string;
    twiMessage: string;
    kbMatch?: KBMatchData | null;
  } | null>(null);

  const [isRinging, setIsRinging] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [msisdn, setMsisdn] = useState('+233240000399');
  const [busy, setBusy] = useState(false);
  const [assessment, setAssessment] = useState<AssessmentResult | null>(null);
  const [error, setError] = useState('');
  const [showRawJson, setShowRawJson] = useState(false);

  const addEvent = useStore((state) => state.addEvent);
  const setAnalysis = useStore((state) => state.setAnalysis);
  const currentRisk = useStore((state) => state.currentRisk);
  const handsetMode = useStore((state) => state.handsetMode);
  const handsetMessage = useStore((state) => state.handsetMessage);
  const soundEnabled = useStore((state) => state.soundEnabled);

  const analyze = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setError('');

    try {
      const channel = voice ? 'voice' : 'sms';

      // 1. Play incoming channel sound
      if (voice) {
        setIsRinging(true);
        void playRingSound();
        setTimeout(() => setIsRinging(false), 2400);
      } else {
        void playSmsSound();
      }

      // 2. Submit to Intelligence Core API
      const sandboxEvent = buildLabEvent({ msisdn, channel, text: text.trim() });
      const res = await submitSandboxEvent(sandboxEvent);
      setAssessment(res);

      const mode: RiskLevel =
        res.risk_tier === 'HIGH' ? 'high' : res.risk_tier === 'MEDIUM' ? 'medium' : 'low';

      const englishMsg =
        res.action_taken === 'BLOCKED'
          ? 'Transaction blocked. This request may be a scam. Never share your MoMo PIN. Call 100 for help.'
          : mode === 'medium'
            ? 'Take a moment before you act. We noticed unusual pressure. Never share your PIN.'
            : 'This message looks safe. Remember: MoMo will never ask for your PIN.';

      const twiMsg =
        res.action_taken === 'BLOCKED'
          ? 'Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!'
          : mode === 'medium'
            ? 'Mepa wo kyɛw, twɛn kakra ansa. Mfa wo PIN mma obiara.'
            : 'Wo MoMo sika bɔne biara nni ho. MoMo remmisa wo PIN da.';

      setResult({
        score: res.risk_score,
        rules: res.triggered_rules,
        intent: res.llm_intent ?? 'pending',
        decision:
          res.action_taken === 'BLOCKED'
            ? 'SIMULATED HOLD'
            : res.action_taken === 'WARNED'
              ? 'COOLING-OFF PROMPT'
              : 'ALLOW - LOW RISK',
        mode,
        message: englishMsg,
        twiMessage: twiMsg,
        kbMatch: res.kb_match,
      });

      setAnalysis(res.risk_score, englishMsg, twiMsg);

      const event = assessmentToSignalEvent(res);
      const alert = assessmentToAlert(res);
      addEvent(event, alert ? { ...alert, summary: 'Signal Lab - live assessment' } : undefined);

      // 3. Audio & Real Phone Bridge Intervention
      if (res.risk_tier === 'HIGH') {
        void playAlertTone();
        // Trigger English + Twi voice warning if sound is enabled
        if (soundEnabled) {
          setIsPlayingAudio(true);
          void playEnglishTwiWarning({
            englishText: englishMsg,
            twiText: twiMsg,
            onEnded: () => setIsPlayingAudio(false),
          });
        }

        // Bridge to real phone (Asterisk SIP Linphone) if present
        try {
          void fetch(`${apiBase()}/api/v1/demo/real-phone-action?action=ring`, { method: 'POST' }).catch(() => { });
        } catch {
          // ignore
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Assessment failed - is the Intelligence Core running?');
    } finally {
      setBusy(false);
    }
  };

  const handlePlayVoiceWarning = () => {
    setIsPlayingAudio(true);
    void playEnglishTwiWarning({
      englishText: result?.message || englishWarningDefault,
      twiText: result?.twiMessage || twiWarningDefault,
      onEnded: () => setIsPlayingAudio(false),
    });
  };

  const handleStopAudio = () => {
    stopAllSounds();
    setIsPlayingAudio(false);
    setIsRinging(false);
  };

  const reset = () => {
    stopAllSounds();
    setText('');
    setResult(null);
    setAssessment(null);
    setError('');
    setIsPlayingAudio(false);
    setAnalysis(0, 'Your MoMo account is protected. Never share your PIN with anyone.', twiWarningDefault);
  };

  const mode = result?.mode ?? handsetMode;
  const score = result?.score ?? currentRisk;
  // Only surface KB matches above the confidence floor; weaker hits are noise.
  const kbMatch = result?.kbMatch && result.kbMatch.similarity >= 0.35 ? result.kbMatch : null;

  return (
    <AppShell>
      {/* Header bar */}
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-[.2em] text-slate-400">
              Evaluation Workspace
            </span>
            <Badge variant="medium">SANDBOX</Badge>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            Live Signal <span className="text-[#ffcc00]">Lab</span>
          </h1>
          <p className="mt-1.5 max-w-xl text-xs text-slate-300">
            Challenge the hybrid engine with live synthetic inputs. Hear real-time tones &amp; English + Twi voice interventions.
          </p>
        </div>

        <Link
          href="/handset"
          className="flex items-center gap-2 rounded-lg border border-white/[.12] bg-white/[.04] px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:border-[#ffcc00] hover:text-[#ffcc00]"
        >
          <Smartphone size={15} />
          Open Full Handset Simulator <ArrowRight size={14} />
        </Link>
      </div>

      {/* Main Grid */}
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,.95fr)]">
        {/* Left Column: Input Panel */}
        <Card className="overflow-hidden">
          <div className="border-b border-white/[.08] px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-[#ffcc00]/15 text-[#ffcc00]">
                <Radio size={16} />
              </div>
              <div>
                <h2 className="text-sm font-bold text-white">Synthetic Signal Input</h2>
                <p className="mt-0.5 text-xs text-slate-400">
                  Paste or type any scam or safe SMS, or simulate a voice call transcript
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-5 p-6">
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label htmlFor="signal-text" className="text-xs font-bold text-slate-200">
                  Message or Transcript
                </label>
                <span className="font-mono text-[10px] font-semibold text-slate-400">{text.length} chars</span>
              </div>
              <Textarea
                id="signal-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste or type an SMS or voice transcript…"
                className="min-h-[160px] font-mono text-xs leading-relaxed"
              />
              {/* Case Study Library Preset Selector */}
              <div className="mt-3.5 space-y-2">
                <div className="flex items-center justify-between text-[11px] font-bold text-slate-400">
                  <span>Track 1 Case Study Dossiers (InnoFemme Library):</span>
                  <button
                    type="button"
                    onClick={reset}
                    className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-white"
                  >
                    <RotateCcw size={11} />
                    Reset
                  </button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                  {CASE_STUDY_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => {
                        setText(preset.text);
                        setMsisdn(preset.msisdn);
                        setVoice(preset.voice);
                      }}
                      className={`rounded-lg border px-2.5 py-1.5 text-left text-[11px] font-semibold transition ${
                        text === preset.text
                          ? 'border-[#ffcc00] bg-[#ffcc00]/15 text-[#ffcc00]'
                          : preset.id === 'SAFE'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20'
                            : 'border-white/[.1] bg-white/[.03] text-slate-300 hover:bg-white/[.08] hover:text-white'
                      }`}
                      title={preset.tag}
                    >
                      <span className="block truncate font-bold">{preset.label}</span>
                      <span className="block text-[9px] text-slate-400 truncate">{preset.tag}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <label htmlFor="msisdn" className="mb-2 block text-xs font-bold text-slate-200">
                Subscriber MSISDN (Ghana Sandbox)
              </label>
              <Input
                id="msisdn"
                value={msisdn}
                onChange={(e) => setMsisdn(e.target.value)}
                placeholder="+233XXXXXXXXX"
                className="h-10 font-mono text-xs"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="language" className="mb-2 flex items-center gap-1.5 text-xs font-bold text-slate-200">
                  <Languages size={14} className="text-[#ffcc00]" />
                  Language / Dialect
                </label>
                <select
                  id="language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="h-10 w-full rounded-lg border border-white/[.14] bg-[#080d14] px-3.5 text-xs font-semibold text-slate-100 outline-none transition focus:border-[#ffcc00] focus:ring-2 focus:ring-[#ffcc00]/20"
                >
                  <option>English</option>
                  <option>Twi</option>
                  <option>Ghanaian Pidgin</option>
                </select>
              </div>

              <div className="flex items-end">
                <label className="flex h-10 w-full cursor-pointer items-center gap-3 rounded-lg border border-white/[.14] bg-[#080d14] px-3.5 transition hover:border-white/30">
                  <input
                    type="checkbox"
                    checked={voice}
                    onChange={(e) => setVoice(e.target.checked)}
                    className="h-4 w-4 rounded accent-[#ffcc00]"
                  />
                  <span className="grid h-6 w-6 place-items-center rounded-md bg-white/[.08] text-slate-300">
                    <Mic size={13} />
                  </span>
                  <span className="flex-1 text-xs font-bold text-slate-200">Simulate Voice Call</span>
                  <span className="font-mono text-[10px] font-bold text-slate-400">{voice ? 'VOICE' : 'SMS'}</span>
                </label>
              </div>
            </div>

            {voice && (
              <div
                className={`flex items-center gap-3.5 rounded-xl border border-amber-400/25 bg-amber-400/[.07] p-3.5 ${isRinging ? 'ringing' : ''
                  }`}
              >
                <div className="grid h-9 w-9 place-items-center rounded-full bg-amber-400/20 text-amber-300">
                  <AudioLines size={18} />
                </div>
                <div className="flex-1">
                  <p className="text-xs font-bold text-amber-200">Voice-Channel Simulation Active</p>
                  <p className="mt-0.5 text-[11px] text-amber-300/80">
                    Will trigger phone ring tones and evaluate conversational coercion patterns.
                  </p>
                </div>
                <Waves size={18} className="text-amber-400 animate-pulse" />
              </div>
            )}

            {/* Active InnoFemme Network Interception Hook Info */}
            <div className="flex items-center justify-between rounded-lg border border-white/[.08] bg-white/[.02] px-3.5 py-2 text-[11px] font-mono text-slate-400">
              <span className="flex items-center gap-1.5 text-slate-300 font-sans font-medium">
                <Radio size={12} className="text-[#ffcc00]" />
                <span>Interception Gateway:</span>
              </span>
              <span className="text-emerald-300 font-semibold bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded">
                {voice ? 'Hook 13: call.connect (Pre-ring)' : 'Hook 12: sms.deliver (Pre-delivery)'}
              </span>
            </div>

            {/* Action Button */}
            <Button
              onClick={analyze}
              disabled={busy || !text.trim()}
              size="lg"
              className="w-full text-xs font-extrabold tracking-wide shadow-md"
            >
              <Sparkles size={16} />
              {busy ? 'Scoring Risk...' : 'Analyze Synthetic Signal'}
              <ArrowRight size={16} />
            </Button>

            {error && (
              <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-center text-xs font-semibold text-rose-200">
                {error}
              </p>
            )}

            <div className="flex items-center justify-between border-t border-white/[.07] pt-3 text-[10px] text-slate-400">
              <span>Engine: MoMo Shield Intelligence Core</span>
              <span>Latency: {assessment ? `${assessment.latency_ms} ms` : 'Standby'}</span>
            </div>
          </div>
        </Card>

        {/* Right Column: Engine Response & Handset Preview */}
        <div className="space-y-5">
          {/* Engine Response Card */}
          <Card className="overflow-hidden">
            <CardHeader className="border-b border-white/[.08] px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-white">Engine Assessment</CardTitle>
                  <CardDescription className="mt-0.5 text-xs text-slate-400">
                    {result ? 'Analysis complete · hybrid multi-tier rules' : 'Awaiting signal input'}
                  </CardDescription>
                </div>
                <Badge variant={result ? result.mode : 'outline'}>
                  {result
                    ? result.mode === 'high'
                      ? 'HIGH RISK'
                      : result.mode === 'medium'
                        ? 'MEDIUM RISK'
                        : 'LOW RISK'
                    : 'STANDBY'}
                </Badge>
              </div>
            </CardHeader>

            <div className="flex flex-col items-center gap-3 py-6 px-6">
              <motion.div
                key={score}
                initial={{ opacity: 0.7, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.35 }}
              >
                <RiskGauge value={score} size={170} label="Risk Score" />
              </motion.div>

              <div
                className={`flex items-center gap-2.5 rounded-lg border px-4 py-2 text-xs font-bold tracking-wide ${result?.mode === 'high'
                  ? 'border-rose-500/40 bg-rose-500/15 text-rose-200'
                  : result?.mode === 'medium'
                    ? 'border-amber-500/40 bg-amber-500/15 text-amber-200'
                    : result?.mode === 'low'
                      ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-200'
                      : 'border-white/10 bg-white/[.03] text-slate-400'
                  }`}
              >
                {result?.mode === 'low' ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
                <span>{result?.decision ?? 'AWAITING INPUT'}</span>
              </div>

              {/* On-Screen Warning Notification (English + Twi) */}
              {result && result.mode === 'high' && (
                <div className="mt-2 w-full rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-extrabold text-rose-300">
                    <ShieldAlert size={16} />
                    <span>⚠️ TRANSACTION ON HOLD / INTERVENTION ACTIVE</span>
                  </div>
                  <div className="mt-2 space-y-1.5 text-xs leading-relaxed text-slate-100">
                    <p>
                      <strong className="text-white">English: </strong>
                      {result.message}
                    </p>
                    <p className="border-t border-rose-500/20 pt-1.5">
                      <strong className="text-[#ffcc00]">Twi (Kɔkɔbɔ): </strong>
                      {result.twiMessage}
                    </p>
                  </div>

                  {/* Audio Controls inside warning */}
                  <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-rose-500/20 pt-3">
                    <button
                      type="button"
                      onClick={handlePlayVoiceWarning}
                      disabled={isPlayingAudio}
                      className="flex items-center gap-1.5 rounded-lg border border-amber-400/40 bg-[#ffcc00] px-3 py-1.5 text-xs font-bold text-slate-950 transition hover:bg-[#ffdb4d] disabled:opacity-50"
                    >
                      <Volume2 size={14} />
                      {isPlayingAudio ? 'Speaking Warning...' : 'Play English + Twi Audio'}
                    </button>
                    {isPlayingAudio && (
                      <button
                        type="button"
                        onClick={handleStopAudio}
                        className="flex items-center gap-1.5 rounded-lg border border-white/20 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700"
                      >
                        <Square size={12} />
                        Stop Audio
                      </button>
                    )}
                    <span className="text-[10px] text-slate-300">
                      {soundEnabled ? '🔊 Audio Active' : '🔇 Muted for Real Phone'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Behavioral Threat & Intent Analysis */}
            {(() => {
              const lowerText = text.toLowerCase();
              const hasSecretSolicitation =
                lowerText.includes('pin') ||
                lowerText.includes('otp') ||
                lowerText.includes('password') ||
                lowerText.includes('code') ||
                lowerText.includes('secret') ||
                lowerText.includes('wo pin') ||
                (result?.rules.some((r) => r.toLowerCase().includes('secret') || r.toLowerCase().includes('pin')) ?? false);

              const hasAuthorityImpersonation =
                lowerText.includes('mtn') ||
                lowerText.includes('momo') ||
                lowerText.includes('bank') ||
                lowerText.includes('police') ||
                lowerText.includes('agent') ||
                lowerText.includes('official') ||
                lowerText.includes('head office') ||
                (result?.rules.some((r) => r.toLowerCase().includes('authority') || r.toLowerCase().includes('impersonat')) ?? false);

              const hasUrgencyCoercion =
                lowerText.includes('suspend') ||
                lowerText.includes('immediately') ||
                lowerText.includes('urgent') ||
                lowerText.includes('block') ||
                lowerText.includes('right now') ||
                lowerText.includes('losing') ||
                lowerText.includes('within') ||
                (result?.rules.some((r) => r.toLowerCase().includes('urgency') || r.toLowerCase().includes('loss')) ?? false);

              const hasFinancialBait =
                lowerText.includes('congratulations') ||
                lowerText.includes('won') ||
                lowerText.includes('prize') ||
                lowerText.includes('reward') ||
                lowerText.includes('gh₵') ||
                lowerText.includes('ghc') ||
                lowerText.includes('bonus') ||
                lowerText.includes('credit');

              return (
                <div className="border-t border-white/[.08] px-6 py-5">
                  <div className="mb-3.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-[#ffcc00]/25 bg-[#ffcc00]/10">
                        <Cpu size={14} className="text-[#ffcc00]" />
                      </div>
                      <div>
                        <span className="text-xs font-bold text-slate-100">Behavioral Threat &amp; Intent Analysis</span>
                        <span className="ml-2 font-mono text-[10px] text-slate-400">Gemini 3.5 + Rules Core</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={result?.mode === 'high' ? 'high' : result?.mode === 'medium' ? 'medium' : 'outline'}>
                        {result ? `${result.mode.toUpperCase()} THREAT` : 'STANDBY'}
                      </Badge>
                      <button
                        type="button"
                        onClick={() => setShowRawJson(!showRawJson)}
                        className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-slate-900/80 px-2.5 py-1 text-[11px] font-semibold text-slate-300 transition hover:bg-slate-800 hover:text-white"
                      >
                        {showRawJson ? (
                          <>
                            <Layers size={12} className="text-[#ffcc00]" />
                            <span>Executive View</span>
                          </>
                        ) : (
                          <>
                            <Code2 size={12} className="text-slate-400" />
                            <span>Raw JSON</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {showRawJson ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span>Underlying Engine Telemetry (JSON)</span>
                        <span className="font-mono text-[10px] text-slate-500">FastAPI / InnoFemme Schema</span>
                      </div>
                      <pre className="scrollbar-thin overflow-x-auto rounded-lg border border-white/[.08] bg-[#070b10] p-3.5 font-mono text-[11px] leading-relaxed text-slate-300">
                        {JSON.stringify(
                          {
                            intent_pattern: result?.intent ?? 'pending',
                            triggered_rules: result?.rules ?? [],
                            language,
                            channel: voice ? 'voice' : 'sms',
                            intervention: result?.decision ?? 'pending',
                            engine: 'MoMo Shield Hybrid v2.0 (Rules + Gemini 3.5 Flash-Lite)',
                            psychological_levers: {
                              credential_solicitation: hasSecretSolicitation,
                              authority_impersonation: hasAuthorityImpersonation,
                              urgency_coercion: hasUrgencyCoercion,
                              financial_bait: hasFinancialBait,
                            },
                          },
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  ) : (
                    <div className="space-y-3.5">
                      {/* Primary Intent Card */}
                      <div
                        className={`rounded-xl border p-3.5 transition-all ${result?.mode === 'high'
                          ? 'border-rose-500/30 bg-rose-500/[0.07]'
                          : result?.mode === 'medium'
                            ? 'border-amber-500/30 bg-amber-500/[0.07]'
                            : result
                              ? 'border-emerald-500/30 bg-emerald-500/[0.07]'
                              : 'border-white/10 bg-slate-900/40'
                          }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                Classified Behavioral Intent
                              </span>
                              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[9px] font-semibold text-slate-300">
                                {voice ? 'Voice Coercion' : 'Inbound SMS'}
                              </span>
                            </div>
                            <p className="text-sm font-bold text-white">
                              {result?.intent && result.intent !== 'pending'
                                ? result.intent
                                : busy
                                  ? 'Evaluating semantic threat vectors...'
                                  : 'Awaiting signal - click "Analyze signal" to assess'}
                            </p>
                          </div>
                          <div className="shrink-0 text-right">
                            <span className="block text-[10px] font-mono uppercase text-slate-400">Intervention</span>
                            <span
                              className={`mt-0.5 inline-block rounded px-2 py-0.5 text-[11px] font-black uppercase tracking-wider ${result?.mode === 'high'
                                ? 'border border-rose-500/30 bg-rose-500/20 text-rose-300'
                                : result?.mode === 'medium'
                                  ? 'border border-amber-500/30 bg-amber-500/20 text-amber-300'
                                  : result
                                    ? 'border border-emerald-500/30 bg-emerald-500/20 text-emerald-300'
                                    : 'border border-white/5 bg-slate-800 text-slate-400'
                                }`}
                            >
                              {result?.decision ?? 'STANDBY'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* 4 Psychological Threat Levers Grid */}
                      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                        {/* Lever 1: Credential Solicitation */}
                        <div
                          className={`rounded-lg border p-2.5 transition-all ${hasSecretSolicitation
                            ? 'border-rose-500/30 bg-rose-500/10'
                            : 'border-white/[0.07] bg-slate-900/40'
                            }`}
                        >
                          <div className="mb-1 flex items-center justify-between">
                            <KeyRound size={13} className={hasSecretSolicitation ? 'text-rose-400' : 'text-slate-400'} />
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${hasSecretSolicitation ? 'bg-rose-500/25 text-rose-300' : 'bg-slate-800 text-slate-400'
                                }`}
                            >
                              {hasSecretSolicitation ? 'EXPLOIT' : 'CLEAR'}
                            </span>
                          </div>
                          <p className="text-xs font-semibold text-slate-200">PIN / Secret</p>
                          <p className="mt-0.5 text-[10px] leading-snug text-slate-400">
                            {hasSecretSolicitation ? 'Harvests wallet PIN/OTP' : 'No credentials requested'}
                          </p>
                        </div>

                        {/* Lever 2: Authority Impersonation */}
                        <div
                          className={`rounded-lg border p-2.5 transition-all ${hasAuthorityImpersonation
                            ? 'border-amber-500/30 bg-amber-500/10'
                            : 'border-white/[0.07] bg-slate-900/40'
                            }`}
                        >
                          <div className="mb-1 flex items-center justify-between">
                            <Shield size={13} className={hasAuthorityImpersonation ? 'text-amber-400' : 'text-slate-400'} />
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${hasAuthorityImpersonation ? 'bg-amber-500/25 text-amber-300' : 'bg-slate-800 text-slate-400'
                                }`}
                            >
                              {hasAuthorityImpersonation ? 'SPOOFED' : 'CLEAR'}
                            </span>
                          </div>
                          <p className="text-xs font-semibold text-slate-200">Authority</p>
                          <p className="mt-0.5 text-[10px] leading-snug text-slate-400">
                            {hasAuthorityImpersonation ? 'Poses as MTN/MoMo official' : 'No brand impersonation'}
                          </p>
                        </div>

                        {/* Lever 3: Urgency & Loss Aversion */}
                        <div
                          className={`rounded-lg border p-2.5 transition-all ${hasUrgencyCoercion
                            ? 'border-rose-500/30 bg-rose-500/10'
                            : 'border-white/[0.07] bg-slate-900/40'
                            }`}
                        >
                          <div className="mb-1 flex items-center justify-between">
                            <Zap size={13} className={hasUrgencyCoercion ? 'text-rose-400' : 'text-slate-400'} />
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${hasUrgencyCoercion ? 'bg-rose-500/25 text-rose-300' : 'bg-slate-800 text-slate-400'
                                }`}
                            >
                              {hasUrgencyCoercion ? 'PRESSURE' : 'CALM'}
                            </span>
                          </div>
                          <p className="text-xs font-semibold text-slate-200">Urgency</p>
                          <p className="mt-0.5 text-[10px] leading-snug text-slate-400">
                            {hasUrgencyCoercion ? 'Account freeze panic tactic' : 'Standard conversational tone'}
                          </p>
                        </div>

                        {/* Lever 4: Financial Bait */}
                        <div
                          className={`rounded-lg border p-2.5 transition-all ${hasFinancialBait
                            ? 'border-indigo-500/30 bg-indigo-500/10'
                            : 'border-white/[0.07] bg-slate-900/40'
                            }`}
                        >
                          <div className="mb-1 flex items-center justify-between">
                            <Flame size={13} className={hasFinancialBait ? 'text-indigo-400' : 'text-slate-400'} />
                            <span
                              className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${hasFinancialBait ? 'bg-indigo-500/25 text-indigo-300' : 'bg-slate-800 text-slate-400'
                                }`}
                            >
                              {hasFinancialBait ? 'BAIT' : 'NONE'}
                            </span>
                          </div>
                          <p className="text-xs font-semibold text-slate-200">Financial Hook</p>
                          <p className="mt-0.5 text-[10px] leading-snug text-slate-400">
                            {hasFinancialBait ? 'Lottery / reversal lure' : 'No advance fee hook'}
                          </p>
                        </div>
                      </div>

                      {/* RAG Knowledge Base Forensic Precedent (only above confidence floor) */}
                      {kbMatch && (
                        <div className={`rounded-xl border p-3.5 text-xs shadow-sm space-y-2 ${kbMatch.is_benign ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-amber-500/30 bg-amber-500/10'}`}>
                          <div className="flex items-center justify-between">
                            <span className={`flex items-center gap-1.5 font-bold ${kbMatch.is_benign ? 'text-emerald-300' : 'text-amber-300'}`}>
                              <Sparkles size={14} className={kbMatch.is_benign ? 'text-emerald-400' : 'text-[#ffcc00]'} />
                              {kbMatch.is_benign ? 'RAG Benign-Control Match' : 'RAG Precedent Match: InnoFemme Dossier'} {kbMatch.case_id}
                            </span>
                            <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-bold border ${kbMatch.is_benign ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-amber-500/25 text-[#ffcc00] border-amber-500/30'}`}>
                              {Math.round(kbMatch.similarity * 100)}% Similarity
                            </span>
                          </div>
                          <p className="font-semibold text-white leading-snug">{kbMatch.title}</p>
                          <div className="flex flex-wrap items-center gap-1.5 pt-1">
                            {kbMatch.psychological_levers.map((lever) => (
                              <span key={lever} className={`rounded bg-black/40 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider border ${kbMatch.is_benign ? 'text-emerald-300 border-emerald-500/20' : 'text-amber-300 border-amber-500/20'}`}>
                                {lever}
                              </span>
                            ))}
                            <span className="ml-auto text-[10px] text-slate-400 italic">
                              {kbMatch.source}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Triggered Deterministic Heuristic Rules */}
                      {result && result.rules.length > 0 ? (
                        <div className="space-y-1.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            Triggered Deterministic Rules ({result.rules.length})
                          </span>
                          {result.rules.map((rule) => (
                            <div
                              key={rule}
                              className="flex items-center justify-between rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-xs text-rose-200 shadow-sm"
                            >
                              <div className="flex items-center gap-2">
                                <ShieldAlert size={14} className="shrink-0 text-rose-400" />
                                <span className="font-medium">{rule}</span>
                              </div>
                              <span className="rounded bg-rose-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-rose-300">
                                HIGH RISK
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : result ? (
                        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-300">
                          <CheckCircle2 size={14} className="shrink-0 text-emerald-400" />
                          <span>Zero fraud heuristic rules triggered. Low-risk baseline behavior.</span>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })()}
          </Card>

          {/* Victim Handset Preview */}
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/[.08] px-5 py-3.5">
              <div>
                <p className="text-xs font-bold text-white">Victim Handset Preview</p>
                <p className="mt-0.5 text-[10px] text-slate-400">
                  Real-time visual display as received on subscriber handset
                </p>
              </div>
              <Link
                href="/handset"
                className="flex items-center gap-1 text-xs font-semibold text-slate-400 hover:text-[#ffcc00] transition"
              >
                Inspect <ArrowRight size={13} />
              </Link>
            </div>
            <div className="bg-[radial-gradient(ellipse_at_center,rgba(56,76,96,.2),transparent_70%)] px-4 py-5">
              <HandsetFrame
                mode={mode}
                message={result?.message ?? handsetMessage}
                compact
                onReadAloud={handlePlayVoiceWarning}
              />
            </div>
          </Card>
        </div>
      </div>

      {/* Info Card */}
      <Card className="mt-6 flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-3">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-sky-400/15 text-sky-300">
            <Clipboard size={15} />
          </div>
          <div>
            <p className="text-xs font-bold text-slate-200">Judge-in-the-Loop Dynamic Verification</p>
            <p className="mt-0.5 text-xs text-slate-400">
              Enter any real scam message in Twi or English to demonstrate live zero-shot classification.
            </p>
          </div>
        </div>
        <span className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
          <CheckCircle2 size={14} />
          Live WebSocket Telemetry Synced
        </span>
      </Card>
    </AppShell>
  );
}
