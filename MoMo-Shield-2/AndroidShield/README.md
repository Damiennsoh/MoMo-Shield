# MoMo Shield — Companion Android App

On-device fraud shield for consenting users. This is **Tier 2** of the
hybrid architecture: the same rules engine that runs inside the MNO
middleware, packaged as a lightweight native APK that lives on the
user's own phone.

## Privacy architecture (the Act 843 answer)

| Data | Where it is processed | Leaves device? |
|---|---|---|
| SMS text | `RulesEngine` on-device (regex/keywords) | **Never** |
| Sender number | Local blacklist check (SharedPreferences) | Never (unless user opts in) |
| Warnings | Overlay + Twi/English audio on-device | Never |
| Blacklist | Device-local; optional consented sync to threat ledger | Opt-in only |

No SMS body, call content, or personal data is transmitted to any server.
The backend (`Backend-2`) remains available for consenting users who want
cloud corroboration (Glance, threat ledger) — that path is not wired yet
and must be gated behind an explicit in-app consent toggle.

## How detection works

1. `ShieldNotificationListener` (Android `NotificationListenerService`)
   reads incoming-message **notifications** — no `READ_SMS` permission
   required, which keeps the app installable outside the Play default-SMS
   restriction.
2. Sender + body → `RulesEngine.scoreSms()` — a Kotlin port of
   `Backend-2/app/engine/rules.py` (same weights: credential solicitation
   +45, phishing link +45, suspicious host +45, failed-txn lure +35,
   financial link context +25, advance-fee +40, approve-to-receive +40,
   blacklist +60 …).
3. Score ≥ 40 → `WarningOverlay` red banner over any app + warning sound
   + English TTS. HIGH tier (≥75) adds a **Block number** action that
   writes to the on-device blacklist.

## Build

Requires Android SDK (API 35) + JDK 17. Open this folder in Android
Studio, or:

```
gradle wrapper        # once, to generate the wrapper jar
./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

## First-run setup (the three gotchas, handled)

1. **Overlay permission** — `MainActivity` opens
   `Settings.ACTION_MANAGE_OVERLAY_PERMISSION`; user must toggle "Allow
   display over other apps". Without it no banner can draw.
2. **POST_NOTIFICATIONS** — requested at runtime on API 33+.
3. **Notification access** — user must enable "MoMo Shield" under
   Settings → Special app access → Device & app notifications →
   Notification access. Until then the listener is dormant.

## Audio

- `res/raw/momo_warning.wav` — placeholder alarm (currently the backend's
  `momo-warning.wav`). **Replace with a recorded Twi warning
  (`warning_twi.mp3`) for the demo** — Android has no Twi TTS voice.
- English guidance uses `TextToSpeech` (en-US).

## Known limitations (be honest about these)

- **SMS blocking is not possible** for non-default-SMS apps on Android —
  we warn, we cannot stop delivery. Blocking requires being the default
  SMS handler (Play-restricted).
- **iOS**: NotificationListener equivalent does not exist — this tier is
  Android-only.
- **Feature phones**: unreachable — covered only by the MNO middleware
  tier (metadata-only, no content access).
- **Call content**: not accessed at all. CallScreening/spam-label is a
  possible future addition via `CallScreeningService`.
- Some OEMs (Xiaomi/Oppo/Vivo) kill background services aggressively —
  whitelist the app from battery optimization for the demo phone.
