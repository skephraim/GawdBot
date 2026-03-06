package com.gawdbot.app.ui.chat

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import com.gawdbot.app.databinding.FragmentChatBinding
import kotlinx.coroutines.launch
import java.util.Locale

class ChatFragment : Fragment() {

    private var _binding: FragmentChatBinding? = null
    private val binding get() = _binding!!
    private val vm: ChatViewModel by viewModels({ requireActivity() })
    private val adapter = MessageAdapter()
    private var speech: SpeechRecognizer? = null

    private val micPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startVoiceInput() else
            Toast.makeText(requireContext(), "Microphone permission needed for voice", Toast.LENGTH_SHORT).show()
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, saved: Bundle?): View {
        _binding = FragmentChatBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.recycler.layoutManager = LinearLayoutManager(requireContext()).apply {
            stackFromEnd = true
        }
        binding.recycler.adapter = adapter

        binding.btnSend.setOnClickListener {
            val text = binding.etMessage.text.toString().trim()
            if (text.isNotEmpty()) {
                vm.sendMessage(text)
                binding.etMessage.setText("")
            }
        }

        binding.btnMic.setOnClickListener {
            if (ContextCompat.checkSelfPermission(requireContext(), Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED
            ) {
                startVoiceInput()
            } else {
                micPermission.launch(Manifest.permission.RECORD_AUDIO)
            }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    vm.messages.collect { msgs ->
                        adapter.submitList(msgs.toList()) {
                            binding.recycler.scrollToPosition(adapter.itemCount - 1)
                        }
                    }
                }
                launch {
                    vm.isThinking.collect { thinking ->
                        binding.progressThinking.visibility =
                            if (thinking) View.VISIBLE else View.GONE
                    }
                }
            }
        }
    }

    private fun startVoiceInput() {
        speech?.destroy()
        speech = SpeechRecognizer.createSpeechRecognizer(requireContext())
        speech?.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                val text = matches?.firstOrNull() ?: return
                vm.sendMessage(text)
            }
            override fun onError(error: Int) {
                Toast.makeText(requireContext(), "Voice error: $error", Toast.LENGTH_SHORT).show()
            }
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(results: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        val intent = android.content.Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
        }
        speech?.startListening(intent)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        speech?.destroy()
        _binding = null
    }
}
