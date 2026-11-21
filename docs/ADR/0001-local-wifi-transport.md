# ADR 0001: Local Wi‑Fi / hotspot transport (initial)

- **Status:** Proposed
- **Date:** 2026-11-18

## Context
InputBridge must work without internet, using phone hotspot or same local network between Windows laptop and Android phone.

## Decision
Use an authenticated local transport on LAN/hotspot for MVP/prototype direction:
- Prefer **WebSocket over TLS** (or TLS TCP) for production.
- Prototype may use a simpler local channel on trusted hotspot only if isolated behind pairing+auth immediately after; must not ship unauthenticated listener.

## Consequences
- Must handle hotspot client isolation, IP changes, firewall rules, reconnects.
- No replay of stale input after reconnect.
- Discovery/pairing flow must surface connection guidance to users.

## Alternatives considered
- Cloud relay: rejected (privacy, latency, internet dependency).
- Bluetooth data transport: considered later for discovery/aux; does not solve Android input injection/HID role by itself.
