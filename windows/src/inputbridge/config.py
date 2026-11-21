"""JSON settings store (no external dependencies)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

from inputbridge.protocol import DEFAULT_PORT

DEFAULT_CONFIG: Dict[str, Any] = {
    "host": "192.168.43.1",
    "port": DEFAULT_PORT,
    "device_id": "",
    "device_name": "Windows laptop",
    "paired_token": "",
    "default_mode": "PHONE_BOTH",
    "auto_connect": True,
    "toggle_shortcut_display": "Shift+CapsLock / CapsLock in Phone",
    "emergency_shortcut_display": "Ctrl+Alt+F12",
    "notifications": True,
}


def config_path() -> Path:
    base = Path.home() / ".inputbridge"
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> Dict[str, Any]:
    p = config_path()
    if not p.exists():
        cfg = DEFAULT_CONFIG.copy()
        cfg["device_id"] = str(uuid.uuid4())
        save_config(cfg)
        return cfg
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        if not merged.get("device_id"):
            merged["device_id"] = str(uuid.uuid4())
        return merged
    except Exception:
        cfg = DEFAULT_CONFIG.copy()
        cfg["device_id"] = str(uuid.uuid4())
        return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    p = config_path()
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def clear_pairing(cfg: Dict[str, Any]) -> None:
    cfg["paired_token"] = ""
    save_config(cfg)
