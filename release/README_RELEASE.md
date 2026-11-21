# Release artifacts

QR-only MVP built on 2026-11-21 from the current source.

## Windows

- Folder: `InputBridge-Windows\`
- Run: `InputBridge-Windows\InputBridge.exe`
- Keep `_internal\` next to the EXE.
- PyInstaller one-folder build from `windows/src/inputbridge/app.py`.
- `InputBridge.exe` size: 1,973,356 bytes.
- SHA-256: `1601123C8FB0FAB824A6E037CC2BDB3CEF07AC9E008E5067425E7061A247AE8F`

## Android

- `InputBridge-Android\InputBridge-release.apk` — signed, installable, evaluation certificate.
  - Size: 5,409,554 bytes.
  - SHA-256: `4C84A567F38DDF5A5171F2689E1FE07C8FCB8991992E3AA64A5873BB7683EBAA`
  - Signer DN: `CN=InputBridge MVP, OU=Local, O=InputBridge, L=Local, ST=Local, C=US`
  - Certificate SHA-256 digest: `aa0542db2feb9f1e2b33856ad8eba952a0d1a4cd8720769d696b2cf3626e9535`
- `InputBridge-Android\InputBridge-debug.apk` — debug-signed development build.
  - Size: 7,567,432 bytes.
  - SHA-256: `DC1662B42881FC4F50B831197783383196CD9E01FDF16C2E9640CD52B1835EB5`

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
6. Use routing buttons or `Shift+CapsLock` on Windows; in Phone mode, `CapsLock` alone also returns to Laptop; use `Ctrl+Alt+F12` for emergency local return.
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

- Trusted local network only; HMAC-SHA256 authentication/integrity, no TLS/encryption.
- A visual cursor overlay follows the Windows mouse in Phone mode while the accessibility service is enabled; mouse movement is coalesced to reduce delay. Android gestures are still tap/swipe based with status/navigation-bar-aware click mapping, not native mouse semantics.
- No arbitrary system-key injection or secure-desktop/UAC coverage.
- No on-device camera/connectivity smoke test was performed in this environment.
