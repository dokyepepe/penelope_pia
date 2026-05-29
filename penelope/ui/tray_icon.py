"""
Penélope — System Tray Icon
Always-visible tray icon with state indicators and context menu.
"""

from typing import Optional

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType, HudState, SystemMode
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class TrayIcon:
    """
    System tray icon for Penélope.

    States:
    - Pulsing slow (cyan): Idle — waiting for wake word
    - Pulsing fast (cyan): Listening to command
    - Spinning (purple): Processing response
    - Static (red): Error / degraded mode

    Right-click menu provides quick access to modes and status.
    """

    def __init__(self) -> None:
        self._app = None
        self._tray = None
        self._state = HudState.IDLE
        self._current_mode = SystemMode.NORMAL
        self._user_name: Optional[str] = None
        self.bus = get_event_bus()
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize the tray icon.

        Returns:
            True if initialized successfully.
        """
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
            from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
            from PyQt6.QtCore import QSize

            # Create icon pixmap (cyan circle)
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#00F0FF"))
            painter.setPen(QColor("#00F0FF"))
            painter.drawEllipse(4, 4, 24, 24)
            painter.end()

            icon = QIcon(pixmap)

            self._tray = QSystemTrayIcon(icon)
            self._tray.setToolTip("Penélope — Idle")

            # Context menu
            menu = QMenu()

            status_action = QAction("🟣 Penélope v0.1.0", menu)
            status_action.setEnabled(False)
            menu.addAction(status_action)

            menu.addSeparator()

            # Mode actions
            mode_menu = menu.addMenu("🔧 Modo")
            for mode in [SystemMode.NORMAL, SystemMode.WORK, SystemMode.SILENT,
                         SystemMode.NIGHT, SystemMode.POWER]:
                action = QAction(f"  {mode.value.title()}", mode_menu)
                action.triggered.connect(lambda checked, m=mode: self._on_mode_select(m))
                mode_menu.addAction(action)

            # Status
            status_item = QAction("📊 Status do Sistema", menu)
            status_item.triggered.connect(self._on_status_click)
            menu.addAction(status_item)

            menu.addSeparator()

            # Quit (requires owner auth)
            quit_action = QAction("🔒 Encerrar (requer autenticação)", menu)
            quit_action.triggered.connect(self._on_quit_click)
            menu.addAction(quit_action)

            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._on_tray_activated)
            self._tray.show()

            self._initialized = True
            log.info("System tray icon initialized")

            # Register event handlers
            self._register_events()

            return True

        except ImportError:
            log.warning("PyQt6 not available — tray icon disabled")
            return False
        except Exception as e:
            log.error(f"Failed to initialize tray icon: {e}")
            return False

    def _register_events(self) -> None:
        """Register event bus handlers for state updates."""
        from penelope.ui.event_bridge import QtEventBridge
        self.bridge = QtEventBridge()
        self.bridge.wake_word_detected.connect(lambda: self.set_state(HudState.LISTENING))
        self.bridge.listening_stopped.connect(lambda: self.set_state(HudState.PROCESSING))
        self.bridge.llm_response_complete.connect(lambda _: self.set_state(HudState.IDLE))
        self.bridge.tts_started.connect(lambda: self.set_state(HudState.SPEAKING))
        self.bridge.tts_finished.connect(lambda: self.set_state(HudState.IDLE))
        self.bridge.llm_offline.connect(lambda: self.set_state(HudState.ERROR))

    def set_state(self, state: HudState) -> None:
        """Update the tray icon state."""
        self._state = state

        tooltips = {
            HudState.IDLE: "Penélope — Aguardando",
            HudState.LISTENING: "Penélope — Escutando...",
            HudState.PROCESSING: "Penélope — Processando...",
            HudState.SPEAKING: "Penélope — Falando...",
            HudState.ERROR: "Penélope — Erro (clique para detalhes)",
        }

        if self._tray:
            self._tray.setToolTip(tooltips.get(state, "Penélope"))
            self._update_icon_color(state)

    def _update_icon_color(self, state: HudState) -> None:
        """Update the icon color based on state."""
        if not self._tray:
            return

        try:
            from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon

            colors = {
                HudState.IDLE: "#00F0FF",
                HudState.LISTENING: "#00FF88",
                HudState.PROCESSING: "#7B2FFF",
                HudState.SPEAKING: "#00F0FF",
                HudState.ERROR: "#FF3366",
            }

            color = colors.get(state, "#00F0FF")
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(color))
            painter.setPen(QColor(color))
            painter.drawEllipse(4, 4, 24, 24)
            painter.end()

            self._tray.setIcon(QIcon(pixmap))
        except Exception:
            pass

    def set_user(self, name: str) -> None:
        """Update the displayed user name."""
        self._user_name = name

    def _on_mode_select(self, mode: SystemMode) -> None:
        """Handle mode selection from menu."""
        self.bus.emit_sync(EventType.MODE_CHANGED, new_mode=mode)

    def _on_status_click(self) -> None:
        """Handle status menu click."""
        self.bus.emit_sync(EventType.HUD_UPDATE, action="show_status")

    def _on_quit_click(self) -> None:
        """Handle quit menu click — requires authentication."""
        self.bus.emit_sync(EventType.HUD_UPDATE, action="request_quit_auth")

    def _on_tray_activated(self, reason) -> None:
        """Handle tray icon click/double-click."""
        from PyQt6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.bus.emit_sync(EventType.HUD_UPDATE, action="toggle_hud")

    def show_notification(
        self,
        title: str,
        message: str,
        icon_type: str = "info",
    ) -> None:
        """
        Show a system notification balloon.

        Args:
            title: Notification title.
            message: Notification body.
            icon_type: 'info', 'warning', or 'critical'.
        """
        if self._tray is None:
            return

        from PyQt6.QtWidgets import QSystemTrayIcon
        icons = {
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "critical": QSystemTrayIcon.MessageIcon.Critical,
        }
        self._tray.showMessage(
            title,
            message,
            icons.get(icon_type, QSystemTrayIcon.MessageIcon.Information),
            5000,
        )

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def cleanup(self) -> None:
        """Remove the tray icon."""
        if self._tray:
            self._tray.hide()
            self._tray = None
        log.info("Tray icon cleaned up")
