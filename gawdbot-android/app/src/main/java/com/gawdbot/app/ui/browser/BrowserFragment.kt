package com.gawdbot.app.ui.browser

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.*
import androidx.fragment.app.Fragment
import com.gawdbot.app.databinding.FragmentBrowserBinding

class BrowserFragment : Fragment() {

    private var _binding: FragmentBrowserBinding? = null
    private val binding get() = _binding!!

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, saved: Bundle?): View {
        _binding = FragmentBrowserBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        binding.webView.apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.setSupportZoom(true)
            settings.builtInZoomControls = true
            settings.displayZoomControls = false
            webViewClient = object : WebViewClient() {
                override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                    binding.progressBar.visibility = View.VISIBLE
                    binding.etUrl.setText(url)
                }
                override fun onPageFinished(view: WebView?, url: String?) {
                    binding.progressBar.visibility = View.GONE
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onProgressChanged(view: WebView?, newProgress: Int) {
                    binding.progressBar.progress = newProgress
                }
            }
            loadUrl("https://duckduckgo.com")
        }

        binding.etUrl.setOnEditorActionListener { v, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO || actionId == EditorInfo.IME_ACTION_SEARCH) {
                val input = v.text.toString().trim()
                val url = if (input.startsWith("http")) input
                          else "https://duckduckgo.com/?q=${android.net.Uri.encode(input)}"
                binding.webView.loadUrl(url)
                true
            } else false
        }

        binding.btnBack.setOnClickListener {
            if (binding.webView.canGoBack()) binding.webView.goBack()
        }

        binding.btnForward.setOnClickListener {
            if (binding.webView.canGoForward()) binding.webView.goForward()
        }

        binding.btnRefresh.setOnClickListener {
            binding.webView.reload()
        }
    }

    fun loadUrl(url: String) {
        binding.webView.loadUrl(url)
    }

    override fun onDestroyView() {
        binding.webView.destroy()
        super.onDestroyView()
        _binding = null
    }
}
