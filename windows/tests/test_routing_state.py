import ctypes
import threading
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import inputbridge.input_capture as input_capture  # noqa: E402
from inputbridge.routing_state import RoutingMode, RoutingStateMachine  # noqa: E402


class TestRoutingStateMachine(unittest.TestCase):
    def test_default_laptop(self) -> None:
        sm = RoutingStateMachine()
        self.assertEqual(sm.current, RoutingMode.LAPTOP)

    def test_toggle_and_emergency(self) -> None:
        sm = RoutingStateMachine()
        sm.set_mode(RoutingMode.PHONE_BOTH)
        self.assertEqual(sm.current, RoutingMode.PHONE_BOTH)
        sm.emergency_return_to_laptop()
        self.assertEqual(sm.current, RoutingMode.LAPTOP)


class TestInputHotkeys(unittest.TestCase):
    def test_shift_caps_toggle_while_phone_routing(self) -> None:
        toggles = []
        emergency = threading.Event()
        done = threading.Event()

        def on_toggle() -> None:
            toggles.append(True)
            done.set()

        capture = input_capture.InputCapture(on_toggle, emergency.set)
        capture.set_routing(True, True)
        capture._stop.clear()

        original_get_key_state = input_capture.user32.GetKeyState
        original_call_next = input_capture.user32.CallNextHookEx
        input_capture.user32.GetKeyState = lambda vk: 0
        input_capture.user32.CallNextHookEx = lambda *args: 0

        def event(vk: int, down: bool = True) -> None:
            flags = 0 if down else input_capture.LLKHF_UP
            struct = input_capture.KBDLLHOOKSTRUCT(vk, 0, flags, 0, 0)
            message = input_capture.WM_KEYDOWN if down else input_capture.WM_KEYUP
            capture._keyboard_proc(0, message, ctypes.addressof(struct))

        try:
            for _ in range(2):
                event(input_capture.VK_SHIFT)
                event(input_capture.VK_CAPITAL)
                event(input_capture.VK_CAPITAL, False)
                event(input_capture.VK_SHIFT, False)
            event(input_capture.VK_CONTROL)
            event(input_capture.VK_MENU)
            event(input_capture.VK_F12)
            self.assertTrue(done.wait(1))
            self.assertTrue(emergency.wait(1))
            self.assertEqual(len(toggles), 2)

            done.clear()
            event(input_capture.VK_CAPITAL)
            event(input_capture.VK_CAPITAL, False)
            self.assertTrue(done.wait(1))
            self.assertEqual(len(toggles), 3)
        finally:
            input_capture.user32.GetKeyState = original_get_key_state
            input_capture.user32.CallNextHookEx = original_call_next


if __name__ == "__main__":
    unittest.main()
