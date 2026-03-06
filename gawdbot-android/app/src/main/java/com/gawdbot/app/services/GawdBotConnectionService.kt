package com.gawdbot.app.services

import android.app.*
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjection
import android.os.IBinder
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import com.gawdbot.app.App
import com.gawdbot.app.MainActivity
import com.gawdbot.app.R
import com.gawdbot.app.capture.ScreenCapture
import com.gawdbot.app.utils.Prefs
import com.gawdbot.app.websocket.*
import kotlinx.coroutines.*
import java.util.UUID

private const val TAG = "GawdBotService"
private const val NOTIF_CHANNEL = "gawdbot_service"
private const val NOTIF_ID = 1001

class GawdBotConnectionService : Service() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var screenCapture: ScreenCapture? = null
    private val deviceId = UUID.randomUUID().toString()

    companion object {
        var isRunning = false
            private set

        fun start(context: Context, mediaProjection: MediaProjection? = null) {
            val intent = Intent(context, GawdBotConnectionService::class.java)
            context.startForegroundService(intent)
            // Pass projection separately (can't parcel MediaProjection)
            pendingProjection = mediaProjection
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, GawdBotConnectionService::class.java))
        }

        var pendingProjection: MediaProjection? = null
    }

    override fun onCreate() {
        super.onCreate()
        isRunning = true
        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification("Connecting..."))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val projection = pendingProjection
        pendingProjection = null

        val metrics = DisplayMetrics().also {
            (getSystemService(Context.WINDOW_SERVICE) as WindowManager).defaultDisplay.getMetrics(it)
        }

        if (projection != null) {
            screenCapture = ScreenCapture(this, projection).also { it.start() }
            App.instance.screenCapture = screenCapture
            Log.i(TAG, "Screen capture ready: ${metrics.widthPixels}×${metrics.heightPixels}")
        }

        scope.launch {
            connectAndListen(metrics)
        }

        return START_STICKY
    }

    private suspend fun connectAndListen(metrics: DisplayMetrics) {
        val url = Prefs.getServerUrl(this)
        val deviceName = Prefs.getDeviceName(this)
        val client = App.instance.client

        client.connect(url)

        // Wait for CONNECTED state then send hello
        client.state.collect { state ->
            when (state) {
                ConnectionState.CONNECTED -> {
                    updateNotification("Connected")
                    client.send(HelloMessage(
                        device_id = deviceId,
                        device_name = deviceName,
                        screen_width = metrics.widthPixels,
                        screen_height = metrics.heightPixels,
                    ))
                    // Start listening for screenshot requests
                    scope.launch { handleMessages() }
                }
                ConnectionState.FAILED, ConnectionState.DISCONNECTED -> {
                    updateNotification("Disconnected — retrying...")
                    delay(5000)
                    client.connect(url)
                }
                else -> {}
            }
        }
    }

    private suspend fun handleMessages() {
        App.instance.client.messages.collect { msg ->
            when (msg) {
                is ServerMessage.RequestScreenshot -> {
                    val capture = screenCapture
                    if (capture != null) {
                        scope.launch(Dispatchers.IO) {
                            val b64 = capture.captureBase64()
                            if (b64 != null) {
                                App.instance.client.send(
                                    ScreenshotResponse(request_id = msg.requestId, image = b64)
                                )
                            }
                        }
                    }
                }
                is ServerMessage.Notification -> {
                    showUserNotification(msg.title, msg.body)
                }
                else -> {} // Actions handled by PhoneControlService
            }
        }
    }

    private fun showUserNotification(title: String, body: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notif = NotificationCompat.Builder(this, NOTIF_CHANNEL)
            .setSmallIcon(R.drawable.ic_gawdbot)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .build()
        nm.notify(System.currentTimeMillis().toInt(), notif)
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        scope.cancel()
        screenCapture?.stop()
        App.instance.screenCapture = null
        App.instance.client.disconnect()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        val ch = NotificationChannel(
            NOTIF_CHANNEL,
            "GawdBot Connection",
            NotificationManager.IMPORTANCE_LOW,
        ).apply { description = "Keeps GawdBot connected in the background" }
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .createNotificationChannel(ch)
    }

    private fun buildNotification(status: String): Notification {
        val pi = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, NOTIF_CHANNEL)
            .setSmallIcon(R.drawable.ic_gawdbot)
            .setContentTitle("GawdBot")
            .setContentText(status)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(status: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, buildNotification(status))
    }
}

// Add screenCapture property to App
var App.screenCapture: ScreenCapture?
    get() = _screenCapture
    set(value) { _screenCapture = value }

private var _screenCapture: ScreenCapture? = null
