package com.momoshield.app

import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/** Short, dismissible warning shown only after the user enabled overlay access. */
object WarningOverlay {
    private const val AUTO_DISMISS_MS = 15_000L
    @Volatile private var activeView: android.view.View? = null
    private val main = Handler(Looper.getMainLooper())
    private var dismissRunnable: Runnable? = null

    fun canDraw(ctx: Context): Boolean = Settings.canDrawOverlays(ctx)

    fun show(
        ctx: Context,
        tier: String,
        headline: String,
        detail: String,
        sender: String,
        onFlag: (() -> Unit)? = null,
    ) {
        main.post {
            if (!canDraw(ctx)) return@post
            dismiss()
            val pad = dp(ctx, 16)
            val high = tier == "HIGH"
            val panel = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(pad, pad, pad, pad)
                setBackgroundColor(if (high) Color.rgb(137, 27, 36) else Color.rgb(169, 83, 0))
                elevation = dp(ctx, 8).toFloat()
            }
            val title = TextView(ctx).apply {
                text = if (high) "HIGH-RISK SIGNAL · PAUSE" else "SUSPICIOUS SIGNAL · VERIFY"
                setTextColor(Color.WHITE)
                setTypeface(null, Typeface.BOLD)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
                contentDescription = if (high) "High risk warning" else "Suspicious activity warning"
            }
            val body = TextView(ctx).apply {
                text = "$headline\n\n$detail"
                setTextColor(Color.WHITE)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
                maxLines = 7
                setPadding(0, dp(ctx, 8), 0, dp(ctx, 4))
            }
            val twi = TextView(ctx).apply {
                text = "Twi draft: Mfa wo PIN anaa OTP mma obiara. Frɛ MTN 100 na bisa."
                setTextColor(Color.WHITE)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
                setPadding(0, dp(ctx, 5), 0, dp(ctx, 8))
            }
            panel.addView(title)
            panel.addView(body)
            panel.addView(twi)

            val actions = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
            if (onFlag != null && sender.count(Char::isDigit) >= 7) {
                actions.addView(Button(ctx).apply {
                    text = "Report locally"
                    contentDescription = "Save this number as a local suspect report"
                    setOnClickListener {
                        onFlag()
                        Toast.makeText(ctx, "Saved only on this phone. Undo it in MoMo Shield.", Toast.LENGTH_LONG).show()
                        dismiss()
                    }
                }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            }
            actions.addView(Button(ctx).apply {
                text = "Dismiss"
                setOnClickListener { dismiss() }
            }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            panel.addView(actions)

            val layout = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
                PixelFormat.TRANSLUCENT,
            ).apply { gravity = Gravity.TOP; y = dp(ctx, 12) }
            val manager = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
            try {
                manager.addView(panel, layout)
                activeView = panel
            } catch (_: Exception) {
                return@post
            }
            val timeout = Runnable { if (activeView === panel) dismiss() }
            dismissRunnable = timeout
            main.postDelayed(timeout, AUTO_DISMISS_MS)
        }
    }

    fun dismiss() {
        dismissRunnable?.let(main::removeCallbacks)
        dismissRunnable = null
        val view = activeView ?: return
        activeView = null
        try {
            (view.context.getSystemService(Context.WINDOW_SERVICE) as? WindowManager)?.removeView(view)
        } catch (_: Exception) { }
    }

    private fun dp(ctx: Context, value: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value.toFloat(), ctx.resources.displayMetrics).toInt()
}
