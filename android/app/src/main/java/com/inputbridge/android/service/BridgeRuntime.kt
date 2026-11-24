package com.inputbridge.android.service

import android.content.Context
import android.content.SharedPreferences
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import com.inputbridge.android.ime.BridgeIme
import com.inputbridge.android.net.BridgeClient
import com.inputbridge.android.settings.SettingsStore
import org.json.JSONObject
import java.util.ArrayDeque
import java.util.concurrent.CopyOnWriteArrayList

object BridgeRuntime {
    enum class LinkState { STOPPED, CONNECTING, CONNECTED, PAIRED }

    data class Status(
        val link: LinkState = LinkState.STOPPED,
        val message: String = "Not started",
        val paired: Boolean = false,
        val remoteName: String = "",
        val capabilities: JSONObject = JSONObject(),
    )

    private val listeners = CopyOnWriteArrayList<(Status) -> Unit>()
    private val uiHandler = Handler(Looper.getMainLooper())
    private var notifyScheduled = false
    private val notifyRunnable = Runnable {
        notifyScheduled = false
        val snapshot = currentStatus
        listeners.forEach { runCatching { it(snapshot) } }
    }
    private var prefs: SharedPreferences? = null
    private var currentStatus = Status()
    val status: Status
        get() = currentStatus
    var client: BridgeClient? = null
        private set
    private val logBuffer = ArrayDeque<String>()
    private var capsCache: JSONObject? = null
    private var capsCacheAt = 0L
    private var mouseRouting = false

    fun init(context: Context) {
        if (prefs == null) prefs = context.applicationContext.getSharedPreferences("inputbridge", Context.MODE_PRIVATE)
        SettingsStore.init(context)
    }

    val savedTokenHex: String
        get() = prefs?.getString("paired_token", "") ?: ""

    val savedHost: String
        get() = prefs?.getString("host", "") ?: ""

    val savedPort: Int
        get() = prefs?.getInt("port", 27123) ?: 27123

    fun saveToken(hex: String) {
        prefs?.edit()?.putString("paired_token", hex)?.apply()
    }

    fun connectQr(context: Context, host: String, port: Int, tokenHex: String) {
        init(context)
        prefs?.edit()
            ?.putString("host", host)
            ?.putInt("port", port)
            ?.putString("paired_token", tokenHex)
            ?.apply()
        startClient(context)
    }

    fun revoke() {
        saveToken("")
        prefs?.edit()?.remove("host")?.remove("port")?.apply()
        stopClient()
        publish(Status(message = "Pairing revoked"))
    }

    fun addListener(listener: (Status) -> Unit) {
        listeners.add(listener)
        listener(status)
    }

    fun removeListener(listener: (Status) -> Unit) {
        listeners.remove(listener)
    }

    fun publish(next: Status) {
        currentStatus = next
        if (notifyScheduled) return
        notifyScheduled = true
        uiHandler.post(notifyRunnable)
    }

    fun log(line: String) {
        synchronized(logBuffer) {
            logBuffer.addLast(line)
            while (logBuffer.size > 120) logBuffer.removeFirst()
        }
        publish(currentStatus.copy(message = line))
    }

    fun logs(): List<String> = synchronized(logBuffer) { logBuffer.toList() }

    fun startClient(context: Context) {
        init(context)
        if (client?.isRunning == true) return
        val host = savedHost
        val token = savedTokenHex
        if (host.isEmpty() || token.isEmpty()) {
            log("Scan the laptop QR code first")
            return
        }
        stopClient()
        val bridge = BridgeClient(
            host = host,
            port = savedPort,
            tokenHex = token,
            onStatus = { text -> log(text) },
            onState = { state, remote ->
                publish(
                    status.copy(
                        link = state,
                        paired = state == LinkState.PAIRED,
                        remoteName = remote,
                    )
                )
            },
            onPaired = { hex -> saveToken(hex) },
            onInput = { payload -> dispatchInput(payload) },
        )
        client = bridge
        bridge.start()
    }

    fun stopClient() {
        client?.stop()
        client = null
        publish(status.copy(link = LinkState.STOPPED, paired = false, remoteName = ""))
    }

    private fun dispatchInput(payload: JSONObject) {
        when (payload.optString("kind")) {
            "pointer" -> InputAccessibilityService.instance?.handle(payload)
            "key" -> {
                val ime = BridgeIme.instance
                if (ime != null && ime.canHandle()) ime.handle(payload) else InputAccessibilityService.instance?.handleKey(payload)
            }
        }
    }

    fun setMouseRouting(enabled: Boolean) {
        mouseRouting = enabled
    }

    fun mouseRouting(): Boolean = mouseRouting

    fun invalidateCapabilities() {
        capsCache = null
        capsCacheAt = 0L
    }

    fun capabilities(): JSONObject {
        val now = SystemClock.elapsedRealtime()
        capsCache?.let { if (now - capsCacheAt < 1000L) return it }
        val caps = JSONObject()
        caps.put("accessibility", InputAccessibilityService.instance != null)
        caps.put("ime", BridgeIme.instance != null)
        caps.put("pointerTap", InputAccessibilityService.instance != null)
        caps.put("pointerSwipe", InputAccessibilityService.instance != null)
        caps.put("pointerMove", InputAccessibilityService.instance != null)
        caps.put("mouseButtons", false)
        caps.put("scroll", InputAccessibilityService.instance != null)
        caps.put("text", BridgeIme.instance != null)
        caps.put("keyEvents", false)
        caps.put("pointerRateHz", SettingsStore.pointerRateHz)
        caps.put("scrollDirection", SettingsStore.scrollDirection)
        caps.put("scrollSensitivity", SettingsStore.scrollSensitivity)
        caps.put("rightButtonAction", SettingsStore.rightButtonAction)
        caps.put("middleButtonAction", SettingsStore.middleButtonAction)
        val screen = android.content.res.Resources.getSystem().displayMetrics
        caps.put("screenWidth", screen.widthPixels)
        caps.put("screenHeight", screen.heightPixels)
        capsCache = caps
        capsCacheAt = now
        return caps
    }
}
