package com.gawdbot.app.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gawdbot.app.App
import com.gawdbot.app.websocket.ServerMessage
import com.gawdbot.app.websocket.UserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ChatMessage(
    val text: String,
    val isUser: Boolean,
    val timestamp: Long = System.currentTimeMillis(),
)

class ChatViewModel : ViewModel() {

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages

    private val _isThinking = MutableStateFlow(false)
    val isThinking: StateFlow<Boolean> = _isThinking

    init {
        viewModelScope.launch {
            App.instance.client.messages.collect { msg ->
                when (msg) {
                    is ServerMessage.Response -> {
                        _isThinking.value = false
                        addMessage(ChatMessage(text = msg.text, isUser = false))
                    }
                    else -> {}
                }
            }
        }
    }

    fun sendMessage(text: String) {
        addMessage(ChatMessage(text = text, isUser = true))
        _isThinking.value = true
        App.instance.client.send(UserMessage(text = text))
    }

    private fun addMessage(msg: ChatMessage) {
        _messages.value = _messages.value + msg
    }
}
