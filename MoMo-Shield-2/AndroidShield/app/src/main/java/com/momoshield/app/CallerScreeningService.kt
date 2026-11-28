package com.momoshield.app

import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import android.telecom.Connection

/**
 * Optional Android call-ID/screening integration. It makes no network calls,
 * reads no microphone audio, and never blocks/rejects a call in this pilot.
 */
class CallerScreeningService : CallScreeningService() {
    override fun onScreenCall(callDetails: Call.Details) {
        val isIncoming = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            callDetails.callDirection == Call.Details.DIRECTION_INCOMING
        val rawNumber = callDetails.handle?.takeIf { it.scheme == "tel" }
            ?.schemeSpecificPart.orEmpty()
        val localReport = isIncoming && rawNumber.isNotBlank() && ScamBlacklist.contains(this, rawNumber)
        val verificationFailed = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            callDetails.callerNumberVerificationStatus == Connection.VERIFICATION_STATUS_FAILED

        // Always respond promptly and let the caller ring. This feature is advisory only.
        respondToCall(
            callDetails,
            CallResponse.Builder()
                .setDisallowCall(false)
                .setRejectCall(false)
                .setSilenceCall(false)
                .setSkipCallLog(false)
                .setSkipNotification(false)
                .build(),
        )

        if (!isIncoming || rawNumber.isBlank()) return
        val verdict = CallerRiskEngine.evaluate(localReport, verificationFailed)
        if (verdict.tier == "LOW") return
        val details = verdict.reasons.joinToString("\n• ", "• ") +
            "\n\nThis call is still allowed. Do not share your PIN or OTP."
        WarningOverlay.show(
            ctx = this,
            tier = verdict.tier,
            headline = "Incoming call — pause and verify before sharing information.",
            detail = details,
            sender = rawNumber,
            onFlag = { ScamBlacklist.add(this, rawNumber, "Reported from incoming call", "call") },
        )
        WarningAudio.play(this)
    }
}
