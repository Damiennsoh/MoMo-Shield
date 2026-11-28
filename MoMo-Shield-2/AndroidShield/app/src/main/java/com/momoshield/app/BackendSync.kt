package com.momoshield.app

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Optional, consent-gated backend corroboration.
 *
 * Privacy contract (Act 843):
 * - OFF by default; the user must flip the toggle in Settings.
 * - SMS text is PII-redacted on-device BEFORE it leaves the phone
 *   (phone numbers, GH₵ amounts, Ghana Card numbers, long digit runs,
 *   emails are masked — scam keywords survive).
 * - The sender number is sent as a salted SHA-256 hash, never raw.
 * - Only fires on messages that already scored MEDIUM+ locally, so benign
 *   traffic generates zero backend calls.
 * - Failure is silent: the on-device verdict stands alone.
 */
object BackendSync {
    const val PREFS = "momo_shield_settings"
    const val ENABLED = "backend_sync_enabled"
    const val URL = "backend_url"
    const val DEFAULT_URL = "http://10.0.2.2:8001" // emulator → host loopback

    fun enabled(ctx: Context): Boolean =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(ENABLED, false)

    fun baseUrl(ctx: Context): String =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(URL, DEFAULT_URL)?.trim()?.trimEnd('/') ?: DEFAULT_URL

    /** Mask PII while keeping scam-signal keywords intact. */
    fun redact(text: String): String {
        var t = text
        t = EMAIL_REGEX.replace(t, "[email]")
        t = GHANA_CARD_REGEX.replace(t, "[ghana-card]")
        t = MONEY_REGEX.replace(t, "[amount]")
        t = PHONE_REGEX.replace(t, "[number]")
        t = LONG_DIGITS_REGEX.replace(t, "[number]")
        return t
    }

    /** Stable per-device hash of the sender — correlatable, not reversible. */
    fun hashSender(sender: String): String {
        val d = sender.filter { it.isDigit() }.ifEmpty { sender }
        val md = MessageDigest.getInstance("SHA-256")
        return md.digest("momo-shield|$d".toByteArray())
            .joinToString("") { "%02x".format(it) }.take(24)
    }

    /**
     * POST a redacted sms.deliver event to the backend plug-in endpoint.
     * Returns the backend decision ("reject"/"warn"/"allow") or null on any
     * failure/timeout. Runs on the caller's thread — call off the main thread.
     */
    fun score(
        ctx: Context,
        sender: String,
        body: String,
        ondeviceScore: Int,
        ondeviceTier: String,
        reasons: List<String>,
    ): String? {
        if (!enabled(ctx)) return null
        return try {
            val payload = JSONObject().apply {
                put("point", "sms.deliver")
                put("institution", "ondevice")
                put("data", JSONObject().apply {
                    put("to", hashSender(sender))
                    put("from", "ondevice-app")
                    put("text", redact(body).take(1500))
                    put("ondevice_score", ondeviceScore)
                    put("ondevice_tier", ondeviceTier)
                    put("ondevice_reasons", org.json.JSONArray(reasons.take(5)))
                })
            }
            val conn = URL("${baseUrl(ctx)}/api/v1/plugin").openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 1200
            conn.readTimeout = 1200
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.outputStream.use { it.write(payload.toString().toByteArray()) }
            if (conn.responseCode !in 200..299) return null
            val resp = conn.inputStream.bufferedReader().readText()
            JSONObject(resp).optString("decision", "").ifBlank { null }
        } catch (_: Exception) {
            null
        }
    }

    private val EMAIL_REGEX = Regex("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
    private val GHANA_CARD_REGEX = Regex("\\bGHA-?\\d{3}-?\\d{6}-?\\d\\b", RegexOption.IGNORE_CASE)
    private val MONEY_REGEX = Regex("(?:GH[Cc₵S]?\\s*|GHS\\s*|cedis?\\s*)\\d[\\d,]*(?:\\.\\d+)?|\\d[\\d,]*(?:\\.\\d+)?\\s*(?:GH[CS₵]|cedis?)\\b", RegexOption.IGNORE_CASE)
    private val PHONE_REGEX = Regex("(?:\\+?233|0)\\d{2}[- ]?\\d{3}[- ]?\\d{4}|\\+?\\d[\\d -]{8,14}")
    private val LONG_DIGITS_REGEX = Regex("\\b\\d{9,}\\b")
}
