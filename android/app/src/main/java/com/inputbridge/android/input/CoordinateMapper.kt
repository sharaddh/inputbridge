package com.inputbridge.android.input

import android.content.Context
import android.graphics.Rect
import android.os.Build
import android.view.WindowInsets
import android.view.WindowManager
import kotlin.math.roundToInt

class CoordinateMapper(context: Context) {
    private val manager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    var screenWidth = 1
        private set
    var screenHeight = 1
        private set
    var usableLeft = 0
        private set
    var usableTop = 0
        private set
    var usableRight = 1
        private set
    var usableBottom = 1
        private set

    init {
        refresh()
    }

    fun refresh() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val metrics = manager.currentWindowMetrics
            val bounds: Rect = metrics.bounds
            screenWidth = bounds.width().coerceAtLeast(1)
            screenHeight = bounds.height().coerceAtLeast(1)
            val types = WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout()
            val insets = metrics.windowInsets.getInsets(types)
            usableLeft = insets.left.coerceIn(0, screenWidth - 1)
            usableTop = insets.top.coerceIn(0, screenHeight - 1)
            usableRight = (screenWidth - insets.right).coerceAtLeast(usableLeft + 1)
            usableBottom = (screenHeight - insets.bottom).coerceAtLeast(usableTop + 1)
        } else {
            @Suppress("DEPRECATION")
            val metrics = android.util.DisplayMetrics()
            @Suppress("DEPRECATION")
            manager.defaultDisplay.getRealMetrics(metrics)
            screenWidth = metrics.widthPixels.coerceAtLeast(1)
            screenHeight = metrics.heightPixels.coerceAtLeast(1)
            usableLeft = 0
            usableTop = 0
            usableRight = screenWidth
            usableBottom = screenHeight
        }
    }

    val usableWidth: Int get() = (usableRight - usableLeft).coerceAtLeast(1)
    val usableHeight: Int get() = (usableBottom - usableTop).coerceAtLeast(1)

    fun point(xNorm: Float, yNorm: Float, offsetX: Int = 0, offsetY: Int = 0): Pair<Int, Int> {
        val x = usableLeft + xNorm.coerceIn(0f, 1f) * usableWidth + offsetX
        val y = usableTop + yNorm.coerceIn(0f, 1f) * usableHeight + offsetY
        return x.roundToInt().coerceIn(0, screenWidth - 1) to
            y.roundToInt().coerceIn(0, screenHeight - 1)
    }
}
