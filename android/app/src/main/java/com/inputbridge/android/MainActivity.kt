package com.inputbridge.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.method.ScrollingMovementMethod
import android.widget.Button
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

class MainActivity : AppCompatActivity() {
    private lateinit var stateView: TextView
    private lateinit var messageView: TextView
    private lateinit var capsView: TextView
    private lateinit var logView: TextView
    private lateinit var scanLauncher: ActivityResultLauncher<Intent>
    private lateinit var cameraLauncher: ActivityResultLauncher<String>
    private var lastStateText = ""
    private var lastLink: BridgeRuntime.LinkState? = null
    private var lastMessageText = ""
    private var lastCapsText = ""
    private var lastLogText = ""
    private val listener: (BridgeRuntime.Status) -> Unit = { status -> runOnUiThread { render(status) } }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        BridgeRuntime.init(this)

        stateView = findViewById(R.id.tvState)
        messageView = findViewById(R.id.tvMessage)
        capsView = findViewById(R.id.tvCaps)
        logView = findViewById(R.id.tvLog)
        logView.movementMethod = ScrollingMovementMethod()
        logView.setHorizontallyScrolling(true)

        scanLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode != RESULT_OK) return@registerForActivityResult
            val text = result.data?.getStringExtra(QrScanActivity.EXTRA_QR)
            try {
                val config = QrPayload.parse(text)
                BridgeRuntime.connectQr(this, config.host, config.port, config.tokenHex)
                BridgeForegroundService.start(this)
                Toast.makeText(this, "Connecting to laptop", Toast.LENGTH_SHORT).show()
            } catch (e: IllegalArgumentException) {
                Toast.makeText(this, "Invalid QR: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }

        cameraLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) scanLauncher.launch(Intent(this, QrScanActivity::class.java))
            else Toast.makeText(this, "Camera permission is needed to scan the QR", Toast.LENGTH_LONG).show()
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
            val manager = getSystemService(android.content.Context.INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            manager.showInputMethodPicker()
        }

        findViewById<Button>(R.id.btnRevoke).setOnClickListener {
            BridgeRuntime.revoke()
            BridgeForegroundService.stop(this)
            Toast.makeText(this, "Pairing revoked", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btnOverlay).setOnClickListener {
            if (Settings.canDrawOverlays(this)) {
                InputAccessibilityService.instance?.refreshCursor()
                Toast.makeText(this, "Cursor overlay refreshed", Toast.LENGTH_SHORT).show()
            } else {
                startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName"),
                    )
                )
            }
        }

        requestNotificationPermission()
    }

    override fun onStart() {
        super.onStart()
        BridgeRuntime.addListener(listener)
    }

    override fun onResume() {
        super.onResume()
        InputAccessibilityService.instance?.refreshCursor()
    }

    override fun onStop() {
        BridgeRuntime.removeListener(listener)
        super.onStop()
    }

    private fun render(status: BridgeRuntime.Status) {
        val remote = if (status.remoteName.isEmpty()) "" else " · ${status.remoteName}"
        val stateText = "${status.link}$remote${if (status.paired) " · paired" else ""}"
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
        }
        val messageText = status.message.ifEmpty { getString(R.string.log_empty) }
        if (messageText != lastMessageText) {
            lastMessageText = messageText
            messageView.text = messageText
        }
        val caps = BridgeRuntime.capabilities()
        val on = "on"
        val off = "off"
        val access = if (caps.optBoolean("accessibility")) on else off
        val keyboard = if (caps.optBoolean("ime")) on else off
        val pointer = if (caps.optBoolean("pointerTap")) on else off
        val capsText = "Accessibility $access · Keyboard $keyboard · Pointer $pointer · " +
            "${caps.optInt("screenWidth")}×${caps.optInt("screenHeight")}"
        if (capsText != lastCapsText) {
            lastCapsText = capsText
            capsView.text = capsText
        }
        val logText = BridgeRuntime.logs().takeLast(40).joinToString("\n")
        if (logText != lastLogText) {
            lastLogText = logText
            logView.text = logText
            logView.post { logView.scrollTo(0, logView.layout?.height ?: 0) }
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        ) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
    }
}
