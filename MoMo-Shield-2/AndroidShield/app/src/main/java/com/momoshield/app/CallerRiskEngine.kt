package com.momoshield.app

/** Conservative call signals; no call audio or contact contents are inspected. */
object CallerRiskEngine {
    data class Verdict(val tier: String, val reasons: List<String>)

    fun evaluate(isLocallyReported: Boolean, networkNumberVerificationFailed: Boolean): Verdict {
        val reasons = mutableListOf<String>()
        if (isLocallyReported) reasons += "This number was reported on this phone"
        if (networkNumberVerificationFailed) reasons += "The mobile network could not verify the caller ID"
        val tier = when {
            isLocallyReported -> "HIGH"
            networkNumberVerificationFailed -> "MEDIUM"
            else -> "LOW"
        }
        return Verdict(tier, reasons)
    }
}
