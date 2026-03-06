package com.gawdbot.app.utils

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

object Prefs {
    private const val NAME = "gawdbot_prefs"
    private const val KEY_SERVER_URL = "server_url"
    private const val KEY_DEVICE_NAME = "device_name"

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    fun getServerUrl(ctx: Context): String =
        prefs(ctx).getString(KEY_SERVER_URL, "ws://192.168.1.100:8080/ws") ?: "ws://192.168.1.100:8080/ws"

    fun setServerUrl(ctx: Context, url: String) =
        prefs(ctx).edit { putString(KEY_SERVER_URL, url) }

    fun getDeviceName(ctx: Context): String {
        val saved = prefs(ctx).getString(KEY_DEVICE_NAME, null)
        if (!saved.isNullOrBlank()) return saved
        return android.os.Build.MODEL
    }

    fun setDeviceName(ctx: Context, name: String) =
        prefs(ctx).edit { putString(KEY_DEVICE_NAME, name) }
}
