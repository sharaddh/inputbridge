from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from inputbridge.config import ACCENTS, THEMES


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_on: str
    accent_hover: str
    accent_pressed: str
    success: str
    warning: str
    danger: str
    log_bg: str
    log_text: str


_ACCENT_COLORS = {
    "blue": ("#2563EB", "#6EA8FF", "#FFFFFF", "#0B1220"),
    "teal": ("#0F766E", "#4FD1C5", "#FFFFFF", "#0B1220"),
    "violet": ("#7C3AED", "#B69BFF", "#FFFFFF", "#0B1220"),
    "amber": ("#B45309", "#F5B94B", "#FFFFFF", "#0B1220"),
    "slate": ("#475569", "#A9B7C9", "#FFFFFF", "#0B1220"),
}


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _mix(first: str, second: str, amount: float) -> str:
    a = _rgb(first)
    b = _rgb(second)
    return _hex(tuple(round(x + (y - x) * amount) for x, y in zip(a, b)))


def _system_uses_dark() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except (OSError, ValueError):
        return False


class ThemeManager:
    def __init__(self, root: Any, cfg: Dict[str, Any]) -> None:
        self.root = root
        self.cfg = cfg
        self.fonts: Dict[str, tuple] = {}
        self.spacing: Dict[str, int] = {}
        self._subscribers: List[Callable[[Palette], None]] = []
        self._preview: Dict[str, Any] = {}
        self.palette = self._build_palette()
        self._build_tokens()
        self.apply()

    def subscribe(self, callback: Callable[[Palette], None]) -> None:
        self._subscribers.append(callback)
        callback(self.palette)

    def set_preview(self, **values: Any) -> None:
        self._preview.update(values)
        self.apply()

    def clear_preview(self) -> None:
        self._preview.clear()
        self.apply()

    def theme_setting(self) -> str:
        value = str(self._preview.get("theme", self.cfg.get("theme", "system"))).lower()
        return value if value in THEMES else "system"

    def accent_setting(self) -> str:
        value = str(self._preview.get("accent", self.cfg.get("accent", "blue"))).lower()
        return value if value in ACCENTS else "blue"

    def compact(self) -> bool:
        return bool(self._preview.get("compact_mode", self.cfg.get("compact_mode", False)))

    def effective_mode(self) -> str:
        mode = self.theme_setting()
        if mode == "system":
            return "dark" if _system_uses_dark() else "light"
        return mode

    def _build_tokens(self) -> None:
        compact = self.compact()
        scale = 9 if compact else 10
        family = "Segoe UI"
        self.fonts.clear()
        self.fonts.update(
            {
                "caption": (family, 8),
                "small": (family, 9),
                "body": (family, scale),
                "body_bold": (family, scale, "bold"),
                "subtitle": (family, scale + 2, "bold"),
                "title": (family, 16 if compact else 19, "bold"),
                "hero": (family, 19 if compact else 23, "bold"),
                "button": (family, scale + 1, "bold"),
                "mono": ("Consolas", 9),
            }
        )
        factor = 0.75 if compact else 1.0
        self.spacing.clear()
        self.spacing.update(
            {
                "xs": max(2, round(4 * factor)),
                "sm": max(4, round(8 * factor)),
                "md": max(6, round(12 * factor)),
                "lg": max(10, round(18 * factor)),
                "xl": max(14, round(24 * factor)),
                "card_pad": max(8, round(16 * factor)),
            }
        )

    def _build_palette(self) -> Palette:
        dark = self.effective_mode() == "dark"
        accent_light, accent_dark, on_light, on_dark = _ACCENT_COLORS[self.accent_setting()]
        accent = accent_dark if dark else accent_light
        accent_on = on_dark if dark else on_light
        if dark:
            base = Palette(
                bg="#151A21",
                surface="#1F2731",
                surface_alt="#273140",
                text="#E8EEF6",
                muted="#9AA9BA",
                border="#3A4757",
                accent=accent,
                accent_on=accent_on,
                accent_hover=_mix(accent, "#FFFFFF", 0.12),
                accent_pressed=_mix(accent, "#000000", 0.16),
                success="#5FD6A0",
                warning="#F2C35C",
                danger="#FF8A80",
                log_bg="#111722",
                log_text="#D8E2EE",
            )
        else:
            base = Palette(
                bg="#F3F5F8",
                surface="#FFFFFF",
                surface_alt="#EDF1F6",
                text="#1B2430",
                muted="#5B6B7C",
                border="#D5DDE7",
                accent=accent,
                accent_on=accent_on,
                accent_hover=_mix(accent, "#000000", 0.12),
                accent_pressed=_mix(accent, "#000000", 0.22),
                success="#137A4C",
                warning="#9A6100",
                danger="#B3261E",
                log_bg="#FFFFFF",
                log_text="#243040",
            )
        return base

    def apply(self) -> None:
        self._build_tokens()
        p = self._build_palette()
        self.palette = p
        self.root.configure(bg=p.bg)

        from tkinter import ttk

        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        fonts = self.fonts
        style.configure(".", font=fonts["body"], foreground=p.text, background=p.bg)
        style.configure("TFrame", background=p.bg)
        style.configure("Card.TFrame", background=p.surface)
        style.configure("Alt.TFrame", background=p.surface_alt)
        style.configure("TLabel", background=p.bg, foreground=p.text, font=fonts["body"])
        style.configure("Small.TLabel", background=p.bg, foreground=p.muted, font=fonts["small"])
        style.configure("Muted.TLabel", background=p.bg, foreground=p.muted, font=fonts["small"])
        style.configure("Title.TLabel", background=p.bg, foreground=p.text, font=fonts["title"])
        style.configure("Subtitle.TLabel", background=p.bg, foreground=p.text, font=fonts["subtitle"])
        style.configure("Card.TLabel", background=p.surface, foreground=p.text, font=fonts["body"])
        style.configure("CardTitle.TLabel", background=p.surface, foreground=p.text, font=fonts["subtitle"])
        style.configure("CardMuted.TLabel", background=p.surface, foreground=p.muted, font=fonts["small"])
        style.configure("Status.TLabel", background=p.bg, foreground=p.muted, font=fonts["body_bold"])
        style.configure("Success.TLabel", background=p.bg, foreground=p.success, font=fonts["body_bold"])
        style.configure("Warning.TLabel", background=p.bg, foreground=p.warning, font=fonts["small"])

        style.configure("TButton", font=fonts["body"], padding=(10, 6), background=p.surface_alt, foreground=p.text, borderwidth=1)
        style.map(
            "TButton",
            background=[("disabled", p.surface), ("pressed", p.border), ("active", _mix(p.surface_alt, p.border, 0.55)), ("", p.surface_alt)],
            foreground=[("disabled", p.muted), ("", p.text)],
        )
        style.configure("Primary.TButton", font=fonts["button"], padding=(16, 10), background=p.accent, foreground=p.accent_on, borderwidth=0, focuscolor=p.accent)
        style.map(
            "Primary.TButton",
            background=[("disabled", p.surface_alt), ("pressed", p.accent_pressed), ("active", p.accent_hover), ("", p.accent)],
            foreground=[("disabled", p.muted), ("", p.accent_on)],
        )
        style.configure("Hero.TButton", font=fonts["hero"], padding=(20, 14), background=p.accent, foreground=p.accent_on, borderwidth=0, focuscolor=p.accent)
        style.map(
            "Hero.TButton",
            background=[("disabled", p.surface_alt), ("pressed", p.accent_pressed), ("active", p.accent_hover), ("", p.accent)],
            foreground=[("disabled", p.muted), ("", p.accent_on)],
        )
        style.configure("Secondary.TButton", font=fonts["body"], padding=(10, 6), background=p.surface, foreground=p.text, borderwidth=1)
        style.map(
            "Secondary.TButton",
            background=[("disabled", p.surface), ("pressed", p.border), ("active", p.surface_alt), ("", p.surface)],
            foreground=[("disabled", p.muted), ("", p.text)],
        )
        style.configure("Quiet.TButton", font=fonts["small"], padding=(4, 2), background=p.bg, foreground=p.accent, borderwidth=0)
        style.map(
            "Quiet.TButton",
            background=[("active", p.surface_alt), ("", p.bg)],
            foreground=[("disabled", p.muted), ("", p.accent)],
        )
        style.configure("Danger.TButton", font=fonts["body"], padding=(8, 6), background=p.surface, foreground=p.danger, borderwidth=1)
        style.map(
            "Danger.TButton",
            background=[("active", p.surface_alt), ("", p.surface)],
            foreground=[("disabled", p.muted), ("", p.danger)],
        )
        style.configure("Tool.TButton", font=fonts["small"], padding=(8, 6), background=p.surface_alt, foreground=p.text, borderwidth=1)
        style.map(
            "Tool.TButton",
            background=[("selected", p.accent), ("pressed", p.accent_pressed), ("active", p.border), ("", p.surface_alt)],
            foreground=[("selected", p.accent_on), ("pressed", p.accent_on), ("", p.text)],
        )

        style.configure("TNotebook", background=p.bg, borderwidth=0, tabmargins=(0, self.spacing["sm"], 0, 0))
        style.configure(
            "TNotebook.Tab",
            background=p.surface_alt,
            foreground=p.muted,
            font=fonts["body_bold"],
            padding=(self.spacing["lg"], self.spacing["sm"]),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", p.surface), ("active", _mix(p.surface_alt, p.border, 0.5)), ("", p.surface_alt)],
            foreground=[("selected", p.accent), ("", p.muted)],
        )

        style.configure("TLabelframe", background=p.bg, foreground=p.text, bordercolor=p.border, relief="groove")
        style.configure("TLabelframe.Label", background=p.bg, foreground=p.text, font=fonts["body_bold"])
        style.configure("TCheckbutton", background=p.bg, foreground=p.text, font=fonts["body"], focuscolor=p.bg)
        style.map("TCheckbutton", background=[("active", p.bg), ("", p.bg)], foreground=[("disabled", p.muted), ("", p.text)])
        style.configure("TRadiobutton", background=p.bg, foreground=p.text, font=fonts["body"], focuscolor=p.bg)
        style.map("TRadiobutton", background=[("active", p.bg), ("", p.bg)], foreground=[("disabled", p.muted), ("", p.text)])
        style.configure("TEntry", fieldbackground=p.surface, foreground=p.text, insertcolor=p.text, bordercolor=p.border, padding=(6, 4))
        style.map("TEntry", fieldbackground=[("disabled", p.surface_alt), ("", p.surface)], foreground=[("disabled", p.muted), ("", p.text)])
        style.configure("TCombobox", fieldbackground=p.surface, foreground=p.text, arrowcolor=p.muted, bordercolor=p.border, padding=(6, 4))
        style.map("TCombobox", fieldbackground=[("disabled", p.surface_alt), ("", p.surface)], foreground=[("disabled", p.muted), ("", p.text)])
        style.configure("TSpinbox", fieldbackground=p.surface, foreground=p.text, arrowcolor=p.muted, bordercolor=p.border, padding=(6, 4))
        style.configure("TScale", background=p.bg, troughcolor=p.surface_alt, bordercolor=p.bg, lightcolor=p.accent, darkcolor=p.accent)
        style.configure("TScrollbar", background=p.surface_alt, troughcolor=p.bg, bordercolor=p.bg, arrowcolor=p.muted)

        for subscriber in list(self._subscribers):
            subscriber(p)
