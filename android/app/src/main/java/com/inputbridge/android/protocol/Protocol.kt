package com.inputbridge.android.protocol

import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object Protocol {
    const val VERSION = 1
    const val DEFAULT_PORT = 27123
    const val MAX_MESSAGE_BYTES = 64 * 1024
    const val HEARTBEAT_INTERVAL_MS = 2000L
    const val HEARTBEAT_TIMEOUT_MS = 15000L
    private const val MAX_CLOCK_SKEW_MS = 30_000L
    private val UNSIGNED_TYPES = setOf("hello", "error")

    private val random = SecureRandom()

    fun pairingToken(code: String): ByteArray =
        sha256("inputbridge-pair:${code.trim()}".toByteArray(Charsets.UTF_8))

    fun newSessionId(): String = hex(randomBytes(16))

    fun newPairingSecret(): String = hex(randomBytes(32))

    fun randomBytes(count: Int): ByteArray = ByteArray(count).also { random.nextBytes(it) }

    private fun hex(bytes: ByteArray): String = bytes.joinToString("") { "%02x".format(it) }

    private fun sha256(data: ByteArray): ByteArray =
        MessageDigest.getInstance("SHA-256").digest(data)

    fun canonical(obj: JSONObject): String {
        val keys = obj.keys().asSequence().sorted()
        return keys.joinToString(",", "{", "}") { key ->
            "${JSONObject.quote(key)}:${canonicalValue(obj.get(key))}"
        }
    }

    private fun canonicalValue(value: Any?): String = when (value) {
        null, JSONObject.NULL -> "null"
        is JSONObject -> canonical(value)
        is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") {
            canonicalValue(value.get(it))
        }
        is String -> JSONObject.quote(value)
        is Number, is Boolean -> value.toString()
        else -> JSONObject.quote(value.toString())
    }

    fun sign(obj: JSONObject, token: ByteArray): JSONObject {
        val clone = JSONObject(canonical(obj))
        clone.remove("sig")
        clone.put("sig", hmac(canonical(clone).toByteArray(Charsets.UTF_8), token))
        return clone
    }

    private fun hmac(data: ByteArray, token: ByteArray): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(token, "HmacSHA256"))
        return hex(mac.doFinal(data))
    }

    fun makeMessage(
        type: String,
        payload: JSONObject = JSONObject(),
        sessionId: String,
        seq: Int,
        token: ByteArray? = null,
    ): JSONObject {
        val obj = JSONObject()
        obj.put("v", VERSION)
        obj.put("type", type)
        obj.put("sessionId", sessionId)
        obj.put("seq", seq)
        obj.put("ts", System.currentTimeMillis())
        obj.put("payload", payload)
        return if (token == null || UNSIGNED_TYPES.contains(type)) obj else sign(obj, token)
    }

    fun encodeLine(obj: JSONObject): String {
        val text = canonical(obj)
        require(text.toByteArray(Charsets.UTF_8).size <= MAX_MESSAGE_BYTES) { "message too large" }
        return text + "\n"
    }

    fun decodeLine(line: String): JSONObject {
        require(line.toByteArray(Charsets.UTF_8).size <= MAX_MESSAGE_BYTES) { "message too large" }
        val obj = JSONObject(line)
        require(obj.optInt("v") == VERSION) { "unsupported protocol version" }
        require(obj.optString("type").isNotEmpty()) { "missing message type" }
        require(obj.optString("sessionId").isNotEmpty()) { "missing session id" }
        require(obj.optInt("seq", -1) >= 1) { "invalid sequence" }
        require(obj.has("ts")) { "invalid timestamp" }
        require(obj.opt("payload") is JSONObject) { "invalid payload" }
        return obj
    }

    fun verify(
        obj: JSONObject,
        token: ByteArray?,
        expectedSession: String? = null,
        minSeq: Int = 1,
    ): Boolean {
        val type = obj.optString("type")
        if (UNSIGNED_TYPES.contains(type)) return true
        if (token == null) return false
        if (expectedSession != null && obj.optString("sessionId") != expectedSession) return false
        if (obj.optInt("seq") < minSeq) return false
        if (kotlin.math.abs(System.currentTimeMillis() - obj.optLong("ts")) > MAX_CLOCK_SKEW_MS) return false
        val supplied = obj.optString("sig", "")
        if (supplied.isEmpty()) return false
        val clone = JSONObject(canonical(obj))
        clone.remove("sig")
        val expected = hmac(canonical(clone).toByteArray(Charsets.UTF_8), token)
        return MessageDigest.isEqual(supplied.toByteArray(Charsets.UTF_8), expected.toByteArray(Charsets.UTF_8))
    }

    class SequenceTracker {
        private var sessionId: String = ""
        private var lastSeq: Int = 0

        fun reset(id: String = "") {
            sessionId = id
            lastSeq = 0
        }

        fun check(obj: JSONObject): Boolean {
            val sid = obj.optString("sessionId")
            val seq = obj.optInt("seq")
            if (sessionId.isNotEmpty() && sid != sessionId) return false
            if (seq <= lastSeq) return false
            sessionId = sid
            lastSeq = seq
            return true
        }
    }
}
