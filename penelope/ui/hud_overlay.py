"""
Penélope — HUD Overlay
Transparent, always-on-top holographic interface.
"""

import time
from typing import Optional

from penelope.core.event_bus import get_event_bus
from penelope.ui.theme import ThemeConfig, THEMES, get_hud_stylesheet
from penelope.utils.constants import EventType, HudState, SystemMode, UserLevel
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class HudOverlay:
    """
    The main visual interface for Penélope.

    A transparent, borderless, always-on-top PyQt6 window
    with sci-fi holographic aesthetics.

    Features:
    - Animated audio waveform during listening
    - Live transcription display
    - Typewriter response effect
    - System status bar (time, uptime, CPU, RAM)
    - User profile badge
    - Mode indicator
    """

    def __init__(
        self,
        theme_name: str = "holographic",
        width: int = 420,
        height: int = 280,
        position: str = "bottom-right",
    ) -> None:
        self.theme = THEMES.get(theme_name, THEMES["holographic"])
        self.width = width
        self.height = height
        self.position = position

        self._window = None
        self._initialized = False
        self._visible = True
        self._state = HudState.IDLE
        self._current_user: Optional[str] = None
        self._current_level: Optional[UserLevel] = None
        self._current_mode = SystemMode.NORMAL
        self._response_text = ""
        self._transcription_text = ""

        # Qt widgets (set during initialize)
        self._label_title = None
        self._label_status = None
        self._label_response = None
        self._label_transcription = None
        self._label_user_badge = None
        self._label_mode = None
        self._label_time = None

        self.bus = get_event_bus()

    def initialize(self) -> bool:
        """
        Create and show the HUD overlay window.

        Returns:
            True if initialized successfully.
        """
        try:
            from PyQt6.QtWidgets import (
                QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication,
            )
            from PyQt6.QtCore import Qt, QTimer
            from PyQt6.QtGui import QFont

            # Create main window
            self._window = QWidget()
            self._window.setObjectName("hud_main")
            self._window.setWindowTitle("Penélope HUD")
            self._window.setFixedSize(self.width, self.height)

            # Window flags: frameless, always on top, transparent, tool window
            self._window.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self._window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

            # Apply theme stylesheet
            self._window.setStyleSheet(get_hud_stylesheet(self.theme))

            # Layout
            layout = QVBoxLayout(self._window)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(6)

            # Top bar: title + badge + mode
            top_bar = QHBoxLayout()

            self._label_title = QLabel("PENÉLOPE")
            self._label_title.setObjectName("hud_title")
            top_bar.addWidget(self._label_title)

            top_bar.addStretch()

            self._label_user_badge = QLabel("● —")
            self._label_user_badge.setObjectName("hud_badge_owner")
            top_bar.addWidget(self._label_user_badge)

            self._label_mode = QLabel("NORMAL")
            self._label_mode.setObjectName("hud_status")
            top_bar.addWidget(self._label_mode)

            layout.addLayout(top_bar)

            # Transcription line
            self._label_transcription = QLabel("")
            self._label_transcription.setObjectName("hud_transcription")
            self._label_transcription.setWordWrap(True)
            self._label_transcription.setMaximumHeight(40)
            layout.addWidget(self._label_transcription)

            # Response area
            self._label_response = QLabel("Aguardando...")
            self._label_response.setObjectName("hud_response")
            self._label_response.setWordWrap(True)
            self._label_response.setMinimumHeight(100)
            layout.addWidget(self._label_response)

            # Status bar
            status_bar = QHBoxLayout()

            self._label_time = QLabel(time.strftime("%H:%M"))
            self._label_time.setObjectName("hud_status")
            status_bar.addWidget(self._label_time)

            status_bar.addStretch()

            self._label_status = QLabel("● Online")
            self._label_status.setObjectName("hud_status")
            status_bar.addWidget(self._label_status)

            layout.addLayout(status_bar)

            # Position the window
            self._position_window()

            # Show
            self._window.show()
            self._initialized = True
            self._visible = True

            # Timer for clock update
            self._timer = QTimer()
            self._timer.timeout.connect(self._update_clock)
            self._timer.start(1000)

            # Register event handlers
            self._register_events()

            log.info("HUD overlay initialized")
            return True

        except ImportError:
            log.warning("PyQt6 not available — HUD disabled")
            return False
        except Exception as e:
            log.error(f"Failed to initialize HUD: {e}")
            return False

    def _position_window(self) -> None:
        """Position the window based on settings."""
        if not self._window:
            return

        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen is None:
                return

            geo = screen.availableGeometry()
            margin = 20

            positions = {
                "bottom-right": (
                    geo.width() - self.width - margin,
                    geo.height() - self.height - margin,
                ),
                "bottom-left": (margin, geo.height() - self.height - margin),
                "top-right": (geo.width() - self.width - margin, margin),
                "top-left": (margin, margin),
                "center": (
                    (geo.width() - self.width) // 2,
                    (geo.height() - self.height) // 2,
                ),
            }

            x, y = positions.get(self.position, positions["bottom-right"])
            self._window.move(x, y)
        except Exception as e:
            log.warning(f"Failed to position HUD: {e}")

    def _register_events(self) -> None:
        """Register event handlers for HUD updates."""
        self.bus.on(EventType.TRANSCRIPTION_READY, self._on_transcription)
        self.bus.on(EventType.LLM_RESPONSE_CHUNK, self._on_response_chunk)
        self.bus.on(EventType.LLM_RESPONSE_COMPLETE, self._on_response_complete)
        self.bus.on(EventType.AUTH_SUCCESS, self._on_auth_success)
        self.bus.on(EventType.SESSION_EXPIRED, self._on_session_expired)
        self.bus.on(EventType.MODE_CHANGED, self._on_mode_changed)
        self.bus.on(EventType.WAKE_WORD_DETECTED, self._on_wake_word)

    def _on_wake_word(self, **kwargs) -> None:
        """Handle wake word detection."""
        self.set_state(HudState.LISTENING)
        self.set_transcription("Escutando...")

    def _on_transcription(self, text: str = "", **kwargs) -> None:
        """Handle live transcription update."""
        self.set_transcription(text)
        self.set_state(HudState.PROCESSING)

    def _on_response_chunk(self, chunk: str = "", **kwargs) -> None:
        """Handle streaming response chunk."""
        self._response_text += chunk
        if self._label_response:
            self._label_response.setText(self._response_text)

    def _on_response_complete(self, response: str = "", **kwargs) -> None:
        """Handle complete response."""
        self.set_response(response or self._response_text)
        self._response_text = ""
        self.set_state(HudState.IDLE)

    def _on_auth_success(self, user_name: str = "", user_level=None, **kwargs) -> None:
        """Handle successful authentication."""
        self.set_user(user_name, user_level)

    def _on_session_expired(self, **kwargs) -> None:
        """Handle session expiration."""
        self.set_user(None, None)
        self.set_response("Sessão encerrada.")

    def _on_mode_changed(self, new_mode: SystemMode = SystemMode.NORMAL, **kwargs) -> None:
        """Handle mode change."""
        self.set_mode(new_mode)

    def set_state(self, state: HudState) -> None:
        """Update the visual state of the HUD."""
        self._state = state

        state_texts = {
            HudState.IDLE: "● Online",
            HudState.LISTENING: "◉ Escutando",
            HudState.PROCESSING: "◌ Processando",
            HudState.SPEAKING: "◈ Falando",
            HudState.ERROR: "✖ Erro",
        }

        if self._label_status:
            self._label_status.setText(state_texts.get(state, "● Online"))

    def set_transcription(self, text: str) -> None:
        """Update the transcription display."""
        self._transcription_text = text
        if self._label_transcription:
            display = text[:100] + "..." if len(text) > 100 else text
            self._label_transcription.setText(f'🎤 "{display}"')

    def set_response(self, text: str) -> None:
        """Update the response display."""
        if self._label_response:
            self._label_response.setText(text)

    def set_user(self, name: Optional[str], level: Optional[UserLevel] = None) -> None:
        """Update the user badge."""
        self._current_user = name
        self._current_level = level

        if self._label_user_badge:
            if name:
                badge_colors = {
                    UserLevel.OWNER: ("🔵", "hud_badge_owner"),
                    UserLevel.CO_OWNER: ("🟣", "hud_badge_co_owner"),
                    UserLevel.COMMON: ("🟢", "hud_badge_common"),
                }
                emoji, obj_name = badge_colors.get(level, ("⚪", "hud_status"))
                self._label_user_badge.setText(f"{emoji} {name}")
                self._label_user_badge.setObjectName(obj_name)
            else:
                self._label_user_badge.setText("● —")

    def set_mode(self, mode: SystemMode) -> None:
        """Update the mode indicator."""
        self._current_mode = mode
        if self._label_mode:
            self._label_mode.setText(mode.value.upper())

    def _update_clock(self) -> None:
        """Update the clock display."""
        if self._label_time:
            self._label_time.setText(time.strftime("%H:%M"))

    def toggle_visibility(self) -> None:
        """Toggle HUD visibility."""
        if self._window:
            if self._visible:
                self._window.hide()
            else:
                self._window.show()
            self._visible = not self._visible

    def show(self) -> None:
        """Show the HUD."""
        if self._window:
            self._window.show()
            self._visible = True

    def hide(self) -> None:
        """Hide the HUD (does not close)."""
        if self._window:
            self._window.hide()
            self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def cleanup(self) -> None:
        """Cleanup and destroy the HUD window."""
        if self._window:
            self._window.close()
            self._window = None
        self._initialized = False
        log.info("HUD overlay cleaned up")
