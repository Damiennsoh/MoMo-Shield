# Local demo telephony references

These sources informed the opt-in, local-only SIP bridge and client recommendation:

- Asterisk ARI Channels API: `POST /channels` originates a channel to a required endpoint, with optional context/extension/priority and timeout parameters. https://docs.asterisk.org/Latest_API/API_Documentation/Asterisk_REST_Interface/Channels_REST_API/
- Asterisk PJSIP overview: PJSIP configuration belongs in `pjsip.conf`; endpoint, auth, AOR, transport, and dialplan configuration are required for a softphone. https://docs.asterisk.org/Configuration/Channel-Drivers/SIP/Configuring-res_pjsip/
- Asterisk `TryExec()` and `Playback()` behavior used for the prerecorded-warning/beep fallback: https://docs.asterisk.org/Latest_API/API_Documentation/Dialplan_Applications/TryExec/ and https://docs.asterisk.org/Latest_API/API_Documentation/Dialplan_Applications/Playback/
- Asterisk Docker image source/tag documentation. This is a community-maintained image, pinned in the demo Dockerfile to `22.10.1_debian-trixie`; it is not an official Asterisk project image. https://github.com/andrius/asterisk
- Linphone states the app/service can be used for free and supports SIP softphone use; its download page lists Android, iOS, Windows, macOS, and Linux. https://www.linphone.org/en/ and https://www.linphone.org/en/download/

The software is configured for one registered PJSIP extension and a dedicated warning-playback context. No trunk, PSTN route, recipient-number input, or cellular SMS gateway is part of this demo.
