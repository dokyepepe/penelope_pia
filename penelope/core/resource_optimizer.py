"""
Penélope — Resource Optimizer & Mode Manager
Adjusts system priorities, wake word frequencies, and detects active games to manage system load.
"""

import os
import platform
import threading
import time
from datetime import datetime
from typing import List, Optional

import psutil

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType, SystemMode
from penelope.utils.logger import get_logger

log = get_logger("optimizer")


class ResourceOptimizer:
    """
    Optimizes system resource usage based on the active operating mode.
    Manages process priority, wake word check interval, and handles game mode detection.
    """

    def __init__(self, main_module) -> None:
        self.main_module = main_module
        self.bus = get_event_bus()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._time_thread: Optional[threading.Thread] = None
        self._known_games: List[str] = [
            "gta5.exe", "valorant.exe", "cs2.exe", "rocketleague.exe", "fortnitelauncher.exe"
        ]
        self._detection_interval = 10.0
        self._manual_mode_override = False  # True when user explicitly set a mode
        self._load_config()

    def _load_config(self) -> None:
        """Load game list and check interval from settings.yaml."""
        try:
            from penelope.utils.constants import SETTINGS_FILE
            import yaml
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = yaml.safe_load(f)
                    modes_cfg = settings.get("modes", {})
                    game_mode_cfg = modes_cfg.get("game_mode", {})
                    
                    self._known_games = [
                        g.lower() for g in game_mode_cfg.get("known_games", self._known_games)
                    ]
                    self._detection_interval = float(
                        game_mode_cfg.get("detection_interval_seconds", self._detection_interval)
                    )
                    log.info(
                        f"Configuração carregada. Jogos monitorados: {len(self._known_games)}, "
                        f"Intervalo: {self._detection_interval}s"
                    )
        except Exception as e:
            log.warning(f"Falha ao carregar configurações de game_mode do settings.yaml: {e}")

    def start(self) -> None:
        """Start the background game detection and register event listeners."""
        if self._running:
            return

        self._running = True
        
        # Register for mode changed events
        self.bus.on(EventType.MODE_CHANGED, self._on_mode_changed)
        
        # Start game detection loop thread
        self._thread = threading.Thread(
            target=self._game_detection_loop,
            name="game_detection",
            daemon=True
        )
        self._thread.start()

        # Start time-based mode switching thread
        self._time_thread = threading.Thread(
            target=self._time_mode_loop,
            name="time_mode_check",
            daemon=True
        )
        self._time_thread.start()

        log.info("Otimizador de Recursos iniciado.")

    def stop(self) -> None:
        """Stop resource optimizer."""
        self._running = False
        self.bus.off(EventType.MODE_CHANGED, self._on_mode_changed)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._time_thread:
            self._time_thread.join(timeout=2.0)
            self._time_thread = None
        log.info("Otimizador de Recursos parado.")

    def _on_mode_changed(self, old_mode: str = "", new_mode: str = "", source: str = "", **kwargs) -> None:
        """React to operating mode changes by adjusting resource allocations."""
        log.info(f"Otimizador: Modo alterado de '{old_mode}' para '{new_mode}' (source={source})")

        # Track if this was a manual/voice change (not from auto-detection)
        if source in ("user", "voice", "radial", ""):
            # Game mode and auto-time are automatic, everything else is manual
            if new_mode not in (SystemMode.GAME.value, SystemMode.MORNING.value, SystemMode.NIGHT.value):
                self._manual_mode_override = True
            elif source in ("user", "voice", "radial"):
                self._manual_mode_override = True
            else:
                self._manual_mode_override = False
        
        # 1. Update wake word check interval
        # Mappings of check interval (ms) per mode
        interval_map = {
            SystemMode.NORMAL.value: 100,
            SystemMode.MORNING.value: 100,
            SystemMode.WORK.value: 100,
            SystemMode.ENTERTAINMENT.value: 100,
            SystemMode.NIGHT.value: 300,
            SystemMode.SILENT.value: 200,
            SystemMode.GAME.value: 500,
            SystemMode.POWER.value: 50,
        }
        interval = interval_map.get(new_mode, 100)
        if self.main_module._wake_word:
            try:
                self.main_module._wake_word.set_interval(interval)
            except Exception as e:
                log.error(f"Falha ao atualizar intervalo da wake word: {e}")

        # 2. Adjust HUD visual state
        if self.main_module._hud:
            try:
                if new_mode == SystemMode.GAME.value:
                    log.info("Suspendendo HUD visual para economizar recursos gráficos.")
                    self.main_module._hud.hide()
                else:
                    self.main_module._hud.show()
                    self.main_module._hud.set_mode(SystemMode(new_mode))
                    if new_mode == SystemMode.SILENT.value:
                        self.main_module._hud.set_response("[Modo Silencioso Ativo]")
            except Exception as e:
                log.error(f"Falha ao ajustar HUD visual: {e}")

        # 3. Adjust LLM Client / Memory suspension
        if self.main_module._llm_client:
            try:
                if new_mode == SystemMode.GAME.value:
                    log.info("Limpando histórico do Ollama para liberar VRAM.")
                    self.main_module._llm_client.clear_history()
            except Exception as e:
                log.error(f"Falha ao ajustar cliente LLM: {e}")

        # 4. Suspend or restore Clipboard Monitoring
        if self.main_module._command_executor and self.main_module._command_executor.clipboard_manager:
            try:
                if new_mode == SystemMode.GAME.value:
                    log.info("Desativando monitor de área de transferência durante o jogo.")
                    self.main_module._command_executor.clipboard_manager.stop()
                else:
                    self.main_module._command_executor.clipboard_manager.start()
            except Exception as e:
                log.error(f"Falha ao ajustar monitor de clipboard: {e}")

        # 5. Process CPU priority
        self._adjust_process_priority(new_mode)

    def _adjust_process_priority(self, mode: str) -> None:
        """Adjust process priority on Windows based on system mode."""
        if platform.system() != "Windows":
            return

        try:
            p = psutil.Process()
            # Priorities in psutil/Windows:
            # IDLE_PRIORITY_CLASS: 0x40
            # NORMAL_PRIORITY_CLASS: 0x20
            # HIGH_PRIORITY_CLASS: 0x80
            if mode == SystemMode.POWER.value:
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                log.info("Prioridade do processo elevada para HIGH (Potência Total)")
            elif mode == SystemMode.GAME.value:
                p.nice(psutil.IDLE_PRIORITY_CLASS)
                log.info("Prioridade do processo reduzida para IDLE (Game Mode)")
            else:
                p.nice(psutil.NORMAL_PRIORITY_CLASS)
                log.info("Prioridade do processo definida como NORMAL")
        except Exception as e:
            log.warning(f"Não foi possível ajustar a prioridade de CPU: {e}")

    def _game_detection_loop(self) -> None:
        """Periodically check running processes for game instances."""
        while self._running:
            try:
                # Iterate running processes to see if any known games are running
                detected_games = []
                for proc in psutil.process_iter(["name"]):
                    try:
                        name = proc.info["name"]
                        if name and name.lower() in self._known_games:
                            detected_games.append(name.lower())
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                is_gaming = len(detected_games) > 0
                executor = self.main_module._command_executor
                current_mode = executor.current_mode if executor else None

                if is_gaming:
                    if current_mode != SystemMode.GAME:
                        log.warning(f"Jogo detectado em execução: {detected_games}. Ativando Game Mode.")
                        if executor:
                            old = executor._current_mode
                            executor._current_mode = SystemMode.GAME
                            self.bus.emit_sync(
                                EventType.MODE_CHANGED,
                                old_mode=old.value,
                                new_mode=SystemMode.GAME.value
                            )
                else:
                    # If game was running and is now stopped, restore to normal
                    if current_mode == SystemMode.GAME:
                        log.info("Nenhum jogo em execução. Retornando ao modo Normal.")
                        if executor:
                            old = executor._current_mode
                            executor._current_mode = SystemMode.NORMAL
                            self.bus.emit_sync(
                                EventType.MODE_CHANGED,
                                old_mode=old.value,
                                new_mode=SystemMode.NORMAL.value
                            )

            except Exception as e:
                log.error(f"Erro no loop de detecção de jogos: {e}")

            time.sleep(self._detection_interval)

    def _time_mode_loop(self) -> None:
        """
        Periodically check the time to switch between Morning and Night modes.

        Morning: 06:00–10:00
        Night: 22:00–06:00
        """
        _last_auto_mode: Optional[str] = None

        while self._running:
            try:
                # Don't override if the user manually chose a mode
                if self._manual_mode_override:
                    time.sleep(60)
                    continue

                executor = self.main_module._command_executor
                if not executor:
                    time.sleep(60)
                    continue

                current_mode = executor.current_mode
                # Don't override game mode (it's managed by game detection)
                if current_mode == SystemMode.GAME:
                    time.sleep(60)
                    continue

                now = datetime.now()
                hour = now.hour

                target_mode: Optional[SystemMode] = None

                if 6 <= hour < 10:
                    target_mode = SystemMode.MORNING
                elif hour >= 22 or hour < 6:
                    target_mode = SystemMode.NIGHT
                else:
                    # Daytime: return to normal if we were in an auto mode
                    if current_mode in (SystemMode.MORNING, SystemMode.NIGHT):
                        target_mode = SystemMode.NORMAL

                if target_mode and current_mode != target_mode:
                    auto_mode_str = target_mode.value
                    if _last_auto_mode != auto_mode_str:
                        log.info(
                            f"Troca automática de modo por horário: "
                            f"{current_mode.value} → {target_mode.value} ({hour:02d}:{now.minute:02d})"
                        )
                        old = executor._current_mode
                        executor._current_mode = target_mode
                        self.bus.emit_sync(
                            EventType.MODE_CHANGED,
                            old_mode=old.value,
                            new_mode=target_mode.value,
                            source="auto_time",
                        )
                        _last_auto_mode = auto_mode_str

            except Exception as e:
                log.error(f"Erro no loop de verificação de horário: {e}")

            time.sleep(60)
