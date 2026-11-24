# Final build status

Date: 2026-11-22

## Status: QR-only Touch Pointer MVP v0.3.1-fix built in this workspace

The pairing flow has been changed from manual IP + 6-digit code to QR-only: Windows displays a QR and hosts the TCP server; Android scans it with ZXing embedded and connects as the client.

## Artifacts

| Artifact | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| `release/InputBridge-Windows/InputBridge.exe` | 2,292,280 | `5D0F674FA97962B77B289C01F754CB26DD7AEAFC1638276BBA3BAA93C04D94D3` |
| `release/InputBridge-Android/InputBridge-release.apk` | 5,482,651 | `123823D12A8F4058D9AD72E0D581A00E339A7AB5C6E13EA560D6FE644B6C7C33` |
| `release/InputBridge-Android/InputBridge-debug.apk` | 6,886,519 | `0E72AE3B4D25EF5DFE67826561323D5C49CAEFBF45B3161B3E890615EE36213F` |
| `release/InputBridge-Windows.zip` | 13,308,613 | `CA9E87E06B905D2387F494691136368987D2DFA76AA0077916D31D37D124A022` |

Windows release folder contains 941 files including `InputBridge.exe` and `_internal/`; keep the folder intact.

## What was done

### v0.3.1 fix pass

- Fixed the reporting failure where a paired/connected phone still received no keyboard, click, or cursor movement: Windows now re-asserts the routing mode every 5 seconds, Android remembers mouse routing after an app/service restart, and the cursor is shown again when the Accessibility service connects after a mode message.
- Added an Accessibility fallback for key events when the InputBridge IME object exists but is not the active keyboard; text entry still requires selecting the InputBridge IME.
- Fixed Windows UI text/background blending by forcing the high-contrast `clam` ttk theme and by adding an explicit “Connected. Press SWITCH TO PHONE...” hint while routing is still local.
- Fixed Android button text contrast on primary-colored buttons by adding theme-aware `on_primary` colors and replacing low-contrast text colors.
- Updated the Windows desktop note so it no longer incorrectly says traffic is unencrypted.
- Android version bumped to `versionCode=4`, `versionName=0.3.1-fix`.

### v0.3.0 quality pass

- Implemented the product-quality report: latest-value Windows pointer slot with 60 Hz default send rate (30/60/120 selectable), monotonic capture/send timestamps, stale-point and unchanged-point rejection, and ACK/latency diagnostics.
- Android pointer core now uses Choreographer frame callbacks, WindowMetrics/WindowInsets mapping, a single shared coordinate transform for cursor and gestures, hotspot-aware overlay placement, edge clamping by hotspot, and a crosshair calibration screen with saved offsets.
- Android button mapping is explicit: right = context menu/back/none, middle = recents/none, extra side button = Back; drag is intentionally not claimed.
- Windows and Android UIs were redesigned around one primary action, setup checklist, Diagnostics, and Settings/Appearance personalization with theme, device name, scroll, pointer rate, button, and cursor controls.
- Protocol v2 encrypts all post-pairing messages with AES-256-GCM. Key = SHA-256("inputbridge-aead-v2" + QR token). Pairing remains signed v1; `hello`/`error` remain unsigned. AAD binds version/type/session/sequence/timestamp/encoding. Wrong-key and tamper tests pass.
- Android and Windows Diagnostics expose pointer counters and latency/queue telemetry without input content.
- Android version bumped to `versionCode=3`, `versionName=0.3.0-quality`.

### Windows

- Replaced the old client/pairing UI with a QR server:
  - `windows/src/inputbridge/net_server.py`: TCP server on port `27123`, QR-token pairing, HMAC verification, heartbeats, sequence tracking, periodic `capabilities_request`, disconnect handling.
  - `windows/src/inputbridge/qrcode.py`: pure-stdlib QR Code model 2 encoder (version 5-L, 37x37) used to render the desktop QR.
  - `windows/src/inputbridge/app.py`: QR display, **New QR**, **Disconnect phone**, routing controls, tray, log, settings.
  - `windows/src/inputbridge/controller.py`: now drives `BridgeServer` instead of `BridgeClient`.
- Fixed 64-bit Win32 `ctypes` signatures in `input_capture.py` and `tray.py` (`GetModuleHandleW`, `CreateWindowExW`, `GetMessageW`, `TranslateMessage`, `DispatchMessageW`); hook/tray message windows now create successfully and failures are reported instead of falsely marking the pipeline ready.
- Added a controller guard so Phone mode cannot be entered when input hooks are not running.
- Fixed Shift+CapsLock getting stuck in Phone mode: low-level hook now tracks Shift/Ctrl/Alt internally because suppressed modifier keys do not update `GetKeyState`; toggle/emergency callbacks are dispatched off the hook thread. Added optional registered global hotkeys with automatic fallback to the hook when Windows reports the hotkey already in use. In Phone mode, CapsLock alone now also returns to Laptop so the escape path does not depend on modifier-key tracking at all.
- Mouse movement is no longer suppressed in Phone mode: suppression froze `MSLLHOOKSTRUCT.pt`, so the phone cursor jumped back to a stale position. Windows now keeps moving normally and sends absolute coordinates; buttons/wheel remain suppressed. Pointer moves are coalesced to 30 Hz and Android applies only the newest main-thread update, reducing queue/network backlog. The Windows cursor is hidden only while mouse routing is active and restored on Laptop/disconnect.
- Removed obsolete `windows/src/inputbridge/net_client.py`.
- QR payload format: `{"v":1,"h":"<lan-ip>","p":27123,"t":"<32 hex chars>"}`.
- Host IP is detected locally without sending traffic; `New QR` rotates the token.
- Executable rebuilt with PyInstaller 6.22.3 / Python 3.11.9:
  ```powershell
  cd D:\switcher\windows
  python -m PyInstaller --clean --noconfirm InputBridge.spec
  ```

### Android

- Replaced the old server/code UI with QR scanning:
  - `app/src/main/java/com/inputbridge/android/QrScanActivity.kt`: ZXing `IntentIntegrator` QR scan.
  - `app/src/main/java/com/inputbridge/android/qr/QrPayload.kt`: validates QR version, host, port, and 32-hex token.
  - `app/src/main/java/com/inputbridge/android/net/BridgeClient.kt`: connects to the laptop, sends signed `pair_request`, accepts `pair_approval`, handles input/mode/release messages, heartbeats, acks, rate limiting, answers capability requests, writes signed messages atomically to preserve sequence order, and now auto-reconnects with backoff after socket/heartbeat failures.
  - `app/src/main/java/com/inputbridge/android/service/BridgeRuntime.kt`: persists QR host/port/token, starts/stops the client, dispatches input.
  - `app/src/main/java/com/inputbridge/android/MainActivity.kt`: **Scan laptop QR**, camera permission, disconnect, revoke, accessibility/IME setup.
- Added dependency `com.journeyapps:zxing-android-embedded:4.3.0` and `CAMERA` permission.
- Added a visible overlay cursor in `InputAccessibilityService.kt` that follows Windows pointer `move`/`down`/`up` messages using normalized coordinates; it first tries `TYPE_ACCESSIBILITY_OVERLAY`, then falls back to `TYPE_APPLICATION_OVERLAY` when **Display over other apps** is granted. Added an **Allow cursor overlay** button and phone-log diagnostics (`Cursor overlay added...` / `Cursor overlay failed...`); Cursor updates, gesture dispatch, and global actions are posted to Android's main thread so network-thread input cannot silently fail. The cursor is hidden unless a `mode` message enables mouse routing, and tap/gesture coordinates use the same status/navigation-bar-aware mapping as the overlay to fix click offset. Scroll direction was reversed to match normal mouse wheel behavior. `pointerMove` capability now reports `true` when the accessibility service is active.
- Performance/UX pass for v0.2.0:
  - Accessibility service no longer subscribes to all accessibility events or window content; it only requests filtered key events, removing a major main-thread event flood.
  - Status/log/capability updates are coalesced on the Android main thread; unchanged TextViews are not rewritten, and the log buffer is bounded with an O(1) queue.
  - Cursor movement uses cached screen metrics, cached system bar insets, and a cached `WindowManager` instead of doing resource lookups per pointer update.
  - Wheel events are coalesced into one gesture instead of queueing a gesture per Windows wheel tick; high-frequency pointer moves no longer generate ACK packets.
  - Socket connect has a timeout and can be cancelled promptly; rate-limit warnings are throttled.
  - Main screen redesigned into compact Material cards with a color-coded connection chip, current status line, clearer capability summary, and a contained scrolling activity log.
  - Android version bumped to `versionCode=2`, `versionName=0.2.0-smooth`.
- Removed obsolete `BridgeServer.kt`.
- Builds:
  ```powershell
  cd D:\switcher\android
  .\gradlew.bat assembleDebug assembleRelease
  ```
- Release APK signing verified with `apksigner`:
  - Signer: `CN=InputBridge MVP, OU=Local, O=InputBridge, L=Local, ST=Local, C=US`
  - SHA-256 cert digest: `aa0542db2feb9f1e2b33856ad8eba952a0d1a4cd8720769d696b2cf3626e9535`
  - Keystore: `release/inputbridge-release.jks` (evaluation only; paths/passwords are local in `android/local.properties`).

## Verification

- Windows unit tests:
  ```powershell
  cd D:\switcher\windows
  $env:PYTHONPATH='src'
  python -m unittest discover -s tests -p 'test_*.py' -v
  ```
  Result: `Ran 13 tests ... OK` (AES-GCM v2 protocol roundtrip/tamper/wrong-key, legacy signed pairing, unsigned error, routing, QR format/size/limit, and Shift+CapsLock toggle tests).
- Windows imports: `inputbridge.app`, `controller`, `input_capture`, `tray`, `net_server`, `qrcode` → `imports ok`.
- 12-second localhost protocol integration test: paired successfully, received 3 periodic `capabilities_request` messages, stayed connected/paired, no heartbeat timeout. Heartbeat timeout raised from 6 to 15 seconds on both sides; Android reconnects after brief drops instead of stopping permanently.
- Windows startup bugs previously fixed: deferred emergency-button binding and 64-bit `ctypes` argtypes for window/hook callbacks. Input-hook diagnostic ran 8 seconds with hook window/keyboard hook/mouse hook all alive and no errors; tray diagnostic ran 3 seconds with its window alive and no errors; injected real `Shift+CapsLock` events fired the toggle callback twice and `Ctrl+Alt+F12` fired the emergency callback once.
- Packaged `InputBridge.exe` launch smoke test: stayed running for 5 seconds with no stderr, then stopped cleanly.
- QR encoder verified by decoding a generated image with ZXing core 3.4.1; decoded payload matched the source JSON exactly.
- Android `assembleDebug` and `assembleRelease` both completed successfully.
- `apksigner verify --print-certs` passed for the release APK.

## Known limitations

- No TLS or production key management. Pairing is HMAC-signed and post-pairing traffic is AES-256-GCM encrypted; trusted local network still required.
- Touch Pointer uses a hotspot-aware cursor overlay with calibration, but Android gestures are still tap/swipe based with WindowMetrics/Insets mapping. No native hover/drag/wheel semantics, arbitrary system-key injection, or secure-desktop/UAC control.
- No Android device/ADB install or real-device latency smoke test was performed for v0.3.0 or v0.3.1-fix; manual hardware validation is still required.
- No Android device/ADB install or camera-permission smoke test was performed here; `adb.exe` exists at `C:\Users\wwwsh\AppData\Local\Android\Sdk\platform-tools\adb.exe`.
- Release certificate is self-signed for evaluation, not production distribution.

## How to run

See `README.md` and `release/README_RELEASE.md`.
