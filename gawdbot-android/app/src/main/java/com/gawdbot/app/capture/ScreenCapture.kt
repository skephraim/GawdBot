package com.gawdbot.app.capture

import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.util.Base64
import android.util.DisplayMetrics
import android.view.WindowManager
import java.io.ByteArrayOutputStream

class ScreenCapture(
    private val context: Context,
    private val projection: MediaProjection,
) {
    private val metrics: DisplayMetrics = DisplayMetrics().also {
        (context.getSystemService(Context.WINDOW_SERVICE) as WindowManager)
            .defaultDisplay.getMetrics(it)
    }

    private val width = metrics.widthPixels
    private val height = metrics.heightPixels
    private val density = metrics.densityDpi

    private val imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
    private var virtualDisplay: VirtualDisplay? = null

    fun start() {
        virtualDisplay = projection.createVirtualDisplay(
            "GawdBotCapture",
            width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader.surface, null, null,
        )
    }

    fun captureBase64(quality: Int = 80): String? {
        // Give the virtual display a moment to render
        Thread.sleep(150)
        val image = imageReader.acquireLatestImage() ?: return null
        return try {
            val plane = image.planes[0]
            val rowPadding = plane.rowStride - plane.pixelStride * width
            val bmp = Bitmap.createBitmap(
                width + rowPadding / plane.pixelStride,
                height,
                Bitmap.Config.ARGB_8888,
            )
            bmp.copyPixelsFromBuffer(plane.buffer)

            // Crop to exact screen size
            val cropped = Bitmap.createBitmap(bmp, 0, 0, width, height)
            bmp.recycle()

            val out = ByteArrayOutputStream()
            cropped.compress(Bitmap.CompressFormat.JPEG, quality, out)
            cropped.recycle()

            Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
        } finally {
            image.close()
        }
    }

    fun stop() {
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader.close()
        projection.stop()
    }

    val screenWidth get() = width
    val screenHeight get() = height
}
