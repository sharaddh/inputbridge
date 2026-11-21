"""Routing controller: joins hooks, state machine, transport and watchdog."""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

from inputbridge.hotkey import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    VK_CAPITAL,
    VK_F12,
    HotkeyManager,
)
from inputbridge.input_capture import InputCapture
from inputbridge.net_server import BridgeServer
from inputbridge.routing_state import RoutingMode, RoutingStateMachine

PHONE_MODES = {
    RoutingMode.PHONE_BOTH: (True, True),
    RoutingMode.PHONE_KEYBOARD: (True, False),
    RoutingMode.PHONE_MOUSE: (False, True),
}
MOVE_SEND_INTERVAL = 1.0 / 30.0


class BridgeController:
    def __init__(
        self,
        client: BridgeServer,
        on_mode: Optional[Callable[[RoutingMode], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_capabilities: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.client = client
        self.sm = RoutingStateMachine()
        self.on_mode = on_mode
        self.on_status = on_status
        self.on_capabilities = on_capabilities
        self.desired_phone_mode = RoutingMode.PHONE_BOTH
        self.capabilities: Dict[str, Any] = {}
        self._stop = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._watchdog: Optional[threading.Thread] = None
        self.hotkeys = HotkeyManager()
        self._last_tick = time.monotonic()
        self._pending_move: Optional[Dict[str, Any]] = None
        self._last_move_send = 0.0
        self._connection_state = "disconnected"
        self.capture = InputCapture(
            on_toggle=self.toggle,
            on_emergency=self.emergency,
            on_error=self._status,
        )
        self.sm.add_listener(self._emit_mode)
        client.on_state = self._on_connection_state
        client.on_message = self._on_message

    def _status(self, text: str) -> None:
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

    def _emit_mode(self, mode: RoutingMode) -> None:
        if self.on_mode:
            try:
                self.on_mode(mode)
            except Exception:
                pass
        self._status(f"Mode: {mode.value}")

    def start(self) -> None:
        self.capture.start()
        try:
            self.hotkeys.register(MOD_SHIFT, VK_CAPITAL, self.toggle)
            self.hotkeys.register(MOD_CONTROL | MOD_ALT, VK_F12, self.emergency)
            self.capture.hotkeys_active = True
            self._status("Global hotkeys registered")
        except (OSError, RuntimeError) as exc:
            self.hotkeys.unregister_all()
            self.capture.hotkeys_active = False
            self._status(f"Global hotkeys in use; using hook fallback ({exc})")
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="input-forward", daemon=True)
        self._worker.start()
        self._watchdog = threading.Thread(target=self._watch, name="safety-watchdog", daemon=True)
        self._watchdog.start()
        self._last_tick = time.monotonic()

    def stop(self) -> None:
        self._stop.set()
        self.hotkeys.stop()
        self.capture.hotkeys_active = False
        self.emergency()
        self.capture.stop()
        if self._worker:
            self._worker.join(timeout=2)
        if self._watchdog:
            self._watchdog.join(timeout=2)
        self._worker = None
        self._watchdog = None

    def _active_routing(self) -> tuple[bool, bool]:
        return PHONE_MODES.get(self.sm.current, (False, False))

    def _apply_routing(self) -> None:
        kb, ms = self._active_routing()
        self.capture.set_routing(kb, ms)
        self.client.send(
            "mode",
            {
                "mode": self.sm.current.value,
                "keyboard": kb,
                "mouse": ms,
            },
        )

    def set_mode(self, mode: RoutingMode) -> None:
        if mode in PHONE_MODES:
            self.desired_phone_mode = mode
            if not self.capture.running:
                self._status("Input hooks not running; cannot enable phone mode")
                return
            if not self.client.connected or not self.client.paired:
                self.sm.set_mode(RoutingMode.CONNECTING)
                self._status("Phone not paired/connected; waiting for link")
            else:
                self.sm.set_mode(mode)
                self._apply_routing()
        else:
            self.sm.set_mode(mode)
            self.capture.set_routing(False, False)
            self.client.send("mode", {"mode": mode.value, "keyboard": False, "mouse": False})
            if mode == RoutingMode.LAPTOP:
                self.client.send("release_all", {"reason": "laptop-mode"})

    def toggle(self) -> None:
        if self.sm.current in PHONE_MODES:
            self.set_mode(RoutingMode.LAPTOP)
        else:
            self.set_mode(self.desired_phone_mode)

    def emergency(self) -> None:
        was_phone_mode = self.sm.current in PHONE_MODES
        self._pending_move = None
        self.sm.emergency_return_to_laptop()
        self.capture.set_routing(False, False)
        try:
            while True:
                self.capture.events.get_nowait()
        except queue.Empty:
            pass
        if was_phone_mode:
            self.client.send("release_all", {"reason": "emergency"})
            self._status("Emergency return: local input restored")

    def _on_connection_state(self, state: str) -> None:
        self._connection_state = state
        if state == "disconnected":
            self._pending_move = None
            if self.sm.current in PHONE_MODES or self.sm.current == RoutingMode.CONNECTING:
                self.sm.set_mode(RoutingMode.ERROR_SAFE)
                self._status("Phone disconnected; returning to Laptop")
                time.sleep(0.05)
                self.sm.set_mode(RoutingMode.LAPTOP)
            self.capture.set_routing(False, False)
            try:
                while True:
                    self.capture.events.get_nowait()
            except queue.Empty:
                pass
        elif state == "connected":
            if self.sm.current == RoutingMode.CONNECTING:
                self.set_mode(self.desired_phone_mode)
            elif self.sm.current in PHONE_MODES:
                self._apply_routing()

    def _on_message(self, obj: Dict[str, Any]) -> None:
        msg_type = obj.get("type")
        payload = obj.get("payload", {})
        if msg_type == "capabilities":
            changed = self.capabilities != payload
            self.capabilities = payload
            if changed:
                self._status("Phone capabilities received")
            if self.on_capabilities:
                try:
                    self.on_capabilities(payload)
                except Exception:
                    pass
        elif msg_type == "error":
            self._status(f"Phone error: {payload.get('message', 'unknown')}")

    def _send_input(self, payload: Dict[str, Any]) -> None:
        if not (self.client.connected and self.client.paired):
            return
        self.client.send("input", payload)
        self._last_tick = time.monotonic()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                event = self.capture.events.get(timeout=0.02)
            except queue.Empty:
                event = None
            kb, ms = self._active_routing()
            if event:
                payload = event.get("payload", {})
                kind = payload.get("kind")
                action = payload.get("action")
                allowed = (kind == "key" and kb) or (kind == "pointer" and ms)
                if allowed and kind == "pointer" and action == "move":
                    self._pending_move = payload
                elif allowed:
                    if self._pending_move:
                        self._send_input(self._pending_move)
                        self._pending_move = None
                        self._last_move_send = time.monotonic()
                    self._send_input(payload)
                else:
                    self._pending_move = None
            now = time.monotonic()
            if (
                self._pending_move
                and ms
                and now - self._last_move_send >= MOVE_SEND_INTERVAL
            ):
                self._send_input(self._pending_move)
                self._pending_move = None
                self._last_move_send = now

    def _watch(self) -> None:
        while not self._stop.wait(1.0):
            kb, ms = self._active_routing()
            if not (kb or ms):
                continue
            if not (self.capture.running and self._worker and self._worker.is_alive()):
                self._status("Watchdog detected stopped input pipeline; failing safe")
                self.emergency()
            elif not (self.client.connected and self.client.paired):
                self._status("Watchdog detected lost link; failing safe")
                self.emergency()
