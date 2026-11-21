"""Windows low-level input capture with routing-aware suppression.

Hook callbacks stay short: they classify an event, optionally push a small
serialisable record onto a bounded queue, and return immediately. Network
work happens on a separate worker thread in controller.py.

Limitations: low-level hooks do not cover secure desktop/UAC and can be
removed by Windows. A watchdog in controller.py fails safe to Laptop mode.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

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

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_QUIT = 0x0012

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_F12 = 0x7B

SM_CXSCREEN = 0
SM_CYSCREEN = 1
LLKHF_UP = 0x80
LLMHF_INJECTED = 0x10
MOVE_INTERVAL = 0.01
QUEUE_MAXSIZE = 512

LRESULT = ctypes.c_ssize_t
HMENU = getattr(wt, "HMENU", wt.HANDLE)
KeyboardProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
MouseProc = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wt.POINT),
        ("mouseData", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.ToUnicodeEx.argtypes = [
    wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_ubyte), wt.LPWSTR,
    ctypes.c_int, wt.UINT, ctypes.c_void_p,
]
user32.ToUnicodeEx.restype = ctypes.c_int
user32.GetKeyboardLayout.argtypes = [wt.DWORD]
user32.GetKeyboardLayout.restype = ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetForegroundWindow.restype = wt.HWND
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HINSTANCE
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, HMENU, wt.HINSTANCE, ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wt.HWND
user32.DestroyWindow.argtypes = [wt.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
user32.UnhookWindowsHookEx.restype = wt.BOOL
user32.ShowCursor.argtypes = [wt.BOOL]
user32.ShowCursor.restype = ctypes.c_int


class InputCapture:
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_emergency: Callable[[], None],
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.on_toggle = on_toggle
        self.on_emergency = on_emergency
        self.on_error = on_error
        self.events: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._keyboard = False
        self._mouse = False
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._failed = False
        self._thread: Optional[threading.Thread] = None
        self._kb_hook: Optional[int] = None
        self._ms_hook: Optional[int] = None
        self._proc_refs: list[Any] = []
        self._hwnd: Optional[int] = None
        self._toggle_latched = False
        self.hotkeys_active = False
        self._shift_down = False
        self._ctrl_down = False
        self._alt_down = False
        self._last_move = 0.0
        self._cursor_hidden = False
        self._dropped = 0
        self._screen_w = max(1, user32.GetSystemMetrics(SM_CXSCREEN))
        self._screen_h = max(1, user32.GetSystemMetrics(SM_CYSCREEN))

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def running(self) -> bool:
        return not self._failed and self._ready.is_set() and self._thread is not None and self._thread.is_alive()

    def set_routing(self, keyboard: bool, mouse: bool) -> None:
        with self._lock:
            self._keyboard = keyboard
            self._mouse = mouse
            self._set_cursor_hidden(mouse)

    def _set_cursor_hidden(self, hidden: bool) -> None:
        if hidden == self._cursor_hidden:
            return
        if hidden:
            for _ in range(64):
                if user32.ShowCursor(False) < 0:
                    break
        else:
            for _ in range(64):
                if user32.ShowCursor(True) >= 0:
                    break
        self._cursor_hidden = hidden

    def routing(self) -> tuple[bool, bool]:
        with self._lock:
            return self._keyboard, self._mouse

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._ready.clear()
        self._failed = False
        self._toggle_latched = False
        self._shift_down = False
        self._ctrl_down = False
        self._alt_down = False
        self._thread = threading.Thread(target=self._run, name="input-hooks", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("input hooks did not start")

    def stop(self) -> None:
        self._stop.set()
        if self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, WM_QUIT, 0, 0)
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        self._ready.clear()
        self._hwnd = None
        self._set_cursor_hidden(False)

    def _error(self, text: str) -> None:
        if self.on_error:
            try:
                self.on_error(text)
            except Exception:
                pass

    @staticmethod
    def _invoke(callback: Callable[[], None]) -> None:
        threading.Thread(target=callback, daemon=True).start()

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        msg = {"v": 1, "type": "input", "payload": payload}
        try:
            self.events.put_nowait(msg)
        except queue.Full:
            self._dropped += 1
            self._error("input queue full; failing safe")
            self.on_emergency()

    def _run(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        wndproc_type = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        wnd_proc = wndproc_type(lambda hwnd, msg, wp, lp: user32.DefWindowProcW(hwnd, msg, wp, lp))
        self._proc_refs.append(wnd_proc)

        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(wnd_proc, ctypes.c_void_p).value
        wc.hInstance = hinst
        wc.lpszClassName = "InputBridgeHookWndClass"
        user32.RegisterClassW(ctypes.byref(wc))
        self._hwnd = user32.CreateWindowExW(
            0, "InputBridgeHookWndClass", None, 0, 0, 0, 0, 0,
            -3, 0, hinst, None,
        )
        if not self._hwnd:
            self._failed = True
            self._error("could not create hook message window")
            self._ready.set()
            return

        kb_proc = KeyboardProc(self._keyboard_proc)
        ms_proc = MouseProc(self._mouse_proc)
        self._proc_refs.extend([kb_proc, ms_proc])
        self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, kb_proc, hinst, 0)
        if not self._kb_hook:
            self._failed = True
            self._error("keyboard hook failed")
            self._ready.set()
            return
        self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, ms_proc, hinst, 0)
        if not self._ms_hook:
            self._failed = True
            self._error("mouse hook failed")
            user32.UnhookWindowsHookEx(self._kb_hook)
            self._kb_hook = None
            self._ready.set()
            return
        self._ready.set()

        msg = wt.MSG()
        while not self._stop.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._kb_hook:
            user32.UnhookWindowsHookEx(self._kb_hook)
            self._kb_hook = None
        if self._ms_hook:
            user32.UnhookWindowsHookEx(self._ms_hook)
            self._ms_hook = None
        user32.DestroyWindow(self._hwnd)
        self._hwnd = None

    def _keyboard_proc(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode >= 0 and not self._stop.is_set():
            info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = int(info.vkCode)
            scan = int(info.scanCode)
            flags = int(info.flags)
            down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            up = wParam in (WM_KEYUP, WM_SYSKEYUP)

            if vk == VK_SHIFT:
                self._shift_down = down
            elif vk == VK_CONTROL:
                self._ctrl_down = down
            elif vk == VK_MENU:
                self._alt_down = down
            shift = self._shift_down or bool(user32.GetKeyState(VK_SHIFT) & 0x8000)
            ctrl = self._ctrl_down or bool(user32.GetKeyState(VK_CONTROL) & 0x8000)
            alt = self._alt_down or bool(user32.GetKeyState(VK_MENU) & 0x8000)
            emergency = down and vk == VK_F12 and ctrl and alt
            if emergency:
                if not self.hotkeys_active:
                    self._invoke(self.on_emergency)
                return 1

            kb, _ = self.routing()
            toggle = vk == VK_CAPITAL and (shift or kb) and not (flags & LLKHF_UP)
            if toggle and not self._toggle_latched:
                self._toggle_latched = True
                if not self.hotkeys_active:
                    self._invoke(self.on_toggle)
            elif up and vk == VK_CAPITAL:
                self._toggle_latched = False
            if toggle and (self._toggle_latched or kb):
                return 1

            if kb and not (flags & LLMHF_INJECTED):
                char = self._to_unicode(vk, scan, flags) if down else ""
                self._enqueue(
                    {
                        "kind": "key",
                        "action": "down" if down else "up",
                        "vk": vk,
                        "scan": scan,
                        "flags": flags,
                        "char": char,
                        "repeat": bool(flags & 0x8000) and down,
                    }
                )
                return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _mouse_proc(self, nCode: int, wParam: int, lParam: int) -> int:
        if nCode >= 0 and not self._stop.is_set():
            _, ms = self.routing()
            if ms:
                info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                suppress = True
                if wParam == WM_MOUSEMOVE:
                    now = time.monotonic()
                    if now - self._last_move >= MOVE_INTERVAL:
                        self._last_move = now
                        self._enqueue(
                            {
                                "kind": "pointer",
                                "action": "move",
                                "x": round(info.pt.x / self._screen_w, 5),
                                "y": round(info.pt.y / self._screen_h, 5),
                            }
                        )
                    suppress = False
                elif wParam in (WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP,
                                WM_MBUTTONDOWN, WM_MBUTTONUP, WM_XBUTTONDOWN, WM_XBUTTONUP):
                    button = {
                        WM_LBUTTONDOWN: "left", WM_LBUTTONUP: "left",
                        WM_RBUTTONDOWN: "right", WM_RBUTTONUP: "right",
                        WM_MBUTTONDOWN: "middle", WM_MBUTTONUP: "middle",
                        WM_XBUTTONDOWN: "back", WM_XBUTTONUP: "back",
                    }[wParam]
                    self._enqueue(
                        {
                            "kind": "pointer",
                            "action": "down" if wParam in
                                      (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN)
                                      else "up",
                            "button": button,
                            "x": round(info.pt.x / self._screen_w, 5),
                            "y": round(info.pt.y / self._screen_h, 5),
                        }
                    )
                elif wParam == WM_MOUSEWHEEL:
                    delta = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
                    self._enqueue({"kind": "pointer", "action": "wheel", "delta": delta})
                if suppress:
                    return 1
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    @staticmethod
    def _to_unicode(vk: int, scan: int, flags: int) -> str:
        state = (ctypes.c_ubyte * 256)()
        user32.GetKeyboardState.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        if not user32.GetKeyboardState(state):
            return ""
        hwnd = user32.GetForegroundWindow()
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        hkl = user32.GetKeyboardLayout(tid)
        buf = ctypes.create_unicode_buffer(8)
        count = user32.ToUnicodeEx(vk, scan, state, buf, 8, 0, hkl)
        if count <= 0:
            return ""
        text = buf.value
        if flags & 0x8000 and len(text) == 1:
            return text
        return text[:1]
