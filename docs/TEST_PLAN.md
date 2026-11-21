# Test plan (Summary)

Source of truth: `../InputBridge_PRD_SRS_TRD.md` (§14, §21).

## Levels
- **Unit:** shortcut parse/validate, modifier tracking, routing state transitions, repeat suppression, (de)serialization, seq validation, capability negotiation, heartbeat/timeouts, queue overflow, cleanup.
- **Windows integration:** built-in/USB/wireless keyboards, wireless mouse dongle, multi-device cases, layouts, Caps/Num, sleep/resume, crash/restart, elevated apps, hook failure, emergency under network loss.
- **Android integration:** target Vivo (Android 15), screen on/off, orientation, scaling, permission granted/denied, IME states, battery optimization, background, hotspot toggles, lock/unlock, overlays, supported/unsupported events.
- **Network:** hotspot/same Wi‑Fi, interruption, IP change, sleep/resume, app killed, high rate, malformed/duplicate/delayed packets, unknown client.
- **Safety (release blockers):** disconnect never leaves local input suppressed unintentionally; emergency shortcut never forwarded as normal key; stuck modifiers cleaned or local route restored; shutdown restores normal input; no replay after reconnect; user can recover without touching phone.

## Prototype exit criteria
See `InputBridge_PRD_SRS_TRD.md` §21 (10 points).
