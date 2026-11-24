from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from typing import Any, Callable, Dict, List, Sequence, Tuple

from inputbridge.config import ACCENTS, DEFAULT_CONFIG, POINTER_RATES, PROFILES
from inputbridge.ui.shortcuts import DEFAULTS as SHORTCUT_DEFAULTS
from inputbridge.ui.shortcuts import normalize, validate as validate_shortcuts
from inputbridge.ui.widgets import Card, ScrolledFrame, wrap_on_resize

MODE_CHOICES: Tuple[Tuple[str, str], ...] = (
    ("Laptop", "LAPTOP"),
    ("Phone: keyboard + pointer", "PHONE_BOTH"),
    ("Phone: keyboard only", "PHONE_KEYBOARD"),
    ("Phone: pointer only", "PHONE_MOUSE"),
)
PHONE_MODE_CHOICES = MODE_CHOICES[1:]

PROFILE_PRESETS: Dict[str, Dict[str, Any]] = {
    "work": {"default_mode": "PHONE_BOTH", "pointer_rate_hz": "60", "scroll_sensitivity": 1.0, "theme": "system"},
    "phone": {"default_mode": "PHONE_BOTH", "pointer_rate_hz": "120", "scroll_sensitivity": 1.0, "theme": "dark"},
    "typing": {"default_mode": "PHONE_KEYBOARD", "pointer_rate_hz": "60", "scroll_sensitivity": 1.0, "theme": "system"},
    "navigation": {"default_mode": "PHONE_MOUSE", "pointer_rate_hz": "120", "scroll_sensitivity": 1.25, "theme": "light"},
}

DEVELOPER_NOTES = (
    "Touch Pointer uses accessibility gestures. There is no native Android mouse "
    "support, hover, drag, wheel or guaranteed right-click behavior.",
    "Pointer rate, button mappings, cursor style and scroll preferences are stored "
    "locally and applied when the input engine and phone companion support them.",
    "Active system hotkeys are registered by the input engine as Shift+CapsLock and "
    "Ctrl+Alt+F12. Changing the shortcut text below changes the displayed label only.",
    "Transport uses HMAC-SHA256 for integrity and authentication, not encryption. "
    "Use a trusted local network until an encrypted transport is available.",
)


class SettingsView(ttk.Frame):
    def __init__(self, master: Any, theme: Any, cfg: Dict[str, Any], actions: Dict[str, Callable[..., None]]) -> None:
        super().__init__(master, style="TFrame")
        self.theme = theme
        self.cfg = cfg
        self.actions = actions
        self.vars: Dict[str, Any] = {}
        self._kinds: Dict[str, str] = {}
        self._combo_maps: Dict[str, Dict[str, Any]] = {}
        self._applying_profile = False
        self._ready = False
        self._build_vars()
        self._build()
        self._ready = True
        for key in ("default_mode", "pointer_rate_hz", "scroll_sensitivity"):
            self.vars[key].trace_add("write", self._mark_custom)
        self._update_shortcut_preview()
        self._update_sensitivity_label()
        theme.subscribe(lambda palette: self._draw_cursor_preview())

    def _build_vars(self) -> None:
        specs: Dict[str, str] = {
            "device_name": "str",
            "phone_name": "str",
            "paired_token": "str",
            "default_mode": "str",
            "startup_mode": "str",
            "auto_connect": "bool",
            "notifications": "bool",
            "start_minimized": "bool",
            "toggle_shortcut_display": "str",
            "emergency_shortcut_display": "str",
            "pointer_rate_hz": "str",
            "scroll_direction": "str",
            "scroll_sensitivity": "float",
            "right_button_action": "str",
            "middle_button_action": "str",
            "theme": "str",
            "accent": "str",
            "compact_mode": "bool",
            "cursor_shape": "str",
            "cursor_size": "str",
            "cursor_fill": "str",
            "cursor_outline": "str",
            "cursor_trail": "bool",
            "click_ripple": "bool",
            "profile": "str",
            "diagnostics_enabled": "bool",
            "connection_timeout": "float",
        }
        for key, kind in specs.items():
            self._kinds[key] = kind
            value = self.cfg.get(key, DEFAULT_CONFIG.get(key))
            if kind == "bool":
                self.vars[key] = tk.BooleanVar(value=bool(value))
            elif kind == "float":
                self.vars[key] = tk.DoubleVar(value=float(value))
            else:
                self.vars[key] = tk.StringVar(value=str(value))

    def _build(self) -> None:
        s = self.theme.spacing
        host = ttk.Frame(self, style="TFrame")
        host.pack(fill=tk.BOTH, expand=True, padx=(s["lg"], s["lg"]), pady=(s["md"], 0))
        ttk.Label(host, text="Settings", style="Title.TLabel").pack(anchor=tk.W, pady=(0, s["sm"]))

        notebook = ttk.Notebook(host)
        self.notebook = notebook
        notebook.pack(fill=tk.BOTH, expand=True)
        tabs = (
            ("General", self._build_general),
            ("Shortcuts", self._build_shortcuts),
            ("Devices", self._build_devices),
            ("Input", self._build_input),
            ("Appearance", self._build_appearance),
            ("Advanced", self._build_advanced),
        )
        for title, builder in tabs:
            tab = ScrolledFrame(notebook, self.theme)
            notebook.add(tab, text=title)
            tab.inner.configure(padding=(s["md"], s["md"], s["md"], s["md"]))
            builder(tab.inner)

        bar = ttk.Frame(host, style="TFrame")
        bar.pack(fill=tk.X, pady=(s["sm"], s["md"]))
        self.status_var = tk.StringVar(value="Changes are saved on this device only.")
        ttk.Label(bar, textvariable=self.status_var, style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Button(bar, text="Save settings", style="Primary.TButton", command=self._save).pack(side=tk.RIGHT)

    def _section(self, parent: Any, title: str, hint: str | None = None) -> Any:
        frame = ttk.Frame(parent, style="TFrame")
        frame.pack(fill=tk.X, pady=(0, self.theme.spacing["md"]))
        ttk.Label(frame, text=title, style="Subtitle.TLabel").pack(anchor=tk.W)
        if hint:
            label = ttk.Label(frame, text=hint, style="Muted.TLabel", justify=tk.LEFT)
            label.pack(anchor=tk.W, pady=(2, 0))
            wrap_on_resize(label, frame, inset=8)
        return frame

    def _row(self, parent: Any, label: str, widget: Any) -> None:
        s = self.theme.spacing
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill=tk.X, pady=(0, s["xs"]))
        ttk.Label(row, text=label, style="TLabel").pack(side=tk.LEFT, padx=(0, s["md"]))
        widget.pack(side=tk.LEFT, fill=tk.X)

    def _combo(self, parent: Any, label: str, key: str, choices: Sequence[Tuple[str, Any]], hint: str | None = None) -> ttk.Combobox:
        pairs = list(choices)
        labels = [item[0] for item in pairs]
        self._combo_maps[key] = {item[0]: item[1] for item in pairs}
        inverse = {item[1]: item[0] for item in pairs}
        current = str(self.vars[key].get())
        resolved = inverse.get(current)
        if resolved is None:
            resolved = next((label for value, label in inverse.items() if str(value) == current), None)
        self.vars[key].set(resolved if resolved is not None else labels[0])
        row = ttk.Frame(parent, style="TFrame")
        row.pack(fill=tk.X, pady=(0, self.theme.spacing["xs"]))
        ttk.Label(row, text=label, style="TLabel", width=22, anchor=tk.W).pack(side=tk.LEFT, padx=(0, self.theme.spacing["sm"]))
        combo = ttk.Combobox(row, textvariable=self.vars[key], values=labels, state="readonly", width=32)
        combo.pack(side=tk.LEFT, fill=tk.X)
        if hint:
            hint_label = ttk.Label(parent, text=hint, style="Muted.TLabel", justify=tk.LEFT)
            hint_label.pack(anchor=tk.W, pady=(0, self.theme.spacing["sm"]))
            wrap_on_resize(hint_label, parent, inset=8)
        return combo

    def _check(self, parent: Any, text: str, key: str, command: Callable[..., None] | None = None) -> None:
        ttk.Checkbutton(parent, text=text, variable=self.vars[key], command=command).pack(anchor=tk.W, pady=(0, self.theme.spacing["xs"]))

    def _build_general(self, parent: Any) -> None:
        s = self.theme.spacing
        startup = self._section(parent, "Startup", "Startup and disconnect always return control to the laptop for safety.")
        self._check(startup, "Start minimized to the system tray", "start_minimized")
        self._check(startup, "Show switch notifications", "notifications")
        self._combo(startup, "Startup mode", "startup_mode", MODE_CHOICES, "Choose where input starts after launch.")

        profile = self._section(parent, "Profile", "A profile applies a ready-made routing and input preset.")
        self._combo(profile, "Profile", "profile", tuple((name.title(), name) for name in PROFILES))
        self.vars["profile"].trace_add("write", self._apply_profile)

    def _build_shortcuts(self, parent: Any) -> None:
        s = self.theme.spacing
        section = self._section(
            parent,
            "Shortcut labels",
            "Enter a key with optional Ctrl, Alt, Shift or Win modifiers.",
        )
        for label, key in (("Toggle", "toggle_shortcut_display"), ("Emergency return", "emergency_shortcut_display")):
            row = ttk.Frame(section, style="TFrame")
            row.pack(fill=tk.X, pady=(0, s["xs"]))
            ttk.Label(row, text=label, style="TLabel", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, s["sm"]))
            ttk.Entry(row, textvariable=self.vars[key], width=28).pack(side=tk.LEFT, fill=tk.X)

        self.toggle_preview = ttk.Label(section, text="", style="CardMuted.TLabel")
        self.toggle_preview.pack(anchor=tk.W, pady=(s["xs"], 0))
        self.emergency_preview = ttk.Label(section, text="", style="CardMuted.TLabel")
        self.emergency_preview.pack(anchor=tk.W)
        self.shortcut_error = ttk.Label(section, text="", style="Muted.TLabel", justify=tk.LEFT)
        self.shortcut_error.pack(anchor=tk.W, pady=(s["xs"], 0))
        wrap_on_resize(self.shortcut_error, section, inset=8)

        ttk.Button(section, text="Restore defaults", style="Secondary.TButton", command=self._restore_shortcuts).pack(anchor=tk.W, pady=(s["sm"], 0))
        for key in ("toggle_shortcut_display", "emergency_shortcut_display"):
            self.vars[key].trace_add("write", self._update_shortcut_preview)

        self._section(
            parent,
            "Engine behavior",
            "The input engine currently registers Shift+CapsLock to toggle and Ctrl+Alt+F12 for emergency return. In Phone mode, CapsLock alone also returns to the laptop. Editing these fields updates the labels shown in the app; rebinding the OS hotkeys requires an engine update.",
        )

    def _build_devices(self, parent: Any) -> None:
        s = self.theme.spacing
        identity = self._section(parent, "Device names", "Names are shown in the app and on the paired phone.")
        for label, key in (("Laptop name", "device_name"), ("Phone name", "phone_name")):
            row = ttk.Frame(identity, style="TFrame")
            row.pack(fill=tk.X, pady=(0, s["xs"]))
            ttk.Label(row, text=label, style="TLabel", width=20, anchor=tk.W).pack(side=tk.LEFT, padx=(0, s["sm"]))
            ttk.Entry(row, textvariable=self.vars[key], width=32).pack(side=tk.LEFT, fill=tk.X)
        self._check(identity, "Reconnect to the paired phone at startup", "auto_connect")

        pairing = self._section(parent, "Pairing", "The pairing secret is stored locally. It is never displayed in the UI or written to the log.")
        ttk.Button(pairing, text="Pair new device", style="Secondary.TButton", command=self.actions["re_pair"]).pack(side=tk.LEFT, padx=(0, s["sm"]))
        ttk.Button(pairing, text="Revoke pairing", style="Danger.TButton", command=self.actions["revoke"]).pack(side=tk.LEFT)
        note = ttk.Label(pairing, text="Revoking pairing stops the server and restores local input. Pair again to connect a phone.", style="Muted.TLabel", justify=tk.LEFT)
        note.pack(anchor=tk.W, pady=(s["sm"], 0))
        wrap_on_resize(note, pairing, inset=8)

    def _build_input(self, parent: Any) -> None:
        routing = self._section(parent, "Routing", "Choose where input goes when you switch to the phone.")
        self._combo(routing, "Default phone mode", "default_mode", PHONE_MODE_CHOICES)
        self._combo(routing, "Pointer rate", "pointer_rate_hz", (("30 Hz", "30"), ("60 Hz", "60"), ("120 Hz", "120")), "Higher rates need a phone and network that can keep up.")

        scroll = self._section(parent, "Scroll and buttons", "Scroll is translated into touch gestures in Touch Pointer mode.")
        self._combo(scroll, "Scroll direction", "scroll_direction", (("Natural", 1), ("Reverse", -1)))
        s_sm = self.theme.spacing["xs"]
        row = ttk.Frame(scroll, style="TFrame")
        row.pack(fill=tk.X, pady=(0, s_sm))
        ttk.Label(row, text="Scroll sensitivity", style="TLabel", width=22, anchor=tk.W).pack(side=tk.LEFT, padx=(0, self.theme.spacing["sm"]))
        scale = ttk.Scale(row, from_=0.25, to=3.0, orient=tk.HORIZONTAL, variable=self.vars["scroll_sensitivity"], length=210)
        scale.pack(side=tk.LEFT)
        self.sensitivity_label = ttk.Label(row, text="", style="Muted.TLabel", width=8)
        self.sensitivity_label.pack(side=tk.LEFT, padx=(self.theme.spacing["sm"], 0))
        self.vars["scroll_sensitivity"].trace_add("write", self._update_sensitivity_label)
        self._combo(scroll, "Right button", "right_button_action", (("Context menu tap", "context"), ("Back", "back"), ("Not forwarded", "none")))
        self._combo(scroll, "Middle button", "middle_button_action", (("Not forwarded", "none"), ("Auto-scroll", "autoscroll"), ("Home", "home")))
        note = ttk.Label(scroll, text="Button actions depend on companion support. Right-click and middle-click are not native Android mouse events.", style="Muted.TLabel", justify=tk.LEFT)
        note.pack(anchor=tk.W, pady=(s_sm, 0))
        wrap_on_resize(note, scroll, inset=8)

    def _build_appearance(self, parent: Any) -> None:
        s = self.theme.spacing
        theme_section = self._section(parent, "Theme", "Changes preview immediately and are saved with Save settings.")
        for label, value in (("System", "system"), ("Light", "light"), ("Dark", "dark")):
            ttk.Radiobutton(theme_section, text=label, value=value, variable=self.vars["theme"], command=self._preview_theme).pack(side=tk.LEFT, padx=(0, s["lg"]))
        accent = self._combo(theme_section, "Accent", "accent", tuple((name.title(), name) for name in ACCENTS))
        accent.bind("<<ComboboxSelected>>", self._preview_theme)
        self._check(theme_section, "Compact layout", "compact_mode", self._preview_theme)

        cursor = self._section(parent, "Touch Pointer cursor", "A visual overlay for Touch Pointer, not a native Android pointer.")
        preview_row = ttk.Frame(cursor, style="TFrame")
        preview_row.pack(fill=tk.X, pady=(0, s["sm"]))
        self.cursor_canvas = tk.Canvas(
            preview_row,
            width=120,
            height=120,
            bg=self.theme.palette.surface_alt,
            highlightthickness=1,
            highlightbackground=self.theme.palette.border,
        )
        self.cursor_canvas.pack(side=tk.LEFT, padx=(0, s["lg"]))
        controls = ttk.Frame(preview_row, style="TFrame")
        controls.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._combo(controls, "Shape", "cursor_shape", (("Classic arrow", "arrow"), ("Compact arrow", "compact"), ("Dot", "dot"), ("Crosshair", "crosshair"))).bind("<<ComboboxSelected>>", self._draw_cursor_preview)
        self._combo(controls, "Size", "cursor_size", (("Small", "small"), ("Medium", "medium"), ("Large", "large"))).bind("<<ComboboxSelected>>", self._draw_cursor_preview)
        for label, key in (("Fill", "cursor_fill"), ("Outline", "cursor_outline")):
            row = ttk.Frame(controls, style="TFrame")
            row.pack(fill=tk.X, pady=(0, self.theme.spacing["xs"]))
            ttk.Label(row, text=label, style="TLabel", width=10, anchor=tk.W).pack(side=tk.LEFT, padx=(0, self.theme.spacing["sm"]))
            ttk.Entry(row, textvariable=self.vars[key], width=10).pack(side=tk.LEFT)
            ttk.Button(row, text="Pick", style="Quiet.TButton", command=lambda k=key: self._pick_color(k)).pack(side=tk.LEFT)
            self.vars[key].trace_add("write", self._draw_cursor_preview)
        self._check(controls, "Pointer trail (off by default)", "cursor_trail")
        self._check(controls, "Click ripple (off by default)", "click_ripple")
        self._draw_cursor_preview()

    def _build_advanced(self, parent: Any) -> None:
        s = self.theme.spacing
        diagnostics = self._section(parent, "Diagnostics")
        self._check(diagnostics, "Enable diagnostics view and status log", "diagnostics_enabled")
        ttk.Button(diagnostics, text="Export log", style="Secondary.TButton", command=self.actions["export_log"]).pack(anchor=tk.W, pady=(0, s["sm"]))

        network = self._section(parent, "Connection", "The server waits for a phone on the local network.")
        row = ttk.Frame(network, style="TFrame")
        row.pack(fill=tk.X)
        ttk.Label(row, text="Heartbeat timeout (seconds)", style="TLabel").pack(side=tk.LEFT, padx=(0, s["md"]))
        ttk.Entry(row, textvariable=self.vars["connection_timeout"], width=10).pack(side=tk.LEFT)

        notes = self._section(parent, "Developer note")
        for text in DEVELOPER_NOTES:
            label = ttk.Label(notes, text=text, style="Muted.TLabel", justify=tk.LEFT)
            label.pack(anchor=tk.W, pady=(0, s["xs"]))
            wrap_on_resize(label, notes, inset=8)

    def select_tab(self, title: str) -> None:
        for index in range(self.notebook.index("end")):
            if self.notebook.tab(index, "text") == title:
                self.notebook.select(index)
                return

    def _mark_custom(self, *args: Any) -> None:
        if not self._applying_profile and self.vars["profile"].get() != "custom":
            self.vars["profile"].set("custom")

    def _apply_profile(self, *args: Any) -> None:
        if self._applying_profile:
            return
        preset = PROFILE_PRESETS.get(self.vars["profile"].get())
        if not preset:
            return
        self._applying_profile = True
        try:
            for key, value in preset.items():
                if key not in self.vars:
                    continue
                if key in self._combo_maps:
                    inverse = {stored: label for label, stored in self._combo_maps[key].items()}
                    self.vars[key].set(inverse.get(value, str(value)))
                else:
                    self.vars[key].set(value)
            self._preview_theme()
        finally:
            self._applying = False

    def _preview_theme(self, *args: Any) -> None:
        if not self._ready:
            return
        self.theme.set_preview(
            theme=self.vars["theme"].get(),
            accent=self._combo_maps["accent"].get(self.vars["accent"].get(), "blue"),
            compact_mode=bool(self.vars["compact_mode"].get()),
        )

    def _update_shortcut_preview(self, *args: Any) -> None:
        if not hasattr(self, "toggle_preview"):
            return
        toggle = self.vars["toggle_shortcut_display"].get()
        emergency = self.vars["emergency_shortcut_display"].get()
        self.toggle_preview.configure(text=f"Toggle preview: {normalize(toggle) or 'none'}")
        self.emergency_preview.configure(text=f"Emergency preview: {normalize(emergency) or 'none'}")
        errors = validate_shortcuts(toggle, emergency)
        p = self.theme.palette
        self.shortcut_error.configure(text="\n".join(errors), foreground=p.danger if errors else p.muted)

    def _update_sensitivity_label(self, *args: Any) -> None:
        if not hasattr(self, "sensitivity_label"):
            return
        try:
            value = float(self.vars["scroll_sensitivity"].get())
        except (TypeError, ValueError):
            value = 1.0
        self.sensitivity_label.configure(text=f"{value:.2f}x")

    def _pick_color(self, key: str) -> None:
        chosen = colorchooser.askcolor(color=self.vars[key].get(), title="Choose cursor color")
        if chosen and chosen[1]:
            self.vars[key].set(str(chosen[1]).upper())

    def _draw_cursor_preview(self, *args: Any) -> None:
        if not hasattr(self, "cursor_canvas"):
            return
        canvas = self.cursor_canvas
        p = self.theme.palette
        canvas.configure(bg=p.surface_alt, highlightbackground=p.border)
        canvas.delete("all")
        fill = self.vars["cursor_fill"].get() or p.text
        outline = self.vars["cursor_outline"].get() or p.accent
        shape = self._combo_maps["cursor_shape"].get(self.vars["cursor_shape"].get(), "arrow")
        size_name = self._combo_maps["cursor_size"].get(self.vars["cursor_size"].get(), "medium")
        scale = {"small": 0.7, "medium": 1.0, "large": 1.35}.get(size_name, 1.0)
        cx, cy = 44, 40
        if shape in ("arrow", "compact"):
            width = 1.0 if shape == "arrow" else 0.65
            points = [
                (0, 0),
                (0, 34),
                (8, 26),
                (14, 40),
                (20, 36),
                (14, 24),
                (26, 24),
            ]
            coords = [coord for x, y in points for coord in (cx + x * scale * width, cy + y * scale * width)]
            canvas.create_polygon(coords, fill=fill, outline=outline, width=2)
        elif shape == "dot":
            r = 8 * scale
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=2)
        else:
            r = 16 * scale
            canvas.create_line(cx - r, cy, cx + r, cy, fill=fill, width=3)
            canvas.create_line(cx, cy - r, cx, cy + r, fill=fill, width=3)
            canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, outline=outline, width=2)
        canvas.create_text(60, 104, text=f"{shape.title()} / {size_name}", font=self.theme.fonts["caption"], fill=p.muted)

    def _restore_shortcuts(self) -> None:
        self.vars["toggle_shortcut_display"].set(SHORTCUT_DEFAULTS["toggle"])
        self.vars["emergency_shortcut_display"].set(SHORTCUT_DEFAULTS["emergency"])

    def validate(self) -> List[str]:
        errors = validate_shortcuts(
            self.vars["toggle_shortcut_display"].get(),
            self.vars["emergency_shortcut_display"].get(),
        )
        rate_value = self.vars["pointer_rate_hz"].get()
        rate_value = self._combo_maps["pointer_rate_hz"].get(rate_value, rate_value)
        try:
            rate = int(rate_value)
            if rate not in POINTER_RATES:
                errors.append("Pointer rate must be 30, 60 or 120 Hz.")
        except (TypeError, ValueError):
            errors.append("Pointer rate must be 30, 60 or 120 Hz.")
        for key, label, low, high in (
            ("scroll_sensitivity", "Scroll sensitivity", 0.25, 3.0),
            ("connection_timeout", "Heartbeat timeout", 3.0, 120.0),
        ):
            try:
                value = float(self.vars[key].get())
                if not low <= value <= high:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{label} must be between {low} and {high}.")
        for key, label in (("device_name", "Laptop name"), ("phone_name", "Phone name")):
            if not self.vars[key].get().strip():
                errors.append(f"{label} cannot be empty.")
        return errors

    def collect(self) -> Dict[str, Any]:
        result: Dict[str, Any] = dict(self.cfg)
        for key, kind in self._kinds.items():
            value = self.vars[key].get()
            if key in self._combo_maps:
                value = self._combo_maps[key].get(value, value)
            if kind == "bool":
                result[key] = bool(value)
            elif kind == "float":
                try:
                    result[key] = round(float(value), 2)
                except (TypeError, ValueError):
                    result[key] = DEFAULT_CONFIG[key]
            elif key == "pointer_rate_hz":
                try:
                    result[key] = int(value)
                except (TypeError, ValueError):
                    result[key] = DEFAULT_CONFIG[key]
            else:
                result[key] = str(value).strip()
        result["toggle_shortcut_display"] = normalize(result["toggle_shortcut_display"])
        result["emergency_shortcut_display"] = normalize(result["emergency_shortcut_display"])
        result["scroll_direction"] = int(result["scroll_direction"]) if result["scroll_direction"] in (1, -1) else 1
        return result

    def _save(self) -> None:
        errors = self.validate()
        if errors:
            messagebox.showwarning("InputBridge", "Fix the following before saving:\n\n- " + "\n- ".join(errors))
            return
        settings = self.collect()
        self.actions["save"](settings)
        self.status_var.set("Settings saved on this device.")
