# Self-contained alert tone (no network, no TTS dependency).
#
# Generates a two-tone WAV in memory so the HIGH-RISK alert plays even on
# hackathon Wi-Fi. Browsers may require one user click before autoplay.

import io
import math
import struct
import wave


def alert_tone_bytes() -> bytes:
    buf = io.BytesIO()
    rate = 22050
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for freq, dur in [(880, 0.22), (0, 0.06), (880, 0.22), (0, 0.06), (660, 0.4)]:
            n = int(rate * dur)
            for i in range(n):
                amp = int(12000 * math.sin(2 * math.pi * freq * i / rate)) if freq else 0
                frames += struct.pack("<h", amp)
        w.writeframes(bytes(frames))
    return buf.getvalue()
