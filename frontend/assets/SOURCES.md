# Third-party demo audio sources

The application bundles two short audio cues downloaded on 18 November 2026. Both source pages identify the recordings as CC0 1.0 Universal / public-domain-equivalent and permit redistribution, modification, and commercial use without attribution. Attribution is not required, but is retained here for provenance.

- `ring.mp3` — **Phone Ring #5**, two cordless-landline ringtones, 8 seconds on the source page, mono, recorded by Joseph Sardin. Source: [sound details and license](https://bigsoundbank.com/phone-ring-5-s0375.html). Direct asset: [MP3 download](https://bigsoundbank.com/UPLOAD/mp3/0375.mp3?v=m).
- `sms.mp3` — **Message #1**, a mobile-message notification sound, 7 seconds on the source page, mono, recorded by Joseph Sardin. The source describes it as the same note used for an iPhone message alert. Source: [sound details and license](https://bigsoundbank.com/message-1-s1111.html). Direct asset: [MP3 download](https://bigsoundbank.com/UPLOAD/mp3/1111.mp3?v=m).
- License terms: [BigSoundBank license page](https://bigsoundbank.com/license.html), which states CC0 1.0 Universal, allows sharing/adaptation/commercial use without restrictions, and says attribution is optional.

The handset limits message playback to 1.8 seconds and incoming-call playback to 6 seconds. These cues are replaceable by putting a properly licensed `sms.mp3` or `ring.mp3` in this directory. The downloaded clips are convenience defaults, not a claim that they are Ghanaian carrier-specific tones.

The bilingual intervention warning is not sourced from this library. Teams should provide a consented, reviewed Twi/English recording as `frontend/assets/warning_twi.mp3` or `warning_twi.wav`; otherwise the handset falls back to English recording or browser TTS. In the optional SIP path, Linphone's fixed local call is terminated when the same intervention event is emitted, while the handset/dashboard provides the synchronized warning. The Asterisk dialplan intentionally does not play a long recording on answer; see `demo/asterisk/sounds/README.md`.
