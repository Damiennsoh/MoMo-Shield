package com.momoshield.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/**
 * A phone-local suspect/report database. A report is an allegation, not proof.
 * Numbers, source and timestamp stay in this app's private SQLite database.
 */
object ScamBlacklist {
    private const val DB_NAME = "momo_shield_local.db"
    private const val DB_VERSION = 1
    private const val TABLE = "suspect_reports"
    private const val TTL_DAYS = 180L
    private const val TTL_MS = TTL_DAYS * 24L * 60L * 60L * 1000L
    @Volatile private var helperInstance: Helper? = null

    data class Entry(
        val number: String,
        val reports: Int,
        val lastReportedAt: Long,
        val source: String,
        val reason: String,
    )

    private class Helper(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {
        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL(
                "CREATE TABLE $TABLE (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                    "number TEXT NOT NULL," +
                    "reason TEXT NOT NULL," +
                    "source TEXT NOT NULL," +
                    "created_at INTEGER NOT NULL)"
            )
            db.execSQL("CREATE INDEX idx_suspect_number_date ON $TABLE(number, created_at)")
        }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            // Versioned migration hook. Do not discard local reports automatically.
        }
    }

    @Synchronized
    private fun database(context: Context): SQLiteDatabase {
        val appContext = context.applicationContext
        val helper = helperInstance ?: Helper(appContext).also { helperInstance = it }
        val db = helper.writableDatabase
        db.delete(TABLE, "created_at<?", arrayOf((System.currentTimeMillis() - TTL_MS).toString()))
        val oldPrefs = appContext.getSharedPreferences("scam_blacklist", Context.MODE_PRIVATE)
        if (!oldPrefs.getBoolean("migrated_to_sqlite_v1", false)) {
            val now = System.currentTimeMillis()
            val oldNumbers = oldPrefs.getStringSet("numbers", emptySet())?.toSet().orEmpty()
            db.beginTransaction()
            try {
                oldNumbers.forEach { oldNumber ->
                    val normalized = normalize(oldNumber)
                    if (normalized.length in 7..15) {
                        val values = ContentValues().apply {
                            put("number", normalized)
                            put("reason", "Migrated from earlier local flag")
                            put("source", "legacy")
                            put("created_at", now)
                        }
                        db.insert(TABLE, null, values)
                    }
                }
                db.setTransactionSuccessful()
                oldPrefs.edit().putBoolean("migrated_to_sqlite_v1", true).apply()
            } finally {
                db.endTransaction()
            }
        }
        return db
    }

    /** Canonical Ghana local form for +233 numbers; retain international digits otherwise. */
    fun normalize(number: String): String {
        var digits = number.filter(Char::isDigit)
        if (digits.startsWith("233") && digits.length == 12) digits = "0" + digits.substring(3)
        return digits
    }

    fun add(
        context: Context,
        number: String,
        reason: String = "User reported as suspicious",
        source: String = "user",
    ): Boolean {
        val normalized = normalize(number)
        if (normalized.length !in 7..15) return false
        val db = database(context)
        val now = System.currentTimeMillis()
        val duplicate = db.rawQuery(
            "SELECT 1 FROM $TABLE WHERE number=? AND source=? AND created_at>? LIMIT 1",
            arrayOf(normalized, source.take(32), (now - 60_000L).toString()),
        ).use { it.moveToFirst() }
        if (duplicate) return true
        val values = ContentValues().apply {
            put("number", normalized)
            put("reason", reason.take(160))
            put("source", source.take(32))
            put("created_at", now)
        }
        return db.insert(TABLE, null, values) != -1L
    }

    /** Remove the latest report for this number; used by the visible Undo action. */
    fun undoLast(context: Context, number: String): Boolean {
        val normalized = normalize(number)
        if (normalized.length !in 7..15) return false
        val db = database(context)
        val id = db.rawQuery(
            "SELECT id FROM $TABLE WHERE number=? ORDER BY created_at DESC, id DESC LIMIT 1",
            arrayOf(normalized),
        ).use { if (it.moveToFirst()) it.getLong(0) else null } ?: return false
        return db.delete(TABLE, "id=?", arrayOf(id.toString())) > 0
    }

    /** Compatibility alias for prior local flag actions: remove all reports for this number. */
    fun remove(context: Context, number: String) {
        val normalized = normalize(number)
        if (normalized.length !in 7..15) return
        database(context).delete(TABLE, "number=?", arrayOf(normalized))
    }

    fun contains(context: Context, number: String): Boolean {
        val normalized = normalize(number)
        if (normalized.length !in 7..15) return false
        val cutoff = System.currentTimeMillis() - TTL_MS
        return database(context).rawQuery(
            "SELECT 1 FROM $TABLE WHERE number=? AND created_at>=? LIMIT 1",
            arrayOf(normalized, cutoff.toString()),
        ).use { it.moveToFirst() }
    }

    fun all(context: Context): List<Entry> {
        val db = database(context)
        val cutoff = System.currentTimeMillis() - TTL_MS
        val entries = mutableListOf<Entry>()
        db.rawQuery(
            "SELECT number, COUNT(*) AS reports, MAX(created_at) AS last_reported " +
                "FROM $TABLE WHERE created_at>=? GROUP BY number ORDER BY last_reported DESC",
            arrayOf(cutoff.toString()),
        ).use { cursor ->
            while (cursor.moveToNext()) {
                val number = cursor.getString(0)
                val count = cursor.getInt(1)
                val lastReported = cursor.getLong(2)
                val latest = db.rawQuery(
                    "SELECT source, reason FROM $TABLE WHERE number=? ORDER BY created_at DESC, id DESC LIMIT 1",
                    arrayOf(number),
                ).use { detail ->
                    if (detail.moveToFirst()) detail.getString(0) to detail.getString(1)
                    else "unknown" to "User report"
                }
                entries += Entry(number, count, lastReported, latest.first, latest.second)
            }
        }
        return entries
    }
}
