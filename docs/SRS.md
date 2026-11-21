# SRS (Summary)

Source of truth: `../InputBridge_PRD_SRS_TRD.md` (sections 6, 9, 12).

## System context
Two apps + authenticated local channel:
- Windows 11 app (tray + settings): shortcut manager, routing state machine, adapters, network client, pairing.
- Android companion (Kotlin): pairing/connection, protocol decode, capability manager, input adapters, status UI.

## Operating environment
- Windows 11 64-bit (initial). No admin required for ordinary UI/network; some advanced approaches may require elevation (separately assessed).
- Android 11+ dev target noted; initial test device Vivo Android 15. Permissions vary by strategy (Accessibility/IME/ADB dev-only).

## External interfaces
- Windows UI: tray, main window, shortcut recorder, mode selector, status, pairing, diagnostics.
- Android UI: welcome, pairing approval, status, permissions/capabilities, disconnect/revoke, diagnostics.
- Network: authenticated local link (recommended production: TLS/TCP or WebSocket over TLS; prototype may start simpler but must harden before release).

## Data/protocol notes
- Versioned JSON envelope examples in full doc (§6.4). Rules: monotonic sequence per session, reject malformed/out-of-order, authenticate, rate/size limits, no typed text in logs, normalized coords when needed, always release keys/buttons on session end where supported.

## Non-functional (selected)
- Shortcut transition target < 150 ms (not guaranteed); fail closed to Laptop on unhealthy phone route.
- Only paired devices establish sessions; no input-content logging.

## UI specs
See full doc §12 (layouts/state colors guidance: don’t rely on color alone).
