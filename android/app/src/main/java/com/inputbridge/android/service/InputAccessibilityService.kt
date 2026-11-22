package com.inputbridge.android.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.accessibilityservice.GestureDescription
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PixelFormat
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import org.json.JSONObject

class InputAccessibilityService : AccessibilityService() {
    private var pendingButton: String = ""
    private var pendingX = 0f
    private var pendingY = 0f
    private var cursorView: View? = null
    private var cursorParams: WindowManager.LayoutParams? = null
    private var cursorVisible = false
    private var cursorAddLogged = false
    private var windowManager: WindowManager? = null
    private var screenWidth = 1
    private var screenHeight = 1
    private var statusBarHeight = 0
    private var navigationBarHeight = 0
    private val mainHandler = Handler(Looper.getMainLooper())
    private val pendingCursor = floatArrayOf(0.5f, 0.5f)
    private var cursorUpdateScheduled = false
    private val cursorUpdateRunnable = Runnable {
        cursorUpdateScheduled = false
        applyCursorPosition(pendingCursor[0], pendingCursor[1])
    }
    private var pendingWheel = 0
    private var wheelUpdateScheduled = false
    private val wheelUpdateRunnable = Runnable {
        wheelUpdateScheduled = false
        val delta = pendingWheel
        pendingWheel = 0
        if (delta != 0) dispatchSwipe(0.5f, 0.5f, 0.5f, if (delta > 0) 0.75f else 0.25f, 140)
    }

    override fun onCreate() {
        super.onCreate()
        refreshMetrics()
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
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {}

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
                moveCursor(
                    payload.optDouble("x", pendingX.toDouble()).toFloat(),
                    payload.optDouble("y", pendingY.toDouble()).toFloat(),
                )
            }
            "down" -> {
                pendingButton = payload.optString("button", "left")
                pendingX = payload.optDouble("x", 0.5).toFloat()
                pendingY = payload.optDouble("y", 0.5).toFloat()
                moveCursor(pendingX, pendingY)
            }
            "up" -> {
                val button = pendingButton.ifEmpty { payload.optString("button", "left") }
                val x = payload.optDouble("x", pendingX.toDouble()).toFloat()
                val y = payload.optDouble("y", pendingY.toDouble()).toFloat()
                moveCursor(x, y)
                pendingButton = ""
                when (button) {
                    "left" -> tap(x, y, 90)
                    "right" -> tap(x, y, 550)
                    "middle" -> globalAction(GLOBAL_ACTION_RECENTS)
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
                4 -> performGlobalAction(GLOBAL_ACTION_BACK)
                187 -> performGlobalAction(GLOBAL_ACTION_RECENTS)
                27 -> performGlobalAction(GLOBAL_ACTION_BACK)
            }
        }
    }

    private fun globalAction(action: Int) {
        mainHandler.post { performGlobalAction(action) }
    }

    private fun queueWheel(delta: Int) {
        if (delta == 0) return
        synchronized(this) {
            pendingWheel = (pendingWheel + delta).coerceIn(-3, 3)
            if (!wheelUpdateScheduled) {
                wheelUpdateScheduled = true
                mainHandler.post(wheelUpdateRunnable)
            }
        }
    }

    private fun tap(xNorm: Float, yNorm: Float, duration: Long) {
        mainHandler.post { dispatchTap(xNorm, yNorm, duration) }
    }

    private fun dispatchTap(xNorm: Float, yNorm: Float, duration: Long) {
        val path = Path().apply { moveTo(screenX(xNorm).toFloat(), screenY(yNorm).toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, duration)
        dispatchGesture(GestureDescription.Builder().addStroke(stroke).build(), null, null)
    }

    private fun swipe(x1: Float, y1: Float, x2: Float, y2: Float, duration: Long) {
        mainHandler.post { dispatchSwipe(x1, y1, x2, y2, duration) }
    }

    private fun dispatchSwipe(x1: Float, y1: Float, x2: Float, y2: Float, duration: Long) {
        val path = Path().apply {
            moveTo(screenX(x1).toFloat(), screenY(y1).toFloat())
            lineTo(screenX(x2).toFloat(), screenY(y2).toFloat())
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
            .build()
        dispatchGesture(gesture, null, null)
    }

    private fun addCursor() {
        refreshMetrics()
        val manager = windowManager ?: return
        val density = resources.displayMetrics.density
        val width = (28 * density).toInt().coerceAtLeast(1)
        val height = (32 * density).toInt().coerceAtLeast(1)
        val types = mutableListOf(WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY)
        if (Settings.canDrawOverlays(this)) {
            types.add(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY)
        }
        var lastError: Throwable? = null
        for (type in types) {
            val view = object : View(this@InputAccessibilityService) {
                private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    color = Color.WHITE
                    style = Paint.Style.FILL
                }
                private val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    color = Color.rgb(25, 28, 32)
                    style = Paint.Style.STROKE
                    strokeWidth = 2f * density
                    strokeJoin = Paint.Join.ROUND
                }
                private val arrow = Path()

                override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
                    arrow.reset()
                    arrow.moveTo(0f, 0f)
                    arrow.lineTo(0f, h * 0.76f)
                    arrow.lineTo(w * 0.26f, h * 0.56f)
                    arrow.lineTo(w * 0.43f, h * 0.94f)
                    arrow.lineTo(w * 0.62f, h * 0.86f)
                    arrow.lineTo(w * 0.45f, h * 0.49f)
                    arrow.lineTo(w * 0.78f, h * 0.47f)
                    arrow.close()
                }

                override fun onDraw(canvas: Canvas) {
                    canvas.drawPath(arrow, fill)
                    canvas.drawPath(arrow, outline)
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
                moveCursor(0.5f, 0.5f)
                if (!cursorAddLogged) {
                    cursorAddLogged = true
                    BridgeRuntime.log(
                        if (type == WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY) {
                            "Cursor overlay added (accessibility)"
                        } else {
                            "Cursor overlay added (draw over apps)"
                        }
                    )
                }
                return
            }
            lastError = result.exceptionOrNull()
            runCatching { manager.removeView(view) }
        }
        BridgeRuntime.log("Cursor overlay failed: ${lastError?.message ?: "no window type available"}; grant Display over other apps")
    }

    fun refreshCursor() {
        refreshMetrics()
        removeCursor()
        addCursor()
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
            if (visible) applyCursorPosition(pendingCursor[0], pendingCursor[1])
        }
    }

    private fun refreshMetrics() {
        windowManager = getSystemService(WINDOW_SERVICE) as? WindowManager
        val metrics = resources.displayMetrics
        screenWidth = metrics.widthPixels.coerceAtLeast(1)
        screenHeight = metrics.heightPixels.coerceAtLeast(1)
        statusBarHeight = dimension("status_bar_height")
        navigationBarHeight = dimension("navigation_bar_height")
    }

    private fun dimension(name: String): Int {
        val id = resources.getIdentifier(name, "dimen", "android")
        return if (id > 0) resources.getDimensionPixelSize(id) else 0
    }

    private fun screenX(norm: Float): Int {
        return (norm.coerceIn(0f, 1f) * screenWidth).toInt().coerceIn(0, screenWidth - 1)
    }

    private fun screenY(norm: Float): Int {
        val usable = (screenHeight - statusBarHeight - navigationBarHeight).coerceAtLeast(1)
        return (statusBarHeight + norm.coerceIn(0f, 1f) * usable).toInt().coerceIn(0, screenHeight - 1)
    }

    private fun moveCursor(xNorm: Float, yNorm: Float) {
        synchronized(this) {
            pendingCursor[0] = xNorm
            pendingCursor[1] = yNorm
            if (!cursorUpdateScheduled) {
                cursorUpdateScheduled = true
                mainHandler.post(cursorUpdateRunnable)
            }
        }
    }

    private fun applyCursorPosition(xNorm: Float, yNorm: Float) {
        if (!cursorVisible) return
        val view = cursorView ?: return
        val params = cursorParams ?: return
        val manager = windowManager ?: return
        params.x = screenX(xNorm).coerceIn(0, (screenWidth - params.width).coerceAtLeast(0))
        params.y = screenY(yNorm).coerceIn(0, (screenHeight - params.height).coerceAtLeast(0))
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
