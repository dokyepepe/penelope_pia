"""
Penélope — Theme System
Sci-fi holographic color palette, fonts, and animation definitions.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class ColorPalette:
    """Color palette for a Penélope theme."""
    # Primary
    primary: str = "#00F0FF"          # Cyan
    primary_glow: str = "#00F0FF80"   # Cyan with alpha
    primary_dark: str = "#006B73"

    # Secondary
    secondary: str = "#7B2FFF"        # Purple
    secondary_glow: str = "#7B2FFF60"

    # Accents
    accent_green: str = "#00FF88"     # Success / online
    accent_red: str = "#FF3366"       # Error / critical
    accent_yellow: str = "#FFD700"    # Warning
    accent_orange: str = "#FF6B35"    # Alert

    # Backgrounds
    bg_dark: str = "#0A0E17"          # Deep space blue-black
    bg_panel: str = "#0D1520"         # Panel background
    bg_overlay: str = "#0A0E17CC"     # Transparent overlay (80% opacity)
    bg_glass: str = "#1A2332AA"       # Glassmorphism effect

    # Text
    text_primary: str = "#E8F4F8"     # Near-white
    text_secondary: str = "#7B8FA3"   # Muted
    text_dim: str = "#4A5568"         # Very muted

    # Borders
    border: str = "#1E3A5F"
    border_glow: str = "#00F0FF40"

    # Profile badges
    badge_owner: str = "#00F0FF"
    badge_co_owner: str = "#7B2FFF"
    badge_common: str = "#00FF88"


@dataclass
class ThemeConfig:
    """Complete theme configuration."""
    name: str = "holographic"
    colors: ColorPalette = None
    font_family: str = "Rajdhani, Orbitron, Segoe UI, sans-serif"
    font_size_small: int = 11
    font_size_normal: int = 13
    font_size_large: int = 16
    font_size_title: int = 20
    border_radius: int = 12
    glow_blur: int = 15
    animation_speed_ms: int = 300

    def __post_init__(self):
        if self.colors is None:
            self.colors = ColorPalette()


# Pre-defined themes
THEMES: Dict[str, ThemeConfig] = {
    "holographic": ThemeConfig(
        name="holographic",
        colors=ColorPalette(),
    ),
    "dark_minimal": ThemeConfig(
        name="dark_minimal",
        colors=ColorPalette(
            primary="#FFFFFF",
            primary_glow="#FFFFFF40",
            secondary="#888888",
            bg_dark="#000000",
            bg_panel="#111111",
            bg_overlay="#000000CC",
        ),
        glow_blur=5,
    ),
    "night": ThemeConfig(
        name="night",
        colors=ColorPalette(
            primary="#FF6B9D",
            primary_glow="#FF6B9D40",
            secondary="#C850C0",
            bg_dark="#0A0512",
            bg_panel="#120A1E",
            bg_overlay="#0A0512DD",
        ),
    ),
}


def get_hud_stylesheet(theme: ThemeConfig) -> str:
    """
    Generate the Qt stylesheet for the HUD overlay.

    Args:
        theme: Theme configuration.

    Returns:
        Qt stylesheet string.
    """
    c = theme.colors
    return f"""
    QWidget#hud_main {{
        background-color: {c.bg_overlay};
        border: 1px solid {c.border};
        border-radius: {theme.border_radius}px;
        font-family: {theme.font_family};
    }}

    QLabel#hud_title {{
        color: {c.primary};
        font-size: {theme.font_size_title}px;
        font-weight: bold;
        font-family: {theme.font_family};
    }}

    QLabel#hud_status {{
        color: {c.text_secondary};
        font-size: {theme.font_size_small}px;
        font-family: {theme.font_family};
    }}

    QLabel#hud_response {{
        color: {c.text_primary};
        font-size: {theme.font_size_normal}px;
        font-family: {theme.font_family};
        padding: 8px;
        background-color: {c.bg_glass};
        border-radius: 8px;
        border: 1px solid {c.border_glow};
    }}

    QLabel#hud_transcription {{
        color: {c.primary};
        font-size: {theme.font_size_normal}px;
        font-family: {theme.font_family};
        font-style: italic;
    }}

    QLabel#hud_badge_owner {{
        color: {c.badge_owner};
        font-size: {theme.font_size_small}px;
        font-weight: bold;
    }}

    QLabel#hud_badge_co_owner {{
        color: {c.badge_co_owner};
        font-size: {theme.font_size_small}px;
        font-weight: bold;
    }}

    QLabel#hud_badge_common {{
        color: {c.badge_common};
        font-size: {theme.font_size_small}px;
        font-weight: bold;
    }}

    QProgressBar {{
        background-color: {c.bg_panel};
        border: 1px solid {c.border};
        border-radius: 4px;
        height: 6px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {c.primary};
        border-radius: 3px;
    }}

    QPushButton {{
        background-color: {c.bg_glass};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 6px;
        padding: 6px 12px;
        font-family: {theme.font_family};
        font-size: {theme.font_size_normal}px;
    }}

    QPushButton:hover {{
        background-color: {c.primary_dark};
        border-color: {c.primary};
    }}

    QMenu {{
        background-color: {c.bg_panel};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 4px;
        font-family: {theme.font_family};
    }}

    QMenu::item:selected {{
        background-color: {c.primary_dark};
    }}
    """
