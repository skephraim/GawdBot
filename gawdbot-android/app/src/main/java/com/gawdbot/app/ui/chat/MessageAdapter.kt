package com.gawdbot.app.ui.chat

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.gawdbot.app.R

private const val VIEW_USER = 0
private const val VIEW_BOT = 1

class MessageAdapter : ListAdapter<ChatMessage, MessageAdapter.VH>(DIFF) {

    override fun getItemViewType(position: Int) =
        if (getItem(position).isUser) VIEW_USER else VIEW_BOT

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val layout = if (viewType == VIEW_USER)
            R.layout.item_message_user
        else
            R.layout.item_message_bot
        val view = LayoutInflater.from(parent.context).inflate(layout, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.bind(getItem(position))
    }

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        private val text: TextView = view.findViewById(R.id.tvMessage)
        fun bind(msg: ChatMessage) {
            text.text = msg.text
        }
    }

    companion object {
        val DIFF = object : DiffUtil.ItemCallback<ChatMessage>() {
            override fun areItemsTheSame(a: ChatMessage, b: ChatMessage) =
                a.timestamp == b.timestamp
            override fun areContentsTheSame(a: ChatMessage, b: ChatMessage) = a == b
        }
    }
}
