package com.gawdbot.app.ui.settings

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import com.gawdbot.app.App
import com.gawdbot.app.databinding.FragmentSettingsBinding
import com.gawdbot.app.services.GawdBotConnectionService
import com.gawdbot.app.utils.Prefs

class SettingsFragment : Fragment() {

    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, saved: Bundle?): View {
        _binding = FragmentSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.etServerUrl.setText(Prefs.getServerUrl(requireContext()))
        binding.etDeviceName.setText(Prefs.getDeviceName(requireContext()))

        binding.btnSave.setOnClickListener {
            val url = binding.etServerUrl.text.toString().trim()
            val name = binding.etDeviceName.text.toString().trim()
            if (url.isBlank()) {
                Toast.makeText(requireContext(), "Server URL cannot be empty", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            Prefs.setServerUrl(requireContext(), url)
            if (name.isNotBlank()) Prefs.setDeviceName(requireContext(), name)
            Toast.makeText(requireContext(), "Saved. Reconnecting...", Toast.LENGTH_SHORT).show()
            App.instance.client.disconnect()
            GawdBotConnectionService.start(requireContext())
        }

        binding.btnAccessibility.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        binding.btnDisconnect.setOnClickListener {
            GawdBotConnectionService.stop(requireContext())
            Toast.makeText(requireContext(), "Disconnected", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
