"""Colors, fonts and asset paths shared by the UI.

Every color is a (light mode, dark mode) pair, which CustomTkinter switches
between automatically.
"""

from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

ACCENT = ("#4F46E5", "#6366F1")
ACCENT_HOVER = ("#4338CA", "#4F46E5")
BG = ("#F3F4F8", "#0E1016")
CARD = ("#FFFFFF", "#171A22")
BORDER = ("#E3E6EE", "#252A36")
FIELD = ("#F3F4F8", "#1F232E")  # inputs, segmented tracks, inner cards
FIELD_HOVER = ("#E8EAF1", "#2A2F3C")
SELECTED = ("#FFFFFF", "#353B4D")  # the selected segment of a segmented button
TRACK = ("#E6E8EF", "#1F232E")  # segmented button sitting directly on the background
TEXT = ("#111827", "#E8EAF0")
MUTED = ("#6B7280", "#8E94A6")
ERROR = ("#DC2626", "#F87171")
SUCCESS = ("#15803D", "#4ADE80")
ON_ACCENT = "#FFFFFF"
ON_ACCENT_DIM = "#C7D2FE"  # text on the accent color while busy

BADGE_COLORS = {".pdf": "#E5484D", ".pptx": "#EA580C"}

# Colors for the pieces in the preview bar (cycled). All readable with white text.
PART_COLORS = ["#6366F1", "#0284C7", "#059669", "#D97706", "#E11D48", "#8B5CF6"]


def pick(color: str | tuple[str, str]) -> str:
    """Resolve a (light, dark) pair for widgets that aren't CustomTkinter widgets."""
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def asset(name: str) -> Path:
    """Path to a file in assets/, also inside the packaged app (PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


class Fonts:
    """Fonts can only be created once the window exists, so they live here."""

    def __init__(self) -> None:
        self.title = ctk.CTkFont(size=22, weight="bold")
        self.subtitle = ctk.CTkFont(size=13)
        self.section = ctk.CTkFont(size=11, weight="bold")
        self.body = ctk.CTkFont(size=13)
        self.body_bold = ctk.CTkFont(size=13, weight="bold")
        self.small = ctk.CTkFont(size=12)
        self.badge = ctk.CTkFont(size=10, weight="bold")
        self.button = ctk.CTkFont(size=14, weight="bold")
        self.family = self.body.cget("family")
