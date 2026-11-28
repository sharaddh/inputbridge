package com.inputbridge.android.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.accessibilityservice.GestureDescription
import android.content.Context
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Choreographer
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import com.inputbridge.android.input.CoordinateMapper
import com.inputbridge.android.input.PointerMetrics
import com.inputbridge.android.settings.SettingsStore
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.min

class InputAccessibilityService : AccessibilityService() {
    private var pendingButton = ""
    private var cursorView: View? = null
    private var cursorParams: WindowManager.LayoutParams? = null
    private var cursorVisible = false
    private var windowManager: WindowManager? = null
    private var currentStyle = SettingsStore.CursorStyle("classic", 28, Color.WHITE, Color.rgb(25, 28, 32), 2f, 0f, 0f)
    @Volatile private var latestX = 0.5f
    @Volatile private var latestY = 0.5f
    @Volatile private var calibrationOffsetX = 0
    @Volatile private var calibrationOffsetY = 0
    private var pendingX = 0.5f
    private var pendingY = 0.5f
    private var pendingMoveReceivedMono = 0L
    private var hasPendingMove = false
    private var frameScheduled = false
    private var pendingWheel = 0
    private var wheelScheduled = false
    private val mainHandler = Handler(Looper.getMainLooper())
    private val choreographer = Choreographer.getInstance()
    private lateinit var mapper: CoordinateMapper
    private val metrics = PointerMetrics()

    private val frameCallback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            var x = 0f
            var y = 0f
            var receivedMono = 0L
            var hasMove = false
            synchronized(this@InputAccessibilityService) {
                frameScheduled = false
                if (hasPendingMove) {
                    x = pendingX
                    y = pendingY
                    receivedMono = pendingMoveReceivedMono
                    hasPendingMove = false
                    hasMove = true
                }
            }
            if (hasMove) {
                applyCursorPosition(x, y)
                val latency = (System.nanoTime() - receivedMono) / 1_000_000L
                if (latency > 250L) metrics.stale() else metrics.frame(latency)
            }
        }
    }

    private val wheelRunnable = Runnable {
        synchronized(this) {
            wheelScheduled = false
        }
        val delta = synchronized(this) {
            val value = pendingWheel
            pendingWheel = 0
            value
        }
        if (delta == 0) return@Runnable
        val direction = SettingsStore.scrollDirection
        val sensitivity = SettingsStore.scrollSensitivity
        val distance = (min(abs(delta), 3) * 0.16f * sensitivity).coerceIn(0.06f, 0.42f)
        val upward = if (direction >= 0) delta > 0 else delta < 0
        val from = latestPoint()
        val toY = (from.second + if (upward) distance else -distance).coerceIn(0f, 1f)
        dispatchSwipe(from.first, from.second, from.first, toY, 130)
    }

    override fun onCreate() {
        super.onCreate()
        SettingsStore.init(applicationContext)
        mapper = CoordinateMapper(this)
        windowManager = getSystemService(Context.WINDOW_SERVICE) as? WindowManager
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        serviceInfo = AccessibilityServiceInfo().apply {
            flags = AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
            eventTypes = 0
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
        }
        refreshMetrics()
        addCursor()
        setCursorVisible(BridgeRuntime.mouseRouting())
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {}

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        mainHandler.post {
            refreshMetrics()
            rebuildCursor(SettingsStore.cursorStyle())
        }
    }

    override fun onDestroy() {
        removeCursor()
        instance = null
        super.onDestroy()
    }

    fun handle(payload: JSONObject) {
        when (payload.optString("action", "")) {
            "release_all" -> {
                pendingButton = ""
                setCursorVisible(false)
            }
            "move" -> {
                val x = payload.optDouble("x", latestX.toDouble()).toFloat().coerceIn(0f, 1f)
                val y = payload.optDouble("y", latestY.toDouble()).toFloat().coerceIn(0f, 1f)
                synchronized(this) {
                    latestX = x
                    latestY = y
                    if (hasPendingMove) metrics.coalesced()
                    pendingX = x
                    pendingY = y
                    pendingMoveReceivedMono = System.nanoTime()
                    hasPendingMove = true
                    metrics.received()
                    metrics.queueDepth(if (frameScheduled) 1 else 0)
                }
                scheduleFrame()
            }
            "down" -> {
                pendingButton = payload.optString("button", "left")
                updateLatest(payload)
            }
            "up" -> {
                updateLatest(payload)
                val button = if (pendingButton.isNotEmpty()) pendingButton else payload.optString("button", "left")
                pendingButton = ""
                val point = latestPoint()
                when (button) {
                    "left" -> tap(point.first, point.second, 90)
                    "right" -> when (SettingsStore.rightButtonAction) {
                        "back" -> globalAction(GLOBAL_ACTION_BACK)
                        "none" -> Unit
                        else -> tap(point.first, point.second, 550)
                    }
                    "middle" -> when (SettingsStore.middleButtonAction) {
                        "recents" -> globalAction(GLOBAL_ACTION_RECENTS)
                        else -> Unit
                    }
                    "back" -> globalAction(GLOBAL_ACTION_BACK)
                }
            }
            "wheel" -> queueWheel(payload.optInt("delta", 0))
        }
    }

    fun handleKey(payload: JSONObject) {
        if (payload.optString("action") != "down") return
        mainHandler.post {
            when (payload.optInt("vk", -1)) {
                3 -> performGlobalAction(GLOBAL_ACTION_HOME)
                4, 27 -> performGlobalAction(GLOBAL_ACTION_BACK)
                187 -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            }
        }
    }

    fun pointerStats(): Map<String, Any> {
        val result = metrics.snapshot().toMutableMap()
        result["usable_bounds"] = "${mapper.usableLeft},${mapper.usableTop},${mapper.usableRight},${mapper.usableBottom}"
        return result
    }

    fun refreshCursor() {
        mainHandler.post {
            refreshMetrics()
            rebuildCursor(SettingsStore.cursorStyle())
        }
    }

    fun setCursorVisible(visible: Boolean) {
        mainHandler.post {
            cursorVisible = visible
            val view = cursorView
            if (view == null) {
                if (visible) addCursor()
                return@post
            }
            view.visibility = if (visible) View.VISIBLE else View.GONE
            if (visible) applyCursorPosition(latestX, latestY)
        }
    }

    private fun updateLatest(payload: JSONObject) {
        val x = payload.optDouble("x", latestX.toDouble()).toFloat().coerceIn(0f, 1f)
        val y = payload.optDouble("y", latestY.toDouble()).toFloat().coerceIn(0f, 1f)
        latestX = x
        latestY = y
        if (cursorVisible) mainHandler.post { applyCursorPosition(x, y) }
    }

    private fun latestPoint(): Pair<Float, Float> = latestX to latestY

    private fun scheduleFrame() {
        var post = false
        synchronized(this) {
            if (!frameScheduled && cursorVisible) {
                frameScheduled = true
                post = true
            }
        }
        if (post) mainHandler.post { choreographer.postFrameCallback(frameCallback) }
    }

    private fun globalAction(action: Int) {
        mainHandler.post {
            if (performGlobalAction(action)) metrics.gesture()
        }
    }

    private fun queueWheel(delta: Int) {
        if (delta == 0) return
        synchronized(this) {
            pendingWheel = (pendingWheel + delta).coerceIn(-3, 3)
            if (!wheelScheduled) {
                wheelScheduled = true
                mainHandler.post(wheelRunnable)
            }
        }
    }

    private fun tap(xNorm: Float, yNorm: Float, duration: Long) {
        mainHandler.post { dispatchTap(xNorm, yNorm, duration) }
    }

    private fun dispatchTap(xNorm: Float, yNorm: Float, duration: Long) {
        val point = physicalPoint(xNorm, yNorm)
        val path = Path().apply { moveTo(point.first.toFloat(), point.second.toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, duration)
        if (dispatchGesture(GestureDescription.Builder().addStroke(stroke).build(), null, null)) {
            metrics.gesture()
        }
    }

    private fun dispatchSwipe(x1Norm: Float, y1Norm: Float, x2Norm: Float, y2Norm: Float, duration: Long) {
        val start = physicalPoint(x1Norm, y1Norm)
        val end = physicalPoint(x2Norm, y2Norm)
        val path = Path().apply {
            moveTo(start.first.toFloat(), start.second.toFloat())
            lineTo(end.first.toFloat(), end.second.toFloat())
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
            .build()
        if (dispatchGesture(gesture, null, null)) metrics.gesture()
    }

    private fun targetPoint(xNorm: Float, yNorm: Float): Pair<Int, Int> =
        mapper.point(xNorm, yNorm, SettingsStore.calibrationOffsetX, SettingsStore.calibrationOffsetY)

    private fun physicalPoint(xNorm: Float, yNorm: Float): Pair<Int, Int> =
        targetPoint(xNorm, yNorm)

    private fun refreshMetrics() {
        mapper.refresh()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as? WindowManager
    }

    private fun cursorSizePx(style: SettingsStore.CursorStyle): Int =
        (style.sizeDp * resources.displayMetrics.density).toInt().coerceAtLeast(12)

    private fun styleKey(style: SettingsStore.CursorStyle): String =
        listOf(
            style.shape,
            style.sizeDp,
            style.fillColor,
            style.outlineColor,
            style.outlineWidthDp,
            style.hotspotX,
            style.hotspotY,
        ).joinToString("|")

    private fun addCursor() {
        rebuildCursor(SettingsStore.cursorStyle())
    }

    private fun rebuildCursor(style: SettingsStore.CursorStyle) {
        removeCursor()
        refreshMetrics()
        currentStyle = style
        currentStyleKey = styleKey(style)
        val manager = windowManager ?: return
        val density = resources.displayMetrics.density
        val width = cursorSizePx(style)
        val height = (width * 1.15f).toInt().coerceAtLeast(width)
        val types = mutableListOf(WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY)
        if (Settings.canDrawOverlays(this)) {
            types.add(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY)
        }
        var lastError: Throwable? = null
        for (type in types) {
            val view = object : View(this@InputAccessibilityService) {
                override fun onDraw(canvas: Canvas) {
                    drawCursor(canvas, width, height, density, style)
                }
            }
            val params = WindowManager.LayoutParams(
                width,
                height,
                type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT,
            ).apply {
                gravity = Gravity.TOP or Gravity.LEFT
            }
            val result = runCatching { manager.addView(view, params) }
            if (result.isSuccess) {
                cursorView = view
                cursorParams = params
                view.visibility = if (cursorVisible) View.VISIBLE else View.GONE
                applyCursorPosition(latestX, latestY)
                return
            }
            lastError = result.exceptionOrNull()
            runCatching { manager.removeView(view) }
        }
        BridgeRuntime.log("Cursor overlay failed: ${lastError?.message ?: "no window type available"}")
    }

    private fun drawCursor(canvas: Canvas, width: Int, height: Int, density: Float, style: SettingsStore.CursorStyle) {
        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = style.fillColor
            this.style = Paint.Style.FILL
        }
        val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = style.outlineColor
            this.style = Paint.Style.STROKE
            strokeWidth = (style.outlineWidthDp * density).coerceAtLeast(0f)
            strokeJoin = Paint.Join.ROUND
            strokeCap = Paint.Cap.ROUND
        }
        when (style.shape) {
            "dot" -> {
                val radius = min(width, height) / 2f - outline.strokeWidth
                canvas.drawCircle(width / 2f, height / 2f, radius.coerceAtLeast(1f), fill)
                if (outline.strokeWidth > 0f) {
                    canvas.drawCircle(width / 2f, height / 2f, radius.coerceAtLeast(1f), outline)
                }
            }
            "crosshair" -> {
                val cx = width / 2f
                val cy = height / 2f
                canvas.drawLine(cx, 0f, cx, height.toFloat(), outline)
                canvas.drawLine(0f, cy, width.toFloat(), cy, outline)
                canvas.drawCircle(cx, cy, 3f * density, fill)
            }
            "compact" -> {
                val arrow = Path().apply {
                    moveTo(2f, 2f)
                    lineTo(2f, height * 0.66f)
                    lineTo(width * 0.3f, height * 0.46f)
                    lineTo(width * 0.5f, height * 0.82f)
                    lineTo(width * 0.66f, height * 0.75f)
                    lineTo(width * 0.46f, height * 0.4f)
                    lineTo(width * 0.72f, height * 0.38f)
                    close()
                }
                canvas.drawPath(arrow, fill)
                if (outline.strokeWidth > 0f) canvas.drawPath(arrow, outline)
            }
            else -> {
                val arrow = Path().apply {
                    moveTo(0f, 0f)
                    lineTo(0f, height * 0.76f)
                    lineTo(width * 0.26f, height * 0.56f)
                    lineTo(width * 0.43f, height * 0.94f)
                    lineTo(width * 0.62f, height * 0.86f)
                    lineTo(width * 0.45f, height * 0.49f)
                    lineTo(width * 0.78f, height * 0.47f)
                    close()
                }
                canvas.drawPath(arrow, fill)
                if (outline.strokeWidth > 0f) canvas.drawPath(arrow, outline)
            }
        }
    }

    private fun applyCursorPosition(xNorm: Float, yNorm: Float) {
        if (!cursorVisible) return
        val style = SettingsStore.cursorStyle()
        if (styleKey(style) != currentStyleKey) {
            rebuildCursor(style)
            return
        }
        val view = cursorView ?: return
        val params = cursorParams ?: return
        val manager = windowManager ?: return
        val point = physicalPoint(xNorm, yNorm)
        val hotspotX = (style.hotspotX * params.width).toInt()
        val hotspotY = (style.hotspotY * params.height).toInt()
        params.x = (point.first - hotspotX).coerceIn(
            mapper.usableLeft - hotspotX,
            mapper.usableRight - (params.width - hotspotX),
        )
        params.y = (point.second - hotspotY).coerceIn(
            mapper.usableTop - hotspotY,
            mapper.usableBottom - (params.height - hotspotY),
        )
        runCatching { manager.updateViewLayout(view, params) }
    }

    private fun removeCursor() {
        val view = cursorView ?: return
        val manager = windowManager ?: return
        runCatching { manager.removeView(view) }
        cursorView = null
        cursorParams = null
    }

    companion object {
        var instance: InputAccessibilityService? = null
            private set
    }
}
