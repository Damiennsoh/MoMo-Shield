package com.momoshield.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DetectorRegressionTest {
    @Test
    fun credentialPromptScoresHighAndExplainsWhy() {
        val verdict = RulesEngine.scoreSms(
            "MTN security team: urgent, send your OTP now or your wallet will be blocked."
        )
        assertEquals("HIGH", verdict.tier)
        assertTrue(verdict.reasons.any { it.contains("secret", ignoreCase = true) })
    }

    @Test
    fun defensiveSafetyAdviceIsNotFlaggedAsCredentialTheft() {
        val verdict = RulesEngine.scoreSms("Never share your PIN or OTP with anyone.")
        assertEquals("LOW", verdict.tier)
        assertEquals(0, verdict.score)
    }

    @Test
    fun ghanaInternationalNumberNormalizesToLocalForm() {
        assertEquals("0240000000", ScamBlacklist.normalize("+233 24 000 0000"))
    }

    @Test
    fun callSignalsRemainAdvisoryAndExplainTheirSource() {
        assertEquals("HIGH", CallerRiskEngine.evaluate(true, false).tier)
        assertEquals("MEDIUM", CallerRiskEngine.evaluate(false, true).tier)
        assertEquals("LOW", CallerRiskEngine.evaluate(false, false).tier)
        assertTrue(CallerRiskEngine.evaluate(true, true).reasons.size == 2)
    }
}
