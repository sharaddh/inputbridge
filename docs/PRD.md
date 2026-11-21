# PRD (Summary)

Source of truth: `../InputBridge_PRD_SRS_TRD.md` (sections 1–5, 12–13).

## Vision
Switch a physical keyboard + wireless mouse between Windows 11 laptop and Android phone using a configurable global shortcut.

## Primary goals (high level)
- Toggle Laptop ↔ Phone via configurable shortcut (default example `Shift + Caps Lock`).
- Routing modes: Both / Keyboard only / Mouse only (plus Paused / safe states).
- Local-only connection (hotspot/same Wi‑Fi), authenticated pairing, no cloud relay.
- Always-visible mode/status, emergency return to Laptop.
- Recoverability: on disconnect/failure, stop forwarding and restore Windows routing.

## Non-goals (first release)
- No system-wide “driver replacement” promise on all Windows contexts (secure desktop/UAC/etc.).
- No iOS. No multi-phone. No gaming-grade latency promises. No input logging/spy behavior.
- No root required on Android.

## Key functional requirements (see full doc)
- FR-01 Default Laptop mode; if app not running, normal Windows input unaffected.
- FR-02 Configurable global shortcut + default restore + conflict warnings.
- FR-03 Routing modes including Paused.
- FR-04 Toggle behavior (debounce key repeat; one deliberate activation).
- FR-05 Emergency return shortcut + tray “Return to Laptop” (local, works if phone down).
- FR-06 Pairing (approve on Android, trust identity, revoke).
- FR-07 Local authenticated transport; show status; no unauth open port.
- FR-08/09 Keyboard/mouse forwarding subject to selected Android injection strategy.
- FR-10 Independent device selection, atomic intent where possible, no false “both routed”.
- FR-11 Disconnect handling: stop, clear, release if possible, return to Laptop, notify, no replay.
- FR-12 System tray actions.
- FR-13 Settings list.
- FR-14 Privacy: no keystroke recording, no clipboard/screenshots by default, no telemetry of input content.

## UX highlights
- Mode always visible; clear Phone-mode indicator; immediate feedback.
- On failure to enter Phone mode, explain why.

## Acceptance criteria
See `InputBridge_PRD_SRS_TRD.md` §13 (AC-01..AC-10).
