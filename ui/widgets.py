"""Reusable pieces of the PDF Cutter window."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from . import theme
from .theme import pick

Range = tuple[int, int]


# --------------------------------------------------------------- helpers --


def unit_for(path: Path, count: int) -> str:
    word = "slide" if path.suffix.lower() == ".pptx" else "page"
    return word if count == 1 else word + "s"


def describe_range(path: Path, start: int, end: int) -> str:
    if start == end:
        return f"{unit_for(path, 1)} {start}"
    return f"{unit_for(path, 2)} {start}–{end}"


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def shorten_path(path: Path, limit: int) -> str:
    text = str(path)
    return text if len(text) <= limit else "…" + text[-(limit - 1):]


def section_label(master, text: str, fonts: theme.Fonts) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master, text=text.upper(), font=fonts.section, text_color=theme.MUTED, anchor="w", height=18
    )


def bind_click(widgets, callback: Callable[[], None]) -> None:
    for widget in widgets:
        widget.bind("<Button-1>", lambda _e: callback())


# --------------------------------------------------------------- widgets --


class Badge(ctk.CTkLabel):
    """Small colored "PDF" / "PPTX" tag."""

    def __init__(self, master, path: Path, fonts: theme.Fonts):
        suffix = path.suffix.lower()
        super().__init__(
            master,
            text=suffix.lstrip(".").upper(),
            font=fonts.badge,
            text_color=theme.ON_ACCENT,
            fg_color=theme.BADGE_COLORS.get(suffix, "#6B7280"),
            corner_radius=6,
            width=44,
            height=22,
        )


class DropZone(ctk.CTkFrame):
    """The "drop files here" area. Clicking it opens the file picker."""

    def __init__(self, master, fonts: theme.Fonts, icon: ctk.CTkImage, on_click: Callable[[], None]):
        super().__init__(
            master, height=150, fg_color=theme.FIELD, border_width=2, border_color=theme.BORDER, corner_radius=16
        )
        self.grid_propagate(False)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        icon_label = ctk.CTkLabel(inner, text="", image=icon, height=44)
        title = ctk.CTkLabel(
            inner, text="Drop PDF or PowerPoint files here", font=fonts.body_bold, text_color=theme.TEXT, height=22
        )
        hint = ctk.CTkLabel(inner, text="or click to browse", font=fonts.small, text_color=theme.ACCENT, height=20)
        icon_label.pack(pady=(0, 6))
        title.pack()
        hint.pack()

        parts = (self, inner, icon_label, title, hint)
        bind_click(parts, on_click)
        for widget in parts:
            widget.bind("<Enter>", lambda _e: self.set_highlight(True), add="+")
            widget.bind("<Leave>", lambda _e: self.set_highlight(False), add="+")
        self.configure(cursor="hand2")

    def set_highlight(self, on: bool) -> None:
        self.configure(
            border_color=theme.ACCENT if on else theme.BORDER,
            fg_color=theme.FIELD_HOVER if on else theme.FIELD,
        )


class Stepper(ctk.CTkFrame):
    """A number box with − and + buttons."""

    def __init__(self, master, variable: tk.StringVar, fonts: theme.Fonts):
        super().__init__(master, fg_color="transparent")
        self.variable = variable
        button = dict(
            width=36, height=36, corner_radius=10, fg_color=theme.FIELD, hover_color=theme.FIELD_HOVER,
            text_color=theme.TEXT, font=fonts.button,
        )
        ctk.CTkButton(self, text="−", command=lambda: self.step(-1), **button).grid(row=0, column=0)
        ctk.CTkEntry(
            self, textvariable=variable, width=70, height=36, justify="center", corner_radius=10, border_width=0,
            fg_color=theme.FIELD, text_color=theme.TEXT, font=fonts.body_bold,
        ).grid(row=0, column=1, padx=6)
        ctk.CTkButton(self, text="+", command=lambda: self.step(1), **button).grid(row=0, column=2)

    def step(self, delta: int) -> None:
        try:
            value = int(self.variable.get())
        except ValueError:
            value = 0 if delta > 0 else 2
        self.variable.set(str(max(1, value + delta)))


class SplitBar(tk.Canvas):
    """A bar representing the whole document, colored by the file each page goes to."""

    HEIGHT = 30

    def __init__(self, master, total: int, ranges: list[Range], font_family: str, background):
        self.scale = ctk.ScalingTracker.get_widget_scaling(master)
        super().__init__(
            master, height=round(self.HEIGHT * self.scale), highlightthickness=0, borderwidth=0, bg=pick(background)
        )
        self.total, self.ranges, self.font_family = total, ranges, font_family
        self.bind("<Configure>", lambda _e: self.redraw())

    def redraw(self) -> None:
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 10:
            return
        s = self.scale
        gap, radius = 3 * s, 7 * s
        _round_rect(self, 0, 0, width, height, radius, fill=pick(theme.FIELD_HOVER))
        show_numbers = len(self.ranges) <= 40
        for index, (start, end) in enumerate(self.ranges):
            x0 = (start - 1) / self.total * width + (gap / 2 if start > 1 else 0)
            x1 = end / self.total * width - (gap / 2 if end < self.total else 0)
            x0, x1 = round(x0), round(max(x1, x0 + 2 * s))
            color = theme.PART_COLORS[index % len(theme.PART_COLORS)]
            _round_rect(self, x0, 0, x1, height, min(radius, (x1 - x0) / 2), fill=color)
            if show_numbers and x1 - x0 > 20 * s:
                self.create_text(
                    (x0 + x1) / 2, height / 2, text=str(index + 1), fill=theme.ON_ACCENT,
                    font=(self.font_family, -round(12 * s), "bold"),
                )


def _round_rect(canvas: tk.Canvas, x0, y0, x1, y1, r, **kwargs) -> None:
    points = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
        x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    canvas.create_polygon(points, smooth=True, outline="", **kwargs)


class PreviewCard(ctk.CTkFrame):
    """One input file: its name, a bar showing the cuts, and the files that will be created."""

    MAX_ROWS = 8

    def __init__(
        self,
        master,
        fonts: theme.Fonts,
        path: Path,
        total: int,
        on_remove: Callable[[], None],
        plan: list[Range] | None = None,
        targets: list[Path] | None = None,
        error: str | None = None,
    ):
        super().__init__(master, fg_color=theme.FIELD, corner_radius=16)
        self.columnconfigure(1, weight=1)

        Badge(self, path, fonts).grid(row=0, column=0, padx=(16, 10), pady=(14, 0))
        ctk.CTkLabel(
            self, text=shorten(path.name, 40), font=fonts.body_bold, text_color=theme.TEXT, anchor="w"
        ).grid(row=0, column=1, sticky="w", pady=(14, 0))
        summary = f"{total} {unit_for(path, total)}"
        if plan:
            summary += f"  →  {len(plan)} file" + ("" if len(plan) == 1 else "s")
        ctk.CTkLabel(self, text=summary, font=fonts.small, text_color=theme.MUTED).grid(
            row=0, column=2, padx=(10, 4), pady=(14, 0)
        )
        ctk.CTkButton(
            self, text="×", width=28, height=28, corner_radius=8, fg_color="transparent",
            hover_color=theme.FIELD_HOVER, text_color=theme.MUTED, font=fonts.button, command=on_remove,
        ).grid(row=0, column=3, padx=(0, 10), pady=(14, 0))

        if error or not plan or not targets:
            ctk.CTkLabel(
                self, text=error or "", font=fonts.body, text_color=theme.ERROR, anchor="w", justify="left",
                wraplength=440,
            ).grid(row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=(8, 16))
            return

        SplitBar(self, total, plan, fonts.family, theme.FIELD).grid(
            row=1, column=0, columnspan=4, sticky="ew", padx=16, pady=(12, 10)
        )

        rows = ctk.CTkFrame(self, fg_color="transparent")
        rows.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=(0, 14))
        rows.columnconfigure(1, weight=1)
        shown = len(plan) if len(plan) <= self.MAX_ROWS else self.MAX_ROWS - 1
        for i, ((start, end), target) in enumerate(zip(plan[:shown], targets)):
            color = theme.PART_COLORS[i % len(theme.PART_COLORS)]
            ctk.CTkFrame(rows, width=10, height=10, corner_radius=5, fg_color=color).grid(
                row=i, column=0, padx=(2, 10)
            )
            ctk.CTkLabel(
                rows, text=shorten(target.name, 44), font=fonts.body, text_color=theme.TEXT, anchor="w", height=26
            ).grid(row=i, column=1, sticky="w")
            ctk.CTkLabel(
                rows, text=describe_range(path, start, end), font=fonts.small, text_color=theme.MUTED, height=26
            ).grid(row=i, column=2, sticky="e")
        if shown < len(plan):
            ctk.CTkLabel(
                rows, text=f"… and {len(plan) - shown} more, up to {targets[-1].name}", font=fonts.small,
                text_color=theme.MUTED, anchor="w", height=26,
            ).grid(row=shown, column=1, columnspan=2, sticky="w")
