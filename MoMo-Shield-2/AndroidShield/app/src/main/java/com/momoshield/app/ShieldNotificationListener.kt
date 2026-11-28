package com.momoshield.app

import android.app.Notification
import android.content.Context
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.speech.tts.TextToSpeech
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

/**
 * Reads incoming-message notifications (the NotificationListener path —
 * no READ_SMS permission needed) and scores them with the on-device
 * RulesEngine. SMS text never leaves the device.
 */
class ShieldNotificationListener : NotificationListenerService() {

    private var tts: TextToSpeech? = null
    private val main = Handler(Looper.getMainLooper())

    // sender+textHash -> lastShownAt, 90s dedupe so one SMS doesn't re-warn
    private val recent = ConcurrentHashMap<Long, Long>()

    override fun onListenerConnected() {
        super.onListenerConnected()
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) tts?.language = Locale.US
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val pkg = sbn.packageName ?: return
        if (!looksLikeMessageApp(pkg)) return

        val n = sbn.notification ?: return
        val extras = n.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString().orEmpty()
        val body = if (bigText.isNotBlank()) bigText else text
        if (body.isBlank()) return

        // Sender = notification title for SMS apps (number or alphanumeric ID).
        val sender = title.ifBlank { "unknown" }
        val knownScam = ScamBlacklist.contains(this, sender)
        val verdict = RulesEngine.scoreSms(body, knownScam)
        if (verdict.score < 40) return

        // Dedupe
        val key = (sender + "|" + body.hashCode().toString()).hashCode().toLong()
        val now = System.currentTimeMillis()
        val last = recent[key]
        if (last != null && now - last < 90_000) return
        recent[key] = now
        if (recent.size > 200) recent.keys.removeAll { now - (recent[it] ?: 0) > 300_000 }

        val headline = when (verdict.tier) {
            "HIGH" -> "Fraud detected — do NOT click links, share PIN/OTP, or send money."
            else -> "Suspicious message — verify the sender before acting."
        }
        val detail = verdict.reasons.take(3).joinToString("\n• ", "• ")

        WarningOverlay.show(
            ctx = this,
            tier = verdict.tier,
            headline = headline,
            detail = detail,
            sender = sender,
            onBlock = { ScamBlacklist.add(this, sender) },
        )
        speakWarning(verdict.tier)
        playWarningSound()
    }

    private fun looksLikeMessageApp(pkg: String): Boolean {
        val p = pkg.lowercase()
        return p.contains("messag") || p.contains("sms") ||
            p.contains("telecel") || p.contains("vodafone") ||
            p.contains("airtel") || p.contains("tigo") ||
            p.contains("mtn")
    }

    private fun speakWarning(tier: String) {
        // English guidance via TTS. Twi is a bundled recording (no Twi TTS voice exists).
        val msg = if (tier == "HIGH")
            "MoMo Shield warning. This message is likely a scam. Never share your PIN or OTP. Do not send money."
        else
            "MoMo Shield warning. This message looks suspicious. Verify before you act."
        main.post { tts?.speak(msg, TextToSpeech.QUEUE_FLUSH, null, "momo-shield") }
    }

    private fun playWarningSound() {
        try {
            val mp = MediaPlayer.create(this, R.raw.momo_warning) ?: return
            mp.setOnCompletionListener { it.release() }
            mp.start()
        } catch (_: Exception) { }
    }

    override fun onListenerDisconnected() {
        tts?.shutdown()
        tts = null
        super.onListenerDisconnected()
    }
}
