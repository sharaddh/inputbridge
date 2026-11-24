# Release artifacts

QR-only Touch Pointer MVP v0.3.1-fix built on 2026-11-22 from the current source.

## Windows

- Folder: `InputBridge-Windows\`
- Run: `InputBridge-Windows\InputBridge.exe`
- Keep `_internal\` next to the EXE.
- PyInstaller one-folder build from `windows/src/inputbridge/app.py`.
- `InputBridge.exe` size: 2,292,280 bytes.
- SHA-256: `5D0F674FA97962B77B289C01F754CB26DD7AEAFC1638276BBA3BAA93C04D94D3`

## Android

- `InputBridge-Android\InputBridge-release.apk` — signed, installable, evaluation certificate.
  - Size: 5,482,651 bytes.
  - SHA-256: `123823D12A8F4058D9AD72E0D581A00E339A7AB5C6E13EA560D6FE644B6C7C33`
  - Signer DN: `CN=InputBridge MVP, OU=Local, O=InputBridge, L=Local, ST=Local, C=US`
  - Certificate SHA-256 digest: `aa0542db2feb9f1e2b33856ad8eba952a0d1a4cd8720769d696b2cf3626e9535`
- `InputBridge-Android\InputBridge-debug.apk` — debug-signed development build.
  - Size: 6,886,519 bytes.
  - SHA-256: `0E72AE3B4D25EF5DFE67826561323D5C49CAEFBF45B3161B3E890615EE36213F`

Android version: `0.3.1-fix` (`versionCode=4`).

## Performance and UX changes

- Windows uses a latest-value pointer slot and paced 60 Hz sender (30/60/120 Hz selectable), with stale/unchanged point rejection and diagnostics.
- Android uses Choreographer frame callbacks, WindowMetrics/WindowInsets mapping, hotspot-aware cursor placement, calibration offsets, and latest-point taps/scrolls.
- The accessibility service no longer listens to all accessibility events or retrieves window content; status/log updates are coalesced.
- Wheel events are coalesced into one gesture at the current cursor point; pointer-move ACK traffic was removed.
- Both apps now have a primary action, setup checklist, Diagnostics, and theme/device name/scroll/button/cursor personalization.
- Post-pairing messages use AES-256-GCM protocol v2; pairing remains HMAC-signed protocol v1.
- v0.3.1-fix re-asserts routing mode every 5 seconds, restores the cursor when the Accessibility service starts after a mode message, adds an IME fallback for non-text key events, and fixes Windows/Android button contrast.

Install with adb:
```powershell
& 'C:\Users\wwwsh\AppData\Local\Android\Sdk\platform-tools\adb.exe' install -r 'D:\switcher\release\InputBridge-Android\InputBridge-release.apk'
```

Or copy the APK to the phone and install manually (allow unknown sources).

## First-run sequence (QR only)

1. Run the Windows app; a QR appears in the **Pair with phone (QR)** panel.
2. On Android, open InputBridge, grant camera permission, and tap **Scan laptop QR**.
3. Point the camera at the Windows QR. The phone connects automatically; there is no manual IP or pairing code.
4. Enable the Accessibility service for taps/swipes, and select the InputBridge keyboard for typing in text fields.
5. The Android cursor stays hidden in Laptop mode and appears only after switching to Phone mode. If it does not appear then, tap **Allow cursor overlay** and grant **Display over other apps**, then reopen InputBridge; the phone log will show `Cursor overlay added...` or the exact failure. The Windows cursor is hidden only while Phone mode includes mouse routing and returns automatically in Laptop mode.
6. After pairing, press **Switch to Phone** (or use `Shift+CapsLock`); connection alone leaves input on the laptop. In Phone mode, `CapsLock` alone also returns to Laptop; use `Ctrl+Alt+F12` for emergency local return.
7. Tap **New QR** on Windows only when you intend to rescan; it rotates the key and permanently invalidates the phone's saved token. Brief connection drops now auto-reconnect without pressing it.

On Realme UI, accessibility is under **Additional settings → Accessibility → Downloaded services → InputBridge**. The keyboard is under **Additional settings → Languages & input → Manage keyboards → InputBridge**; also switch to it from the keyboard icon when a text field is focused. If the phone shows `IME=false`, the InputBridge keyboard is not currently selected. Windows requests capabilities every 5 seconds, so the Windows panel refreshes automatically while connected.

Both devices must be on the same trusted local network.

## Rebuild commands

Windows:
```powershell
cd D:\switcher\windows
python -m PyInstaller --clean --noconfirm InputBridge.spec
```

Android:
```powershell
cd D:\switcher\android
$env:JAVA_HOME='D:\android studio\jbr'
.\gradlew.bat assembleDebug assembleRelease
```

The release signing keystore is `D:\switcher\release\inputbridge-release.jks`; it is self-signed for evaluation only. Do not use it for production/Play Store distribution.

## MVP limits

- Trusted local network only; pairing is HMAC-signed and post-pairing traffic is AES-256-GCM encrypted, but there is no TLS or production key management.
- Touch Pointer has hotspot-aware cursor rendering, calibration, and WindowMetrics/Insets mapping, but remains accessibility-gesture based, not native mouse semantics. No true hover/drag/wheel semantics in all apps.
- No arbitrary system-key injection or secure-desktop/UAC coverage.
- No on-device camera/connectivity/latency smoke test was performed in this environment.
