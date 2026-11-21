# Windows (no .NET)

Python 3.11+, standard library only (Tkinter + ctypes). No pip installs required for running from source.

## Run

```powershell
cd D:\switcher\windows
python -m inputbridge.app
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_app.ps1
```

Run the packaged build: `D:\switcher\release\InputBridge-Windows\InputBridge.exe` (keep `_internal\` beside it).

## What this MVP does

- Shows a QR code containing the laptop LAN IP, port `27123`, and a one-time 128-bit HMAC key.
- **New QR** rotates the key and invalidates the current phone link; **Disconnect phone** restores local input.
- Tk control panel with Laptop / Both / Keyboard-only / Mouse-only / Pause modes.
- `Shift+CapsLock` toggles phone mode; in Phone mode, `CapsLock` alone also returns to Laptop; `Ctrl+Alt+F12` restores local input immediately.
- Low-level keyboard/mouse hooks with routing-aware suppression, bounded queue, worker thread, watchdog, and fail-safe emergency return.
- Signed JSON-lines TCP protocol (`protocol.py`) and authenticated server (`net_server.py`) on port `27123`.
- Pure-stdlib QR encoder (`qrcode.py`, version 5-L) renders the QR directly on the Tk canvas.
- System tray icon with Open / Phone / Laptop / Pause / Exit.
- Log panel shows status only, never key content.

## Settings

- Default phone mode.
- Device identity and name in `~/.inputbridge/config.json`.
- No manual phone IP or pairing code: the QR carries the connection details.

## Build executable

Requires PyInstaller (available in this environment as 6.22.3):

```powershell
cd D:\switcher\windows
python -m PyInstaller --clean --noconfirm InputBridge.spec
```

Output: `dist\InputBridge\InputBridge.exe`.

## Tests

```powershell
cd D:\switcher\windows
$env:PYTHONPATH='src'
python -m unittest discover -s tests -p 'test_*.py' -v
```

Result in this workspace: 11 tests, all passed.

## Probe

The observe-only hook probe is still available:

```powershell
cd D:\switcher\windows
python src\inputbridge\phase0_probe.py
```

## Safety and limits

- Defaults to Laptop mode; failures/disconnects restore local input.
- HMAC-SHA256 provides integrity/authentication, not confidentiality. Use only on a trusted local network.
- Text injection requires the InputBridge IME selected on Android; gestures require the Accessibility service enabled.
- No secure-desktop/UAC coverage. See `..\docs\SECURITY.md` and `..\FINAL_BUILD_STATUS.md`.
