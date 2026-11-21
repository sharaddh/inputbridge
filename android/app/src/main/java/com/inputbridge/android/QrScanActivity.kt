@file:Suppress("DEPRECATION")

package com.inputbridge.android

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.google.zxing.integration.android.IntentIntegrator

@Suppress("DEPRECATION")
class QrScanActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val integrator = IntentIntegrator(this)
        integrator.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
        integrator.setPrompt("Scan the QR code shown on the laptop")
        integrator.setCameraId(0)
        integrator.setBeepEnabled(false)
        integrator.setBarcodeImageEnabled(false)
        integrator.initiateScan()
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        val result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data)
        if (result == null) {
            super.onActivityResult(requestCode, resultCode, data)
            return
        }
        if (resultCode == Activity.RESULT_OK && !result.contents.isNullOrBlank()) {
            setResult(Activity.RESULT_OK, Intent().putExtra(EXTRA_QR, result.contents))
        }
        finish()
    }

    companion object {
        const val EXTRA_QR = "qr"
    }
}
