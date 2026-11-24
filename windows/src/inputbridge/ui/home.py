from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Sequence

from inputbridge.routing_state import RoutingMode
from inputbridge.ui.widgets import Card, ScrolledFrame, wrap_on_resize

PHONE_MODES = {
    RoutingMode.PHONE_BOTH,
    RoutingMode.PHONE_KEYBOARD,
    RoutingMode.PHONE_MOUSE,
}

MODE_TEXT = {
    RoutingMode.LAPTOP: "Control is on your Laptop",
    RoutingMode.PHONE_BOTH: "Control is on your Phone",
    RoutingMode.PHONE_KEYBOARD: "Control is on your Phone",
    RoutingMode.PHONE_MOUSE: "Control is on your Phone",
    RoutingMode.PAUSED: "Routing is Paused",
    RoutingMode.CONNECTING: "Connecting to your Phone",
    RoutingMode.ERROR_SAFE: "Local input restored",
}

MODE_DETAIL = {
    RoutingMode.LAPTOP: "Keyboard and mouse stay on this laptop.",
    RoutingMode.PHONE_BOTH: "Keyboard and Touch Pointer go to your phone.",
    RoutingMode.PHONE_KEYBOARD: "Keyboard goes to your phone. Mouse stays local.",
    RoutingMode.PHONE_MOUSE: "Touch Pointer goes to your phone. Keyboard stays local.",
    RoutingMode.PAUSED: "Input is not forwarded. Local input stays active.",
    RoutingMode.CONNECTING: "Waiting for the phone. Local input stays active.",
    RoutingMode.ERROR_SAFE: "The link was lost and local input was restored.",
}

TOUCH_POINTER_NOTE = (
    "Touch Pointer uses accessibility gestures, not a native Android mouse. "
    "There is no native hover, drag, wheel or right-click behavior, and some apps "
    "will not respond like desktop applications."
)

TRUSTED_NETWORK_NOTE = (
    "Trusted networks only. Pairing is HMAC-signed and input traffic is AES-256-GCM "
    "encrypted. Use InputBridge on a Wi-Fi network you control."
)


class HomeView(ttk.Frame):
    def __init__(self, master: Any, theme: Any, actions: Dict[str, Callable[..., None]]) -> None:
        super().__init__(master, style="TFrame")
        self.theme = theme
        self.actions = actions
        self.mode = RoutingMode.LAPTOP
        self.connected = False
        self.paired = False
        self._warning_labels: List[Any] = []
        self._route_buttons: Dict[RoutingMode, Any] = {}
        self._build()
        theme.subscribe(self._on_palette)

    def _build(self) -> None:
        s = self.theme.spacing
        scroll = ScrolledFrame(self, self.theme)
        scroll.pack(fill=tk.BOTH, expand=True)
        host = scroll.inner
        host.configure(padding=(s["lg"], s["md"], s["lg"], s["lg"]))

        hero = Card(host, self.theme)
        hero.pack(fill=tk.X, pady=(0, s["md"]))
        self.diagram = tk.Canvas(hero, height=76, bd=0, highlightthickness=0, bg=self.theme.palette.surface)
        self.diagram.pack(fill=tk.X)
        self.diagram.bind("<Configure>", self._draw_diagram)

        self.mode_label = ttk.Label(hero.body, style="Title.TLabel", font=self.theme.fonts["title"], anchor=tk.CENTER)
        self.mode_label.pack(fill=tk.X, pady=(s["sm"], 0))
        self.mode_detail = ttk.Label(hero.body, style="CardMuted.TLabel", anchor=tk.CENTER)
        self.mode_detail.pack(fill=tk.X, pady=(self.theme.spacing["xs"], s["md"]))

        self.primary = ttk.Button(hero.body, style="Hero.TButton", command=self._primary_action)
        self.primary.pack(fill=tk.X)

        routes_card = Card(host, self.theme)
        routes_card.pack(fill=tk.X, pady=(0, s["md"]))
        ttk.Label(routes_card.body, text="Quick routing", style="CardTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(routes_card.body, text="Fine-tune where keyboard and pointer go.", style="CardMuted.TLabel").pack(anchor=tk.W)

        row = ttk.Frame(routes_card.body, style="Card.TFrame")
        row.pack(fill=tk.X, pady=(s["sm"], s["sm"]))
        options = (
            ("Both", RoutingMode.PHONE_BOTH),
            ("Keyboard", RoutingMode.PHONE_KEYBOARD),
            ("Mouse", RoutingMode.PHONE_MOUSE),
            ("Pause", RoutingMode.PAUSED),
        )
        for index, (label, mode) in enumerate(options):
            row.columnconfigure(index, weight=1)
            button = ttk.Button(row, text=label, style="Tool.TButton", command=lambda m=mode: self.actions["set_mode"](m))
            button.grid(row=0, column=index, sticky="ew", padx=(0, s["sm"] if index < len(options) - 1 else 0))
            self._route_buttons[mode] = button

        ttk.Button(
            routes_card.body,
            text="Emergency: Return to Laptop",
            style="Danger.TButton",
            command=self.actions["emergency"],
        ).pack(fill=tk.X)

        self.pair_card = Card(host, self.theme)
        self.pair_card.pack(fill=tk.X, pady=(0, s["md"]))
        ttk.Label(self.pair_card.body, text="Pair your phone", style="CardTitle.TLabel").pack(anchor=tk.W)
        self.pair_hint = ttk.Label(self.pair_card.body, style="CardMuted.TLabel")
        self.pair_hint.pack(anchor=tk.W, pady=(2, s["sm"]))
        self.qr_canvas = tk.Canvas(
            self.pair_card.body,
            width=210,
            height=210,
            bg="white",
            highlightthickness=1,
            highlightbackground=self.theme.palette.border,
        )
        self.qr_canvas.pack(pady=(0, s["sm"]))
        pair_buttons = ttk.Frame(self.pair_card.body, style="Card.TFrame")
        pair_buttons.pack(fill=tk.X)
        ttk.Button(pair_buttons, text="New QR", style="Secondary.TButton", command=self.actions["new_qr"]).pack(side=tk.LEFT, padx=(0, s["sm"]))
        ttk.Button(pair_buttons, text="Disconnect phone", style="Secondary.TButton", command=self.actions["disconnect"]).pack(side=tk.LEFT)

        details = Card(host, self.theme)
        details.pack(fill=tk.X, pady=(0, s["md"]))
        self._details_card = details
        ttk.Label(details.body, text="Status and shortcuts", style="CardTitle.TLabel").pack(anchor=tk.W)
        grid = ttk.Frame(details.body, style="Card.TFrame")
        grid.pack(fill=tk.X, pady=(s["sm"], s["sm"]))
        grid.columnconfigure(1, weight=1)
        self.status_var = tk.StringVar(value="Phone: waiting for QR scan")
        self.capability_var = tk.StringVar(value="Capabilities: not received yet")
        self.toggle_var = tk.StringVar(value=self.theme.cfg.get("toggle_shortcut_display", "Shift+CapsLock"))
        self.emergency_var = tk.StringVar(value=self.theme.cfg.get("emergency_shortcut_display", "Ctrl+Alt+F12"))
        rows = (
            ("Connection", self.status_var),
            ("Phone", self.capability_var),
            ("Toggle", self.toggle_var),
            ("Emergency", self.emergency_var),
        )
        for index, (label, variable) in enumerate(rows):
            ttk.Label(grid, text=label, style="CardMuted.TLabel").grid(row=index, column=0, sticky=tk.W, padx=(0, s["md"]), pady=2)
            ttk.Label(grid, textvariable=variable, style="Card.TLabel").grid(row=index, column=1, sticky=tk.W, pady=2)
        ttk.Button(grid, text="Edit", style="Quiet.TButton", command=self.actions["shortcuts"]).grid(row=2, column=2, sticky=tk.E)
        ttk.Button(grid, text="Edit", style="Quiet.TButton", command=self.actions["shortcuts"]).grid(row=3, column=2, sticky=tk.E)

        links = ttk.Frame(details.body, style="Card.TFrame")
        links.pack(fill=tk.X)
        ttk.Button(links, text="Device settings", style="Secondary.TButton", command=self.actions["devices"]).pack(side=tk.LEFT, padx=(0, s["sm"]))
        ttk.Button(links, text="Diagnostics", style="Secondary.TButton", command=self.actions["diagnostics"]).pack(side=tk.LEFT)

        safety = Card(host, self.theme)
        safety.pack(fill=tk.X)
        self._warning_labels.extend(
            [
                self._add_warning(safety.body, TOUCH_POINTER_NOTE),
                self._add_warning(safety.body, TRUSTED_NETWORK_NOTE),
            ]
        )
        wrap_on_resize(safety.body, safety.body, inset=s["card_pad"] * 2)

    def _add_warning(self, parent: Any, text: str) -> Any:
        label = ttk.Label(parent, text=text, style="Card.TLabel", justify=tk.LEFT)
        label.pack(anchor=tk.W, pady=(0, self.theme.spacing["xs"]))
        return label

    def _on_palette(self, palette: Any) -> None:
        self.diagram.configure(bg=palette.surface)
        self.qr_canvas.configure(highlightbackground=palette.border)
        for label in self._warning_labels:
            label.configure(foreground=palette.warning)
        self._draw_diagram()

    def _round_rect(self, canvas: tk.Canvas, box: tuple[int, int, int, int], radius: int, **kwargs: Any) -> None:
        x1, y1, x2, y2 = box
        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, **kwargs)
        canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, **kwargs)
        canvas.create_arc(x1, y1, x1 + 2 * radius, y1 + 2 * radius, start=90, extent=90, **kwargs)
        canvas.create_arc(x2 - 2 * radius, y1, x2, y1 + 2 * radius, start=0, extent=90, **kwargs)
        canvas.create_arc(x1, y2 - 2 * radius, x1 + 2 * radius, y2, start=180, extent=90, **kwargs)
        canvas.create_arc(x2 - 2 * radius, y2 - 2 * radius, x2, y2, start=270, extent=90, **kwargs)

    def _draw_diagram(self, event: Any = None) -> None:
        canvas = self.diagram
        width = canvas.winfo_width() or 520
        p = self.theme.palette
        canvas.delete("all")
        center_y = 38
        box_w = min(180, max(110, width // 3))
        box_h = 52
        left_center = width * 0.25
        right_center = width * 0.75
        phone_active = self.mode in PHONE_MODES or self.mode == RoutingMode.CONNECTING

        canvas.create_line(left_center + box_w // 2 + 6, center_y, right_center - box_w // 2 - 6, center_y, fill=p.border, width=3)
        if phone_active:
            tip = right_center - box_w // 2 - 6
            canvas.create_polygon(tip - 10, center_y - 6, tip - 10, center_y + 6, tip, center_y, fill=p.accent)
        else:
            tip = left_center + box_w // 2 + 6
            canvas.create_polygon(tip + 10, center_y - 6, tip + 10, center_y + 6, tip, center_y, fill=p.accent)

        for label, cx, active in (("LAPTOP", left_center, not phone_active), ("PHONE", right_center, phone_active)):
            box = (cx - box_w // 2, center_y - box_h // 2, cx + box_w // 2, center_y + box_h // 2)
            self._round_rect(
                canvas,
                box,
                10,
                fill=p.accent if active else p.surface_alt,
                outline=p.accent if active else p.border,
            )
            canvas.create_text(
                cx,
                center_y,
                text=label,
                font=self.theme.fonts["body_bold"],
                fill=p.accent_on if active else p.text,
            )

    def _primary_action(self) -> None:
        if self.mode in PHONE_MODES:
            self.actions["laptop"]()
        elif self.mode != RoutingMode.CONNECTING:
            self.actions["switch"]()

    def set_state(self, mode: RoutingMode, connected: bool, paired: bool) -> None:
        self.mode = mode
        self.connected = connected
        self.paired = paired

        phone_control = mode in PHONE_MODES
        detail = MODE_DETAIL.get(mode, "")
        if connected and paired and not phone_control and mode != RoutingMode.CONNECTING:
            detail = "Connected. Press SWITCH TO PHONE to send keyboard and Touch Pointer to your phone."
        self.mode_label.configure(text=MODE_TEXT.get(mode, mode.value), foreground=self.theme.palette.accent if phone_control else self.theme.palette.text)
        self.mode_detail.configure(text=detail, foreground=self.theme.palette.accent if connected and paired and not phone_control else self.theme.palette.muted)

        if mode == RoutingMode.CONNECTING:
            self.primary.configure(text="Connecting to Phone...", state=tk.DISABLED)
        elif phone_control:
            self.primary.configure(text="Return to Laptop", state=tk.NORMAL)
        else:
            self.primary.configure(text="Switch to Phone", state=tk.NORMAL)

        for route_mode, button in self._route_buttons.items():
            active = mode == route_mode
            button.state(["selected"] if active else ["!selected"])

        self.status_var.set(self._connection_text())
        if self.paired and self.connected:
            if self.pair_card.winfo_manager():
                self.pair_card.pack_forget()
        else:
            if not self.pair_card.winfo_manager():
                self.pair_card.pack(before=self._details_card, fill=tk.X, pady=(0, self.theme.spacing["md"]))
            self.pair_hint.configure(text=self._pair_hint_text())
        self._draw_diagram()

    def _connection_text(self) -> str:
        if self.connected and self.paired:
            return "Connected on your local network"
        if self.connected:
            return "Phone linked, waiting for pairing approval"
        if self.paired:
            return "Paired, phone not connected"
        return "Not paired, show the QR to your phone"

    def _pair_hint_text(self) -> str:
        if self.paired and not self.connected:
            return "The paired phone is offline. Scan again or reconnect it."
        if self.connected and not self.paired:
            return "Scan with the InputBridge app to approve this laptop."
        return "Scan with the InputBridge phone app to connect."

    def set_capabilities(self, capabilities: Dict[str, Any]) -> None:
        if not capabilities:
            self.capability_var.set("Capabilities: not received yet")
            return
        parts = []
        if capabilities.get("accessibility"):
            parts.append("Touch Pointer ready")
        else:
            parts.append("Accessibility not enabled")
        if capabilities.get("ime"):
            parts.append("text ready")
        width = capabilities.get("screenWidth")
        height = capabilities.get("screenHeight")
        if width and height:
            parts.append(f"{width}x{height}")
        self.capability_var.set("Phone: " + ", ".join(parts))

    def set_shortcuts(self, toggle: str, emergency: str) -> None:
        self.toggle_var.set(toggle)
        self.emergency_var.set(emergency)

    def set_qr(self, matrix: Sequence[Sequence[bool]]) -> None:
        canvas = self.qr_canvas
        canvas.delete("all")
        if not matrix:
            return
        scale = max(1, 200 // max(len(matrix), len(matrix[0])))
        offset = (210 - scale * len(matrix[0])) // 2
        top = (210 - scale * len(matrix)) // 2
        for y, row in enumerate(matrix):
            for x, dark in enumerate(row):
                if dark:
                    x1 = offset + x * scale
                    y1 = top + y * scale
                    canvas.create_rectangle(x1, y1, x1 + scale, y1 + scale, fill="black", outline="black")
