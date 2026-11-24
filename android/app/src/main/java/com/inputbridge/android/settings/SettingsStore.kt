package com.inputbridge.android.settings

import android.content.Context
import android.content.SharedPreferences
import android.graphics.Color

object SettingsStore {
    data class CursorStyle(
        val shape: String,
        val sizeDp: Int,
        val fillColor: Int,
        val outlineColor: Int,
        val outlineWidthDp: Float,
        val hotspotX: Float,
        val hotspotY: Float,
    )

    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        if (prefs == null) {
            prefs = context.applicationContext.getSharedPreferences("inputbridge_settings", Context.MODE_PRIVATE)
        }
    }

    private fun string(key: String, default: String): String = prefs?.getString(key, default) ?: default
    private fun int(key: String, default: Int): Int = prefs?.getInt(key, default) ?: default
    private fun float(key: String, default: Float): Float = prefs?.getFloat(key, default) ?: default
    private fun put(block: SharedPreferences.Editor.() -> Unit) {
        prefs?.edit()?.apply(block)?.apply()
    }

    var deviceName: String
        get() = string("device_name", "This phone")
        set(value) = put { putString("device_name", value) }

    var themeMode: String
        get() = string("theme_mode", "system")
        set(value) = put { putString("theme_mode", value) }

    var pointerRateHz: Int
        get() = int("pointer_rate_hz", 60).coerceIn(30, 120)
        set(value) = put { putInt("pointer_rate_hz", value.coerceIn(30, 120)) }

    var scrollDirection: Int
        get() = if (int("scroll_direction", 1) >= 0) 1 else -1
        set(value) = put { putInt("scroll_direction", if (value >= 0) 1 else -1) }

    var scrollSensitivity: Float
        get() = float("scroll_sensitivity", 1f).coerceIn(0.5f, 2f)
        set(value) = put { putFloat("scroll_sensitivity", value.coerceIn(0.5f, 2f)) }

    var rightButtonAction: String
        get() = string("right_button_action", "context_menu")
        set(value) = put { putString("right_button_action", value) }

    var middleButtonAction: String
        get() = string("middle_button_action", "recents")
        set(value) = put { putString("middle_button_action", value) }

    var calibrationOffsetX: Int
        get() = int("calibration_x", 0)
        set(value) = put { putInt("calibration_x", value) }

    var calibrationOffsetY: Int
        get() = int("calibration_y", 0)
        set(value) = put { putInt("calibration_y", value) }

    var cursorShape: String
        get() = string("cursor_shape", "classic")
        set(value) {
            put { putString("cursor_shape", value) }
            when (value) {
                "dot", "crosshair" -> setHotspot(0.5f, 0.5f)
                "compact" -> setHotspot(0.1f, 0f)
                else -> setHotspot(0f, 0f)
            }
        }

    var cursorSizeDp: Int
        get() = int("cursor_size_dp", 28).coerceIn(16, 56)
        set(value) = put { putInt("cursor_size_dp", value.coerceIn(16, 56)) }

    var cursorFillColor: Int
        get() = int("cursor_fill", Color.WHITE)
        set(value) = put { putInt("cursor_fill", value) }

    var cursorOutlineColor: Int
        get() = int("cursor_outline", Color.rgb(25, 28, 32))
        set(value) = put { putInt("cursor_outline", value) }

    var cursorOutlineWidthDp: Float
        get() = float("cursor_outline_width", 2f).coerceIn(0f, 5f)
        set(value) = put { putFloat("cursor_outline_width", value.coerceIn(0f, 5f)) }

    var cursorHotspotX: Float
        get() = float("cursor_hotspot_x", 0f).coerceIn(0f, 1f)
        private set(value) = put { putFloat("cursor_hotspot_x", value.coerceIn(0f, 1f)) }

    var cursorHotspotY: Float
        get() = float("cursor_hotspot_y", 0f).coerceIn(0f, 1f)
        private set(value) = put { putFloat("cursor_hotspot_y", value.coerceIn(0f, 1f)) }

    fun setHotspot(x: Float, y: Float) {
        cursorHotspotX = x.coerceIn(0f, 1f)
        cursorHotspotY = y.coerceIn(0f, 1f)
    }

    fun cursorStyle(): CursorStyle = CursorStyle(
        shape = cursorShape,
        sizeDp = cursorSizeDp,
        fillColor = cursorFillColor,
        outlineColor = cursorOutlineColor,
        outlineWidthDp = cursorOutlineWidthDp,
        hotspotX = cursorHotspotX,
        hotspotY = cursorHotspotY,
    )

    fun setCalibration(x: Int, y: Int) {
        calibrationOffsetX = x.coerceIn(-200, 200)
        calibrationOffsetY = y.coerceIn(-200, 200)
    }

    fun resetCursor() {
        put {
            putString("cursor_shape", "classic")
            putInt("cursor_size_dp", 28)
            putInt("cursor_fill", Color.WHITE)
            putInt("cursor_outline", Color.rgb(25, 28, 32))
            putFloat("cursor_outline_width", 2f)
            putFloat("cursor_hotspot_x", 0f)
            putFloat("cursor_hotspot_y", 0f)
            putInt("calibration_x", 0)
            putInt("calibration_y", 0)
        }
    }
}
