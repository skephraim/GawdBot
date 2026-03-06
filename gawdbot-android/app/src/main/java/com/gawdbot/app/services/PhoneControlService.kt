package com.gawdbot.app.services

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import com.gawdbot.app.App
import com.gawdbot.app.websocket.ServerMessage
import kotlinx.coroutines.*

private const val TAG = "PhoneControlService"

class PhoneControlService : AccessibilityService() {

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    companion object {
        var instance: PhoneControlService? = null
            private set
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "Accessibility service connected")

        // Listen for actions from the WebSocket client
        scope.launch {
            App.instance.client.messages.collect { msg ->
                if (msg is ServerMessage.Action) {
                    handleAction(msg)
                }
            }
        }
    }

    override fun onAccessibilityEvent(event: android.view.accessibility.AccessibilityEvent?) {}

    override fun onInterrupt() {
        Log.w(TAG, "Accessibility service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        scope.cancel()
    }

    private fun handleAction(msg: ServerMessage.Action) {
        val params = msg.params
        val success = when (msg.action) {
            "tap" -> {
                val x = params.get("x")?.asFloat ?: 0f
                val y = params.get("y")?.asFloat ?: 0f
                tap(x, y)
            }
            "swipe" -> {
                val startX = params.get("startX")?.asFloat ?: 0f
                val startY = params.get("startY")?.asFloat ?: 0f
                val endX = params.get("endX")?.asFloat ?: 0f
                val endY = params.get("endY")?.asFloat ?: 0f
                val duration = params.get("duration_ms")?.asLong ?: 300L
                swipe(startX, startY, endX, endY, duration)
            }
            "type" -> {
                val text = params.get("text")?.asString ?: ""
                typeText(text)
            }
            "key" -> {
                val key = params.get("key")?.asString ?: ""
                pressKey(key)
            }
            "open_url" -> {
                val url = params.get("url")?.asString ?: ""
                openUrl(url)
            }
            else -> {
                Log.w(TAG, "Unknown action: ${msg.action}")
                false
            }
        }
        App.instance.client.send(
            com.gawdbot.app.websocket.ActionDone(action_id = msg.actionId, success = success)
        )
    }

    private fun tap(x: Float, y: Float): Boolean {
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 100)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(gesture, null, null)
    }

    private fun swipe(startX: Float, startY: Float, endX: Float, endY: Float, durationMs: Long): Boolean {
        val path = Path().apply {
            moveTo(startX, startY)
            lineTo(endX, endY)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(gesture, null, null)
    }

    private fun typeText(text: String): Boolean {
        val node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
        val args = Bundle().apply {
            putString(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    private fun pressKey(key: String): Boolean {
        return when (key.uppercase()) {
            "BACK" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "HOME" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "RECENTS" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "NOTIFICATIONS" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
            "VOLUME_UP" -> {
                // Fire a broadcast — volume keys are handled at OS level
                sendBroadcast(Intent("com.gawdbot.VOLUME_UP"))
                true
            }
            "VOLUME_DOWN" -> {
                sendBroadcast(Intent("com.gawdbot.VOLUME_DOWN"))
                true
            }
            "ENTER" -> {
                val node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return false
                node.performAction(AccessibilityNodeInfo.ACTION_NEXT_AT_MOVEMENT_GRANULARITY)
                true
            }
            "POWER" -> performGlobalAction(GLOBAL_ACTION_LOCK_SCREEN)
            else -> false
        }
    }

    private fun openUrl(url: String): Boolean {
        val intent = android.content.Intent(android.content.Intent.ACTION_VIEW).apply {
            data = android.net.Uri.parse(url)
            flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK
        }
        return try {
            startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e(TAG, "openUrl failed: ${e.message}")
            false
        }
    }
}
