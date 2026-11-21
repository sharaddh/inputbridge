package com.inputbridge.android.ime

import android.inputmethodservice.InputMethodService
import android.view.KeyEvent
import org.json.JSONObject

class BridgeIme : InputMethodService() {
    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    override fun onDestroy() {
        instance = null
        super.onDestroy()
    }

    fun handle(payload: JSONObject) {
        val action = payload.optString("action", "")
        if (action != "down" && action != "repeat") return
        val vk = payload.optInt("vk", -1)
        val text = payload.optString("char", "")
        if (text.isNotEmpty() && text[0].code >= 32) {
            currentInputConnection?.commitText(text, 1)
            return
        }
        val keyCode = when (vk) {
            8 -> KeyEvent.KEYCODE_DEL
            9 -> KeyEvent.KEYCODE_TAB
            13 -> KeyEvent.KEYCODE_ENTER
            27 -> KeyEvent.KEYCODE_ESCAPE
            37 -> KeyEvent.KEYCODE_DPAD_LEFT
            38 -> KeyEvent.KEYCODE_DPAD_UP
            39 -> KeyEvent.KEYCODE_DPAD_RIGHT
            40 -> KeyEvent.KEYCODE_DPAD_DOWN
            46 -> KeyEvent.KEYCODE_FORWARD_DEL
            else -> 0
        }
        if (keyCode != 0) {
            currentInputConnection?.sendKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
            currentInputConnection?.sendKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
        }
    }

    companion object {
        var instance: BridgeIme? = null
            private set
    }
}
