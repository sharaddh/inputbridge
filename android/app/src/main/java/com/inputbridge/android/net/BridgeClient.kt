package com.inputbridge.android.net

import android.os.Build
import com.inputbridge.android.protocol.Protocol
import com.inputbridge.android.service.BridgeRuntime
import com.inputbridge.android.service.InputAccessibilityService
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

class BridgeClient(
    private val host: String,
    private val port: Int = Protocol.DEFAULT_PORT,
    tokenHex: String,
    private val deviceId: String = UUID.randomUUID().toString(),
    private val onStatus: (String) -> Unit,
    private val onState: (BridgeRuntime.LinkState, String) -> Unit,
    private val onPaired: (String) -> Unit,
    private val onInput: (JSONObject) -> Unit,
) {
    private val running = AtomicBoolean(false)
    private var thread: Thread? = null
    private var socket: Socket? = null
    private var writer: OutputStreamWriter? = null
    private val writeLock = Any()
    private var token: ByteArray? = tokenHex.toToken()
    private var paired = false
    private var sessionId: String = ""
    private var seq: Int = 0
    private val tracker = Protocol.SequenceTracker()
    private var eventsThisSecond = 0
    private var rateWindowStart = System.currentTimeMillis()
    private var lastRateStatus = 0L
    private var lastCapsSignature: String? = null

    val isRunning: Boolean get() = running.get()

    fun start() {
        if (running.get()) return
        running.set(true)
        thread = Thread({ runClient() }, "bridge-client").also { it.isDaemon = true; it.start() }
    }

    fun stop() {
        running.set(false)
        try {
            socket?.close()
        } catch (_: Exception) {
        }
        socket = null
        writer = null
        thread?.interrupt()
        thread = null
        paired = false
        lastCapsSignature = null
        onInput(JSONObject().put("kind", "release_all"))
        onState(BridgeRuntime.LinkState.STOPPED, "")
    }

    private fun runClient() {
        var retryDelay = 500L
        while (running.get()) {
            runConnection()
            if (!running.get()) break
            onState(BridgeRuntime.LinkState.CONNECTING, host)
            onStatus("Reconnecting in ${retryDelay / 1000}.${(retryDelay % 1000) / 100}s")
            try {
                Thread.sleep(retryDelay)
            } catch (_: InterruptedException) {
                if (running.get()) Thread.currentThread().interrupt()
                break
            }
            retryDelay = (retryDelay * 2).coerceAtMost(5000L)
        }
    }

    private fun runConnection() {
        try {
            val s = Socket()
            socket = s
            s.use {
                s.connect(InetSocketAddress(host, port), 1500)
                s.soTimeout = 250
                writer = OutputStreamWriter(s.getOutputStream(), Charsets.UTF_8)
                val reader = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.UTF_8))
                onState(BridgeRuntime.LinkState.CONNECTING, host)
                sendPairRequest()
                var lastRx = System.currentTimeMillis()
                var lastTx = System.currentTimeMillis()
                while (running.get()) {
                    val line = try {
                        reader.readLine()
                    } catch (_: SocketTimeoutException) {
                        null
                    }
                    if (line == null) {
                        val now = System.currentTimeMillis()
                        if (now - lastRx > Protocol.HEARTBEAT_TIMEOUT_MS) {
                            onStatus("Heartbeat timeout; reconnecting")
                            break
                        }
                        val current = token
                        if (paired && current != null && now - lastTx >= Protocol.HEARTBEAT_INTERVAL_MS) {
                            send("heartbeat", JSONObject(), current)
                            sendCapabilitiesIfChanged(current)
                            lastTx = now
                        }
                        continue
                    }
                    val now = System.currentTimeMillis()
                    lastRx = now
                    try {
                        processLine(line)
                    } catch (e: Exception) {
                        onStatus("Bad message: ${e.message}")
                    }
                    val current = token
                    if (paired && current != null && now - lastTx >= Protocol.HEARTBEAT_INTERVAL_MS) {
                        send("heartbeat", JSONObject(), current)
                        sendCapabilitiesIfChanged(current)
                        lastTx = now
                    }
                }
            }
        } catch (e: Exception) {
            onStatus("Connection error: ${e.message}; reconnecting")
        } finally {
            paired = false
            lastCapsSignature = null
            socket = null
            writer = null
            onInput(JSONObject().put("kind", "release_all"))
            if (!running.get()) onState(BridgeRuntime.LinkState.STOPPED, "")
        }
    }

    private fun sendPairRequest() {
        val current = token ?: return
        sessionId = Protocol.newSessionId()
        seq = 0
        tracker.reset(sessionId)
        val payload = JSONObject()
            .put("role", "android")
            .put("deviceId", deviceId)
            .put("deviceName", Build.MODEL)
            .put("app", "InputBridge-android-qr")
        send("pair_request", payload, current)
        onStatus("QR pairing request sent")
    }

    private fun processLine(line: String) {
        val obj = Protocol.decodeLine(line)
        val type = obj.optString("type")
        val payload = obj.optJSONObject("payload") ?: JSONObject()

        if (type == "pair_approval") {
            val current = token ?: return
            if (!Protocol.verify(obj, current, sessionId, minSeq = 1)) {
                onStatus("Pair approval rejected (bad signature)")
                return
            }
            val received = payload.optString("token", "")
            if (received.isNotEmpty()) {
                val decoded = received.toToken()
                if (decoded != null) token = decoded
            }
            sessionId = obj.optString("sessionId")
            seq = 0
            tracker.reset(sessionId)
            paired = true
            val remote = payload.optString("deviceName", "Windows laptop")
            onPaired(tokenHexValue())
            onState(BridgeRuntime.LinkState.PAIRED, remote)
            onStatus("Paired with $remote")
            sendCapabilities()
            return
        }

        if (!paired) return
        val current = token ?: return
        if (!Protocol.verify(obj, current, minSeq = 1)) {
            onStatus("Rejected message: bad signature")
            return
        }
        if (!tracker.check(obj)) {
            onStatus("Rejected replayed message")
            return
        }

        when (type) {
            "capabilities_request" -> sendCapabilities()
            "input" -> {
                if (!allowEvent()) {
                    val now = System.currentTimeMillis()
                    if (now - lastRateStatus >= 2000) {
                        lastRateStatus = now
                        onStatus("Input rate limit exceeded")
                    }
                    return
                }
                onInput(payload)
            }
            "mode" -> {
                val mouse = payload.optBoolean("mouse", false)
                InputAccessibilityService.instance?.setCursorVisible(mouse)
                onStatus("Routing mode: ${payload.optString("mode")}, mouse=$mouse")
            }
            "release_all" -> onInput(JSONObject().put("kind", "release_all"))
            "disconnect" -> running.set(false)
            "error" -> {
                val message = payload.optString("message", "unknown")
                if (message.contains("QR", true) || message.contains("token", true)) {
                    onStatus("Laptop QR changed; rescan the new QR code")
                } else {
                    onStatus("Laptop error: $message")
                }
            }
            "ack", "heartbeat" -> Unit
            else -> onStatus("Unknown message: $type")
        }
        val isPointerMove = type == "input" && payload.optString("action") == "move"
        if (type != "ack" && type != "heartbeat" && !isPointerMove) {
            send("ack", JSONObject().put("echoType", type), current)
        }
    }

    private fun sendCapabilities() {
        val current = token ?: return
        val caps = BridgeRuntime.capabilities()
        lastCapsSignature = caps.toString()
        send("capabilities", JSONObject().put("capabilities", caps), current)
    }

    private fun sendCapabilitiesIfChanged(current: ByteArray) {
        val caps = BridgeRuntime.capabilities()
        val signature = caps.toString()
        if (signature == lastCapsSignature) return
        lastCapsSignature = signature
        send("capabilities", JSONObject().put("capabilities", caps), current)
    }

    private fun allowEvent(): Boolean {
        val now = System.currentTimeMillis()
        if (now - rateWindowStart >= 1000) {
            rateWindowStart = now
            eventsThisSecond = 0
        }
        eventsThisSecond++
        return eventsThisSecond <= 500
    }

    private fun nextSeq(): Int = synchronized(this) { ++seq }

    private fun send(type: String, payload: JSONObject, token: ByteArray) {
        synchronized(writeLock) {
            try {
                val msg = Protocol.makeMessage(type, payload, sessionId, nextSeq(), token)
                writer?.write(Protocol.encodeLine(msg))
                writer?.flush()
            } catch (_: Exception) {
            }
        }
    }

    private fun tokenHexValue(): String = token?.joinToString("") { "%02x".format(it) } ?: ""

    private fun String.toToken(): ByteArray? = try {
        val bytes = fromHex()
        bytes.takeIf { it.size == 16 || it.size == 32 }
    } catch (_: Exception) {
        null
    }

    private fun String.fromHex(): ByteArray {
        val clean = trim()
        require(clean.length % 2 == 0) { "invalid token" }
        return ByteArray(clean.length / 2) { clean.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    }
}
