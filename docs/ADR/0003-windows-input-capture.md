# ADR 0003: Windows input capture and suppression (experimental)

- **Status:** Proposed
- **Date:** 2026-11-18

## Context
Need to observe/switch routing for physical keyboard and wireless-mouse-dongle input on Windows 11. Raw Input observes but does not suppress; low-level hooks can suppress in many desktop cases but are risky and limited (secure desktop/UAC, timeouts, hook safety).

## Decision
- Use **Raw Input** for device identification/observation where helpful.
- Use **low-level hooks** only as a tested suppression mechanism for ordinary desktop contexts, with strict rules:
  - minimal work in callbacks, no network I/O;
  - bounded queue + worker thread + watchdog;
  - emergency shortcut must remain recoverable (never break local return path);
  - on failure → fail safe (stop suppression, return to Laptop).
- Defer virtual HID/driver approach to Phase 3 feasibility.

## Consequences
- Some contexts (secure desktop, login, certain elevated flows) may not be suppressible; product must document limits.
- Stability work (watchdog, cleanup of stuck keys/buttons) is mandatory.
