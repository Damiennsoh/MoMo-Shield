# Demo audio assets

The dashboard bundles local `sms.wav`, `ring.wav`, and `alert.wav` cues. For a custom sound, add `sms.mp3`, `ring.mp3`, or `alert.mp3`; MP3 takes precedence over the matching bundled WAV. An alert cue can be followed by a human-recorded intervention warning:

- `warning_twi.mp3` or `warning_twi.wav`: preferred, consented combined Twi/English recording.
- `warning_en.mp3` or `warning_en.wav`: optional recorded English fallback if the combined recording is absent.

On intervention, the dashboard plays the alert cue first, then the combined recording, English-only recording, or browser-native English TTS in that order. Dashboard warning playback is capped at 10 seconds. The handset simulator uses the same asset names via the token-authenticated backend audio route; its warning playback is capped at 8 seconds. MP3 and WAV files are picked up on the next scenario run without code changes. Use only synthetic demo content and recordings the team has permission and consent to use. No bundled file is represented as native Twi speech; provide the team's own recording for that.
