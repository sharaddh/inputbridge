# Phase 0 spike — Windows input (notes)

Goal: validate what’s possible on Windows 11 before building full suppression/routing.

## What to validate (from TRD)
- Global shortcut detection approach (low-level keyboard hook vs `RegisterHotKey`) and pitfalls (key repeat, modifiers, Caps Lock behavior).
- Raw Input: can observe devices/events and identify device handles; confirm it does **not** suppress normal input.
- Low-level hooks (`WH_KEYBOARD_LL`, `WH_MOUSE_LL`): observe + test suppression in ordinary desktop apps; document limitations (secure desktop/UAC, timeouts, must be fast, no network I/O).
- Emergency recovery: ensure we can always restore Laptop/local behavior (design watchdog/fail-safe).

## Manual test checklist (run on target laptop)
1. Log Windows version/build, input devices (built-in keyboard, USB/wireless mouse dongle).
2. Run probe app: press configured test chord; confirm single toggle intent (no repeat storm).
3. With probe observing, type in Notepad and move mouse: confirm events seen; confirm normal behavior unchanged unless suppression explicitly enabled.
4. Test hook suppression in a normal app only (document results). Test `Win+L`, UAC prompt, elevated app — expect limitations.
5. Kill probe process: confirm normal input restored.

## Outputs to record
- What worked / what failed
- Whether suppression is acceptable for MVP scope or if driver/HID path needed
- Recommended MVP input strategy decision
