package com.gawdbot.app.websocket

import com.google.gson.Gson
import com.google.gson.JsonObject

val gson = Gson()

// ── Messages phone sends to server ───────────────────────────────────────────

data class HelloMessage(
    val type: String = "hello",
    val device_id: String,
    val device_name: String,
    val screen_width: Int,
    val screen_height: Int,
)

data class ScreenshotResponse(
    val type: String = "screenshot_response",
    val request_id: String,
    val image: String,  // base64 PNG
)

data class ActionDone(
    val type: String = "action_done",
    val action_id: String,
    val success: Boolean = true,
)

data class UserMessage(
    val type: String = "user_message",
    val text: String,
)

data class PingMessage(val type: String = "ping")

// ── Messages server sends to phone ───────────────────────────────────────────

sealed class ServerMessage {
    data class Welcome(val status: String) : ServerMessage()
    data class RequestScreenshot(val requestId: String) : ServerMessage()
    data class Action(
        val actionId: String,
        val action: String,
        val params: JsonObject,
    ) : ServerMessage()
    data class Response(val text: String) : ServerMessage()
    data class Notification(val title: String, val body: String) : ServerMessage()
    data class Pong(val dummy: Unit = Unit) : ServerMessage()
    data class Unknown(val raw: String) : ServerMessage()
}

fun parseServerMessage(raw: String): ServerMessage {
    return try {
        val obj = gson.fromJson(raw, JsonObject::class.java)
        when (obj.get("type")?.asString) {
            "welcome" -> ServerMessage.Welcome(obj.get("status")?.asString ?: "")
            "request_screenshot" -> ServerMessage.RequestScreenshot(
                obj.get("request_id")?.asString ?: ""
            )
            "action" -> ServerMessage.Action(
                actionId = obj.get("action_id")?.asString ?: "",
                action = obj.get("action")?.asString ?: "",
                params = obj,
            )
            "response" -> ServerMessage.Response(obj.get("text")?.asString ?: "")
            "notification" -> ServerMessage.Notification(
                title = obj.get("title")?.asString ?: "GawdBot",
                body = obj.get("body")?.asString ?: "",
            )
            "pong" -> ServerMessage.Pong()
            else -> ServerMessage.Unknown(raw)
        }
    } catch (e: Exception) {
        ServerMessage.Unknown(raw)
    }
}
