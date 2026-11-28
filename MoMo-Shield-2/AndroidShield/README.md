# MoMo Shield — Android companion pilot

This is an Android-first companion for smartphone users, distinct from the main MoMo Shield MNO middleware and FraudOps dashboard. It gives explainable, advisory warnings from message notifications and optional call screening. It is not an operator interceptor, does not protect feature phones, and does not prove that a sender or caller is fraudulent.

## What this build does

- Reads notification text only after the user enables Android Notification Access. It filters notifications to package names that look like messaging apps and scores message text with a local Kotlin rule subset. Notification previews can be incomplete or hidden by an app/device.
- Shows a short warning overlay for medium/high message signals. The overlay includes English and a clearly marked draft Twi safety line, and offers **Report locally**. The supplied recording is bundled as an optional spoken English warning; the home screen lets the user turn it off and use the alert tone instead.
- Keeps reports in an app-private SQLite database on this phone. A report records a normalized number, a short user-facing reason, source (for example message, call, or manual), and timestamp. It does not store message text. Reports affect local warnings only, stop affecting screening after 180 days, and are purged when the database is next accessed. The home screen provides **Undo** for the latest report per number. A report is a user allegation, not a verified fraud finding.
- Offers optional Android call screening on Android 10 or later. The user must select MoMo Shield in Android's call-screening role prompt. The service checks only the local report database and the system's caller-number verification status. It responds promptly and always allows calls through in this pilot; it does not silence, reject, or block them. The system generally sends screening callbacks for numbers not in the user's contacts. Android documents `CallScreeningService` as the user-selected call-ID/screening approach, without requiring `READ_CALL_LOG` for this function.[1]
- Migrates previously flagged numbers from the earlier SharedPreferences list into the local SQLite database the first time the database opens.

## Languages and warning audio

Two recorded voice notes (`res/raw/warning_1.mp3`, `warning_2.mp3` — one Twi, one English) play in sequence for every warning when voice is enabled. The supplied English clip (`momo_warning_voice.mp3`) and alert tone (`momo_warning.wav`) are fallbacks if the recordings cannot play.

Warnings also display the Twi draft: **“Mfa wo PIN anaa OTP mma obiara. Frɛ MTN 100 na bisa.”** It is displayed as text only. This wording has not been reviewed by a fluent Twi speaker, and there is no Twi speech recording or Twi TTS claim in this build. Have a Ghanaian Twi speaker review it before a public pitch or deployment.

## Privacy, permissions and external reputation

The app has no Internet permission, SMS permissions, call-log permission, microphone permission, or default-SMS/default-dialer role. It does not read the SMS inbox, send SMS, record call audio, upload notification text, or share a user's reports. Notification Access is broad at the Android system level; the app filters incoming notifications locally to likely messaging packages, but the filter can miss OEM variants. The optional overlay permission is separately granted in Android Settings.

**Backend corroboration is optional and off by default.** When the user enables it, only locally-flagged messages are sent to their own MoMo Shield backend — SMS text is PII-redacted on-device (numbers, amounts, Ghana Card IDs masked) and the sender is a salted hash. A backend `reject` escalates the local warning to HIGH. With the toggle off, the app declares INTERNET but makes zero network calls.

**Glance lookups and reports are not enabled in this APK.** No Glance credential, institutional endpoint, or authenticated mobile-to-backend proxy was configured in the build environment. A key must never be embedded in a distributable APK. The existing backend Glance client supports fictional `SYN-####` subjects on its developer sandbox; real phone numbers require an authorized institutional API endpoint/key. Before enabling lookups, add an authenticated backend proxy, keep the Glance key server-side, disclose the exact number being shared, ask for explicit per-lookup/report consent, and return only the limited reputation result needed by the app. Until that service is configured, the app makes no network requests and its UI says so.

## How much of backend rules, RAG and ML belongs on the phone?

The current local Kotlin detector is a small, text-only, explainable subset inspired by the backend rules. Its score is an uncalibrated warning signal, not a probability. It cannot reproduce rules that depend on payment history, fund-flow relationships, SIM-swap metadata, velocity, or the operator's view of a transaction. It is not exact backend parity.

The repository's current backend artifacts are not ready to drop into an Android app: `fraud_pipeline.joblib` is about 3.15 MB and expects Python/scikit-learn/joblib plus pandas/NumPy and feature preparation; the scorer's own documentation notes that several training-time features are unavailable in live plug-in payloads and are zero-filled. The fraud knowledge-base JSON is about 719 KB, while a cached embedding file is about 2.42 MB. The semantic retrieval path uses a Gemini embedding service; those cached vectors do not provide the text-embedding model itself. Bundling those files would not make the Python ML or Gemini RAG pipeline run natively.

A credible lightweight on-device next step is to keep deterministic text rules and a compact, curated local case phrase index first. If ML is justified by labeled Ghanaian message data, retrain on features actually available on the handset, measure precision/recall and false alerts by language and scam type, convert a small model to TensorFlow Lite or ONNX, quantize it, and compare its size/latency/battery impact with the rules-only baseline. Keep fund-flow and operator-only signals on the server. Do not advertise RAG or the Python model as running on-device in this build.

## Build and validate

Requirements: JDK 17 and Android SDK Platform 35. From this directory:

```sh
./gradlew testDebugUnitTest assembleDebug
```

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. It uses package `com.momoshield.app`, version `1.2`, `minSdk 26`, and `targetSdk 35`. It is debug-signed for testing, not signed for production release.

First-run setup:

1. Install and open MoMo Shield.
2. Choose **Allow warning overlays** and grant the special access in Android Settings.
3. Choose **Enable message notification access** and enable MoMo Shield in Notification Access settings.
4. For optional caller alerts on Android 10+, choose **Set up optional call screening** and accept the Android role prompt.
5. Review the report/privacy section and choose whether the supplied spoken English clip should play.

The automated regression tests cover a credential-harvesting message, defensive anti-sharing wording, Ghana number normalization, and caller risk tiers. The APK compiled successfully in the sandbox. It was not installed or exercised on a physical Android device or emulator, so OEM-specific call-screening, audio focus, and overlay behavior still need device validation before a public demo or release.

## References

[1]: https://developer.android.com/develop/connectivity/telecom/dialer-app/screen-calls "Screen calls with CallScreeningService"
[2]: https://developer.android.com/reference/android/telecom/CallScreeningService "CallScreeningService API reference"
