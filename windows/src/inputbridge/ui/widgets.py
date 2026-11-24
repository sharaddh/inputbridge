from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class Card(tk.Frame):
    def __init__(self, master: Any, theme: Any, padding: tuple[int, int] | None = None, **kwargs: Any) -> None:
        super().__init__(
            master,
            bd=0,
            highlightthickness=1,
            bg=theme.palette.surface,
            highlightbackground=theme.palette.border,
            **kwargs,
        )
        self.body = ttk.Frame(self, style="Card.TFrame", padding=padding or (theme.spacing["card_pad"], theme.spacing["md"]))
        self.body.pack(fill=tk.BOTH, expand=True)
        self._theme = theme
        theme.subscribe(self._on_palette)

    def _on_palette(self, palette: Any) -> None:
        self.configure(bg=palette.surface, highlightbackground=palette.border)


class ScrolledFrame(ttk.Frame):
    def __init__(self, master: Any, theme: Any, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.theme = theme
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0, bg=theme.palette.bg)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="TFrame")
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner.bind("<MouseWheel>", self._on_mousewheel)
        theme.subscribe(self._on_palette)

    def _on_palette(self, palette: Any) -> None:
        self.canvas.configure(bg=palette.bg)

    def _on_inner_configure(self, event: Any) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: Any) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_mousewheel(self, event: Any) -> None:
        if event.delta:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")


def wrap_on_resize(widget: Any, master: Any, inset: int = 8) -> None:
    def on_configure(event: Any) -> None:
        width = max(140, event.width - inset)
        try:
            widget.configure(wraplength=width)
            return
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            try:
                child.configure(wraplength=width)
            except tk.TclError:
                pass

    master.bind("<Configure>", on_configure)
