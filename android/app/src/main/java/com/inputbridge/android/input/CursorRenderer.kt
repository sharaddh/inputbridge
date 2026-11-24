package com.inputbridge.android.input

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.view.View
import com.inputbridge.android.settings.SettingsStore
import kotlin.math.min
import kotlin.math.roundToInt

class CursorRenderer(context: Context) : View(context) {
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val outlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeJoin = Paint.Join.ROUND
        strokeCap = Paint.Cap.ROUND
    }
    private val arrowPath = Path()
    private var style = SettingsStore.cursorStyle()
    private var size = 1

    fun setStyle(value: SettingsStore.CursorStyle) {
        style = value
        val density = resources.displayMetrics.density
        size = (value.sizeDp * density).roundToInt().coerceAtLeast(1)
        fillPaint.color = value.fillColor
        outlinePaint.color = value.outlineColor
        outlinePaint.strokeWidth = if (value.shape == "crosshair") {
            (value.outlineWidthDp * density).coerceAtLeast(1.5f * density)
        } else {
            value.outlineWidthDp * density
        }
        rebuildPath()
        invalidate()
    }

    fun sizePx(): Int = size

    fun hotspotXPx(): Float = style.hotspotX.coerceIn(0f, 1f) * size

    fun hotspotYPx(): Float = style.hotspotY.coerceIn(0f, 1f) * size

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        rebuildPath()
    }

    override fun onDraw(canvas: Canvas) {
        when (style.shape) {
            "dot" -> drawDot(canvas)
            "crosshair" -> drawCrosshair(canvas)
            else -> {
                canvas.drawPath(arrowPath, fillPaint)
                if (outlinePaint.strokeWidth > 0f) canvas.drawPath(arrowPath, outlinePaint)
                drawHotspotMarker(canvas)
            }
        }
    }

    private fun drawDot(canvas: Canvas) {
        val radius = (min(width, height) / 2f - outlinePaint.strokeWidth).coerceAtLeast(1f)
        val cx = width / 2f
        val cy = height / 2f
        canvas.drawCircle(cx, cy, radius, fillPaint)
        if (outlinePaint.strokeWidth > 0f) canvas.drawCircle(cx, cy, radius, outlinePaint)
    }

    private fun drawCrosshair(canvas: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val half = min(width, height) / 2f
        canvas.drawLine(cx - half, cy, cx + half, cy, outlinePaint)
        canvas.drawLine(cx, cy - half, cx, cy + half, outlinePaint)
        canvas.drawCircle(cx, cy, (size / 8f).coerceAtLeast(1f), fillPaint)
    }

    private fun drawHotspotMarker(canvas: Canvas) {
        if (style.hotspotX <= 0f && style.hotspotY <= 0f) return
        val radius = 1.5f * resources.displayMetrics.density
        canvas.drawCircle(hotspotXPx(), hotspotYPx(), radius, outlinePaint)
    }

    private fun rebuildPath() {
        arrowPath.reset()
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        if (style.shape == "dot" || style.shape == "crosshair") return
        val tipX = w * if (style.shape == "compact") 0.72f else 1f
        arrowPath.moveTo(0f, 0f)
        arrowPath.lineTo(0f, h * 0.80f)
        arrowPath.lineTo(tipX * 0.24f, h * 0.60f)
        arrowPath.lineTo(tipX * 0.44f, h * 0.96f)
        arrowPath.lineTo(tipX * 0.62f, h * 0.86f)
        arrowPath.lineTo(tipX * 0.43f, h * 0.50f)
        arrowPath.lineTo(tipX * 0.82f, h * 0.47f)
        arrowPath.close()
    }
}
