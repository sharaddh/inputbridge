package com.inputbridge.android.input

class PointerMetrics {
    private val lock = Any()
    private var received = 0L
    private var coalesced = 0L
    private var stale = 0L
    private var frames = 0L
    private var gestures = 0L
    private var lastFrameLatencyMs = 0L
    private var maxQueueDepth = 0

    fun received() = increment { received++ }

    fun coalesced() = increment { coalesced++ }

    fun stale() = increment { stale++ }

    fun frame(latencyMs: Long) = increment {
        frames++
        if (latencyMs >= 0) lastFrameLatencyMs = latencyMs
    }

    fun gesture() = increment { gestures++ }

    fun queueDepth(depth: Int) = increment {
        if (depth > maxQueueDepth) maxQueueDepth = depth
    }

    fun snapshot(): Map<String, Any> = synchronized(lock) {
        mapOf(
            "received" to received,
            "coalesced" to coalesced,
            "stale" to stale,
            "frames" to frames,
            "gestures" to gestures,
            "last_frame_ms" to lastFrameLatencyMs,
            "max_queue_depth" to maxQueueDepth,
        )
    }

    fun reset() = synchronized(lock) {
        received = 0
        coalesced = 0
        stale = 0
        frames = 0
        gestures = 0
        lastFrameLatencyMs = 0
        maxQueueDepth = 0
    }

    private inline fun increment(block: () -> Unit) = synchronized(lock) { block() }
}
