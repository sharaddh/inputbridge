# TRD (Summary)

Source of truth: `../InputBridge_PRD_SRS_TRD.md` (sections 7, 10, 11, 15–21).

## Architecture (recommended)
Modular: capture/adapters ⇄ routing state machine ⇄ transport ⇄ platform input adapters.

### Windows modules (planned)
App Controller, Shortcut Manager, Routing State Machine, Keyboard/Mouse Adapters, Input Suppression Adapter (experimental), Network Client, Pairing Manager, Tray UI, Settings Store, Watchdog.

### Android modules (planned)
Pairing UI, Connection Service, Protocol Decoder, Capability Manager, Accessibility Adapter, optional IME, Status UI, Safety Manager.

## Windows input (high risk)
- Raw Input: observes devices/data but does **not** suppress normal input by itself.
- Low-level hooks (`LowLevelKeyboardProc`/`LowLevelMouseProc`): can suppress in many cases but fragile (timeouts, secure desktop/UAC limits, must be short, no network I/O in callback). Emergency shortcut must never be forwarded/suppressed away unsafely.
- Design rules: minimal hook callbacks → bounded non-blocking queue → worker thread → watchdog → fail safe to allow local input.

## Android input strategies
- **A (prototype only):** ADB over Wi‑Fi for controlled tests (dev setup, not end-user).
- **B (MVP candidate):** Accessibility Service gestures (limited vs native; needs permission/policy care).
- **C:** IME for text entry only (not universal system key injection).
- **D (advanced):** Bluetooth HID / virtual HID — feasibility spike only (laptop-as-peripheral not guaranteed).

## Transport
- Preferred initial: authenticated local link over phone hotspot/same Wi‑Fi (WebSocket/TLS or TLS TCP). Internet not required.
- Handle: client isolation on some hotspots, IP changes, battery optimization, reconnect rules (no replay of stale events).

## State machine (core)
States: `LAPTOP`, `PHONE_BOTH`, `PHONE_KEYBOARD`, `PHONE_MOUSE`, `PAUSED`, `CONNECTING`, `ERROR_SAFE`. Invariant: do not suppress local device unless remote route active and healthy. Transitions include startup→LAPTOP, disconnect→ERROR_SAFE→LAPTOP, hook failure→ERROR_SAFE, emergency always→LAPTOP.

## Protocol (sketch)
Message types: `hello`, `pair_request`, `pair_approval`, `authenticate`, `capabilities`, `mode`, `input`, `ack`, `heartbeat`, `release_all`, `disconnect`, `error`. Capability negotiation is mandatory (Android reports what it supports).

## Tech stack (recommendation)
- Windows: C#/.NET for orchestration + tray/settings UI (WPF/WinUI as chosen later); native only if required. Use `ClientWebSocket`/TLS TCP; JSON early, versioned.
- Android: Kotlin, foreground service as needed, Accessibility Service + optional IME.
- Tools: VS/Rider, Android Studio, Git, Wireshark, logs.

## Milestones (summary)
M0 feasibility → M1 Windows shell → M2 Android shell → M3 network → M4 state engine → M5 input prototype → M6 safety → M7 MVP polish → M8 advanced HID/driver go/no-go.
