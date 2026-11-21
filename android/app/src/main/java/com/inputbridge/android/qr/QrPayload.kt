package com.inputbridge.android.qr

import org.json.JSONObject

data class QrConfig(val host: String, val port: Int, val tokenHex: String)

object QrPayload {
    fun parse(text: String?): QrConfig {
        require(!text.isNullOrBlank()) { "Empty QR code" }
        val obj = JSONObject(text)
        require(obj.optInt("v", -1) == 1) { "Unsupported QR version" }
        val host = obj.optString("h", "").trim()
        require(host.isNotEmpty()) { "Missing laptop IP" }
        val port = obj.optInt("p", -1)
        require(port in 1..65535) { "Invalid port" }
        val token = obj.optString("t", "").trim().lowercase()
        require(token.length == 32 && token.all { it in '0'..'9' || it in 'a'..'f' }) { "Invalid QR token" }
        return QrConfig(host, port, token)
    }
}
