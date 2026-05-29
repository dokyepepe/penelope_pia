"""
Penélope — Radial Menu (Pizza Menu)
Circular action menu that appears centered on the cursor with glowing holographic design.
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
        """Initialize the radial menu and configure input tracking."""
        try:
            from PyQt6.QtWidgets import QWidget
            from PyQt6.QtCore import Qt, pyqtSlot
            from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QRadialGradient

            class RadialWidget(QWidget):
                """Custom widget for the radial menu with tracking and custom painting."""

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
                    self.setMouseTracking(True)
                    size = menu.radius * 2 + 60
                    self.setFixedSize(size, size)
                    self._hovered_slice = -1

                @pyqtSlot()
                def show_at_cursor_widget(self):
                    try:
                        from PyQt6.QtGui import QCursor
                        pos = QCursor.pos()
                        x = pos.x() - self.width() // 2
                        y = pos.y() - self.height() // 2
                        self.move(x, y)
                        self.show()
                        self.activateWindow()
                        self.menu._visible = True
                        self.menu.bus.emit_sync(EventType.RADIAL_MENU_OPENED)
                        log.debug("Radial menu shown at cursor via slot")
                    except Exception as e:
                        log.error(f"Failed to show radial menu widget: {e}")

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

                    # 1. Background dark translucent ring
                    painter.setBrush(QColor(10, 14, 23, 215))
                    painter.setPen(QPen(QColor("#1E3A5F"), 2))
                    painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

                    # 2. Outer glowing cyan ring
                    glow = QColor("#00F0FF")
                    glow.setAlpha(80)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(glow, 3))
                    painter.drawEllipse(cx - r - 2, cy - r - 2, (r + 2) * 2, (r + 2) * 2)

                    # 3. Draw hover highlighted sector
                    if self._hovered_slice != -1:
                        # Angle in Qt starts at 3 o'clock (0 degrees) and is counter-clockwise.
                        # Index 0 starts at -90 degrees (12 o'clock), growing clockwise.
                        start_angle_qt = int((90 - (self._hovered_slice + 1) * angle_per) * 16)
                        span_angle_qt = int(angle_per * 16)

                        grad = QRadialGradient(cx, cy, r)
                        grad.setColorAt(0.0, QColor("#7B2FFF80"))  # Purple central glow
                        grad.setColorAt(1.0, QColor("#00F0FFCC"))  # Neon cyan outer edge

                        painter.setBrush(grad)
                        painter.setPen(QPen(QColor("#00F0FF"), 2))
                        painter.drawPie(cx - r, cy - r, r * 2, r * 2, start_angle_qt, span_angle_qt)

                    # 4. Partition divider dashed lines
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("#1E3A5F"), 1, Qt.PenStyle.DashLine))
                    for i in range(n):
                        angle_rad = math.radians(i * angle_per - 90)
                        x2 = cx + r * math.cos(angle_rad)
                        y2 = cy + r * math.sin(angle_rad)
                        painter.drawLine(int(cx), int(cy), int(x2), int(y2))

                    # 5. Glowing Center Core
                    painter.setBrush(QColor(13, 21, 32, 255))
                    painter.setPen(QPen(QColor("#00F0FF"), 2))
                    painter.drawEllipse(cx - 32, cy - 32, 64, 64)

                    core_pulse = QColor("#00F0FF")
                    core_pulse.setAlpha(60)
                    painter.setBrush(core_pulse)
                    painter.drawEllipse(cx - 24, cy - 24, 48, 48)

                    font = QFont("Rajdhani", 12, QFont.Weight.Bold)
                    painter.setFont(font)
                    painter.setPen(QColor("#E8F4F8"))
                    painter.drawText(cx - 6, cy + 6, "P")

                    # 6. Slices Icons & Labels
                    for i, s in enumerate(slices):
                        angle = math.radians(i * angle_per - 90 + angle_per / 2)
                        label_r = r * 0.70
                        lx = cx + label_r * math.cos(angle)
                        ly = cy + label_r * math.sin(angle)

                        # Highlight text when hovered
                        if i == self._hovered_slice:
                            painter.setPen(QColor("#00F0FF"))
                        else:
                            painter.setPen(QColor("#7B8FA3"))

                        # Icon
                        icon_font = QFont("Segoe UI Emoji", 16)
                        painter.setFont(icon_font)
                        painter.drawText(int(lx - 12), int(ly - 4), s.get("icon", "●"))

                        # Label
                        label_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
                        painter.setFont(label_font)
                        painter.drawText(int(lx - 22), int(ly + 16), s.get("label", ""))

                    painter.end()

                def mouseMoveEvent(self, event):
                    pos = event.position()
                    cx = self.width() / 2
                    cy = self.height() / 2
                    dx = pos.x() - cx
                    dy = pos.y() - cy
                    dist = math.sqrt(dx**2 + dy**2)

                    if 32 <= dist <= self.menu.radius:
                        angle = math.degrees(math.atan2(dy, dx)) + 90
                        if angle < 0:
                            angle += 360
                        
                        n = len(self.menu._slices)
                        slice_idx = int(angle / (360.0 / n)) % n
                        if slice_idx != self._hovered_slice:
                            self._hovered_slice = slice_idx
                            self.update()
                    else:
                        if self._hovered_slice != -1:
                            self._hovered_slice = -1
                            self.update()

                def leaveEvent(self, event):
                    self._hovered_slice = -1
                    self.update()

                def mousePressEvent(self, event):
                    pos = event.position()
                    cx = self.width() / 2
                    cy = self.height() / 2
                    dx = pos.x() - cx
                    dy = pos.y() - cy

                    dist = math.sqrt(dx ** 2 + dy ** 2)
                    if dist < 32:  # Center click
                        self.hide()
                        self.menu._visible = False
                        return

                    if dist > self.menu.radius:
                        self.hide()
                        self.menu._visible = False
                        return

                    # Determine clicked slice
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

            # Register global hotkey
            try:
                import keyboard
                keyboard.add_hotkey(self.hotkey, self.show_at_cursor)
                log.info(f"Radial menu hotkey registered: {self.hotkey}")
            except Exception as e:
                log.warning(f"Could not register keyboard hotkey for radial menu: {e}")

            return True

        except Exception as e:
            log.error(f"Failed to initialize radial menu: {e}")
            return False

    def show_at_cursor(self) -> None:
        """Show the radial menu centered on the current cursor position."""
        if not self._initialized or not self._window:
            return

        import threading
        from PyQt6.QtCore import QCoreApplication
        if QCoreApplication.instance() and threading.current_thread() != QCoreApplication.instance().thread().currentThread():
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(self._window, "show_at_cursor_widget", Qt.ConnectionType.QueuedConnection)
            return

        self._window.show_at_cursor_widget()

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
