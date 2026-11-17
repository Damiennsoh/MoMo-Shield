# Demo audio assets

The app bundles local `sms.wav`, `ring.wav`, and `alert.wav` effects. To replace them with the GuideTwo human recordings, place `sms.mp3`, `ring.mp3`, and/or `alert.mp3` here; each MP3 automatically takes precedence over its bundled WAV cue. To add recorded warnings, place files here:

- `warning_twi.mp3` or `warning_twi.wav`: preferred consented combined Twi/English FraudOps warning.
- `warning_en.mp3` or `warning_en.wav`: optional English-only recorded warning used if the combined recording is absent.

The app automatically picks up these names on the next scenario run. If no recorded warning is present, it speaks the backend's English warning using browser-native TTS. No file is included or represented as a native Twi recording until the team records one.
