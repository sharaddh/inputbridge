from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict

from inputbridge.ui.widgets import Card, ScrolledFrame, wrap_on_resize

TOUCH_POINTER_NOTE = (
    "Touch Pointer is an accessibility-gesture compatibility layer. It does not "
    "provide native hover, drag, wheel or right-click semantics, and it is not "
    "native Android mouse support."
)

TRUSTED_NETWORK_NOTE = (
    "Pairing uses HMAC; input traffic uses AES-256-GCM. Keep InputBridge on a trusted "
    "local network. Logs contain status only, never typed keys, text or tokens."
)

METRICS = (
    "Pointer updates/sec",
    "Median link latency",
    "Dropped movement events",
    "Queue depth",
)


class DiagnosticsView(ttk.Frame):
    def __init__(self, master: Any, theme: Any, actions: Dict[str, Callable[..., None]]) -> None:
        super().__init__(master, style="TFrame")
        self.theme = theme
        self.actions = actions
        self._warnings = []
        self._build()
        theme.subscribe(self._on_palette)

    def _build(self) -> None:
        s = self.theme.spacing
        scroll = ScrolledFrame(self, self.theme)
        scroll.pack(fill=tk.BOTH, expand=True)
        host = scroll.inner
        host.configure(padding=(s["lg"], s["md"], s["lg"], s["lg"]))

        ttk.Label(host, text="Diagnostics", style="Title.TLabel").pack(anchor=tk.W, pady=(0, s["md"]))

        status_card = Card(host, self.theme)
        status_card.pack(fill=tk.X, pady=(0, s["md"]))
        ttk.Label(status_card.body, text="Connection", style="CardTitle.TLabel").pack(anchor=tk.W)
        self.link_var = tk.StringVar(value="Link: not connected")
        self.pair_var = tk.StringVar(value="Pairing: none")
        self.device_var = tk.StringVar(value="Phone: unknown")
        ttk.Label(status_card.body, textvariable=self.link_var, style="Card.TLabel").pack(anchor=tk.W, pady=(s["sm"], 0))
        ttk.Label(status_card.body, textvariable=self.pair_var, style="Card.TLabel").pack(anchor=tk.W)
        ttk.Label(status_card.body, textvariable=self.device_var, style="Card.TLabel").pack(anchor=tk.W)

        perf_card = Card(host, self.theme)
        perf_card.pack(fill=tk.X, pady=(0, s["md"]))
        ttk.Label(perf_card.body, text="Pointer performance", style="CardTitle.TLabel").pack(anchor=tk.W)
        grid = ttk.Frame(perf_card.body, style="Card.TFrame")
        grid.pack(fill=tk.X, pady=(s["sm"], 0))
        self.metric_vars = []
        for index, name in enumerate(METRICS):
            variable = tk.StringVar(value="Not available")
            self.metric_vars.append(variable)
            ttk.Label(grid, text=f"{name}:", style="CardMuted.TLabel").grid(row=index, column=0, sticky=tk.W, padx=(0, s["md"]), pady=1)
            ttk.Label(grid, textvariable=variable, style="Card.TLabel").grid(row=index, column=1, sticky=tk.W, pady=1)

        caps_card = Card(host, self.theme)
        caps_card.pack(fill=tk.X, pady=(0, s["md"]))
        ttk.Label(caps_card.body, text="Phone capabilities", style="CardTitle.TLabel").pack(anchor=tk.W)
        self.cap_var = tk.StringVar(value="Not received yet")
        self.cap_label = ttk.Label(caps_card.body, textvariable=self.cap_var, style="Card.TLabel", justify=tk.LEFT)
        self.cap_label.pack(anchor=tk.W, pady=(s["xs"], 0))
        wrap_on_resize(self.cap_label, caps_card.body, inset=s["card_pad"] * 2)

        self.log_card = Card(host, self.theme)
        self.log_card.pack(fill=tk.BOTH, expand=True, pady=(0, s["md"]))
        ttk.Label(self.log_card.body, text="Status log", style="CardTitle.TLabel").pack(anchor=tk.W)
        log_frame = ttk.Frame(self.log_card.body, style="Card.TFrame")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(s["sm"], s["sm"]))
        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0,
            bg=self.theme.palette.log_bg,
            fg=self.theme.palette.log_text,
            insertbackground=self.theme.palette.text,
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set, state=tk.DISABLED)
        buttons = ttk.Frame(self.log_card.body, style="Card.TFrame")
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Export log", style="Secondary.TButton", command=self.actions["export_log"]).pack(side=tk.LEFT, padx=(0, s["sm"]))
        ttk.Button(buttons, text="Clear log", style="Secondary.TButton", command=self.actions["clear_log"]).pack(side=tk.LEFT)

        self.disabled_label = ttk.Label(host, text="Diagnostics are off. Enable them in Settings > Advanced.", style="Muted.TLabel")

        safety = Card(host, self.theme)
        safety.pack(fill=tk.X)
        self._safety = safety
        for text in (TOUCH_POINTER_NOTE, TRUSTED_NETWORK_NOTE):
            label = ttk.Label(safety.body, text=text, style="Card.TLabel", justify=tk.LEFT)
            label.pack(anchor=tk.W, pady=(0, s["xs"]))
            self._warnings.append(label)
        wrap_on_resize(safety.body, safety.body, inset=s["card_pad"] * 2)

    def _on_palette(self, palette: Any) -> None:
        self.log_text.configure(
            bg=palette.log_bg,
            fg=palette.log_text,
            insertbackground=palette.text,
        )
        for label in self._warnings:
            label.configure(foreground=palette.warning)

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            if self.disabled_label.winfo_manager():
                self.disabled_label.pack_forget()
            if not self.log_card.winfo_manager():
                self.log_card.pack(before=self._safety, fill=tk.BOTH, expand=True, pady=(0, self.theme.spacing["md"]))
        else:
            if self.log_card.winfo_manager():
                self.log_card.pack_forget()
            if not self.disabled_label.winfo_manager():
                self.disabled_label.pack(before=self._safety, anchor=tk.W, pady=(0, self.theme.spacing["md"]))

    def set_status(self, connected: bool, paired: bool, port: int, device_name: str) -> None:
        self.link_var.set("Link: connected" if connected else "Link: waiting for phone")
        self.pair_var.set("Pairing: approved" if paired else "Pairing: none")
        self.device_var.set(f"Laptop: {device_name}   Port: {port}")

    def set_metrics(self, data: Dict[str, Any]) -> None:
        interval = float(data.get("pointer_interval_ms", 16.67))
        values = [
            f"target {1000.0 / max(interval, 1.0):.0f}/s ({interval:.1f} ms)",
            f"ACK {data.get('ack_rtt_ms', 0)} ms · capture→send {data.get('capture_to_send_ms', 0)} ms",
            f"{data.get('moves_stale', 0)} stale · {data.get('moves_unchanged', 0)} unchanged · {data.get('moves_coalesced', 0)} coalesced",
            f"{data.get('queue_depth', 0)} (max {data.get('max_queue_depth', 0)}) · sent {data.get('moves_sent', 0)}",
        ]
        for variable, value in zip(self.metric_vars, values):
            variable.set(value)

    def set_capabilities(self, capabilities: Dict[str, Any]) -> None:
        if not capabilities:
            self.cap_var.set("Not received yet")
            return
        lines = []
        for key, label in (
            ("accessibility", "Touch Pointer gestures"),
            ("ime", "Text entry"),
            ("screenWidth", "Screen width"),
            ("screenHeight", "Screen height"),
        ):
            if key in capabilities:
                value = capabilities[key]
                if isinstance(value, bool):
                    value = "enabled" if value else "disabled"
                lines.append(f"{label}: {value}")
        self.cap_var.set("   |   ".join(lines) if lines else "No capabilities reported")

    def append(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def clear(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
