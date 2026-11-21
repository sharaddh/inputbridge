# InputBridge

InputBridge is a Windows 11 + Android companion app that routes a physical keyboard/mouse between the laptop and an Android phone.

**Status:** QR-only functional MVP built on 2026-11-21.

[Download the latest Windows ZIP and Android APKs from GitHub Releases](https://github.com/sharaddh/inputbridge/releases/latest).

## Release artifacts

| Platform | GitHub Release asset | Notes |
| --- | --- | --- |
| Windows | `InputBridge-Windows.zip` | Extract the folder, keep `_internal/` beside `InputBridge.exe`, then run the EXE. |
| Android | `InputBridge-release.apk` | Signed with a self-signed evaluation certificate. |
| Android | `InputBridge-debug.apk` | Debug-signed, useful for development. |

SHA-256 checksums are recorded in `release/README_RELEASE.md` and `FINAL_BUILD_STATUS.md`.

## What works in this MVP

- Windows shows a QR code containing its LAN IP, port `27123`, and a one-time 128-bit HMAC pairing key.
- Android scans that QR with the camera (ZXing embedded) and connects automatically — no manual IP, no 6-digit code.
- Windows hosts the TCP server; the phone becomes the client.
- Windows control panel: Laptop / Both / Keyboard-only / Mouse-only / Pause modes, connection status, new-QR and disconnect buttons, settings, log panel, system tray.
- Windows input capture: low-level keyboard/mouse hooks with routing-aware suppression, bounded queue, worker thread, watchdog, and fail-safe return to Laptop mode.
- Hotkeys: `Shift+CapsLock` toggles phone mode; in Phone mode `CapsLock` alone also returns to Laptop; `Ctrl+Alt+F12` is the emergency local-return shortcut.
- Android input injection: taps/swipes/scrolls through the Accessibility service; text/navigation through the InputBridge IME. A visual cursor overlay follows the Windows mouse in Phone mode and stays hidden otherwise. Capabilities auto-refresh after the IME is selected.
- Transport security: HMAC-SHA256 signed JSON envelopes with sequence/timestamp replay checks; the pairing key comes from the scanned QR.

## Quick start

1. Download `InputBridge-release.apk` from the latest GitHub Release and install it on the Android device, or install it with `adb install -r InputBridge-release.apk`.
2. On Android, open InputBridge and enable the Accessibility service. Select the **InputBridge** keyboard when you want to type from the phone.
3. Download and extract `InputBridge-Windows.zip` from the latest GitHub Release, then run `InputBridge.exe` on Windows.
4. Tap **Scan laptop QR** in the Android app and point the camera at the QR on the Windows screen.
5. Use the routing buttons or `Shift+CapsLock`. Use **EMERGENCY: Laptop** or `Ctrl+Alt+F12` to restore local input immediately.
6. Tap **New QR** on Windows to rotate the key and invalidate the current phone link.

Both devices must be on the same trusted local network.

## Build from source

Windows:
```powershell
cd windows
python -m PyInstaller --clean --noconfirm InputBridge.spec
```

Android:
```powershell
cd android
.\gradlew.bat assembleDebug
```

Debug builds need no signing setup. To build a signed release APK, copy `android/local.properties.example` to `android/local.properties`, set the Android SDK path and your own keystore values, then run:
```powershell
.\gradlew.bat assembleRelease
```

The original workspace used Java 21, Android SDK Platform 36, and Gradle 9.6.0 via the wrapper.

## Tests

```powershell
cd windows
$env:PYTHONPATH='src'
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Safety and limits

- Default is Laptop mode; errors and disconnects fail back to local input.
- Use only on a **trusted local network**. There is no TLS/encryption yet; HMAC provides integrity/authentication, not confidentiality.
- A visual cursor overlay follows the Windows mouse in Phone mode; Android gestures are still tap/swipe based with status/navigation-bar-aware click mapping, with no native hover. No arbitrary Android system-key injection or secure-desktop/UAC coverage.
- The release signing certificate is for evaluation only, not Play Store or production distribution.
- See `docs/SECURITY.md` for the gap between MVP controls and production requirements.
