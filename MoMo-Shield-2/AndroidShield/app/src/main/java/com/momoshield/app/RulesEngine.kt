package com.momoshield.app

import java.util.regex.Pattern

/**
 * On-device, explainable subset inspired by Backend-2/app/engine/rules.py.
 *
 * This is not exact backend parity: the phone sees notification text only.
 * Rules needing cross-event history (fund-flow ledger, velocity), verified
 * network context, RAG, or calibrated ML are not reproduced here. Scores
 * are uncalibrated warning signals, not probabilities or proof of fraud.
 */
object RulesEngine {

    data class Verdict(val score: Int, val reasons: List<String>) {
        val tier: String
            get() = when {
                score >= 75 -> "HIGH"
                score >= 40 -> "MEDIUM"
                else -> "LOW"
            }
    }

    // ---- Shared patterns (mirrors rules.py) ----
    private val NEGATION = Pattern.compile(
        "\\b(never|do not|don't|won't|will not|no one)\\b[^.]{0,50}\\b(share|give|tell|send|provide|enter|confirm|disclose|reply)\\b" +
        "|\\b(share|give|tell|send|provide|enter|confirm|disclose|reply)\\b[^.]{0,50}\\b(never|no one)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val SECRET = Pattern.compile("\\b(pin|otp|password|passcode|secret|cvv|card number)\\b", Pattern.CASE_INSENSITIVE)
    private val REQUEST = Pattern.compile(
        "\\b(send|share|tell|give|provide|reply with|enter|confirm)\\b[^.]{0,80}\\b(pin|otp|password|passcode|secret|code)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val AUTHORITY = Pattern.compile(
        "\\b(mtn|vodafone|telecel|airteltigo|moMo|momo|mobile money|bank|fraud department|security team|agent|office|head office|official|verified)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val URGENCY = Pattern.compile(
        "\\b(urgent\\w*|immediately|right now|expires?|suspended|blocked|locked|terminate[sd]?|before it expires|be fast|act now|limited time)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val PRIZE = Pattern.compile("\\b(prize|winner|congratulations|reward|lottery|lucky)\\b", Pattern.CASE_INSENSITIVE)
    private val LINK = Pattern.compile("https?://\\S+", Pattern.CASE_INSENSITIVE)
    private val LINK_CRED = Pattern.compile("\\b(verify|login|confirm|update|click|tap|visit|enter)\\b", Pattern.CASE_INSENSITIVE)
    private val NO_CALLBACK = Pattern.compile(
        "\\b(don'?t call|do not call|can'?t talk|cannot talk|busy right now|call you later|no time to talk)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val MONEY_DEMAND = Pattern.compile(
        "\\b(send|transfer|pay|remit|forward)\\b[^.]{0,60}\\b(ghs?|cedis|money|\\d[\\d,]*(?:\\.\\d+)?)\\b" +
        "|\\b(send|transfer|pay|remit)\\s+(?:it|them|the\\s+money|money)?\\s*to\\s+(?:this|my)\\s+(?:number|phone|line|wallet)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val RELATIVE = Pattern.compile(
        "\\b(bro|sis|brother|sister|mum|mom|dad|uncle|auntie|cousin|family|relative|grandma|grandpa)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val IDENTITY_VAGUE = Pattern.compile("\\b(it'?s me|it is me|this is me|i'?m me)\\b", Pattern.CASE_INSENSITIVE)
    private val NEW_NUMBER = Pattern.compile("\\b(new (?:number|phone|sim|line)|changed (?:my |the )?(?:number|phone|sim)|this is my new)\\b", Pattern.CASE_INSENSITIVE)
    private val DISTRESS = Pattern.compile(
        "\\b(help|emergency|hospital|accident|arrested|in trouble|please|urgent|asap)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val FEE_DEMAND = Pattern.compile(
        "\\b(fee|processing|claim|activation|charge|deposit|levy|service charge)\\b[^.]{0,60}\\b(send|transfer|pay|remit|to)\\b" +
        "|\\b(send|transfer|pay|remit)\\b[^.]{0,60}\\b(fee|processing fee|claim|activation|charge|deposit|ghs?\\s*\\d)",
        Pattern.CASE_INSENSITIVE
    )
    private val CREDIT_CLAIM = Pattern.compile(
        "\\b(received|credited|refund(?:ed)?|reversal|payment\\s+alert|money\\s+alert|has\\s+sent|sent\\s+you|deposited)\\b" +
        "|\\bgh[c₵s]?\\s*[-–]?\\s*\\d|\\b\\d[\\d,]*(?:\\.\\d+)?\\s*(?:ghc|ghs|cedis|gh₵)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val RECIPROCAL = Pattern.compile(
        "\\b(call me back|call back|phone me|ring me|send (?:it|the money|money) back|return (?:it|the money)|verify|confirm)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val APPROVE_RECEIVE = Pattern.compile(
        "\\b(approve|accept|confirm|press|dial)\\b[^.]{0,50}\\b(receive|claim|credit|refund|payment)\\b" +
        "|\\b(receive|claim|collect)\\b[^.]{0,50}\\b(approve|accept|confirm)\\b",
        Pattern.CASE_INSENSITIVE
    )

    // Free-hosting domains — telcos never send customers to these (rules.py)
    private val SUSPICIOUS_HOST = Pattern.compile(
        "\\b(?:[a-z0-9-]+\\.)*(?:" +
            "vercel\\.app|netlify\\.app|pages\\.dev|github\\.io|gitlab\\.io|herokuapp\\.com|" +
            "onrender\\.com|fly\\.dev|railway\\.app|surge\\.sh|repl\\.co|web\\.app|firebaseapp\\.com|" +
            "blogspot\\.com|wordpress\\.com|weebly\\.com|wixsite\\.com|000webhostapp\\.com|" +
            "duckdns\\.org|no-ip\\.com|ddns\\.net|zapto\\.org|servehttp\\.com|glitch\\.me" +
        ")\\b",
        Pattern.CASE_INSENSITIVE
    )

    private val FAILED_TXN = Pattern.compile(
        "\\b(tried\\s+sending|failed|unsuccessful|did\\s+not\\s+go\\s+through|been\\s+blocked|" +
        "malicious\\s+activity|unauthori[sz]ed\\s+transaction|could\\s+not\\s+complete)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val RECOVERY_CTA = Pattern.compile(
        "\\b(recover|refund|claim\\s+your|verify\\s+your|update\\s+your|confirm\\s+your|click|tap|visit)\\b",
        Pattern.CASE_INSENSITIVE
    )
    private val FINANCIAL_CTX = Pattern.compile(
        "\\b(ghs?|cedis|gh¢|momo|mobile\\s+money|wallet|transaction|transfer|account|refund|payment|send|receive|balance)\\b" +
        "|\\b\\d[\\d,]*(?:\\.\\d+)?\\s*(?:ghs?|cedis|gh¢)\\b",
        Pattern.CASE_INSENSITIVE
    )

    private fun has(p: Pattern, t: String) = p.matcher(t).find()

    /** Score an SMS body. senderKnownScam adds the local-blacklist signal. */
    fun scoreSms(text: String, senderKnownScam: Boolean = false): Verdict {
        val t = text.trim()
        if (t.isEmpty()) return Verdict(0, emptyList())
        var score = 0
        val reasons = mutableListOf<String>()
        fun add(points: Int, reason: String) {
            score += points
            reasons.add(reason)
        }

        val negated = has(NEGATION, t)
        val secret = has(SECRET, t)
        val request = has(REQUEST, t)
        val authority = has(AUTHORITY, t)
        val urgency = has(URGENCY, t)
        val prize = has(PRIZE, t)
        val link = has(LINK, t)

        // check_content_credential_request (+45 / secret solicitation)
        if (!negated && secret && request) {
            add(45, "Credential request: message asks for a secret (PIN/OTP/password)")
        }
        // check_content_impersonation (+15 each)
        if (!negated && authority && secret) {
            add(15, "Operator/authority impersonation combined with secret solicitation")
        }
        if (!negated && authority && urgency) {
            add(15, "Authority impersonation with urgency pressure")
        }
        // check_content_urgency (+15)
        if (!negated && urgency && (secret || prize)) {
            add(15, "Urgency/loss-aversion pressure with credential or prize bait")
        }
        // check_gh15_phishing_link (+45)
        if (!negated && link && (secret || has(LINK_CRED, t))) {
            add(45, "Phishing link: URL combined with credential/action prompt")
        }
        // check_sms_credential_harvesting (+25 — on-device we warn, not block delivery)
        if (!negated && secret && request &&
            (authority || urgency || prize || link)) {
            add(25, "Credential-harvesting SMS: secret solicitation + deception lever")
        }
        // check_gh23 / check_prize_fee_scam (+40)
        if (!negated && prize && has(FEE_DEMAND, t)) {
            add(40, "Advance-fee scam: prize bait + upfront-fee demand")
        }
        // check_approve_to_receive GH16 (+40)
        if (!negated && has(APPROVE_RECEIVE, t) && (link || FINANCIAL_CTX.matcher(t).find())) {
            add(40, "Approve-to-receive trick: asked to approve an action to receive money")
        }
        // check_unverified_credit_claim — backend needs the fund-flow ledger;
        // on-device we can only see the SMS itself, so score the claim+pressure
        // pattern at warn tier rather than fabricating corroboration.
        if (!negated && has(CREDIT_CLAIM, t) && has(RECIPROCAL, t)) {
            add(25, "Unverified credit claim with reciprocal pressure (cannot corroborate on-device)")
        }
        // check_suspicious_link_host (+45)
        if (!negated && link && has(SUSPICIOUS_HOST, t)) {
            add(45, "Suspicious link host: uses a free-hosting domain commonly abused in scams")
        }
        // check_failed_transaction_lure (+35)
        if (!negated && has(FAILED_TXN, t) && has(RECOVERY_CTA, t)) {
            add(35, "Fake failed-transaction lure: failure hook + recovery call-to-action")
        }
        // check_financial_link_context (+25)
        if (!negated && link && has(FINANCIAL_CTX, t)) {
            add(25, "Link inside financial message — verify sender before clicking")
        }
        // GH19B relative-on-new-number (+30), simplified for SMS-only context
        val relativeOrVague = has(RELATIVE, t) || (has(IDENTITY_VAGUE, t) && has(NEW_NUMBER, t))
        if (!negated && relativeOrVague && has(NEW_NUMBER, t) &&
            (secret || has(MONEY_DEMAND, t) || has(NO_CALLBACK, t))) {
            add(30, "Relative-on-new-number social engineering: distress + money/secrecy demand")
        }
        // Local blacklist — user-confirmed scammer
        if (senderKnownScam) {
            add(60, "User-flagged sender: this sender is on your MoMo Shield list")
        }

        return Verdict(score, reasons)
    }
}
