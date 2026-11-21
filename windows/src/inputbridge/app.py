"""InputBridge Windows control panel (QR-only MVP)."""
from __future__ import annotations

import json
import secrets
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inputbridge.config import load_config, save_config
from inputbridge.controller import BridgeController
from inputbridge.net_server import BridgeServer, local_ip
from inputbridge.qrcode import make_matrix
from inputbridge.routing_state import RoutingMode
from inputbridge.tray import TrayIcon

MODE_LABELS = {
    RoutingMode.LAPTOP: "LAPTOP - local input",
    RoutingMode.PHONE_BOTH: "PHONE - keyboard + mouse",
    RoutingMode.PHONE_KEYBOARD: "PHONE - keyboard only",
    RoutingMode.PHONE_MOUSE: "PHONE - mouse only",
    RoutingMode.PAUSED: "PAUSED - local input",
    RoutingMode.CONNECTING: "CONNECTING - waiting for phone",
    RoutingMode.ERROR_SAFE: "ERROR - local input restored",
}


class InputBridgeApp:
    def __init__(self) -> None:
        self.cfg: Dict[str, Any] = load_config()
        self.port = int(self.cfg.get("port", 27123))
        self.token = secrets.token_hex(16)
        self.root = tk.Tk()
        self.root.title("InputBridge")
        self.root.geometry("700x720")
        self.root.minsize(660, 680)

        self.server = BridgeServer(
            port=self.port,
            token_hex=self.token,
            device_id=str(self.cfg.get("device_id", "")),
            device_name=str(self.cfg.get("device_name", "Windows laptop")),
        )
        self.controller = BridgeController(self.server, on_mode=self._on_mode, on_status=self._log, on_capabilities=self._on_capabilities)
        self.tray = TrayIcon(on_command=self._on_tray_command, on_status=self._log)

        self._build_ui()
        self._draw_qr()
        self._poll_status()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X)
        ttk.Label(header, text="InputBridge", font=("", 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="Shift+CapsLock: toggle   |   CapsLock in Phone: Laptop   |   Ctrl+Alt+F12: emergency",
            foreground="gray",
        ).pack(side=tk.RIGHT)

        mode_frame = ttk.LabelFrame(main, text="Routing", padding=10)
        mode_frame.pack(fill=tk.X, pady=(10, 4))
        self.mode_var = tk.StringVar(value=MODE_LABELS[RoutingMode.LAPTOP])
        ttk.Label(mode_frame, textvariable=self.mode_var, font=("", 15, "bold")).pack(anchor=tk.W)
        self.link_var = tk.StringVar(value="Phone: waiting for QR scan")
        ttk.Label(mode_frame, textvariable=self.link_var).pack(anchor=tk.W, pady=(2, 0))
        btn_frame = ttk.Frame(mode_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        for text, command in (
            ("Laptop", lambda: self.controller.set_mode(RoutingMode.LAPTOP)),
            ("Both", lambda: self.controller.set_mode(RoutingMode.PHONE_BOTH)),
            ("Keyboard only", lambda: self.controller.set_mode(RoutingMode.PHONE_KEYBOARD)),
            ("Mouse only", lambda: self.controller.set_mode(RoutingMode.PHONE_MOUSE)),
            ("Pause", lambda: self.controller.set_mode(RoutingMode.PAUSED)),
        ):
            ttk.Button(btn_frame, text=text, command=command).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="EMERGENCY: Laptop", command=lambda: self.controller.emergency()).pack(side=tk.RIGHT)

        qr_frame = ttk.LabelFrame(main, text="Pair with phone (QR)", padding=10)
        qr_frame.pack(fill=tk.X, pady=4)
        self.qr_canvas = tk.Canvas(qr_frame, width=225, height=225, highlightthickness=0, bg="white")
        self.qr_canvas.pack(anchor=tk.CENTER)
        ttk.Label(qr_frame, text="Scan this QR with the InputBridge phone app", foreground="gray").pack(anchor=tk.CENTER, pady=(4, 6))
        qr_buttons = ttk.Frame(qr_frame)
        qr_buttons.pack(fill=tk.X)
        ttk.Button(qr_buttons, text="New QR", command=self._new_qr).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(qr_buttons, text="Disconnect phone", command=self._disconnect).pack(side=tk.LEFT)

        cap_frame = ttk.LabelFrame(main, text="Phone capabilities", padding=8)
        cap_frame.pack(fill=tk.X, pady=4)
        self.cap_var = tk.StringVar(value="Not received yet")
        ttk.Label(cap_frame, textvariable=self.cap_var, wraplength=660, justify=tk.LEFT).pack(anchor=tk.W)

        settings = ttk.LabelFrame(main, text="Settings", padding=8)
        settings.pack(fill=tk.X, pady=4)
        srow = ttk.Frame(settings)
        srow.pack(fill=tk.X)
        ttk.Label(srow, text="Default phone mode:").pack(side=tk.LEFT)
        self.default_mode_var = tk.StringVar(value=str(self.cfg.get("default_mode", "PHONE_BOTH")))
        ttk.Combobox(
            srow,
            textvariable=self.default_mode_var,
            values=["PHONE_BOTH", "PHONE_KEYBOARD", "PHONE_MOUSE"],
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Button(srow, text="Save settings", command=self._save_settings).pack(side=tk.LEFT)

        log_frame = ttk.LabelFrame(main, text="Log (no key content)", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set)

        ttk.Label(
            main,
            text="MVP limits: text needs the InputBridge keyboard selected on the phone; pointer actions need the accessibility service enabled. Use only on a trusted local network.",
            wraplength=660,
            foreground="gray",
        ).pack(anchor=tk.W, pady=(4, 0))

    def _qr_payload(self) -> Dict[str, Any]:
        return {"v": 1, "h": local_ip(), "p": self.port, "t": self.token}

    def _draw_qr(self) -> None:
        payload = self._qr_payload()
        try:
            matrix = make_matrix(payload)
        except ValueError as exc:
            self._log(f"[qr] {exc}")
            return
        self.qr_canvas.delete("all")
        scale = 5
        border = 4
        offset = border * scale
        for y, row in enumerate(matrix):
            for x, dark in enumerate(row):
                if dark:
                    x1 = offset + x * scale
                    y1 = offset + y * scale
                    self.qr_canvas.create_rectangle(x1, y1, x1 + scale, y1 + scale, fill="black", outline="black")
        self._log(f"[qr] Ready at {payload['h']}:{payload['p']}")

    def _log(self, msg: str) -> None:
        def append() -> None:
            self.log_text.insert(tk.END, msg.rstrip() + "\n")
            self.log_text.see(tk.END)

        self.root.after(0, append)

    def _on_mode(self, mode: RoutingMode) -> None:
        def update() -> None:
            self.mode_var.set(MODE_LABELS.get(mode, mode.value))
            self.tray.set_tip(f"InputBridge: {mode.value}")

        self.root.after(0, update)

    def _on_capabilities(self, caps: Dict[str, Any]) -> None:
        text = (
            f"Accessibility gestures: {caps.get('accessibility', False)} | "
            f"IME text: {caps.get('ime', False)} | "
            f"Screen: {caps.get('screenWidth', '?')}x{caps.get('screenHeight', '?')}"
        )
        self.root.after(0, lambda: self.cap_var.set(text))

    def _poll_status(self) -> None:
        paired = "paired" if self.server.paired else "not paired"
        state = "connected" if self.server.connected else "waiting for QR scan"
        self.link_var.set(f"Phone: {state} ({paired})")
        self.root.after(500, self._poll_status)

    def _new_qr(self) -> None:
        self.controller.emergency()
        self.token = secrets.token_hex(16)
        self.server.set_token(self.token)
        self.server.start()
        self._draw_qr()
        self._log("[qr] New QR generated; previous phone link invalidated")

    def _disconnect(self) -> None:
        self.controller.emergency()
        self.server.stop()
        self._log("[qr] Phone disconnected")

    def _save_settings(self) -> None:
        self.cfg["default_mode"] = self.default_mode_var.get()
        try:
            self.controller.desired_phone_mode = RoutingMode(self.cfg["default_mode"])
        except ValueError:
            pass
        save_config(self.cfg)
        self._log("[settings] Saved")

    def _on_tray_command(self, command: str) -> None:
        def run() -> None:
            if command == "open":
                self.root.deiconify()
                self.root.lift()
            elif command == "phone":
                self.controller.set_mode(self.controller.desired_phone_mode)
            elif command == "laptop":
                self.controller.emergency()
            elif command == "pause":
                self.controller.set_mode(RoutingMode.PAUSED)
            elif command == "settings":
                self.root.deiconify()
                self.root.lift()
            elif command == "exit":
                self._on_close()

        self.root.after(0, run)

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.tray.start()
        self.controller.start()
        self.server.start()
        self._log("InputBridge started in Laptop mode. Show the QR to the phone.")
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
