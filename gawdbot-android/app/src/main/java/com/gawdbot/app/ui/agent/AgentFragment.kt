package com.gawdbot.app.ui.agent

import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Base64
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.gawdbot.app.App
import com.gawdbot.app.databinding.FragmentAgentBinding
import com.gawdbot.app.websocket.ConnectionState
import com.gawdbot.app.websocket.ServerMessage
import kotlinx.coroutines.launch

/**
 * Live view of what GawdBot is doing on the phone.
 * Shows connection status, last screenshot, and action log.
 */
class AgentFragment : Fragment() {

    private var _binding: FragmentAgentBinding? = null
    private val binding get() = _binding!!
    private val log = StringBuilder()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, saved: Bundle?): View {
        _binding = FragmentAgentBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {

                launch {
                    App.instance.client.state.collect { state ->
                        binding.tvStatus.text = when (state) {
                            ConnectionState.CONNECTED -> "Connected"
                            ConnectionState.CONNECTING -> "Connecting..."
                            ConnectionState.DISCONNECTED -> "Disconnected"
                            ConnectionState.FAILED -> "Connection failed — retrying"
                        }
                        val color = when (state) {
                            ConnectionState.CONNECTED -> 0xFF4CAF50.toInt()
                            ConnectionState.FAILED -> 0xFFE53935.toInt()
                            else -> 0xFFFF9800.toInt()
                        }
                        binding.tvStatus.setTextColor(color)
                    }
                }

                launch {
                    App.instance.client.messages.collect { msg ->
                        when (msg) {
                            is ServerMessage.RequestScreenshot -> appendLog("Screenshot requested")
                            is ServerMessage.Action -> appendLog("Action: ${msg.action} ${msg.params}")
                            is ServerMessage.Response -> appendLog("Response: ${msg.text.take(80)}…")
                            is ServerMessage.ScreenshotData -> {
                                appendLog("Screenshot received")
                                showScreenshot(msg.image)
                            }
                            else -> {}
                        }
                    }
                }
            }
        }
    }

    private fun appendLog(line: String) {
        log.insert(0, "$line\n")
        if (log.length > 2000) log.delete(1800, log.length)
        binding.tvLog.text = log.toString()
    }

    private fun showScreenshot(base64: String) {
        try {
            val bytes = Base64.decode(base64, Base64.NO_WRAP)
            val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
            binding.ivScreen.setImageBitmap(bmp)
        } catch (_: Exception) {}
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}

// Extend ServerMessage to handle screenshot data display in AgentFragment
data class ScreenshotData(val image: String) : ServerMessage()
