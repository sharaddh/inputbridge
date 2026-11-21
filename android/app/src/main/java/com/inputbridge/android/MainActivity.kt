package com.inputbridge.android

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
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
    private lateinit var capsView: TextView
    private lateinit var logView: TextView
    private lateinit var scanLauncher: ActivityResultLauncher<Intent>
    private lateinit var cameraLauncher: ActivityResultLauncher<String>
    private val listener: (BridgeRuntime.Status) -> Unit = { status -> runOnUiThread { render(status) } }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        BridgeRuntime.init(this)

        stateView = findViewById(R.id.tvState)
        capsView = findViewById(R.id.tvCaps)
        logView = findViewById(R.id.tvLog)

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
        val remote = if (status.remoteName.isEmpty()) "" else " from ${status.remoteName}"
        stateView.text = "Status: ${status.link}${if (status.paired) " (paired)" else ""}$remote"
        val caps = BridgeRuntime.capabilities()
        capsView.text = "Capabilities: accessibility=${caps.optBoolean("accessibility")}, " +
            "IME=${caps.optBoolean("ime")}, pointer=${caps.optBoolean("pointerTap")}, " +
            "screen=${caps.optInt("screenWidth")}x${caps.optInt("screenHeight")}"
        logView.text = BridgeRuntime.logs().takeLast(60).joinToString("\n")
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        ) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
    }
}
