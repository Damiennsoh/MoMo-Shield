package com.momoshield.app

import android.content.Context
import android.content.SharedPreferences

/**
 * User-owned blacklist of confirmed scam numbers. Stored on-device only;
 * optionally syncable to the MoMo Shield threat ledger if the user consents.
 */
object ScamBlacklist {
    private const val PREFS = "scam_blacklist"
    private const val KEY = "numbers"

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Normalize to local 0XXXXXXXXX form (233… → 0…, strip non-digits). */
    fun normalize(number: String): String {
        var d = number.filter { it.isDigit() }
        if (d.startsWith("233")) d = "0" + d.substring(3)
        return d
    }

    fun add(ctx: Context, number: String) {
        val n = normalize(number)
        if (n.length < 7) return
        val set = prefs(ctx).getStringSet(KEY, mutableSetOf())!!.toMutableSet()
        set.add(n)
        prefs(ctx).edit().putStringSet(KEY, set).apply()
    }

    fun remove(ctx: Context, number: String) {
        val n = normalize(number)
        val set = prefs(ctx).getStringSet(KEY, mutableSetOf())!!.toMutableSet()
        set.remove(n)
        prefs(ctx).edit().putStringSet(KEY, set).apply()
    }

    fun contains(ctx: Context, number: String): Boolean {
        val n = normalize(number)
        if (n.length < 7) return false
        // Also match on the last 9 digits so +233/0 prefixes and sender-IDs align.
        val set = prefs(ctx).getStringSet(KEY, emptySet())!!
        if (n in set) return true
        val tail = n.takeLast(9)
        return set.any { it.takeLast(9) == tail }
    }

    fun all(ctx: Context): Set<String> =
        prefs(ctx).getStringSet(KEY, emptySet())!!.toSet()
}
