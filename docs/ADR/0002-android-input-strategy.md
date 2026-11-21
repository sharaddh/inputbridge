# ADR 0002: Android input strategy (staged)

- **Status:** Proposed
- **Date:** 2026-11-18

## Context
Android restricts arbitrary input injection; ordinary apps cannot act as system input drivers. The product needs honest capability reporting.

## Decision (staged)
- **Phase 0/prototype:** ADB over Wi‑Fi for internal validation only (not end-user dependency).
- **MVP candidates:** Android Accessibility Service for supported gestures/pointer actions where feasible; optional IME for text entry only. Report capabilities via `capabilities` message; never claim unsupported actions.
- **Advanced:** Bluetooth HID / virtual-HID style approaches only after feasibility spike (laptop-as-HID peripheral not guaranteed).

## Consequences
- UX and feature set are capability-driven; UI must explain limits.
- Play Store / policy review required if using Accessibility in distributed builds (future consideration).

## Alternatives considered
- Root-required or system-signed drivers: out of scope.
