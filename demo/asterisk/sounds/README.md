# Asterisk demo sound directory

The local SIP call intentionally stays silent after Linphone answers. FraudOps terminates the fixed demo call when it emits the intervention warning, so a long PBX recording cannot keep the call alive past the simulated hold. The Asterisk dialplan has a 12-second failsafe if the dashboard disconnects before sending that intervention.

For the audible Twi/English warning, use `frontend/assets/warning_twi.wav` or `.mp3`; the token-authenticated handset audio path plays it when the intervention event appears, followed by English-only recording or English TTS fallback if needed. This directory is retained as a safe place for future PBX-specific sounds, but `momo-warning.wav` is not currently played by the synchronized call path.
