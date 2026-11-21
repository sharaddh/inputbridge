"""Routing state machine (scaffold) matching TRD §7.5.

No OS hooks here — pure logic for testing and later integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class RoutingMode(Enum):
    LAPTOP = "LAPTOP"
    PHONE_BOTH = "PHONE_BOTH"
    PHONE_KEYBOARD = "PHONE_KEYBOARD"
    PHONE_MOUSE = "PHONE_MOUSE"
    PAUSED = "PAUSED"
    CONNECTING = "CONNECTING"
    ERROR_SAFE = "ERROR_SAFE"


@dataclass
class RoutingStateMachine:
    current: RoutingMode = RoutingMode.LAPTOP
    _listeners: List[Callable[[RoutingMode], None]] = field(default_factory=list, repr=False)

    def add_listener(self, fn: Callable[[RoutingMode], None]) -> None:
        self._listeners.append(fn)

    def _emit(self) -> None:
        for fn in list(self._listeners):
            try:
                fn(self.current)
            except Exception:
                pass

    def set_mode(self, mode: RoutingMode) -> None:
        if self.current == mode:
            return
        self.current = mode
        self._emit()

    def emergency_return_to_laptop(self) -> None:
        """Always safe local return."""
        self.set_mode(RoutingMode.LAPTOP)


if __name__ == "__main__":
    sm = RoutingStateMachine()
    sm.add_listener(lambda m: print("mode ->", m.value))
    sm.set_mode(RoutingMode.PHONE_BOTH)
    sm.emergency_return_to_laptop()
