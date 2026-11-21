# Protocol (draft)

See full message examples and rules in `../InputBridge_PRD_SRS_TRD.md` (§6.4, §11).

## Principles
- Versioned messages (`protocolVersion`).
- Authenticated sessions only.
- Monotonic `sequence` per session; reject malformed/out-of-order.
- Android sends `capabilities` after session setup; Windows must not send unsupported event types.
- On disconnect/session end, send/trigger `release_all` semantics where supported.

## Files
- `messages/` — JSON examples (to be expanded).
- `schemas/` — JSON Schema files (future).
