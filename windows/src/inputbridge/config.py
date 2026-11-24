"""JSON settings store (no external dependencies)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

from inputbridge.protocol import DEFAULT_PORT
from inputbridge.routing_state import RoutingMode

THEMES = ("system", "light", "dark")
ACCENTS = ("blue", "teal", "violet", "amber", "slate")
POINTER_RATES = (30, 60, 120)
CURSOR_SHAPES = ("arrow", "compact", "dot", "crosshair")
CURSOR_SIZES = ("small", "medium", "large")
RIGHT_BUTTON_ACTIONS = ("context", "back", "none")
MIDDLE_BUTTON_ACTIONS = ("none", "autoscroll", "home")
PROFILES = ("custom", "work", "phone", "typing", "navigation")
MODE_VALUES = tuple(m.value for m in RoutingMode)
PHONE_MODE_VALUES = ("PHONE_BOTH", "PHONE_KEYBOARD", "PHONE_MOUSE")

DEFAULT_CONFIG: Dict[str, Any] = {
    "host": "192.168.43.1",
    "port": DEFAULT_PORT,
    "device_id": "",
    "device_name": "Windows laptop",
    "paired_token": "",
    "default_mode": "PHONE_BOTH",
    "auto_connect": True,
    "toggle_shortcut_display": "Shift+CapsLock",
    "emergency_shortcut_display": "Ctrl+Alt+F12",
    "notifications": True,
    "phone_name": "Android phone",
    "theme": "system",
    "accent": "blue",
    "compact_mode": False,
    "pointer_rate_hz": 60,
    "scroll_direction": 1,
    "scroll_sensitivity": 1.0,
    "right_button_action": "context",
    "middle_button_action": "none",
    "cursor_shape": "arrow",
    "cursor_size": "medium",
    "cursor_fill": "#FFFFFF",
    "cursor_outline": "#1B2430",
    "cursor_trail": False,
    "click_ripple": False,
    "profile": "custom",
    "start_minimized": False,
    "diagnostics_enabled": True,
    "startup_mode": "LAPTOP",
    "connection_timeout": 15.0,
}


def config_path() -> Path:
    base = Path.home() / ".inputbridge"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    result = DEFAULT_CONFIG.copy()
    result.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG or k == "device_id"})

    result["device_id"] = str(result.get("device_id") or "").strip() or str(uuid.uuid4())
    result["host"] = str(result.get("host") or DEFAULT_CONFIG["host"]).strip()
    result["device_name"] = str(result.get("device_name") or DEFAULT_CONFIG["device_name"]).strip()
    result["phone_name"] = str(result.get("phone_name") or DEFAULT_CONFIG["phone_name"]).strip()
    result["paired_token"] = str(result.get("paired_token") or "").strip()

    try:
        port = int(result.get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    result["port"] = port if 1 <= port <= 65535 else DEFAULT_PORT

    for key, allowed in (
        ("theme", THEMES),
        ("accent", ACCENTS),
        ("cursor_shape", CURSOR_SHAPES),
        ("cursor_size", CURSOR_SIZES),
        ("right_button_action", RIGHT_BUTTON_ACTIONS),
        ("middle_button_action", MIDDLE_BUTTON_ACTIONS),
        ("profile", PROFILES),
    ):
        if str(result.get(key, "")).lower() not in allowed:
            result[key] = DEFAULT_CONFIG[key]
        else:
            result[key] = str(result[key]).lower()

    for key, allowed in (("default_mode", PHONE_MODE_VALUES), ("startup_mode", MODE_VALUES)):
        if str(result.get(key, "")) not in allowed:
            result[key] = DEFAULT_CONFIG[key]

    try:
        rate = int(result.get("pointer_rate_hz", 60))
    except (TypeError, ValueError):
        rate = 60
    result["pointer_rate_hz"] = rate if rate in POINTER_RATES else 60

    try:
        direction = int(result.get("scroll_direction", 1))
    except (TypeError, ValueError):
        direction = 1
    result["scroll_direction"] = 1 if direction >= 0 else -1

    try:
        sensitivity = float(result.get("scroll_sensitivity", 1.0))
    except (TypeError, ValueError):
        sensitivity = 1.0
    result["scroll_sensitivity"] = round(min(3.0, max(0.25, sensitivity)), 2)

    try:
        timeout = float(result.get("connection_timeout", 15.0))
    except (TypeError, ValueError):
        timeout = 15.0
    result["connection_timeout"] = round(min(120.0, max(3.0, timeout)), 1)

    for key in ("cursor_fill", "cursor_outline"):
        value = str(result.get(key) or DEFAULT_CONFIG[key]).strip()
        result[key] = value if len(value) == 7 and value.startswith("#") else DEFAULT_CONFIG[key]

    for key in (
        "auto_connect",
        "notifications",
        "compact_mode",
        "cursor_trail",
        "click_ripple",
        "start_minimized",
        "diagnostics_enabled",
    ):
        result[key] = bool(result.get(key, DEFAULT_CONFIG[key]))

    from inputbridge.ui.shortcuts import parse

    for key in ("toggle_shortcut_display", "emergency_shortcut_display"):
        value = str(result.get(key) or "").split(" / ")[0].split(" (")[0].strip()
        if parse(value) is None:
            value = DEFAULT_CONFIG[key]
        result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    p = config_path()
    if not p.exists():
        cfg = normalize_config({})
        save_config(cfg)
        return cfg
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
        return normalize_config(data)
    except (OSError, ValueError, TypeError):
        return normalize_config({})


def save_config(cfg: Dict[str, Any]) -> None:
    p = config_path()
    p.write_text(json.dumps(normalize_config(cfg), indent=2), encoding="utf-8")


def clear_pairing(cfg: Dict[str, Any]) -> None:
    cfg["paired_token"] = ""
    save_config(cfg)
