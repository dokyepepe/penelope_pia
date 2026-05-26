"""
Penélope — Radial Menu (Pizza Menu)
Circular action menu that appears centered on the cursor.
"""

import math
from typing import Callable, Dict, List, Optional, Tuple

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType, UserLevel
from penelope.utils.logger import get_logger

log = get_logger(__name__)


# Default menu slices per profile level
DEFAULT_SLICES: Dict[str, List[Dict]] = {
    "owner": [
        {"label": "Chrome", "icon": "🌐", "action": "open_app", "target": "chrome"},
        {"label": "Arquivos", "icon": "📁", "action": "open_app", "target": "explorer"},
        {"label": "Música", "icon": "🎵", "action": "open_app", "target": "spotify"},
        {"label": "WhatsApp", "icon": "💬", "action": "open_app", "target": "whatsapp"},
        {"label": "Clipboard", "icon": "📋", "action": "clipboard_history", "target": None},
        {"label": "Config", "icon": "⚙️", "action": "open_settings", "target": None},
        {"label": "Volume", "icon": "🔊", "action": "volume_control", "target": None},
        {"label": "Falar", "icon": "🎤", "action": "voice_input", "target": None},
        {"label": "Status", "icon": "📊", "action": "system_status", "target": None},
        {"label": "Travar", "icon": "🔒", "action": "lock_session", "target": None},
    ],
    "co_owner": [
        {"label": "Chrome", "icon": "🌐", "action": "open_app", "target": "chrome"},
        {"label": "Arquivos", "icon": "📁", "action": "open_app", "target": "explorer"},
        {"label": "Música", "icon": "🎵", "action": "open_app", "target": "spotify"},
        {"label": "Volume", "icon": "🔊", "action": "volume_control", "target": None},
        {"label": "Falar", "icon": "🎤", "action": "voice_input", "target": None},
        {"label": "Status", "icon": "📊", "action": "system_status", "target": None},
    ],
    "common": [
        {"label": "Chrome", "icon": "🌐", "action": "open_app", "target": "chrome"},
        {"label": "Volume", "icon": "🔊", "action": "volume_control", "target": None},
        {"label": "Falar", "icon": "🎤", "action": "voice_input", "target": None},
        {"label": "Status", "icon": "📊", "action": "system_status", "target": None},
    ],
}


class RadialMenu:
    """
    Circular (pizza) action menu triggered by a hotkey.

    Appears centered on the cursor with animated opening.
    Slices are filtered based on the active user profile.
    Supports sub-menus for nested actions.
    """

    def __init__(
        self,
        radius: int = 200,
        hotkey: str = "alt+space",
    ) -> None:
        self.radius = radius
        self.hotkey = hotkey
        self._window = None
        self._initialized = False
        self._visible = False
        self._slices: List[Dict] = DEFAULT_SLICES["owner"]
        self._on_action: Optional[Callable] = None
        self.bus = get_event_bus()

    def initialize(self) -> bool:
        """
        Initialize the radial menu.

        Returns:
            True if initialized successfully.
        """
        try:
            from PyQt6.QtWidgets import QWidget, QApplication
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPainterPath

            class RadialWidget(QWidget):
                """Custom widget for the radial menu."""

                def __init__(self, menu: 'RadialMenu'):
                    super().__init__()
                    self.menu = menu
                    self.setWindowFlags(
                        Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.WindowStaysOnTopHint
                        | Qt.WindowType.Tool
                        | Qt.WindowType.Popup
                    )
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                    size = menu.radius * 2 + 60
                    self.setFixedSize(size, size)
                    self._hovered_slice = -1

                def paintEvent(self, event):
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                    cx = self.width() // 2
                    cy = self.height() // 2
                    r = self.menu.radius

                    slices = self.menu._slices
                    if not slices:
                        return

                    n = len(slices)
                    angle_per = 360.0 / n

                    # Draw background circle
                    painter.setBrush(QColor(10, 14, 23, 200))
                    painter.setPen(QPen(QColor("#1E3A5F"), 2))
                    painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

                    # Draw center circle
                    painter.setBrush(QColor(0, 240, 255, 40))
                    painter.setPen(QPen(QColor("#00F0FF"), 2))
                    painter.drawEllipse(cx - 30, cy - 30, 60, 60)

                    # Draw center text
                    font = QFont("Segoe UI", 8)
                    painter.setFont(font)
                    painter.setPen(QColor("#00F0FF"))
                    painter.drawText(cx - 15, cy + 4, "P")

                    # Draw slices
                    font = QFont("Segoe UI", 9)
                    painter.setFont(font)

                    for i, s in enumerate(slices):
                        angle = math.radians(i * angle_per - 90 + angle_per / 2)
                        label_r = r * 0.65
                        lx = cx + label_r * math.cos(angle)
                        ly = cy + label_r * math.sin(angle)

                        # Slice highlight
                        if i == self._hovered_slice:
                            painter.setPen(QColor("#00F0FF"))
                        else:
                            painter.setPen(QColor("#7B8FA3"))

                        # Icon
                        icon_font = QFont("Segoe UI Emoji", 16)
                        painter.setFont(icon_font)
                        painter.drawText(int(lx - 12), int(ly - 4), s.get("icon", "●"))

                        # Label
                        label_font = QFont("Segoe UI", 8)
                        painter.setFont(label_font)
                        painter.drawText(int(lx - 20), int(ly + 16), s.get("label", ""))

                    painter.end()

                def mousePressEvent(self, event):
                    pos = event.position()
                    cx = self.width() / 2
                    cy = self.height() / 2
                    dx = pos.x() - cx
                    dy = pos.y() - cy

                    dist = math.sqrt(dx ** 2 + dy ** 2)
                    if dist < 30:  # Center click
                        self.hide()
                        self.menu._visible = False
                        return

                    if dist > self.menu.radius:
                        self.hide()
                        self.menu._visible = False
                        return

                    # Determine which slice
                    angle = math.degrees(math.atan2(dy, dx)) + 90
                    if angle < 0:
                        angle += 360

                    n = len(self.menu._slices)
                    slice_idx = int(angle / (360.0 / n)) % n

                    if 0 <= slice_idx < n:
                        self.menu._execute_slice(slice_idx)

                    self.hide()
                    self.menu._visible = False

                def keyPressEvent(self, event):
                    from PyQt6.QtCore import Qt as QtKey
                    if event.key() == QtKey.Key.Key_Escape:
                        self.hide()
                        self.menu._visible = False

            self._window = RadialWidget(self)
            self._initialized = True
            log.info("Radial menu initialized")
            return True

        except ImportError:
            log.warning("PyQt6 not available — radial menu disabled")
            return False
        except Exception as e:
            log.error(f"Failed to initialize radial menu: {e}")
            return False

    def show_at_cursor(self) -> None:
        """Show the radial menu centered on the current cursor position."""
        if not self._initialized or not self._window:
            return

        try:
            from PyQt6.QtGui import QCursor

            pos = QCursor.pos()
            x = pos.x() - self._window.width() // 2
            y = pos.y() - self._window.height() // 2

            self._window.move(x, y)
            self._window.show()
            self._window.activateWindow()
            self._visible = True

            self.bus.emit_sync(EventType.RADIAL_MENU_OPENED)
            log.debug("Radial menu shown at cursor")

        except Exception as e:
            log.error(f"Failed to show radial menu: {e}")

    def hide_menu(self) -> None:
        """Hide the radial menu."""
        if self._window:
            self._window.hide()
            self._visible = False
            self.bus.emit_sync(EventType.RADIAL_MENU_CLOSED)

    def set_slices_for_level(self, level: UserLevel) -> None:
        """Update visible slices based on user level."""
        level_key = {
            UserLevel.OWNER: "owner",
            UserLevel.CO_OWNER: "co_owner",
            UserLevel.COMMON: "common",
        }.get(level, "common")

        self._slices = DEFAULT_SLICES.get(level_key, DEFAULT_SLICES["common"])
        if self._window:
            self._window.update()

    def set_action_handler(self, handler: Callable) -> None:
        """Set the callback for slice actions."""
        self._on_action = handler

    def _execute_slice(self, index: int) -> None:
        """Execute the action for a menu slice."""
        if 0 <= index < len(self._slices):
            slice_data = self._slices[index]
            log.info(f"Radial action: {slice_data['label']} ({slice_data['action']})")

            if self._on_action:
                self._on_action(slice_data)

    @property
    def is_visible(self) -> bool:
        return self._visible

    def cleanup(self) -> None:
        """Clean up the radial menu."""
        if self._window:
            self._window.close()
            self._window = None
        self._initialized = False
        log.info("Radial menu cleaned up")
