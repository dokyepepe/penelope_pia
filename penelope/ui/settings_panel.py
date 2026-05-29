"""
Penélope — Settings Panel
A PyQt6 window for graphical configuration of Penélope's settings.
"""

import sys
import yaml
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QMessageBox, QSlider
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from penelope.utils.constants import SETTINGS_FILE
from penelope.ui.theme import THEMES, get_hud_stylesheet
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class SettingsPanel(QWidget):
    """Visual settings configuration panel for Penélope."""

    def __init__(self, theme_name: str = "holographic") -> None:
        super().__init__()
        self.theme = THEMES.get(theme_name, THEMES["holographic"])
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the settings panel layout and load current settings."""
        try:
            self.setWindowTitle("Configurações da Penélope")
            self.setFixedSize(500, 450)
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
            
            # Apply styling from theme
            self.setStyleSheet(get_hud_stylesheet(self.theme) + """
                QWidget {
                    background-color: #0A0E17;
                    color: #E8F4F8;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                QTabWidget::panel {
                    border: 1px solid #1E3A5F;
                    background-color: #0D1520;
                    border-radius: 6px;
                }
                QTabBar::tab {
                    background-color: #0A0E17;
                    color: #7B8FA3;
                    border: 1px solid #1E3A5F;
                    border-bottom-color: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected, QTabBar::tab:hover {
                    background-color: #0D1520;
                    color: #00F0FF;
                    border-bottom-color: #0D1520;
                }
                QLabel {
                    font-size: 12px;
                    background: transparent;
                }
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #1A2332;
                    border: 1px solid #1E3A5F;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #E8F4F8;
                }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 1px solid #00F0FF;
                }
                QPushButton {
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-weight: bold;
                }
            """)

            # Main layout
            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(15, 15, 15, 15)
            main_layout.setSpacing(15)

            # Title
            title = QLabel("⚙️ PAINEL DE CONFIGURAÇÕES")
            title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00F0FF; letter-spacing: 1px;")
            main_layout.addWidget(title)

            # Tab Widget
            self.tabs = QTabWidget()
            main_layout.addWidget(self.tabs)

            # Create Tabs
            self._tab_general = QWidget()
            self._tab_voice = QWidget()
            self._tab_ui = QWidget()

            self.tabs.addTab(self._tab_general, "Geral")
            self.tabs.addTab(self._tab_voice, "Voz")
            self.tabs.addTab(self._tab_ui, "Interface")

            self._setup_general_tab()
            self._setup_voice_tab()
            self._setup_ui_tab()

            # Bottom Buttons
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            self.btn_cancel = QPushButton("Cancelar")
            self.btn_cancel.setStyleSheet("background-color: #1A2332; color: #7B8FA3; border: 1px solid #1E3A5F;")
            self.btn_cancel.clicked.connect(self.close)
            btn_layout.addWidget(self.btn_cancel)

            self.btn_save = QPushButton("Salvar Alterações")
            self.btn_save.setStyleSheet("background-color: #006B73; color: #E8F4F8; border: 1px solid #00F0FF;")
            self.btn_save.clicked.connect(self.save_settings)
            btn_layout.addWidget(self.btn_save)

            main_layout.addLayout(btn_layout)

            self.load_settings()
            self._initialized = True
            return True

        except Exception as e:
            log.error(f"Failed to initialize Settings Panel: {e}", exc_info=True)
            return False

    def _setup_general_tab(self):
        layout = QVBoxLayout(self._tab_general)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Owner Name
        layout.addWidget(QLabel("Nome do Proprietário:"))
        self.edit_owner = QLineEdit()
        layout.addWidget(self.edit_owner)

        # Primary Model Host
        layout.addWidget(QLabel("Host do Ollama (LLM Local):"))
        self.edit_llm_host = QLineEdit()
        layout.addWidget(self.edit_llm_host)

        # Primary Model Name
        layout.addWidget(QLabel("Modelo de IA Principal:"))
        self.edit_llm_model = QLineEdit()
        layout.addWidget(self.edit_llm_model)

        layout.addStretch()

    def _setup_voice_tab(self):
        layout = QVBoxLayout(self._tab_voice)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Whisper Model Size
        layout.addWidget(QLabel("Modelo Whisper (Acurácia STT):"))
        self.combo_stt_model = QComboBox()
        self.combo_stt_model.addItems(["tiny", "base", "small", "medium", "large"])
        layout.addWidget(self.combo_stt_model)

        # Whisper device (auto, cpu, cuda)
        layout.addWidget(QLabel("Dispositivo de Transcrição:"))
        self.combo_stt_device = QComboBox()
        self.combo_stt_device.addItems(["auto", "cpu", "cuda"])
        layout.addWidget(self.combo_stt_device)

        # Silence Duration Slider
        layout.addWidget(QLabel("Sensibilidade de Fim de Fala (silêncio em ms):"))
        self.spin_silence = QSpinBox()
        self.spin_silence.setRange(300, 3000)
        self.spin_silence.setSingleStep(100)
        self.spin_silence.setSuffix(" ms")
        layout.addWidget(self.spin_silence)

        # Beam size (1 = fast, 5 = accurate)
        layout.addWidget(QLabel("Whisper Decodificação (Beam Size - 1 é mais veloz):"))
        self.spin_beam = QSpinBox()
        self.spin_beam.setRange(1, 5)
        layout.addWidget(self.spin_beam)

        layout.addStretch()

    def _setup_ui_tab(self):
        layout = QVBoxLayout(self._tab_ui)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # HUD Position
        layout.addWidget(QLabel("Posição do HUD:"))
        self.combo_hud_pos = QComboBox()
        self.combo_hud_pos.addItems(["bottom-right", "bottom-left", "top-right", "top-left", "center"])
        layout.addWidget(self.combo_hud_pos)

        # HUD Opacity
        layout.addWidget(QLabel("Opacidade do HUD:"))
        self.spin_hud_opacity = QDoubleSpinBox()
        self.spin_hud_opacity.setRange(0.1, 1.0)
        self.spin_hud_opacity.setSingleStep(0.05)
        layout.addWidget(self.spin_hud_opacity)

        # Radial Menu Radius
        layout.addWidget(QLabel("Raio do Menu Radial (tamanho):"))
        self.spin_radial_radius = QSpinBox()
        self.spin_radial_radius.setRange(100, 400)
        self.spin_radial_radius.setSingleStep(10)
        self.spin_radial_radius.setSuffix(" px")
        layout.addWidget(self.spin_radial_radius)

        # Theme Selector
        layout.addWidget(QLabel("Tema Visual:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["holographic", "dark_minimal", "night"])
        layout.addWidget(self.combo_theme)

        layout.addStretch()

    def load_settings(self):
        """Load YAML configuration values into UI fields."""
        try:
            if not SETTINGS_FILE.exists():
                return

            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}

            # General Tab
            self.edit_owner.setText(cfg.get("system", {}).get("owner_name", "Pietro"))
            self.edit_llm_host.setText(cfg.get("llm", {}).get("host", "http://localhost:11434"))
            self.edit_llm_model.setText(cfg.get("llm", {}).get("model_primary", "llama3.1:8b"))

            # Voice Tab
            voice = cfg.get("voice", {})
            stt_model = voice.get("stt_model", "small")
            idx = self.combo_stt_model.findText(stt_model)
            if idx >= 0:
                self.combo_stt_model.setCurrentIndex(idx)

            stt_device = voice.get("stt_device", "auto")
            idx = self.combo_stt_device.findText(stt_device)
            if idx >= 0:
                self.combo_stt_device.setCurrentIndex(idx)

            self.spin_silence.setValue(voice.get("silence_duration_ms", 800))
            self.spin_beam.setValue(voice.get("beam_size", 1))

            # UI Tab
            ui = cfg.get("ui", {})
            hud_pos = ui.get("hud_position", "bottom-right")
            idx = self.combo_hud_pos.findText(hud_pos)
            if idx >= 0:
                self.combo_hud_pos.setCurrentIndex(idx)

            self.spin_hud_opacity.setValue(ui.get("hud_opacity", 0.85))
            self.spin_radial_radius.setValue(ui.get("radial_menu_radius", 200))

            theme = ui.get("theme", "holographic")
            idx = self.combo_theme.findText(theme)
            if idx >= 0:
                self.combo_theme.setCurrentIndex(idx)

            log.info("Settings loaded into panel successfully")
        except Exception as e:
            log.error(f"Failed to load settings: {e}")

    def save_settings(self):
        """Save settings from UI fields back to YAML file."""
        try:
            if not SETTINGS_FILE.exists():
                return

            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}

            # Update dict values
            if "system" not in cfg:
                cfg["system"] = {}
            cfg["system"]["owner_name"] = self.edit_owner.text().strip()

            if "llm" not in cfg:
                cfg["llm"] = {}
            cfg["llm"]["host"] = self.edit_llm_host.text().strip()
            cfg["llm"]["model_primary"] = self.edit_llm_model.text().strip()

            if "voice" not in cfg:
                cfg["voice"] = {}
            cfg["voice"]["stt_model"] = self.combo_stt_model.currentText()
            cfg["voice"]["stt_device"] = self.combo_stt_device.currentText()
            cfg["voice"]["silence_duration_ms"] = self.spin_silence.value()
            cfg["voice"]["beam_size"] = self.spin_beam.value()

            if "ui" not in cfg:
                cfg["ui"] = {}
            cfg["ui"]["hud_position"] = self.combo_hud_pos.currentText()
            cfg["ui"]["hud_opacity"] = round(self.spin_hud_opacity.value(), 2)
            cfg["ui"]["radial_menu_radius"] = self.spin_radial_radius.value()
            cfg["ui"]["theme"] = self.combo_theme.currentText()

            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

            log.info("Settings saved to settings.yaml successfully")
            QMessageBox.information(
                self,
                "Configurações Salvas",
                "As configurações foram salvas com sucesso!\n\nAlgumas alterações (como modelo de IA e dispositivo de voz) exigem que a Penélope seja reiniciada para surtirem efeito."
            )
            self.close()

        except Exception as e:
            log.error(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar as configurações:\n{e}")

    def show_panel(self):
        """Bring the window to the front and reload values."""
        self.load_settings()
        self.show()
        self.raise_()
        self.activateWindow()
