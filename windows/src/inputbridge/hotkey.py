"""Global hotkey via RegisterHotKey + a hidden message window (stdlib ctypes).

This is a scaffold: registers a hotkey and invokes a callback when WM_HOTKEY arrives.
Run the message pump on a background thread; the callback is invoked from that thread,
so UI code must marshal to the main thread (e.g. root.after).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
from typing import Callable, Optional

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

VK_CAPITAL = 0x14
VK_F12 = 0x7B
VK_P = 0x50
WM_QUIT = 0x0012
LRESULT = ctypes.c_ssize_t

if not hasattr(wt, "WNDCLASSW"):
    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wt.UINT),
            ("lpfnWndProc", ctypes.c_void_p),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wt.HINSTANCE),
            ("hIcon", wt.HANDLE),
            ("hCursor", wt.HANDLE),
            ("hbrBackground", wt.HANDLE),
            ("lpszMenuName", wt.LPCWSTR),
            ("lpszClassName", wt.LPCWSTR),
        ]
else:
    WNDCLASSW = wt.WNDCLASSW

kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HINSTANCE
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wt.HWND
user32.DestroyWindow.argtypes = [wt.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wt.BOOL


class HotkeyManager:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._stop = threading.Event()
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._next_id = 1

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._hwnd = None
        self._callbacks.clear()

    def register(self, mods: int, vk: int, callback: Callable[[], None]) -> int:
        if not self._thread or not self._thread.is_alive():
            self.start()
        for _ in range(50):
            if self._hwnd:
                break
            threading.Event().wait(0.05)
        if not self._hwnd:
            raise RuntimeError("Hotkey window not ready")
        hid = self._next_id
        self._next_id += 1
        if not user32.RegisterHotKey(self._hwnd, hid, mods | MOD_NOREPEAT, vk):
            err = ctypes.get_last_error()
            raise OSError(f"RegisterHotKey failed (err={err}). Hotkey may be in use.")
        self._callbacks[hid] = callback
        return hid

    def unregister_all(self) -> None:
        if not self._hwnd:
            self._callbacks.clear()
            return
        for hid in list(self._callbacks.keys()):
            try:
                user32.UnregisterHotKey(self._hwnd, hid)
            except Exception:
                pass
        self._callbacks.clear()

    def _run_loop(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self._wnd_proc_ref = WNDPROC(self._wnd_proc)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(self._wnd_proc_ref, ctypes.c_void_p).value
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = "InputBridgeHotkeyWndClass"
        user32.RegisterClassW(ctypes.byref(wc))
        HWND_MESSAGE = -3
        self._hwnd = user32.CreateWindowExW(0, "InputBridgeHotkeyWndClass", None, 0, 0, 0, 0, 0, HWND_MESSAGE, 0, hinst, None)
        if not self._hwnd:
            self._hwnd = user32.CreateWindowExW(0, "InputBridgeHotkeyWndClass", None, 0, 0, 0, 0, 0, 0, 0, hinst, None)
        if not self._hwnd:
            return

        msg = wt.MSG()
        while not self._stop.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                hid = int(msg.wParam)
                cb = self._callbacks.get(hid)
                if cb:
                    try:
                        cb()
                    except Exception:
                        pass
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self.unregister_all()
        try:
            if self._hwnd:
                user32.DestroyWindow(self._hwnd)
        except Exception:
            pass
        self._hwnd = None

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

