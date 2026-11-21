# Phase 0 spike — Android ADB (prototype only)

**Do not use ADB as end-user solution.** For internal feasibility only (per ADR 0002).

## Goal
Validate that a Windows machine can trigger basic phone actions over the same network context during dev, and document limits (keys, pointer, OEM/Vivo/Android 15 behavior).

## Prereqs
- Android phone: Developer Options enabled, **Wireless debugging** enabled (Android 11+ path). Note pairing code/IP:port shown on phone.
- Windows + ADB installed (platform-tools). Same Wi‑Fi/network considerations as hotspot tests later.

## Checklist
1. Pair: `adb pair <ip>:<port>` (use pairing code) — record success/failure.
2. Connect: `adb connect <ip>:<port>`.
3. `adb devices` shows device `...device`.
4. Test actions (examples):  
   - `adb shell input text "hello"` (text)  
   - `adb shell input tap 500 500`  
   - `adb shell input swipe 500 1500 500 500 200`  
   - Key events: `adb shell input keyevent 3` (HOME) — document which keycodes are useful.
5. Record limits: no true hover/native mouse semantics in many cases, reliability, latency feel, behavior on lock screen/overlays, battery optimization effects.

## Outputs
- Commands that worked
- What is impossible/fragile
- Recommendation: MVP should use Accessibility gestures + optional IME for text, with explicit capability reporting (ADR 0002).
