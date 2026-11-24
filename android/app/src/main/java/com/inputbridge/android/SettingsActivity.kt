package com.inputbridge.android

import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.os.Bundle
import android.util.AttributeSet
import android.view.View
import android.widget.AdapterView
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.RadioGroup
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.content.ContextCompat
import com.inputbridge.android.service.BridgeRuntime
import com.inputbridge.android.service.InputAccessibilityService
import com.inputbridge.android.settings.SettingsStore

internal fun applyAppTheme() {
    val mode = when (SettingsStore.themeMode) {
        "light" -> AppCompatDelegate.MODE_NIGHT_NO
        "dark" -> AppCompatDelegate.MODE_NIGHT_YES
        else -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
    }
    if (AppCompatDelegate.getDefaultNightMode() != mode) {
        AppCompatDelegate.setDefaultNightMode(mode)
    }
}

private fun drawArrow(
    canvas: Canvas,
    left: Float,
    top: Float,
    size: Float,
    fillPaint: Paint,
    outlinePaint: Paint,
) {
    val path = Path()
    path.moveTo(left, top)
    path.lineTo(left, top + size)
    path.lineTo(left + size * 0.24f, top + size * 0.74f)
    path.lineTo(left + size * 0.46f, top + size)
    path.lineTo(left + size * 0.62f, top + size * 0.9f)
    path.lineTo(left + size * 0.39f, top + size * 0.64f)
    path.lineTo(left + size, top + size * 0.52f)
    path.close()
    canvas.drawPath(path, fillPaint)
    if (outlinePaint.strokeWidth > 0f) canvas.drawPath(path, outlinePaint)
}

internal fun drawCursorShape(
    canvas: Canvas,
    style: SettingsStore.CursorStyle,
    left: Float,
    top: Float,
    size: Float,
    outlineWidthPx: Float,
) {
    val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = style.fillColor
        setStyle(Paint.Style.FILL)
    }
    val outlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = style.outlineColor
        setStyle(Paint.Style.STROKE)
        strokeWidth = outlineWidthPx
        strokeJoin = Paint.Join.ROUND
        strokeCap = Paint.Cap.ROUND
    }
    when (style.shape) {
        "dot" -> {
            val radius = (size / 2f - outlineWidthPx).coerceAtLeast(1f)
            val cx = left + size / 2f
            val cy = top + size / 2f
            canvas.drawCircle(cx, cy, radius, fillPaint)
            if (outlineWidthPx > 0f) canvas.drawCircle(cx, cy, radius, outlinePaint)
        }
        "crosshair" -> {
            val cx = left + size / 2f
            val cy = top + size / 2f
            canvas.drawLine(cx - size / 2f, cy, cx + size / 2f, cy, outlinePaint)
            canvas.drawLine(cx, cy - size / 2f, cx, cy + size / 2f, outlinePaint)
            canvas.drawCircle(cx, cy, (size / 8f).coerceAtLeast(1f), fillPaint)
        }
        "compact" -> drawArrow(canvas, left, top, size * 0.75f, fillPaint, outlinePaint)
        else -> drawArrow(canvas, left, top, size, fillPaint, outlinePaint)
    }
}

class CursorPreviewView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {
    private var style = SettingsStore.cursorStyle()
    private val guidePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.divider)
        strokeWidth = 1f
        setStyle(Paint.Style.STROKE)
    }
    private val hotspotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.primary)
        setStyle(Paint.Style.FILL)
    }

    fun setStyle(value: SettingsStore.CursorStyle) {
        style = value
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val cx = width / 2f
        val cy = height / 2f
        val guide = 28f * resources.displayMetrics.density
        canvas.drawLine(cx - guide, cy, cx + guide, cy, guidePaint)
        canvas.drawLine(cx, cy - guide, cx, cy + guide, guidePaint)
        val density = resources.displayMetrics.density
        val size = style.sizeDp * density
        drawCursorShape(
            canvas,
            style,
            cx - size * style.hotspotX,
            cy - size * style.hotspotY,
            size,
            style.outlineWidthDp * density,
        )
        canvas.drawCircle(cx, cy, 3f, hotspotPaint)
    }
}

class SettingsActivity : AppCompatActivity() {
    private val cursorColors = listOf(Color.WHITE, Color.BLACK, Color.BLUE, Color.RED, Color.YELLOW, Color.GREEN)
    private var loading = true

    override fun onCreate(savedInstanceState: Bundle?) {
        SettingsStore.init(this)
        applyAppTheme()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)
        findViewById<ImageButton>(R.id.btnSettingsBack).setOnClickListener { finish() }
        bindControls()
        loadValues()
    }

    override fun onPause() {
        if (!loading) {
            val name = findViewById<EditText>(R.id.etDeviceName).text.toString().trim()
            if (name.isNotEmpty()) SettingsStore.deviceName = name
            BridgeRuntime.invalidateCapabilities()
            InputAccessibilityService.instance?.refreshCursor()
        }
        super.onPause()
    }

    private fun bindControls() {
        findViewById<Button>(R.id.btnSaveDevice).setOnClickListener {
            val name = findViewById<EditText>(R.id.etDeviceName).text.toString().trim()
            if (name.isEmpty()) {
                Toast.makeText(this, getString(R.string.device_name_hint), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            SettingsStore.deviceName = name
            Toast.makeText(this, R.string.saved, Toast.LENGTH_SHORT).show()
        }

        findViewById<RadioGroup>(R.id.rgTheme).setOnCheckedChangeListener { _, id ->
            if (loading) return@setOnCheckedChangeListener
            SettingsStore.themeMode = when (id) {
                R.id.rbThemeLight -> "light"
                R.id.rbThemeDark -> "dark"
                else -> "system"
            }
            applyAppTheme()
            recreate()
        }

        findViewById<RadioGroup>(R.id.rgPointerRate).setOnCheckedChangeListener { _, id ->
            if (loading) return@setOnCheckedChangeListener
            SettingsStore.pointerRateHz = when (id) {
                R.id.rbRate30 -> 30
                R.id.rbRate120 -> 120
                else -> 60
            }
        }

        findViewById<RadioGroup>(R.id.rgScrollDirection).setOnCheckedChangeListener { _, id ->
            if (loading) return@setOnCheckedChangeListener
            SettingsStore.scrollDirection = if (id == R.id.rbScrollReversed) -1 else 1
        }

        findViewById<SeekBar>(R.id.sbScrollSensitivity).setOnSeekBarChangeListener(
            seekBarListener { progress ->
                val value = progress / 100f
                SettingsStore.scrollSensitivity = value
                findViewById<TextView>(R.id.tvScrollSensitivityValue).text =
                    getString(R.string.value_decimal, value)
            },
        )

        findViewById<RadioGroup>(R.id.rgRightButton).setOnCheckedChangeListener { _, id ->
            if (loading) return@setOnCheckedChangeListener
            SettingsStore.rightButtonAction = when (id) {
                R.id.rbRightBack -> "back"
                R.id.rbRightNone -> "none"
                else -> "context_menu"
            }
        }

        findViewById<RadioGroup>(R.id.rgMiddleButton).setOnCheckedChangeListener { _, id ->
            if (loading) return@setOnCheckedChangeListener
            SettingsStore.middleButtonAction = if (id == R.id.rbMiddleNone) "none" else "recents"
        }

        findViewById<RadioGroup>(R.id.rgCursorShape).setOnCheckedChangeListener { _, id ->
            if (loading) return@setOnCheckedChangeListener
            SettingsStore.cursorShape = when (id) {
                R.id.rbShapeCompact -> "compact"
                R.id.rbShapeDot -> "dot"
                R.id.rbShapeCrosshair -> "crosshair"
                else -> "classic"
            }
            SettingsStore.setHotspot(
                findViewById<SeekBar>(R.id.sbHotspotX).progress / 100f,
                findViewById<SeekBar>(R.id.sbHotspotY).progress / 100f,
            )
            refreshPreview()
        }

        findViewById<SeekBar>(R.id.sbCursorSize).setOnSeekBarChangeListener(
            seekBarListener { progress ->
                val value = progress + 16
                SettingsStore.cursorSizeDp = value
                findViewById<TextView>(R.id.tvCursorSizeValue).text = getString(R.string.value_dp, value)
                refreshPreview()
            },
        )

        bindColorSpinner(R.id.spFillColor) { color ->
            SettingsStore.cursorFillColor = color
            refreshPreview()
        }
        bindColorSpinner(R.id.spOutlineColor) { color ->
            SettingsStore.cursorOutlineColor = color
            refreshPreview()
        }

        findViewById<SeekBar>(R.id.sbOutlineWidth).setOnSeekBarChangeListener(
            seekBarListener { progress ->
                val value = progress / 10f
                SettingsStore.cursorOutlineWidthDp = value
                findViewById<TextView>(R.id.tvOutlineWidthValue).text =
                    getString(R.string.value_decimal, value)
                refreshPreview()
            },
        )

        findViewById<SeekBar>(R.id.sbHotspotX).setOnSeekBarChangeListener(
            seekBarListener { progress ->
                SettingsStore.setHotspot(
                    progress / 100f,
                    findViewById<SeekBar>(R.id.sbHotspotY).progress / 100f,
                )
                findViewById<TextView>(R.id.tvHotspotXValue).text =
                    getString(R.string.value_percent, progress)
                refreshPreview()
            },
        )

        findViewById<SeekBar>(R.id.sbHotspotY).setOnSeekBarChangeListener(
            seekBarListener { progress ->
                SettingsStore.setHotspot(
                    findViewById<SeekBar>(R.id.sbHotspotX).progress / 100f,
                    progress / 100f,
                )
                findViewById<TextView>(R.id.tvHotspotYValue).text =
                    getString(R.string.value_percent, progress)
                refreshPreview()
            },
        )

        findViewById<Button>(R.id.btnResetCursor).setOnClickListener {
            SettingsStore.resetCursor()
            loadValues()
        }
        findViewById<Button>(R.id.btnOpenCalibration).setOnClickListener {
            startActivity(Intent(this, CalibrationActivity::class.java))
        }
        findViewById<Button>(R.id.btnResetCalibration).setOnClickListener {
            SettingsStore.setCalibration(0, 0)
            Toast.makeText(this, R.string.saved, Toast.LENGTH_SHORT).show()
        }
    }

    private fun seekBarListener(onProgress: (Int) -> Unit): SeekBar.OnSeekBarChangeListener =
        object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                if (!loading && fromUser) onProgress(progress)
            }

            override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit

            override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
        }

    private fun bindColorSpinner(id: Int, onColor: (Int) -> Unit) {
        findViewById<Spinner>(id).onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, itemId: Long) {
                if (!loading) onColor(cursorColors[position])
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
    }

    private fun loadValues() {
        loading = true
        findViewById<EditText>(R.id.etDeviceName).setText(SettingsStore.deviceName)

        findViewById<RadioGroup>(R.id.rgTheme).check(
            when (SettingsStore.themeMode) {
                "light" -> R.id.rbThemeLight
                "dark" -> R.id.rbThemeDark
                else -> R.id.rbThemeSystem
            },
        )
        findViewById<RadioGroup>(R.id.rgPointerRate).check(
            when (SettingsStore.pointerRateHz) {
                30 -> R.id.rbRate30
                120 -> R.id.rbRate120
                else -> R.id.rbRate60
            },
        )
        findViewById<RadioGroup>(R.id.rgScrollDirection).check(
            if (SettingsStore.scrollDirection < 0) R.id.rbScrollReversed else R.id.rbScrollNatural,
        )
        val sensitivity = ((SettingsStore.scrollSensitivity - 0.5f) * 100f).toInt()
        findViewById<SeekBar>(R.id.sbScrollSensitivity).progress = sensitivity
        findViewById<TextView>(R.id.tvScrollSensitivityValue).text =
            getString(R.string.value_decimal, SettingsStore.scrollSensitivity)

        findViewById<RadioGroup>(R.id.rgRightButton).check(
            when (SettingsStore.rightButtonAction) {
                "back" -> R.id.rbRightBack
                "none" -> R.id.rbRightNone
                else -> R.id.rbRightContext
            },
        )
        findViewById<RadioGroup>(R.id.rgMiddleButton).check(
            if (SettingsStore.middleButtonAction == "none") R.id.rbMiddleNone else R.id.rbMiddleRecents,
        )

        findViewById<RadioGroup>(R.id.rgCursorShape).check(
            when (SettingsStore.cursorShape) {
                "compact" -> R.id.rbShapeCompact
                "dot" -> R.id.rbShapeDot
                "crosshair" -> R.id.rbShapeCrosshair
                else -> R.id.rbShapeClassic
            },
        )
        val size = SettingsStore.cursorSizeDp
        findViewById<SeekBar>(R.id.sbCursorSize).progress = size - 16
        findViewById<TextView>(R.id.tvCursorSizeValue).text = getString(R.string.value_dp, size)

        val style = SettingsStore.cursorStyle()
        findViewById<Spinner>(R.id.spFillColor).setSelection(
            cursorColors.indexOf(style.fillColor).coerceAtLeast(0),
        )
        findViewById<Spinner>(R.id.spOutlineColor).setSelection(
            cursorColors.indexOf(style.outlineColor).coerceAtLeast(0),
        )
        val outlineWidth = (SettingsStore.cursorOutlineWidthDp * 10f).toInt()
        findViewById<SeekBar>(R.id.sbOutlineWidth).progress = outlineWidth
        findViewById<TextView>(R.id.tvOutlineWidthValue).text =
            getString(R.string.value_decimal, SettingsStore.cursorOutlineWidthDp)

        val hotspotX = (style.hotspotX * 100f).toInt()
        val hotspotY = (style.hotspotY * 100f).toInt()
        findViewById<SeekBar>(R.id.sbHotspotX).progress = hotspotX
        findViewById<SeekBar>(R.id.sbHotspotY).progress = hotspotY
        findViewById<TextView>(R.id.tvHotspotXValue).text = getString(R.string.value_percent, hotspotX)
        findViewById<TextView>(R.id.tvHotspotYValue).text = getString(R.string.value_percent, hotspotY)
        refreshPreview()
        loading = false
    }

    private fun refreshPreview() {
        findViewById<CursorPreviewView>(R.id.cursorPreview).setStyle(SettingsStore.cursorStyle())
    }
}
