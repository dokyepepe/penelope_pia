"""
Penélope — HUD Overlay
Transparent, always-on-top holographic interface with waveform animation and glitch typewriter.
"""

import time
import math
import random
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QPainterPath

from penelope.core.event_bus import get_event_bus
from penelope.ui.theme import ThemeConfig, THEMES, get_hud_stylesheet
from penelope.utils.constants import EventType, HudState, SystemMode, UserLevel
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class HudWindow(QWidget):
    """Custom transparent QWidget that paints cyberpunk HUD elements (grid + corners)."""
    
    def __init__(self, theme: ThemeConfig, parent=None):
        super().__init__(parent)
        self.theme = theme

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        c = self.theme.colors

        # 1. Subtle high-tech background scanning grid
        grid_color = QColor(c.primary)
        grid_color.setAlpha(12)  # Highly transparent
        painter.setPen(QPen(grid_color, 1))
        
        grid_size = 30
        for x in range(0, w, grid_size):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, grid_size):
            painter.drawLine(0, y, w, y)

        # 2. Glowing cyberpunk brackets (corners)
        corner_len = 15
        pen_width = 3
        corner_color = QColor(c.primary)
        painter.setPen(QPen(corner_color, pen_width))

        # Top-Left corner
        painter.drawLine(0, 0, corner_len, 0)
        painter.drawLine(0, 0, 0, corner_len)

        # Top-Right corner
        painter.drawLine(w, 0, w - corner_len, 0)
        painter.drawLine(w, 0, w, corner_len)

        # Bottom-Left corner
        painter.drawLine(0, h, corner_len, h)
        painter.drawLine(0, h, 0, h - corner_len)

        # Bottom-Right corner
        painter.drawLine(w, h, w - corner_len, h)
        painter.drawLine(w, h, w, h - corner_len)

        # Decorative inner glowing lines
        inner_pen = QColor(c.secondary)
        inner_pen.setAlpha(50)
        painter.setPen(QPen(inner_pen, 1, Qt.PenStyle.DashLine))
        painter.drawRect(8, 8, w - 16, h - 16)

        painter.end()


class WaveformWidget(QWidget):
    """Pulsing, state-dependent animated waveform widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.state = HudState.IDLE
        self.phase = 0.0
        self.theme = THEMES["holographic"]
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)  # ~33 FPS

    def set_theme(self, theme: ThemeConfig):
        self.theme = theme
        self.update()

    def set_state(self, state: HudState):
        self.state = state
        self.update()

    def update_animation(self):
        # Speed up animation based on current state
        if self.state == HudState.LISTENING:
            self.phase += 0.25
        elif self.state == HudState.PROCESSING:
            self.phase += 0.15
        elif self.state == HudState.SPEAKING:
            self.phase += 0.20
        else:
            self.phase += 0.04  # Resting slow pulse
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cy = h / 2
        c = self.theme.colors

        # Define color and complexity per state
        if self.state == HudState.LISTENING:
            color = QColor(c.accent_green)  # Listening = Green wave
            amplitude_mult = 1.0
            num_waves = 3
        elif self.state == HudState.PROCESSING:
            color = QColor(c.secondary)     # Processing = Purple wave
            amplitude_mult = 0.4
            num_waves = 1
        elif self.state == HudState.SPEAKING:
            color = QColor(c.primary)       # Speaking = Cyan wave
            amplitude_mult = 0.8
            num_waves = 2
        elif self.state == HudState.ERROR:
            color = QColor(c.accent_red)    # Error = Red line
            amplitude_mult = 0.1
            num_waves = 1
        else:
            # Idle = Subtle cyan resting line
            color = QColor(c.primary)
            color.setAlpha(100)
            amplitude_mult = 0.15
            num_waves = 1

        for w_idx in range(num_waves):
            path_color = QColor(color)
            if num_waves > 1:
                path_color.setAlpha(int(200 / (w_idx + 1)))

            painter.setPen(QPen(path_color, 2 - w_idx * 0.5))
            path = QPainterPath()
            path.moveTo(0, cy)

            frequency = 0.02 + w_idx * 0.01
            phase_offset = w_idx * 1.5

            for x in range(0, w, 2):
                # Envelope so waves fade at edges
                envelope = math.sin(x / w * math.pi)
                noise = random.uniform(-1.5, 1.5) if self.state == HudState.LISTENING else 0.0
                
                y = cy + (h / 2.5) * envelope * amplitude_mult * math.sin(x * frequency - self.phase + phase_offset) + noise
                path.lineTo(x, y)

            painter.drawPath(path)
            
        painter.end()


class HudOverlay:
    """
    The main visual interface for Penélope.
    Transparent, borderless, always-on-top PyQt6 window with sci-fi holographic aesthetics.
    """

    def __init__(
        self,
        theme_name: str = "holographic",
        width: int = 420,
        height: int = 310,  # Adjusted to accommodate waveform comfortably
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

        # Typewriter variables
        self._typewriter_target = ""
        self._typewriter_index = 0
        self._typewriter_timer = None

        # Qt widgets
        self._label_title = None
        self._label_status = None
        self._label_response = None
        self._label_transcription = None
        self._label_user_badge = None
        self._label_mode = None
        self._label_time = None
        self._label_cpu = None
        self._label_ram = None
        self._waveform = None

        self.bus = get_event_bus()

    def initialize(self) -> bool:
        """Create and show the HUD overlay window."""
        try:
            # Create main custom HudWindow
            self._window = HudWindow(self.theme)
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
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(8)

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

            # Waveform Widget
            self._waveform = WaveformWidget(self._window)
            self._waveform.set_theme(self.theme)
            layout.addWidget(self._waveform)

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

            self._label_cpu = QLabel("CPU: --%")
            self._label_cpu.setObjectName("hud_status")
            status_bar.addWidget(self._label_cpu)

            self._label_ram = QLabel("RAM: --%")
            self._label_ram.setObjectName("hud_status")
            status_bar.addWidget(self._label_ram)

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

            # Timer for clock update (every 1s)
            self._timer = QTimer()
            self._timer.timeout.connect(self._update_clock)
            self._timer.start(1000)

            # Timer for system stats update (every 2s)
            self._stats_timer = QTimer()
            self._stats_timer.timeout.connect(self._update_system_stats)
            self._stats_timer.start(2000)

            # Timer for typewriter glitch animation
            self._typewriter_timer = QTimer()
            self._typewriter_timer.timeout.connect(self._typewriter_tick)

            # Register event handlers
            self._register_events()

            log.info("HUD overlay initialized with waveform and sci-fi window styling")
            return True

        except Exception as e:
            log.error(f"Failed to initialize HUD: {e}", exc_info=True)
            return False

    def _position_window(self) -> None:
        """Position the window based on settings."""
        if not self._window:
            return

        try:
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
        from penelope.ui.event_bridge import QtEventBridge
        self.bridge = QtEventBridge()
        self.bridge.transcription_ready.connect(self._on_transcription)
        self.bridge.llm_response_chunk.connect(self._on_response_chunk)
        self.bridge.llm_response_complete.connect(self._on_response_complete)
        self.bridge.auth_success.connect(self._on_auth_success)
        self.bridge.session_expired.connect(self._on_session_expired)
        self.bridge.mode_changed.connect(self._on_mode_changed)
        self.bridge.wake_word_detected.connect(self._on_wake_word)

    def _on_wake_word(self, **kwargs) -> None:
        """Handle wake word detection."""
        self.set_state(HudState.LISTENING)
        self.set_transcription("Escutando...")

    def _on_transcription(self, text: str = "", **kwargs) -> None:
        """Handle live transcription update."""
        self.set_transcription(text)
        self.set_state(HudState.PROCESSING)

    def _on_response_chunk(self, chunk: str = "", **kwargs) -> None:
        """Handle streaming response chunk. Keep updating it dynamically."""
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
        """Update the visual state of the HUD and the waveform."""
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
            
        if self._waveform:
            self._waveform.set_state(state)

    def set_transcription(self, text: str) -> None:
        """Update the transcription display."""
        self._transcription_text = text
        if self._label_transcription:
            display = text[:100] + "..." if len(text) > 100 else text
            self._label_transcription.setText(f'🎤 "{display}"')

    def set_response(self, text: str) -> None:
        """Update the response display with a typewriter glitch effect."""
        if not self._label_response:
            return

        # Stop previous typewriter timer if running
        if self._typewriter_timer:
            self._typewriter_timer.stop()

        self._typewriter_target = text
        self._typewriter_index = 0
        
        # Adjust typewriter speed based on response length to keep it responsive
        interval = 12 if len(text) < 100 else 6
        self._typewriter_timer.start(interval)

    def _typewriter_tick(self) -> None:
        """Animate character additions with brief random cyber-glitching."""
        if not self._label_response or not hasattr(self, "_typewriter_target"):
            if self._typewriter_timer:
                self._typewriter_timer.stop()
            return

        GLITCH_CHARS = "01$#@%&?[]{}<>/\\"
        target = self._typewriter_target
        length = len(target)

        if self._typewriter_index >= length:
            self._label_response.setText(target)
            self._typewriter_timer.stop()
            return

        # Advance by 1, 2, or 3 depending on length
        step = 1 if length < 80 else (2 if length < 250 else 3)
        self._typewriter_index += step

        if self._typewriter_index >= length:
            self._label_response.setText(target)
            self._typewriter_timer.stop()
        else:
            revealed = target[:self._typewriter_index]
            glitch = "".join(random.choice(GLITCH_CHARS) for _ in range(min(2, length - self._typewriter_index)))
            self._label_response.setText(revealed + glitch)

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

    def _update_system_stats(self) -> None:
        """Update CPU and RAM usage on the HUD."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            if self._label_cpu:
                self._label_cpu.setText(f"CPU: {cpu:.0f}%")
            if self._label_ram:
                self._label_ram.setText(f"RAM: {ram:.0f}%")
        except Exception:
            pass

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
        if self._typewriter_timer:
            self._typewriter_timer.stop()
        if self._window:
            self._window.close()
            self._window = None
        self._initialized = False
        log.info("HUD overlay cleaned up")
