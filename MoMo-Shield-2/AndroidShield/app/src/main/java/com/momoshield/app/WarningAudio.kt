package com.momoshield.app

import android.content.Context
import android.media.MediaPlayer

object WarningAudio {
    const val PREFS = "momo_shield_settings"
    const val VOICE_ENABLED = "voice_warning_enabled"

    /**
     * Plays the recorded Twi + English voice notes in sequence
     * (res/raw/warning_1.mp3, warning_2.mp3). Falls back to the supplied
     * English clip, then the alert tone, if recordings can't play.
     */
    fun play(context: Context) {
        val app = context.applicationContext
        val voiceEnabled = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(VOICE_ENABLED, true)
        if (!voiceEnabled) {
            playClip(app, R.raw.momo_warning)
            return
        }
        val clips = intArrayOf(R.raw.warning_1, R.raw.warning_2)
        var started = 0
        fun playAt(index: Int) {
            if (index >= clips.size) {
                if (started == 0) {
                    // No recordings — supplied English clip, then alarm.
                    playClip(app, R.raw.momo_warning_voice)
                    playClip(app, R.raw.momo_warning)
                }
                return
            }
            try {
                val player = MediaPlayer.create(app, clips[index])
                if (player == null) { playAt(index + 1); return }
                player.setOnCompletionListener {
                    it.release()
                    playAt(index + 1)
                }
                player.setOnErrorListener { mp, _, _ ->
                    mp.release()
                    playAt(index + 1)
                    true
                }
                player.start()
                started++
            } catch (_: Exception) {
                playAt(index + 1)
            }
        }
        playAt(0)
    }

    private fun playClip(context: Context, resId: Int) {
        try {
            val player = MediaPlayer.create(context, resId) ?: return
            player.setOnCompletionListener { it.release() }
            player.setOnErrorListener { mp, _, _ -> mp.release(); true }
            player.start()
        } catch (_: Exception) {
            // A media decoder/audio-focus failure must never affect handling.
        }
    }
}
