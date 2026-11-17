# Optional human-recorded call warning

Place the team's own consented Twi/English recording at this path as `momo-warning.wav`. Asterisk will play it after the demo softphone answers. The preferred format is mono, 8 kHz, signed 16-bit PCM WAV; for example, convert a team recording with:

```bash
ffmpeg -i your-recording.mp3 -ar 8000 -ac 1 -c:a pcm_s16le momo-warning.wav
```

Keep the recording synthetic and demo-only. If the clip is absent or cannot be played, the dialplan plays a short beep instead. No generated or purportedly human/localized warning is bundled.
