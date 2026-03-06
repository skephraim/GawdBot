package com.gawdbot.app.websocket

import android.util.Log
import com.google.gson.JsonObject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.*
import java.util.concurrent.TimeUnit

private const val TAG = "GawdBotClient"

enum class ConnectionState { DISCONNECTED, CONNECTING, CONNECTED, FAILED }

class GawdBotClient {

    private val http = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)  // no timeout for WebSocket
        .pingInterval(25, TimeUnit.SECONDS)
        .build()

    private var ws: WebSocket? = null

    private val _messages = MutableSharedFlow<ServerMessage>(extraBufferCapacity = 64)
    val messages: SharedFlow<ServerMessage> = _messages

    private val _state = MutableSharedFlow<ConnectionState>(
        replay = 1,
        extraBufferCapacity = 4,
    )
    val state: SharedFlow<ConnectionState> = _state

    fun connect(url: String) {
        _state.tryEmit(ConnectionState.CONNECTING)
        val request = Request.Builder().url(url).build()
        ws = http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "Connected to $url")
                _state.tryEmit(ConnectionState.CONNECTED)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val msg = parseServerMessage(text)
                _messages.tryEmit(msg)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                _state.tryEmit(ConnectionState.DISCONNECTED)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket failure: ${t.message}")
                _state.tryEmit(ConnectionState.FAILED)
            }
        })
    }

    fun disconnect() {
        ws?.close(1000, "User disconnected")
        ws = null
        _state.tryEmit(ConnectionState.DISCONNECTED)
    }

    fun send(obj: Any) {
        val json = gson.toJson(obj)
        ws?.send(json)
    }

    fun isConnected() = _state.replayCache.firstOrNull() == ConnectionState.CONNECTED
}
