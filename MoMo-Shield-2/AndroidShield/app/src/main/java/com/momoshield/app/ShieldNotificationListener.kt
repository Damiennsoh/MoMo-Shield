package com.momoshield.app

import android.app.Notification
import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import java.util.concurrent.ConcurrentHashMap

/** Scores likely messaging-app notification text locally; message contents never leave this device. */
class ShieldNotificationListener : NotificationListenerService() {
    private val main = Handler(Looper.getMainLooper())
    private val recent = ConcurrentHashMap<Long, Long>()

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val pkg = sbn.packageName ?: return
        if (!looksLikeMessageApp(pkg)) return
        val extras = sbn.notification?.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString().orEmpty()
        val body = if (bigText.isNotBlank()) bigText else text
        if (body.isBlank()) return

        val sender = title.ifBlank { "unknown" }
        val verdict = RulesEngine.scoreSms(body, ScamBlacklist.contains(this, sender))
        if (verdict.score < 40) return

        val key = (sender + "|" + body.hashCode()).hashCode().toLong()
        val now = System.currentTimeMillis()
        val lastShown = recent[key]
        if (lastShown != null && now - lastShown < 90_000L) return
        recent[key] = now
        if (recent.size > 200) recent.keys.removeAll { now - (recent[it] ?: 0L) > 300_000L }

        val headline = if (verdict.tier == "HIGH") {
            "High-risk message signal. Do not click, share a PIN/OTP, or send money until verified."
        } else {
            "Suspicious message signal. Verify the sender through an official number before acting."
        }
        val detail = verdict.reasons.take(3).joinToString("\n• ", "• ")
        main.post {
            WarningOverlay.show(
                ctx = this,
                tier = verdict.tier,
                headline = headline,
                detail = detail,
                sender = sender,
                onFlag = { ScamBlacklist.add(this, sender, "Reported from suspicious message", "message") },
            )
        }
        WarningAudio.play(this)

        // Optional backend corroboration (consent-gated, PII-redacted).
        // Local verdict already shown; a backend "reject" escalates to HIGH.
        if (BackendSync.enabled(this)) {
            Thread {
                val decision = BackendSync.score(
                    this, sender, body,
                    verdict.score, verdict.tier, verdict.reasons,
                )
                if (decision == "reject" && verdict.tier != "HIGH") {
                    main.post {
                        WarningOverlay.show(
                            ctx = this,
                            tier = "HIGH",
                            headline = "Backend confirmed high risk — do NOT click, share PIN/OTP, or send money.",
                            detail = "Local warning + MoMo Shield backend corroboration.\n$detail",
                            sender = sender,
                            onFlag = { ScamBlacklist.add(this, sender, "Backend-confirmed fraud", "message") },
                        )
                    }
                }
            }.start()
        }
    }

    private fun looksLikeMessageApp(pkg: String): Boolean {
        val name = pkg.lowercase()
        return name.contains("messag") || name.contains("sms") || name.endsWith(".mms")
    }
}
