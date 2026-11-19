"""Offline-friendly audio helpers for the synthetic scenario replay."""

import base64
import html
import io
import json
import math
import struct
import wave
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"


def _tone_bytes(segments, rate=22050) -> bytes:
    """Build a small mono PCM WAV from (frequency_hz, seconds) segments."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for frequency, duration in segments:
            for index in range(int(rate * duration)):
                sample = int(9000 * math.sin(2 * math.pi * frequency * index / rate)) if frequency else 0
                frames.extend(struct.pack("<h", sample))
        wav.writeframes(bytes(frames))
    return buf.getvalue()


def alert_tone_bytes(variant: int = 0) -> bytes:
    """Generate a short alert sound without network access or external packages."""
    base = 820 + (int(variant) % 7) * 12
    return _tone_bytes([(base, 0.22), (0, 0.06), (base, 0.22), (0, 0.06), (620, 0.4)])


def _audio_bytes(sound_file_name: str):
    # Restrict paths to known filenames in the bundled asset directory.
    name = Path(sound_file_name).name
    path = _ASSET_DIR / name
    if not path.is_file():
        return None, None
    suffix = path.suffix.lower()
    mime = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}.get(suffix)
    if not mime:
        return None, None
    return path.read_bytes(), mime


def play_sfx(sound_file_name: str, delay_ms: int = 0, max_duration_seconds: float = 0) -> bool:
    """Autoplay a bundled sound in an isolated browser frame; missing files are harmless."""
    requested = Path(sound_file_name)
    candidates = [requested.stem + ".mp3", requested.name]
    candidates.extend(requested.stem + suffix for suffix in (".wav", ".ogg"))
    payload, mime = None, None
    for candidate in dict.fromkeys(candidates):
        payload, mime = _audio_bytes(candidate)
        if payload:
            break
    if not payload:
        return False
    data = base64.b64encode(payload).decode("ascii")
    max_ms = max(0, int(float(max_duration_seconds) * 1000))
    components.html(
        f'<audio id="momo-sfx" controls style="width:100%;height:32px" '
        f'src="data:{html.escape(mime)};base64,{data}"></audio>'
        f'<script>setTimeout(function(){{var a=document.getElementById("momo-sfx");if(!a)return;'
        f'var p=a.play();if({max_ms}>0)setTimeout(function(){{if(!a.paused){{a.pause();a.currentTime=0;}}}},{max_ms});'
        f'if(p)p.catch(function(){{}});}},'
        f'{max(0, int(delay_ms))});</script>',
        height=42,
        scrolling=False,
    )
    return True


def speak_english_warning(text: str, delay_ms: int = 1100, max_duration_seconds: float = 10) -> bool:
    """Use browser-native English TTS; no text is evaluated as JavaScript."""
    if not text or not text.strip():
        return False
    safe_text = json.dumps(text, ensure_ascii=True)
    safe_delay = max(0, int(delay_ms))
    max_ms = max(1000, int(float(max_duration_seconds) * 1000))
    components.html(
        "<script>(function(){try{window.speechSynthesis.cancel();"
        f"var u=new SpeechSynthesisUtterance({safe_text});u.lang='en-US';"
        f"setTimeout(function(){{window.speechSynthesis.speak(u);setTimeout(function(){{window.speechSynthesis.cancel();}},{max_ms});}},{safe_delay});"
        "}catch(e){console.warn('Speech unavailable',e);}})();</script>",
        height=0,
        scrolling=False,
    )
    return True


def play_warning_audio(twi_text: str = "", english_text: str = "") -> str:
    """Prefer an optional human-recorded Twi/English clip; never fake a Twi voice."""
    if play_sfx("warning_twi.wav", delay_ms=1100, max_duration_seconds=10) or play_sfx("warning_twi.mp3", delay_ms=1100, max_duration_seconds=10):
        return "recorded"
    if play_sfx("warning_en.wav", delay_ms=1100, max_duration_seconds=10) or play_sfx("warning_en.mp3", delay_ms=1100, max_duration_seconds=10):
        return "recorded_english"
    speak_english_warning(english_text)
    return "english_tts" if english_text else "none"
