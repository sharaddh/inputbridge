# Security

Source of truth: `../InputBridge_PRD_SRS_TRD.md` (§8).

## Principles

- InputBridge is sensitive (it controls input). Only forward when the user explicitly selects Phone mode; show a clear active indicator; allow immediate stop.
- No keystroke content logging. No clipboard/screenshot collection. No cloud relay. No hidden remote control.
- Recoverability beats features: default Laptop, emergency local return, fail closed on errors.

## MVP controls implemented

1. QR-only pairing: Windows displays a QR with its LAN IP, port, and a one-time 128-bit HMAC key; the phone must physically see the screen to scan it.
2. The QR key is used to sign the `pair_request` and `pair_approval` messages; later messages use the same agreed key.
3. **New QR** rotates the key and invalidates the previous phone link; **Forget laptop** clears it on Android.
4. Sequence numbers, timestamps, and replay rejection (`MAX_CLOCK_SKEW_MS`, seen-sequence cache) on both sides.
5. Message size limit (64 KiB) and Android input event rate limit (500 events/s).
6. Status-only logs; no key content, clipboard, or screenshots.
7. Versioned protocol with strict validation and rejection of malformed messages.
8. Windows watchdog and emergency `Ctrl+Alt+F12` local-return path.

## Production gaps

- **No encryption/TLS.** Signing provides integrity/authentication but not confidentiality. MVP is for a trusted local network only.
- The QR is shown openly on the desktop; anyone who can see/photograph it during the session can pair until the key is rotated.
- Revocation is local-only; no device management UI or multi-device identity registry.
- Android Accessibility/IME permissions are powerful and must be explained carefully before enabling.
- No independent security audit or penetration test.
- Release APK uses a self-signed local evaluation certificate, not a production signing key.

## Threat model notes

A local-network attacker can observe traffic metadata but cannot forge signed messages without the QR key. Captured messages cannot be replayed because of sequence tracking. Someone who photographs the QR can pair until the user rotates it with **New QR**. Losing Windows emergency availability is mitigated by default Laptop mode and fail-closed watchdogs, but secure desktop/UAC is out of scope.

## Implementation rules

- Never accept an input session without a valid QR-derived signature.
- On disconnect/session end, restore local routing and release held actions where supported.
- Keep protocol versioned; reject unknown/malformed messages aggressively.
- Keep diagnostics free of input content.
- Move to an encrypted transport before any untrusted-network or production use.
