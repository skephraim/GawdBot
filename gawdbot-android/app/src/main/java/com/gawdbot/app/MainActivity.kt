package com.gawdbot.app

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.navigation.fragment.NavHostFragment
import androidx.navigation.ui.setupWithNavController
import com.gawdbot.app.databinding.ActivityMainBinding
import com.gawdbot.app.services.GawdBotConnectionService

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var projectionManager: MediaProjectionManager

    // Screen capture permission launcher
    private val capturePermission = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            val projection = projectionManager.getMediaProjection(result.resultCode, result.data!!)
            GawdBotConnectionService.start(this, projection)
            Toast.makeText(this, "Screen capture enabled", Toast.LENGTH_SHORT).show()
        } else {
            // Start without screen capture — phone control still works, just no screenshots
            GawdBotConnectionService.start(this, null)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        projectionManager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager

        val navHost = supportFragmentManager.findFragmentById(R.id.navHostFragment) as NavHostFragment
        binding.bottomNav.setupWithNavController(navHost.navController)

        if (!GawdBotConnectionService.isRunning) {
            requestScreenCaptureAndConnect()
        }
    }

    private fun requestScreenCaptureAndConnect() {
        capturePermission.launch(projectionManager.createScreenCaptureIntent())
    }
}
