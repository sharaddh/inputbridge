"""InputBridge Windows control panel."""
from __future__ import annotations

import secrets
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inputbridge.config import clear_pairing, load_config, save_config
from inputbridge.controller import BridgeController
from inputbridge.net_server import BridgeServer, local_ip
from inputbridge.qrcode import make_matrix
from inputbridge.routing_state import RoutingMode
from inputbridge.tray import TrayIcon
from inputbridge.ui.diagnostics import DiagnosticsView
from inputbridge.ui.home import HomeView
from inputbridge.ui.settings import SettingsView
from inputbridge.ui.theme import ThemeManager

MAX_LOG_LINES = 500


class InputBridgeApp:
    def __init__(self) -> None:
        self.cfg: Dict[str, Any] = load_config()
        self.port = int(self.cfg.get("port", 27123))
        self.token = self._initial_token()
        self.log_lines: List[str] = []

        self.root = tk.Tk()
        self.root.title("InputBridge")
        self.root.geometry("820x780")
        self.root.minsize(760, 660)
        self.theme = ThemeManager(self.root, self.cfg)

        self.server = BridgeServer(
            port=self.port,
            token_hex=self.token,
            device_id=str(self.cfg.get("device_id", "")),
            device_name=str(self.cfg.get("device_name", "Windows laptop")),
            on_status=self._log,
        )
        self.controller = BridgeController(
            self.server,
            on_mode=self._on_mode,
            on_status=self._log,
            on_capabilities=self._on_capabilities,
            pointer_interval=1.0 / float(self.cfg.get("pointer_rate_hz", 60)),
        )
        original_state = self.server.on_state

        def state_changed(state: str) -> None:
            if original_state:
                original_state(state)
            self.root.after(0, self._refresh)

        self.server.on_state = state_changed
        self.tray = TrayIcon(on_command=self._on_tray_command, on_status=self._log)

        self._build_ui()
        self._draw_qr()
        self._poll_status()

    def _initial_token(self) -> str:
        raw = str(self.cfg.get("paired_token") or "").strip()
        try:
            token = bytes.fromhex(raw)
        except ValueError:
            token = b""
        if len(token) not in (16, 32):
            token = secrets.token_bytes(16)
            self.cfg["paired_token"] = token.hex()
            save_config(self.cfg)
        return self.cfg["paired_token"]

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, style="TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main, style="TFrame")
        header.pack(fill=tk.X, padx=(self.theme.spacing["lg"], self.theme.spacing["lg"]), pady=(self.theme.spacing["md"], self.theme.spacing["sm"]))
        ttk.Label(header, text="InputBridge", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text="One keyboard. One mouse. Two screens.", style="Muted.TLabel").pack(side=tk.LEFT, padx=(self.theme.spacing["md"], 0))
        self.connection_var = tk.StringVar(value="Waiting for phone")
        self.connection_label = ttk.Label(header, textvariable=self.connection_var, style="Status.TLabel")
        self.connection_label.pack(side=tk.RIGHT, padx=(0, self.theme.spacing["md"]))
        ttk.Button(header, text="Diagnostics", style="Secondary.TButton", command=self._open_diagnostics).pack(side=tk.RIGHT, padx=(0, self.theme.spacing["sm"]))
        ttk.Button(header, text="Settings", style="Secondary.TButton", command=self._open_settings).pack(side=tk.RIGHT, padx=(0, self.theme.spacing["sm"]))

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=(self.theme.spacing["lg"], self.theme.spacing["lg"]))

        actions: Dict[str, Callable[..., None]] = {
            "set_mode": lambda mode: self.controller.set_mode(mode),
            "switch": self._switch_to_phone,
            "laptop": lambda: self.controller.set_mode(RoutingMode.LAPTOP),
            "emergency": self.controller.emergency,
            "new_qr": self._new_qr,
            "disconnect": self._disconnect,
            "shortcuts": lambda: self._open_settings("Shortcuts"),
            "devices": lambda: self._open_settings("Devices"),
            "diagnostics": self._open_diagnostics,
            "save": self._save_settings,
            "re_pair": self._new_qr,
            "revoke": self._revoke,
            "export_log": self._export_log,
            "clear_log": self._clear_log,
        }

        self.home = HomeView(self.notebook, self.theme, actions)
        self.settings = SettingsView(self.notebook, self.theme, self.cfg, actions)
        self.diagnostics = DiagnosticsView(self.notebook, self.theme, actions)
        self.notebook.add(self.home, text="Home")
        self.notebook.add(self.settings, text="Settings")
        self.notebook.add(self.diagnostics, text="Diagnostics")
        self.diagnostics.set_enabled(bool(self.cfg.get("diagnostics_enabled", True)))

        footer = ttk.Frame(main, style="TFrame")
        footer.pack(fill=tk.X, padx=(self.theme.spacing["lg"], self.theme.spacing["lg"]), pady=(self.theme.spacing["sm"], self.theme.spacing["md"]))
        ttk.Label(
            footer,
            text="Touch Pointer uses gestures, not a native mouse. Trusted networks only: traffic is authenticated but not encrypted.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W)

    def _qr_payload(self) -> Dict[str, Any]:
        return {"v": 1, "h": local_ip(), "p": self.port, "t": self.token}

    def _draw_qr(self) -> None:
        payload = self._qr_payload()
        try:
            matrix = make_matrix(payload)
        except ValueError as exc:
            self._log(f"[qr] {exc}")
            return
        self.home.set_qr(matrix)
        self._log(f"[qr] Ready at {payload['h']}:{payload['p']}")

    def _log(self, message: str) -> None:
        def append() -> None:
            line = str(message).rstrip()
            self.log_lines.append(line)
            if len(self.log_lines) > MAX_LOG_LINES:
                del self.log_lines[:-MAX_LOG_LINES]
            if hasattr(self, "diagnostics"):
                self.diagnostics.append(line)

        self.root.after(0, append)

    def _on_mode(self, mode: RoutingMode) -> None:
        def update() -> None:
            self.tray.set_tip(f"InputBridge: {mode.value}")
            self._refresh()

        self.root.after(0, update)

    def _on_capabilities(self, capabilities: Dict[str, Any]) -> None:
        def update() -> None:
            self.home.set_capabilities(capabilities)
            self.diagnostics.set_capabilities(capabilities)

        self.root.after(0, update)

    def _refresh(self) -> None:
        connected = self.server.connected
        paired = self.server.paired
        mode = self.controller.sm.current
        self.home.set_state(mode, connected, paired)
        self.diagnostics.set_status(connected, paired, self.port, str(self.cfg.get("device_name", "Windows laptop")))
        self.diagnostics.set_metrics(self.controller.metrics())
        if connected and paired:
            text = "Phone connected"
            color = self.theme.palette.success
        elif connected:
            text = "Pairing in progress"
            color = self.theme.palette.warning
        else:
            text = "Waiting for phone"
            color = self.theme.palette.muted
        self.connection_var.set(text)
        self.connection_label.configure(foreground=color)

    def _poll_status(self) -> None:
        self._refresh()
        self.root.after(500, self._poll_status)

    def _switch_to_phone(self) -> None:
        self.controller.set_mode(self.controller.desired_phone_mode)
        self.notebook.select(self.home)
        self._refresh()

    def _new_qr(self) -> None:
        self.controller.emergency()
        self.token = secrets.token_hex(16)
        self.cfg["paired_token"] = self.token
        save_config(self.cfg)
        self.server.set_token(self.token)
        self.server.start()
        self._draw_qr()
        self.notebook.select(self.home)
        self._refresh()
        self._log("[qr] New QR generated; previous phone link invalidated")

    def _disconnect(self) -> None:
        self.controller.emergency()
        self.server.stop()
        self._refresh()
        self._log("[device] Phone disconnected")

    def _revoke(self) -> None:
        self.controller.emergency()
        self.server.stop()
        clear_pairing(self.cfg)
        self.token = secrets.token_hex(16)
        self.server.set_token(self.token)
        self._draw_qr()
        self._refresh()
        self._log("[device] Pairing revoked; local input restored")

    def _save_settings(self, settings: Dict[str, Any]) -> None:
        self.cfg.update(settings)
        save_config(self.cfg)
        self.theme.clear_preview()
        self.server.device_name = str(self.cfg.get("device_name", "Windows laptop"))
        try:
            self.controller.desired_phone_mode = RoutingMode(str(self.cfg.get("default_mode", "PHONE_BOTH")))
        except ValueError:
            pass
        self.home.set_shortcuts(
            str(self.cfg.get("toggle_shortcut_display", "")),
            str(self.cfg.get("emergency_shortcut_display", "")),
        )
        self.diagnostics.set_enabled(bool(self.cfg.get("diagnostics_enabled", True)))
        self.tray.set_tip(f"InputBridge: {self.controller.sm.current.value}")
        self._log("[settings] Saved")

    def _export_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export InputBridge log",
            defaultextension=".txt",
            initialfile="inputbridge-diagnostics.txt",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            Path(path).write_text("\n".join(self.log_lines), encoding="utf-8")
            self._log("[diagnostics] Log exported")
        except OSError as exc:
            messagebox.showerror("InputBridge", f"Could not export the log: {exc}")

    def _clear_log(self) -> None:
        self.log_lines.clear()
        self.diagnostics.clear()

    def _open_settings(self, section: str | None = None) -> None:
        self.root.deiconify()
        self.root.lift()
        self.notebook.select(self.settings)
        if section:
            self.settings.select_tab(section)

    def _open_diagnostics(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.notebook.select(self.diagnostics)

    def _on_tray_command(self, command: str) -> None:
        def run() -> None:
            if command == "open":
                self.root.deiconify()
                self.root.lift()
            elif command == "phone":
                self._switch_to_phone()
            elif command == "laptop":
                self.controller.set_mode(RoutingMode.LAPTOP)
            elif command == "pause":
                self.controller.set_mode(RoutingMode.PAUSED)
            elif command == "settings":
                self._open_settings()
            elif command == "exit":
                self._on_close()

        self.root.after(0, run)

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.tray.start()
        self.controller.start()
        try:
            startup_mode = RoutingMode(str(self.cfg.get("startup_mode", "LAPTOP")))
        except ValueError:
            startup_mode = RoutingMode.LAPTOP
        if startup_mode not in (RoutingMode.LAPTOP, RoutingMode.ERROR_SAFE, RoutingMode.CONNECTING):
            self.controller.desired_phone_mode = startup_mode
            self.controller.set_mode(startup_mode)
        if bool(self.cfg.get("auto_connect", True)) or not str(self.cfg.get("paired_token", "")).strip():
            self.server.start()
        else:
            self._log("[server] Auto-connect is off; use Pair new device to start listening")
        if bool(self.cfg.get("start_minimized", False)):
            self.root.withdraw()
        self._log("InputBridge started in Laptop mode. Show the QR to your phone.")
        self.root.mainloop()

    def _on_close(self) -> None:
        try:
            self.controller.stop()
            self.server.stop()
            self.tray.stop()
            save_config(self.cfg)
        finally:
            self.root.destroy()


def main() -> int:
    if sys.platform != "win32":
        messagebox.showwarning("InputBridge", "This app is intended for Windows 11.")
        return 2
    InputBridgeApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
