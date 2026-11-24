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

## Application layout

- **Home** - one primary action (`Switch to Phone` / `Return to Laptop`), an unmistakable Laptop/Phone ownership diagram, secondary quick routing (Both / Keyboard / Mouse / Pause), an always-available Emergency return, and a compact connection summary. The QR pairing card is shown only while disconnected or unpaired.
- **Settings** - General, Shortcuts, Devices, Input, Appearance and Advanced tabs. All values are persisted in `~/.inputbridge/config.json`.
- **Diagnostics** - phone capabilities, honest "Not available" pointer metrics, and the status-only log with export/clear. Raw logs are no longer on the home screen.

`New QR` rotates the pairing secret and invalidates the previous phone link. `Disconnect phone` restores local input. `Revoke pairing` in Devices stops the server and clears the stored pairing secret.

## Settings

| Section | Options |
| --- | --- |
| General | Start minimized, switch notifications, startup mode, named profile |
| Shortcuts | Toggle and emergency display labels, live normalization, conflict validation, restore defaults |
| Devices | Laptop name, phone name, auto-connect, re-pair, revoke |
| Input | Default phone routing, pointer rate 30/60/120 Hz, scroll direction, scroll sensitivity, right/middle button actions |
| Appearance | System/Light/Dark theme, accent preset, compact/comfortable density, Touch Pointer shape/size/fill/outline/trail/ripple with live preview |
| Advanced | Diagnostics toggle, log export, heartbeat timeout, developer note |

Theme and density preview immediately; changes are written with `Save settings`. Existing configuration keys (`host`, `port`, `device_id`, `device_name`, `paired_token`, `default_mode`, `auto_connect`, `toggle_shortcut_display`, `emergency_shortcut_display`, `notifications`) remain supported, along with the new personalization keys.

The app passes `pointer_interval=1.0 / float(pointer_rate_hz)` to `BridgeController`. This requires the controller to accept the optional `pointer_interval` keyword; older controller revisions will fail at startup.

## Behavior and limits

- Defaults to Laptop mode; disconnect, emergency return and shutdown restore local input.
- `Shift+CapsLock` toggles phone mode, `CapsLock` returns to Laptop while in Phone mode, and `Ctrl+Alt+F12` is the emergency return. Shortcut fields in Settings are labels; changing them does not rebind the OS hotkeys until the input engine supports it.
- Touch Pointer is an accessibility-gesture compatibility layer: no native Android hover, drag, wheel, right-click or native mouse support. Some apps will not behave like desktop apps.
- Pairing is HMAC-SHA256 signed; post-pairing input/control messages are AES-256-GCM encrypted. Use only on a trusted local network. Logs contain status only, never typed keys, text or tokens.
- Button mappings, cursor appearance and scroll preferences are persisted locally and applied when the input engine and phone companion support them.
- No secure-desktop/UAC coverage. See `..\docs\SECURITY.md` and `..\FINAL_BUILD_STATUS.md`.

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
