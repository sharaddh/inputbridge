package com.inputbridge.android

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.os.Bundle
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.inputbridge.android.settings.SettingsStore
import kotlin.math.roundToInt

class CalibrationView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {
    var onTap: ((Int, Int) -> Unit)? = null
    private var tapX: Float? = null
    private var tapY: Float? = null
    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.divider)
        strokeWidth = 1f
        setStyle(Paint.Style.STROKE)
    }
    private val targetPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.primary)
        strokeWidth = 3f
        setStyle(Paint.Style.STROKE)
    }
    private val crossPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.primary)
        strokeWidth = 4f
        strokeCap = Paint.Cap.ROUND
        setStyle(Paint.Style.STROKE)
    }
    private val linkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.text_secondary)
        strokeWidth = 2f
        setStyle(Paint.Style.STROKE)
    }
    private val tapPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.text_primary)
        strokeWidth = 3f
        strokeCap = Paint.Cap.ROUND
        setStyle(Paint.Style.STROKE)
    }

    fun clearTap() {
        tapX = null
        tapY = null
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val cx = width / 2f
        val cy = height / 2f
        canvas.drawLine(0f, cy, width.toFloat(), cy, gridPaint)
        canvas.drawLine(cx, 0f, cx, height.toFloat(), gridPaint)
        val radius = 56f * resources.displayMetrics.density
        canvas.drawCircle(cx, cy, radius, targetPaint)
        val arm = radius * 0.5f
        canvas.drawLine(cx - arm, cy, cx + arm, cy, crossPaint)
        canvas.drawLine(cx, cy - arm, cx, cy + arm, crossPaint)
        val x = tapX
        val y = tapY
        if (x != null && y != null) {
            canvas.drawLine(cx, cy, x, y, linkPaint)
            canvas.drawCircle(x, y, 14f, tapPaint)
            canvas.drawLine(x - 26f, y, x + 26f, y, tapPaint)
            canvas.drawLine(x, y - 26f, x, y + 26f, tapPaint)
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> return true
            MotionEvent.ACTION_UP -> {
                tapX = event.x
                tapY = event.y
                val dx = (width / 2f - event.x).roundToInt()
                val dy = (height / 2f - event.y).roundToInt()
                onTap?.invoke(dx, dy)
                invalidate()
                performClick()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }
}

class CalibrationActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        SettingsStore.init(this)
        applyAppTheme()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_calibration)

        val view = findViewById<CalibrationView>(R.id.calibrationView)
        val offsetView = findViewById<TextView>(R.id.tvCalibrationOffset)

        fun showOffset() {
            offsetView.text = getString(
                R.string.calibration_offset,
                SettingsStore.calibrationOffsetX,
                SettingsStore.calibrationOffsetY,
            )
        }

        showOffset()
        view.onTap = { dx, dy ->
            SettingsStore.setCalibration(dx, dy)
            showOffset()
            Toast.makeText(this, R.string.toast_calibration_saved, Toast.LENGTH_SHORT).show()
        }
        findViewById<Button>(R.id.btnResetCalibration).setOnClickListener {
            SettingsStore.setCalibration(0, 0)
            view.clearTap()
            showOffset()
        }
        findViewById<Button>(R.id.btnCalibrationDone).setOnClickListener { finish() }
        findViewById<ImageButton>(R.id.btnCalibrationBack).setOnClickListener { finish() }
    }
}
