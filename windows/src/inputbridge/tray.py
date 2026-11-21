"""Minimal Windows system-tray icon using ctypes only (no pip dependencies)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
from typing import Callable, Optional

if not hasattr(wt, "WNDCLASSW"):
    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
            ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
            ("hInstance", wt.HINSTANCE), ("hIcon", wt.HANDLE),
            ("hCursor", wt.HANDLE), ("hbrBackground", wt.HANDLE),
            ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
        ]
else:
    WNDCLASSW = wt.WNDCLASSW


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uTimeoutOrVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wt.HICON),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
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
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.DestroyWindow.argtypes = [wt.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.CreatePopupMenu.restype = wt.HMENU
user32.TrackPopupMenu.restype = wt.UINT
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = wt.BOOL

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x1
NIF_ICON = 0x2
NIF_TIP = 0x4
WM_APP_TRAY = 0x8001
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
MF_STRING = 0x0
MF_SEPARATOR = 0x800
TPM_RETURNCMD = 0x100
TPM_RIGHTBUTTON = 0x2
IDI_APPLICATION = 32512

MENU_ITEMS = [
    (1, "Open InputBridge"),
    (0, None),
    (2, "Switch to Phone"),
    (3, "Return to Laptop"),
    (4, "Pause"),
    (0, None),
    (5, "Settings"),
    (6, "Exit"),
]


class TrayIcon:
    def __init__(self, on_command: Callable[[str], None], on_status: Optional[Callable[[str], None]] = None):
        self.on_command = on_command
        self.on_status = on_status
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._tip = "InputBridge: Laptop"

    @property
    def running(self) -> bool:
        return self._ready.is_set() and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def set_tip(self, text: str) -> None:
        self._tip = text[:127]
        if not self._hwnd:
            return
        nid = self._make_nid()
        nid.uFlags = NIF_TIP
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def stop(self) -> None:
        self._stop.set()
        if self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, 0x0010, 0, 0)
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None

    def _make_nid(self) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_APP_TRAY
        nid.hIcon = user32.LoadIconW(None, IDI_APPLICATION)
        nid.szTip = self._tip
        return nid

    def _run(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        wndproc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        wnd_proc = wndproc_type(self._wnd_proc)
        self._wnd_proc_ref = wnd_proc
        wc = WNDCLASSW()
        wc.lpfnWndProc = ctypes.cast(wnd_proc, ctypes.c_void_p).value
        wc.hInstance = hinst
        wc.lpszClassName = "InputBridgeTrayWndClass"
        user32.RegisterClassW(ctypes.byref(wc))
        self._hwnd = user32.CreateWindowExW(
            0, "InputBridgeTrayWndClass", "InputBridge", 0, 0, 0, 0, 0, 0, 0, hinst, None
        )
        if not self._hwnd:
            self._ready.set()
            return
        user32.ShowWindow(self._hwnd, 0)
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._make_nid()))
        self._ready.set()

        msg = wt.MSG()
        while not self._stop.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._make_nid()))
        user32.DestroyWindow(self._hwnd)
        self._hwnd = None

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_APP_TRAY:
            if lparam in (WM_RBUTTONUP, WM_LBUTTONDBLCLK):
                self._show_menu()
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self) -> None:
        hmenu = user32.CreatePopupMenu()
        for cmd, label in MENU_ITEMS:
            if label is None:
                user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            else:
                user32.AppendMenuW(hmenu, MF_STRING, cmd, label)
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self._hwnd)
        selected = user32.TrackPopupMenu(
            hmenu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, self._hwnd, None
        )
        user32.DestroyMenu(hmenu)
        names = {1: "open", 2: "phone", 3: "laptop", 4: "pause", 5: "settings", 6: "exit"}
        if selected in names:
            try:
                self.on_command(names[selected])
            except Exception as exc:
                if self.on_status:
                    self.on_status(f"Tray error: {exc}")
