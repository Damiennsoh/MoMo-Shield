'use client';

import { useStore } from './useStore';

let currentAudio: HTMLAudioElement | null = null;

export function isInternalSoundEnabled(): boolean {
  if (typeof window === 'undefined') return true;
  return useStore.getState().soundEnabled;
}

export function stopAllSounds(): void {
  if (typeof window === 'undefined') return;
  if (currentAudio) {
    try {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    } catch {
      // ignore
    }
    currentAudio = null;
  }
  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      // ignore
    }
  }
}

export async function playAudioFile(src: string, volume: number = 0.7): Promise<boolean> {
  if (!isInternalSoundEnabled()) {
    return false;
  }
  if (typeof window === 'undefined') return false;

  stopAllSounds();

  try {
    const audio = new Audio(src);
    audio.volume = Math.max(0, Math.min(1, volume));
    currentAudio = audio;
    await audio.play();
    return true;
  } catch (err) {
    // Autoplay policy or missing codec
    return false;
  }
}

export async function playSmsSound(): Promise<boolean> {
  const played = await playAudioFile('/audio/sms.mp3', 0.65);
  if (!played) {
    return playAudioFile('/audio/sms.wav', 0.65);
  }
  return played;
}

export async function playRingSound(): Promise<boolean> {
  const played = await playAudioFile('/audio/ring.mp3', 0.65);
  if (!played) {
    return playAudioFile('/audio/ring.wav', 0.65);
  }
  return played;
}

export async function playAlertTone(): Promise<boolean> {
  const played = await playAudioFile('/audio/alert.wav', 0.8);
  if (!played && isInternalSoundEnabled() && typeof window !== 'undefined' && 'AudioContext' in window) {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.35);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
      setTimeout(() => { void ctx.close(); }, 500);
      return true;
    } catch {
      // ignore
    }
  }
  return played;
}

export interface WarningSpeechOptions {
  englishText?: string;
  twiText?: string;
  onEnded?: () => void;
}

export async function playEnglishTwiWarning(options: WarningSpeechOptions = {}): Promise<void> {
  if (!isInternalSoundEnabled()) {
    return;
  }
  stopAllSounds();

  // 1. Play initial alert tone
  await playAlertTone();

  if (typeof window === 'undefined') return;

  const twiPrompt = options.twiText || "Kɔkɔbɔ! Yɛn hu sɛ obi rebɔ mmɔden sɛ ɔbɛsisi wo, Mepa wo kyɛw, mfa wo PIN mma obiara!";
  const englishPrompt = options.englishText || "Warning: Transaction hold. Suspicious activity detected. Never share your MoMo PIN with anyone. Call 100 for support.";

  const hasSpeech = 'speechSynthesis' in window;

  // Custom recorded warnings take precedence: drop warning-twi.mp3 /
  // warning-en.mp3 (or .wav) into public/audio/ to replace TTS per language.
  const playCustomOrTts = async (fileBase: string, text: string, lang: string, rate: number): Promise<void> => {
    for (const ext of ['.mp3', '.wav']) {
      const played = await playAudioFile(`/audio/${fileBase}${ext}`, 0.9);
      if (played) return;
    }
    if (hasSpeech) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = rate;
      utterance.pitch = 1.0;
      if (fileBase === 'warning-en' && options.onEnded) {
        utterance.onend = options.onEnded;
      }
      window.speechSynthesis.speak(utterance);
    }
  };

  try {
    await playCustomOrTts('warning-twi', twiPrompt, 'en-GH', 0.95);
    await playCustomOrTts('warning-en', englishPrompt, 'en-US', 1.0);
  } catch (err) {
    console.warn("Warning playback unavailable:", err);
  }
}
