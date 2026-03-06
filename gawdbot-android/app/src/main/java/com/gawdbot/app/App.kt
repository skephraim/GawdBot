package com.gawdbot.app

import android.app.Application
import com.gawdbot.app.websocket.GawdBotClient

class App : Application() {

    val client = GawdBotClient()

    companion object {
        lateinit var instance: App
            private set
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
    }
}
