from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Tuple

DEFAULTS: Dict[str, str] = {
    "toggle": "Shift+CapsLock",
    "emergency": "Ctrl+Alt+F12",
}

_MODIFIERS = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "windows": "Win",
    "meta": "Win",
}

_RESERVED = {
    "Ctrl+Alt+Delete",
    "Alt+F4",
    "Win+L",
    "Ctrl+Shift+Esc",
    "Ctrl+Alt+Tab",
}


def normalize(text: str) -> str:
    parts = [part.strip() for part in str(text or "").split("+")]
    parts = [part for part in parts if part]
    result: List[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered in _MODIFIERS:
            canonical = _MODIFIERS[lowered]
            if canonical not in result:
                result.append(canonical)
            continue
        if len(part) == 1 and part.isalpha():
            result.append(part.upper())
        elif len(part) <= 3 and part.isalpha():
            result.append(part[:1].upper() + part[1:].lower())
        else:
            result.append(part)
    return "+".join(result)


def parse(text: str) -> Optional[Tuple[FrozenSet[str], str]]:
    parts = normalize(text).split("+")
    modifiers = frozenset(part for part in parts if part in ("Ctrl", "Alt", "Shift", "Win"))
    keys = [part for part in parts if part not in modifiers]
    if len(keys) != 1 or not keys[0]:
        return None
    key = keys[0]
    if any(ch.isspace() or ch in "()[]{}" for ch in key):
        return None
    return modifiers, key


def validate(toggle: str, emergency: str) -> List[str]:
    errors: List[str] = []
    toggle = str(toggle or "").strip()
    emergency = str(emergency or "").strip()
    if not toggle:
        errors.append("Enter a toggle shortcut.")
    if not emergency:
        errors.append("Enter an emergency shortcut.")
    parsed_toggle = parse(toggle) if toggle else None
    parsed_emergency = parse(emergency) if emergency else None
    if toggle and parsed_toggle is None:
        errors.append("Toggle must be one key with optional modifiers, for example Shift+CapsLock.")
    if emergency and parsed_emergency is None:
        errors.append("Emergency must be one key with optional modifiers, for example Ctrl+Alt+F12.")
    if parsed_toggle and parsed_emergency and parsed_toggle == parsed_emergency:
        errors.append("Toggle and emergency shortcuts must be different.")
    for label, value in (("Toggle", toggle), ("Emergency", emergency)):
        if normalize(value) in _RESERVED:
            errors.append(f"{label} shortcut is reserved by Windows; choose another combination.")
    if parsed_emergency and parsed_emergency[1].lower() == "capslock" and not parsed_emergency[0]:
        errors.append("Use the toggle shortcut for CapsLock; the emergency shortcut needs a modifier.")
    return errors
