package com.momoshield.app

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/**
 * Red warning banner drawn over whatever app is foreground — including the
 * MoMo USSD menu. Shown for MEDIUM+ verdicts; HIGH adds the block action.
 */
object WarningOverlay {

    private const val AUTO_DISMISS_MS = 12_000L

    @Volatile
    private var activeView: View? = null

    fun canDraw(ctx: Context): Boolean =
        Settings.canDrawOverlays(ctx)

    /** Must be called on the main thread. */
    fun show(
        ctx: Context,
        tier: String,
        headline: String,
        detail: String,
        sender: String,
        onBlock: (() -> Unit)? = null,
    ) {
        val main = Handler(Looper.getMainLooper())
        main.post {
            if (!canDraw(ctx)) return@post
            dismiss()

            val pad = dp(ctx, 14)
            val col = LinearLayout(ctx).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(pad, pad, pad, pad)
                setBackgroundColor(if (tier == "HIGH") Color.parseColor("#B71C1C") else Color.parseColor("#E65100"))
            }

            val title = TextView(ctx).apply {
                text = if (tier == "HIGH") "🚨 FRAUD ALERT — DO NOT PROCEED" else "⚠️ SUSPICIOUS MESSAGE"
                setTextColor(Color.WHITE)
                setTypeface(null, Typeface.BOLD)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
            }
            val twi = TextView(ctx).apply {
                text = "MoMo Shield: Hoo:NSɔ! MFA wo nsa, mfiri wo PIN, OTP, ana sika.",
                setTextColor(Color.parseColor("#FFE0B2"))
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
                setPadding(0, dp(ctx, 4), 0, dp(ctx, 4))
            }
            val body = TextView(ctx).apply {
                text = "$headline\n$detail"
                setTextColor(Color.WHITE)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
                maxLines = 4
            }
            col.addView(title); col.addView(twi); col.addView(body)

            val row = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
            val btnDismiss = Button(ctx).apply {
                text = "Dismiss"
                setOnClickListener { dismiss() }
            }
            row.addView(btnDismiss)
            if (onBlock != null && sender.isNotBlank()) {
                val btnBlock = Button(ctx).apply {
                    text = "Block number"
                    setOnClickListener {
                        onBlock()
                        Toast.makeText(ctx, "Number blocked", Toast.LENGTH_SHORT).show()
                        dismiss()
                    }
                }
                row.addView(btnBlock)
            }
            col.addView(row)

            val lp = WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
                PixelFormat.TRANSLUCENT
            ).apply {
                gravity = Gravity.TOP
                y = 0
            }

            val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as WindowManager
            try {
                wm.addView(col, lp)
                activeView = col
            } catch (e: Exception) {
                // Overlay permission revoked between check and add — fail quiet.
                return@post
            }

            main.postDelayed({ dismiss() }, AUTO_DISMISS_MS)
        }
    }

    fun dismiss() {
        val v = activeView ?: return
        activeView = null
        try {
            val wm = v.context.getSystemService(Context.WINDOW_SERVICE) as? WindowManager
            wm?.removeView(v)
        } catch (_: Exception) { }
    }

    private fun dp(ctx: Context, v: Int): Int =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), ctx.resources.displayMetrics).toInt()
}
