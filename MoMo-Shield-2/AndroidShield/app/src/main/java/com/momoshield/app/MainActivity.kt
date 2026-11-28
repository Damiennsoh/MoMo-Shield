package com.momoshield.app

import android.app.Activity
import android.app.role.RoleManager
import android.content.ComponentName
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** User-controlled activation and phone-local report management. */
class MainActivity : Activity() {
    private lateinit var txtStatus: TextView
    private lateinit var txtCallStatus: TextView
    private lateinit var reportList: LinearLayout
    private lateinit var txtNoReports: TextView
    private lateinit var inputNumber: EditText
    private val prefs by lazy {
        getSharedPreferences(WarningAudio.PREFS, MODE_PRIVATE)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        txtStatus = findViewById(R.id.txtStatus)
        txtCallStatus = findViewById(R.id.txtCallStatus)
        reportList = findViewById(R.id.reportList)
        txtNoReports = findViewById(R.id.txtNoReports)
        inputNumber = findViewById(R.id.inputNumber)

        findViewById<Button>(R.id.btnOverlay).setOnClickListener {
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        }
        findViewById<Button>(R.id.btnListener).setOnClickListener {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        }
        findViewById<Button>(R.id.btnCallScreening).setOnClickListener { requestCallScreeningRole() }
        findViewById<Button>(R.id.btnReport).setOnClickListener { reportTypedNumber() }

        findViewById<Switch>(R.id.switchVoice).apply {
            isChecked = prefs.getBoolean(WarningAudio.VOICE_ENABLED, true)
            setOnCheckedChangeListener { _, enabled ->
                prefs.edit().putBoolean(WarningAudio.VOICE_ENABLED, enabled).apply()
            }
        }

        findViewById<Switch>(R.id.switchBackend).apply {
            isChecked = prefs.getBoolean(BackendSync.ENABLED, false)
            setOnCheckedChangeListener { _, enabled ->
                prefs.edit().putBoolean(BackendSync.ENABLED, enabled).apply()
            }
        }
        findViewById<EditText>(R.id.inputBackendUrl).apply {
            setText(prefs.getString(BackendSync.URL, BackendSync.DEFAULT_URL))
            setOnFocusChangeListener { _, hasFocus ->
                if (!hasFocus) {
                    prefs.edit().putString(BackendSync.URL, text.toString().trim()).apply()
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
        refreshReports()
    }

    private fun requestCallScreeningRole() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            Toast.makeText(this, "Optional call screening needs Android 10 or later.", Toast.LENGTH_LONG).show()
            return
        }
        val roleManager = getSystemService(RoleManager::class.java)
        if (!roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
            Toast.makeText(this, "This device does not offer the call-screening role.", Toast.LENGTH_LONG).show()
            return
        }
        if (roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
            Toast.makeText(this, "MoMo Shield is already selected for call screening.", Toast.LENGTH_SHORT).show()
            return
        }
        startActivityForResult(roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), REQUEST_CALL_ROLE)
    }

    @Deprecated("Android role result is refreshed in onResume")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CALL_ROLE) refreshStatus()
    }

    private fun reportTypedNumber() {
        val number = inputNumber.text?.toString().orEmpty().trim()
        if (!ScamBlacklist.add(this, number, "User reported as suspicious", "manual")) {
            Toast.makeText(this, "Enter a valid phone number (7–15 digits).", Toast.LENGTH_LONG).show()
            return
        }
        inputNumber.text?.clear()
        Toast.makeText(this, "Saved on this phone only. You can undo below.", Toast.LENGTH_LONG).show()
        refreshReports()
    }

    private fun refreshStatus() {
        val overlay = WarningOverlay.canDraw(this)
        val listener = isListenerEnabled()
        txtStatus.text = when {
            overlay && listener -> "MESSAGE WARNINGS · ACTIVE"
            else -> "MESSAGE WARNINGS · SETUP REQUIRED\nEnable both accesses above to activate."
        }
        val callsActive = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
        txtCallStatus.text = if (callsActive) {
            "Call screening is on · locally reported numbers only · calls are still allowed"
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            "Call screening is off"
        } else {
            "Call screening requires Android 10 or later"
        }
    }

    private fun refreshReports() {
        reportList.removeAllViews()
        val entries = ScamBlacklist.all(this)
        txtNoReports.visibility = if (entries.isEmpty()) View.VISIBLE else View.GONE
        entries.forEach { entry ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(12), dp(8), dp(8), dp(8))
                setBackgroundColor(0xFFFFFFFF.toInt())
            }
            val formatter = SimpleDateFormat("dd MMM yyyy", Locale.getDefault())
            val reportText = TextView(this).apply {
                text = "${entry.number}\n${entry.reports} local report(s) · ${formatter.format(Date(entry.lastReportedAt))}\n${entry.reason}"
                textSize = 13f
                setTextColor(0xFF304654.toInt())
            }
            row.addView(reportText, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            val undo = Button(this).apply {
                text = "Undo"
                contentDescription = "Undo latest local report for ${entry.number}"
                setOnClickListener {
                    ScamBlacklist.undoLast(this@MainActivity, entry.number)
                    Toast.makeText(this@MainActivity, "Latest report removed from this phone.", Toast.LENGTH_SHORT).show()
                    refreshReports()
                }
            }
            row.addView(undo)
            val params = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            params.bottomMargin = dp(6)
            reportList.addView(row, params)
        }
    }

    private fun isListenerEnabled(): Boolean {
        val flat = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: return false
        return flat.split(':').mapNotNull(ComponentName::unflattenFromString).any { it.packageName == packageName }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    companion object {
        private const val REQUEST_CALL_ROLE = 3102
    }
}
