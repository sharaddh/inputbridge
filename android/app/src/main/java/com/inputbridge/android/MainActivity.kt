package com.inputbridge.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.inputbridge.android.qr.QrPayload
import com.inputbridge.android.service.BridgeForegroundService
import com.inputbridge.android.service.BridgeRuntime
import com.inputbridge.android.service.InputAccessibilityService
import com.inputbridge.android.settings.SettingsStore

private fun linkLabel(link: BridgeRuntime.LinkState): Int = when (link) {
    BridgeRuntime.LinkState.CONNECTED -> R.string.state_connected
    BridgeRuntime.LinkState.PAIRED -> R.string.state_paired
    BridgeRuntime.LinkState.CONNECTING -> R.string.state_connecting
    BridgeRuntime.LinkState.STOPPED -> R.string.state_not_connected
}

private fun sanitizeLogs(lines: List<String>): String {
    val redacted = lines.takeLast(40).mapNotNull { line ->
        val lower = line.lowercase()
        when {
            lower.contains("token") || lower.contains("password") || lower.contains("secret") -> null
            lower.contains("typed") || lower.contains("key:") -> null
            else -> line.replace(Regex("[0-9a-fA-F]{32,}"), "[redacted]")
        }
    }
    return redacted.joinToString("\n")
}

class MainActivity : AppCompatActivity() {
    private lateinit var stateView: TextView
    private lateinit var deviceView: TextView
    private lateinit var sessionView: TextView
    private lateinit var messageView: TextView
    private lateinit var capsView: TextView
    private lateinit var preview: CursorPreviewView
    private lateinit var checkPair: TextView
    private lateinit var checkAccess: TextView
    private lateinit var checkIme: TextView
    private lateinit var checkOverlay: TextView
    private lateinit var scanLauncher: ActivityResultLauncher<Intent>
    private lateinit var cameraLauncher: ActivityResultLauncher<String>
    private var lastStateText = ""
    private var lastLink: BridgeRuntime.LinkState? = null
    private var lastMessageText = ""
    private var lastCapsText = ""
    private val listener: (BridgeRuntime.Status) -> Unit = { status -> runOnUiThread { render(status) } }

    override fun onCreate(savedInstanceState: Bundle?) {
        SettingsStore.init(this)
        applyAppTheme()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        BridgeRuntime.init(this)

        stateView = findViewById(R.id.tvState)
        deviceView = findViewById(R.id.tvDeviceName)
        sessionView = findViewById(R.id.tvSessionHint)
        messageView = findViewById(R.id.tvMessage)
        capsView = findViewById(R.id.tvCaps)
        preview = findViewById(R.id.cursorPreview)
        checkPair = findViewById(R.id.tvCheckPair)
        checkAccess = findViewById(R.id.tvCheckAccess)
        checkIme = findViewById(R.id.tvCheckIme)
        checkOverlay = findViewById(R.id.tvCheckOverlay)

        scanLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode != RESULT_OK) return@registerForActivityResult
            val text = result.data?.getStringExtra(QrScanActivity.EXTRA_QR)
            try {
                val config = QrPayload.parse(text)
                BridgeRuntime.connectQr(this, config.host, config.port, config.tokenHex)
                BridgeForegroundService.start(this)
                Toast.makeText(this, R.string.toast_connecting, Toast.LENGTH_SHORT).show()
            } catch (e: IllegalArgumentException) {
                Toast.makeText(
                    this,
                    getString(R.string.toast_invalid_qr, e.message ?: ""),
                    Toast.LENGTH_LONG,
                ).show()
            }
        }

        cameraLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) scanLauncher.launch(Intent(this, QrScanActivity::class.java))
            else Toast.makeText(this, R.string.toast_camera_needed, Toast.LENGTH_LONG).show()
        }

        findViewById<Button>(R.id.btnScan).setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                scanLauncher.launch(Intent(this, QrScanActivity::class.java))
            } else {
                cameraLauncher.launch(Manifest.permission.CAMERA)
            }
        }

        findViewById<Button>(R.id.btnDisconnect).setOnClickListener {
            BridgeRuntime.stopClient()
            BridgeForegroundService.stop(this)
        }

        findViewById<Button>(R.id.btnAccess).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        findViewById<Button>(R.id.btnIme).setOnClickListener {
            @Suppress("DEPRECATION")
            val manager = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            manager.showInputMethodPicker()
        }

        findViewById<Button>(R.id.btnRevoke).setOnClickListener {
            BridgeRuntime.revoke()
            BridgeForegroundService.stop(this)
            Toast.makeText(this, R.string.toast_pairing_revoked, Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btnOverlay).setOnClickListener {
            if (Settings.canDrawOverlays(this)) {
                InputAccessibilityService.instance?.refreshCursor()
                Toast.makeText(this, R.string.toast_overlay_refreshed, Toast.LENGTH_SHORT).show()
            } else {
                startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName"),
                    )
                )
            }
        }

        findViewById<ImageButton>(R.id.btnSettings).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        findViewById<Button>(R.id.btnCustomize).setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        findViewById<Button>(R.id.btnDiagnostics).setOnClickListener {
            startActivity(Intent(this, DiagnosticsActivity::class.java))
        }

        requestNotificationPermission()
    }

    override fun onStart() {
        super.onStart()
        BridgeRuntime.addListener(listener)
    }

    override fun onResume() {
        super.onResume()
        SettingsStore.init(this)
        applyAppTheme()
        preview.setStyle(SettingsStore.cursorStyle())
        InputAccessibilityService.instance?.refreshCursor()
    }

    override fun onStop() {
        BridgeRuntime.removeListener(listener)
        super.onStop()
    }

    private fun render(status: BridgeRuntime.Status) {
        val paired = status.paired || BridgeRuntime.savedTokenHex.isNotEmpty()
        val stateText = getString(linkLabel(status.link))
        if (stateText != lastStateText) {
            lastStateText = stateText
            stateView.text = stateText
        }
        if (status.link != lastLink) {
            lastLink = status.link
            val background: Int
            val textColor: Int
            when (status.link) {
                BridgeRuntime.LinkState.PAIRED -> {
                    background = R.drawable.bg_status_paired
                    textColor = R.color.status_paired_text
                }
                BridgeRuntime.LinkState.CONNECTED -> {
                    background = R.drawable.bg_status_connected
                    textColor = R.color.status_connected_text
                }
                BridgeRuntime.LinkState.CONNECTING -> {
                    background = R.drawable.bg_status_connecting
                    textColor = R.color.status_connecting_text
                }
                BridgeRuntime.LinkState.STOPPED -> {
                    background = R.drawable.bg_status_idle
                    textColor = R.color.status_idle_text
                }
            }
            stateView.setBackgroundResource(background)
            stateView.setTextColor(ContextCompat.getColor(this, textColor))
            sessionView.setText(
                if (status.link == BridgeRuntime.LinkState.CONNECTED) R.string.session_active else R.string.session_idle,
            )
        }

        val name = status.remoteName.ifEmpty { SettingsStore.deviceName }
        deviceView.text = if (status.remoteName.isEmpty()) name else getString(R.string.paired_device, name)

        val messageText = status.message.ifEmpty { getString(R.string.log_empty) }
        if (messageText != lastMessageText) {
            lastMessageText = messageText
            messageView.text = messageText
        }

        val caps = BridgeRuntime.capabilities()
        val ready = getString(R.string.availability_ready)
        val off = getString(R.string.availability_off)
        val access = if (caps.optBoolean("accessibility")) ready else off
        val keyboard = if (caps.optBoolean("ime")) ready else off
        val pointer = if (caps.optBoolean("pointerTap")) ready else off
        val capsText = "Keyboard $keyboard · Touch pointer $pointer · Accessibility $access · " +
            "${caps.optInt("screenWidth")}×${caps.optInt("screenHeight")}"
        if (capsText != lastCapsText) {
            lastCapsText = capsText
            capsView.text = capsText
        }

        setCheck(checkPair, paired)
        setCheck(checkAccess, caps.optBoolean("accessibility"))
        setCheck(checkIme, caps.optBoolean("ime"))
        setCheck(checkOverlay, Settings.canDrawOverlays(this))
    }

    private fun setCheck(view: TextView, ready: Boolean) {
        val text = getString(if (ready) R.string.check_done else R.string.check_needed)
        if (view.text.toString() == text) return
        view.text = text
        view.setBackgroundResource(
            if (ready) R.drawable.bg_status_connected else R.drawable.bg_status_idle,
        )
        view.setTextColor(
            ContextCompat.getColor(
                this,
                if (ready) R.color.status_connected_text else R.color.status_idle_text,
            ),
        )
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        ) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
    }
}

class DiagnosticsActivity : AppCompatActivity() {
    private val listener: (BridgeRuntime.Status) -> Unit = { status -> runOnUiThread { render(status) } }

    override fun onCreate(savedInstanceState: Bundle?) {
        SettingsStore.init(this)
        applyAppTheme()
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_diagnostics)
        findViewById<ImageButton>(R.id.btnDiagnosticsBack).setOnClickListener { finish() }
    }

    override fun onStart() {
        super.onStart()
        BridgeRuntime.addListener(listener)
    }

    override fun onStop() {
        BridgeRuntime.removeListener(listener)
        super.onStop()
    }

    private fun render(status: BridgeRuntime.Status) {
        findViewById<TextView>(R.id.tvDiagLink).setText(linkLabel(status.link))
        findViewById<TextView>(R.id.tvDiagMessage).text = status.message.ifEmpty { getString(R.string.log_empty) }

        val caps = BridgeRuntime.capabilities()
        val ready = getString(R.string.availability_ready)
        val off = getString(R.string.availability_off)
        findViewById<TextView>(R.id.tvCapKeyboard).text =
            getString(R.string.capability_keyboard, if (caps.optBoolean("ime")) ready else off)
        findViewById<TextView>(R.id.tvCapPointer).text =
            getString(R.string.capability_pointer, if (caps.optBoolean("pointerTap")) ready else off)
        findViewById<TextView>(R.id.tvCapTyping).text =
            getString(R.string.capability_typing, if (caps.optBoolean("text")) ready else off)
        findViewById<TextView>(R.id.tvCapScroll).text =
            getString(R.string.capability_scroll, if (caps.optBoolean("scroll")) ready else off)

        val service = InputAccessibilityService.instance
        if (service != null) {
            val stats = service.pointerStats()
            findViewById<TextView>(R.id.tvPointerStats).text = buildString {
                append("received=").append(stats["received"]).append("  ")
                append("frames=").append(stats["frames"]).append("  ")
                append("coalesced=").append(stats["coalesced"]).append("  ")
                append("stale=").append(stats["stale"]).append("  ")
                append("gestures=").append(stats["gestures"]).append("\n")
                append("last frame=").append(stats["last_frame_ms"]).append("ms  ")
                append("bounds=").append(stats["usable_bounds"])
            }
        } else {
            findViewById<TextView>(R.id.tvPointerStats).text = getString(R.string.log_empty)
        }

        findViewById<TextView>(R.id.tvLog).text =
            sanitizeLogs(BridgeRuntime.logs()).ifEmpty { getString(R.string.log_empty) }
    }
}
