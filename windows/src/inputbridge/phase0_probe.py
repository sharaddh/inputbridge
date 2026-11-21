#!/usr/bin/env python3
"""
Phase 0 Windows input probe (observe only by default).

- Installs WH_KEYBOARD_LL and WH_MOUSE_LL hooks via ctypes.
- Logs events to stdout (and optional file). Does NOT suppress by default.
- Press Ctrl+C to stop; hooks are uninstalled in finally block.

Run on Windows 11:
  cd D:\\switcher\\windows
  python src\\inputbridge\\phase0_probe.py

Safety: This is for feasibility testing. Do not enable suppression without understanding risks (TRD §7.2).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time
from datetime import datetime, timezone
from typing import Optional

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A

# Hook proc types
LowLevelKeyboardProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wt.WPARAM, wt.LPARAM)
LowLevelMouseProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wt.WPARAM, wt.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wt.POINT),
        ("mouseData", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


_kb_hook = None  # keep ref
_ms_hook = None
_kb_proc_ref = None
_ms_proc_ref = None
_log_file = None
_start = time.time()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _log(line: str) -> None:
    print(line, flush=True)
    if _log_file:
        try:
            _log_file.write(line + "\n")
            _log_file.flush()
        except Exception:
            pass


def _kbd_proc(nCode: int, wParam: int, lParam: int) -> int:
    if nCode >= 0:
        try:
            info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            msg = {WM_KEYDOWN: "KEYDOWN", WM_KEYUP: "KEYUP", WM_SYSKEYDOWN: "SYSKEYDOWN", WM_SYSKEYUP: "SYSKEYUP"}.get(
                wParam, f"MSG_{wParam:#x}"
            )
            elapsed = time.time() - _start
            _log(f"[{_ts()} +{elapsed:8.3f}s] KB {msg} vk=0x{info.vkCode:02X} scan=0x{info.scanCode:02X} flags=0x{info.flags:08X}")
        except Exception as e:
            _log(f"[probe] keyboard parse error: {e}")
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def _mouse_proc(nCode: int, wParam: int, lParam: int) -> int:
    if nCode >= 0:
        try:
            info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            msg_map = {
                WM_MOUSEMOVE: "MOVE",
                WM_LBUTTONDOWN: "LBUTTONDOWN",
                WM_LBUTTONUP: "LBUTTONUP",
                WM_RBUTTONDOWN: "RBUTTONDOWN",
                WM_RBUTTONUP: "RBUTTONUP",
                WM_MOUSEWHEEL: "WHEEL",
            }
            msg = msg_map.get(wParam, f"MSG_{wParam:#x}")
            elapsed = time.time() - _start
            extra = ""
            if wParam == WM_MOUSEWHEEL:
                delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
                extra = f" wheelDelta={delta}"
            _log(
                f"[{_ts()} +{elapsed:8.3f}s] MS {msg} x={info.pt.x} y={info.pt.y}{extra} flags=0x{info.flags:08X}"
            )
        except Exception as e:
            _log(f"[probe] mouse parse error: {e}")
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


def install_hooks(log_path: Optional[str] = None) -> None:
    global _kb_hook, _ms_hook, _kb_proc_ref, _ms_proc_ref, _log_file
    if log_path:
        _log_file = open(log_path, "a", encoding="utf-8")
        _log(f"\n--- probe session start {_ts()} ---")

    _kb_proc_ref = LowLevelKeyboardProc(_kbd_proc)
    _ms_proc_ref = LowLevelMouseProc(_mouse_proc)

    _kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _kb_proc_ref, kernel32.GetModuleHandleW(None), 0)
    if not _kb_hook:
        raise OSError(f"SetWindowsHookExW (keyboard) failed: {ctypes.get_last_error()}")

    _ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, _ms_proc_ref, kernel32.GetModuleHandleW(None), 0)
    if not _ms_hook:
        user32.UnhookWindowsHookEx(_kb_hook)
        _kb_hook = None
        raise OSError(f"SetWindowsHookExW (mouse) failed: {ctypes.get_last_error()}")

    _log("[probe] hooks installed (observe only). Ctrl+C to stop.")


def uninstall_hooks() -> None:
    global _kb_hook, _ms_hook, _log_file
    try:
        if _kb_hook:
            user32.UnhookWindowsHookEx(_kb_hook)
            _kb_hook = None
        if _ms_hook:
            user32.UnhookWindowsHookEx(_ms_hook)
            _ms_hook = None
        _log("[probe] hooks uninstalled.")
    finally:
        if _log_file:
            try:
                _log_file.close()
            except Exception:
                pass
            _log_file = None


def run_message_loop() -> None:
    msg = wt.MSG()
    # GetMessage returns -1 on error, 0 on WM_QUIT, >0 otherwise
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == -1:
            raise OSError(f"GetMessageW failed: {ctypes.get_last_error()}")
        if ret == 0:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def main() -> int:
    if sys.platform != "win32":
        print("This probe is Windows-only.", file=sys.stderr)
        return 2

    log_path = None
    if len(sys.argv) > 1 and sys.argv[1] == "--log":
        log_path = sys.argv[2] if len(sys.argv) > 2 else "phase0_probe.log"
        print(f"[probe] logging to {log_path}")

    try:
        install_hooks(log_path=log_path)
        run_message_loop()
    except KeyboardInterrupt:
        print("\n[probe] interrupted, uninstalling hooks...")
    except Exception as e:
        print(f"[probe] error: {e}", file=sys.stderr)
        return 1
    finally:
        uninstall_hooks()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
