"""
Penélope — Main Entry Point
Core orchestrator that initializes all modules and runs the main loop.

Usage:
    python -m penelope.main
    penelope  (if installed via pip)
"""

import asyncio
import signal
import sys
import threading
import time
from typing import Optional

# Reconfigure standard streams to UTF-8 on Windows to prevent encoding mismatches
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="ignore")
        sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
    except Exception:
        pass

from penelope.utils.constants import UserLevel, SystemMode
from penelope.utils.logger import setup_logging, get_logger

# Initialize logging first
setup_logging(debug="--debug" in sys.argv)
log = get_logger(__name__)


# ============================================
# Module references (initialized in init_*)
# ============================================
_llm_client = None
_audio_manager = None
_wake_word = None
_stt = None
_tts = None
_authenticator = None
_session_manager = None
_intent_parser = None
_command_executor = None
_watchdog = None
_health_monitor = None
_windows_control = None
_memory_manager = None
_shutdown_event = threading.Event()

# UI references
_app = None
_hud = None
_tray = None
_radial_menu = None
_settings_panel = None
_asyncio_loop = None
_asyncio_thread = None
_resource_optimizer = None


def main() -> None:
    """Main entry point for the Penélope system."""
    try:
        from penelope.utils.ascii_art import play_boot_animation
        play_boot_animation()
    except Exception as e:
        log.warning(f"Could not play boot animation: {e}")

    log.info("<magenta>═══════════════════════════════════════════</magenta>")
    log.info("  <cyan>PENÉLOPE v4.0</cyan> — <green>Inicializando...</green>")
    log.info("<magenta>═══════════════════════════════════════════</magenta>")

    # ── 1. Create data directories ──
    from penelope.core.setup_wizard import ensure_directories
    ensure_directories()

    # ── 2. Check first boot ──
    from penelope.core.setup_wizard import needs_setup, run_setup_wizard
    if needs_setup():
        log.info("First boot detected — running setup wizard")
        if not run_setup_wizard():
            log.error("Setup wizard failed or cancelled")
            sys.exit(1)

    # ── 3. Initialize QApplication first (required by Qt) ──
    from PyQt6.QtWidgets import QApplication
    global _app
    _app = QApplication(sys.argv)
    _app.setQuitOnLastWindowClosed(False)

    # ── 4. Initialize all modules ──
    _init_all()

    # ── 5. Initialize UI Components ──
    _init_ui()

    # ── 6. Register signal handlers ──
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # ── 7. Run background asyncio loop ──
    log.info("<magenta>═══════════════════════════════════════════</magenta>")
    log.info("  <cyan>PENÉLOPE ONLINE</cyan> — <green>Aguardando wake word...</green>")
    log.info("  (ou <bold>Alt+Space</bold> como atalho)")
    log.info("<magenta>═══════════════════════════════════════════</magenta>")

    global _asyncio_loop, _asyncio_thread
    _asyncio_loop = asyncio.new_event_loop()

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_main_loop())
        except Exception as e:
            log.error(f"Asyncio main loop crash: {e}", exc_info=True)

    _asyncio_thread = threading.Thread(
        target=run_asyncio_loop,
        args=(_asyncio_loop,),
        name="penelope_async_core",
        daemon=True
    )
    _asyncio_thread.start()

    # ── 8. Start PyQt6 Event Loop on Main Thread ──
    try:
        sys.exit(_app.exec())
    except KeyboardInterrupt:
        log.info("Interrupted by keyboard")
    finally:
        _shutdown()


def _init_all() -> None:
    """Initialize all system modules in the correct order."""
    global _llm_client, _audio_manager, _wake_word, _stt, _tts
    global _authenticator, _session_manager, _intent_parser
    global _command_executor, _watchdog, _health_monitor, _windows_control
    global _memory_manager

    # ── Memory Manager ──
    log.info("Inicializando gerenciador de memória...")
    from penelope.ai.memory import MemoryManager
    _memory_manager = MemoryManager()

    # ── LLM Client ──
    log.info("Inicializando LLM Client...")
    from penelope.ai.llm_client import LLMClient
    _llm_client = LLMClient()
    _connect_llm_sync()

    # ── Voice Pipeline ──
    log.info("Inicializando pipeline de voz...")

    from penelope.voice.audio_manager import AudioManager
    _audio_manager = AudioManager(sample_rate=16000, channels=1, chunk_size=1024)

    # Load voice settings
    stt_model = "tiny"
    stt_language = "pt"
    stt_device = "auto"
    silence_duration_ms = 1500
    beam_size = 1
    try:
        from penelope.utils.constants import SETTINGS_FILE
        import yaml
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
                voice_cfg = settings.get("voice", {})
                stt_model = voice_cfg.get("stt_model", "tiny")
                stt_language = voice_cfg.get("stt_language", "pt")
                stt_device = voice_cfg.get("stt_device", "auto")
                silence_duration_ms = voice_cfg.get("silence_duration_ms", 1500)
                beam_size = voice_cfg.get("beam_size", 1)
    except Exception as e:
        log.warning(f"Falha ao carregar stt_model de settings.yaml: {e}")

    from penelope.voice.stt import SpeechToText
    _stt = SpeechToText(
        model_size=stt_model,
        language=stt_language,
        device=stt_device,
        silence_duration_ms=silence_duration_ms,
        beam_size=beam_size
    )
    if not _stt.load_model():
        log.warning("Whisper STT não carregado — transcrição desabilitada")

    from penelope.voice.tts import TextToSpeech
    _tts = TextToSpeech()
    if not _tts.initialize():
        log.warning("TTS não disponível — respostas apenas em texto")

    from penelope.voice.wake_word import WakeWordDetector
    _wake_word = WakeWordDetector(threshold=0.7, check_interval_ms=100)
    _wake_word.initialize()

    # ── Auth ──
    log.info("Inicializando autenticação...")
    from penelope.auth.authenticator import Authenticator
    from penelope.auth.session import SessionManager
    _authenticator = Authenticator()
    _session_manager = SessionManager()

    # ── Intent Parser + Executor ──
    log.info("Inicializando processamento de comandos...")
    from penelope.ai.intent_parser import IntentParser
    _intent_parser = IntentParser()

    from penelope.system.windows_control import WindowsControl
    _windows_control = WindowsControl()

    from penelope.core.command_executor import CommandExecutor
    _command_executor = CommandExecutor(
        windows_control=_windows_control,
        llm_client=_llm_client,
        audio_manager=_audio_manager,
        memory_manager=_memory_manager,
    )

    # Wire up input callback for interactive flows (user management)
    _command_executor.set_input_callback(_listen_and_transcribe)

    # ── Persistence ──
    log.info("Inicializando watchdog e monitor de saúde...")
    from penelope.persistence.watchdog import ProcessWatchdog
    _watchdog = ProcessWatchdog(check_interval=5.0)
    _watchdog.start()

    from penelope.persistence.health_monitor import HealthMonitor
    _health_monitor = HealthMonitor(check_interval=30.0)
    _health_monitor.start()

    # ── Resource Optimizer ──
    global _resource_optimizer
    from penelope.core.resource_optimizer import ResourceOptimizer
    _resource_optimizer = ResourceOptimizer(sys.modules[__name__])
    _resource_optimizer.start()

    log.info("✓ Todos os módulos inicializados")


def _init_ui() -> None:
    """Initialize PyQt6 user interface components."""
    global _hud, _tray, _radial_menu
    log.info("Inicializando interface gráfica (PyQt6)...")

    # Register HUD_UPDATE listener on EventBus
    from penelope.utils.constants import EventType
    from penelope.core.event_bus import get_event_bus
    bus = get_event_bus()
    bus.on(EventType.HUD_UPDATE, _on_hud_update)

    # 1. Tray Icon
    from penelope.ui.tray_icon import TrayIcon
    _tray = TrayIcon()
    _tray.initialize()

    # 2. HUD Overlay
    from penelope.ui.hud_overlay import HudOverlay
    _hud = HudOverlay()
    _hud.initialize()

    # 3. Radial Menu
    from penelope.ui.radial_menu import RadialMenu
    _radial_menu = RadialMenu()
    _radial_menu.initialize()

    # 4. Settings Panel
    from penelope.ui.settings_panel import SettingsPanel
    global _settings_panel
    _settings_panel = SettingsPanel()
    _settings_panel.initialize()

    # Connect radial menu triggers
    def handle_radial_action(slice_data: dict) -> None:
        action = slice_data.get("action")
        target = slice_data.get("target")
        if _command_executor and _session_manager:
            session = _session_manager.current
            if not session:
                # Create a temporary guest session with OWNER level so all actions from radial menu succeed
                from penelope.auth.profiles import UserProfile
                from penelope.auth.permissions import get_default_permissions
                from penelope.auth.session import Session
                
                # Mock profile
                mock_profile = UserProfile(
                    id=999,
                    name="Convidado",
                    level=UserLevel.OWNER,
                    permissions=get_default_permissions(UserLevel.OWNER),
                    session_timeout_minutes=0
                )
                session = Session(
                    profile=mock_profile,
                    user_name="Convidado",
                    user_level=UserLevel.OWNER,
                    permissions=get_default_permissions(UserLevel.OWNER),
                    timeout_minutes=0
                )

            from penelope.ai.intent_parser import ParsedIntent
            from penelope.utils.constants import IntentCategory
            
            category = IntentCategory.SYSTEM_COMMAND
            if action == "clipboard_history":
                category = IntentCategory.INFORMATION
            elif action == "lock_session":
                category = IntentCategory.SESSION_CONTROL
            elif action == "open_settings":
                category = IntentCategory.CONFIGURATION
            
            intent = ParsedIntent(
                raw_text=slice_data.get("label", ""),
                category=category,
                action=action,
                entities={"app_name": target} if target else {},
                confidence=1.0,
                requires_llm=False
            )
            
            if _asyncio_loop:
                asyncio.run_coroutine_threadsafe(
                    _execute_radial_intent(intent, session),
                    _asyncio_loop
                )

    _radial_menu.set_action_handler(handle_radial_action)


async def _execute_radial_intent(intent, session) -> None:
    """Execute radial menu actions on the background thread."""
    response = await _command_executor.execute(intent, session)
    if _tts and _tts.is_available:
        await _tts.speak(response)
    else:
        log.info(f"Radial Action Executed: {response}")


def _on_hud_update(action: str = "", **kwargs) -> None:
    """Handle HUD updates and system trays events from main thread."""
    log.info(f"HUD Update Event: {action}")
    if action == "toggle_hud":
        if _hud:
            _hud.toggle_visibility()
    elif action == "open_settings":
        if _settings_panel:
            _settings_panel.show_panel()
    elif action == "show_status":
        if _hud:
            _hud.show()
            if _health_monitor:
                snapshot = _health_monitor.get_snapshot()
                if snapshot:
                    summary = (
                        f"Status do Sistema:\n"
                        f"CPU: {snapshot.cpu_percent:.1f}%\n"
                        f"RAM: {snapshot.ram_percent:.1f}%\n"
                        f"Disco: {snapshot.disk_used_gb:.1f}/{snapshot.disk_total_gb:.1f} GB"
                    )
                else:
                    summary = "Status do Sistema: Coletando informações..."
                _hud.set_response(summary)
    elif action == "request_quit_auth":
        log.info("Quit requested via tray menu")
        if _app:
            _app.quit()


def _connect_llm_sync() -> None:
    """Connect to Ollama synchronously."""
    try:
        loop = asyncio.new_event_loop()
        connected = loop.run_until_complete(_llm_client.connect())
        loop.close()
        if connected:
            log.info(f"✓ LLM conectado: {_llm_client.model}")
        else:
            log.warning("⚠ Ollama offline — modo degradado (regras simples)")
    except Exception as e:
        log.warning(f"⚠ Não foi possível conectar ao Ollama: {e}")


async def _main_loop() -> None:
    """
    Main interaction loop.

    Flow:
    1. Wait for wake word (or Alt+Space) [Only if audio is available]
    2. Authenticate user
    3. Listen for command
    4. Parse intent
    5. Execute command
    6. Speak response
    7. Check session timeout
    8. Repeat
    """
    # Check if audio/mic recording is available
    audio_available = False
    try:
        import sounddevice as sd
        import numpy as np
        audio_available = True
    except ImportError:
        log.warning("Sistema de áudio indisponível (sounddevice/numpy ausentes) — rodando em modo texto puro.")

    # Start audio recording for wake word if audio is available
    if audio_available:
        _audio_manager.register_callback(_wake_word.on_audio_chunk)
        _audio_manager.start_recording()
        _wake_word.start()

    # Wake word event trigger
    wake_event = asyncio.Event()

    if audio_available:
        def on_wake():
            """Called from the wake word thread when triggered."""
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(wake_event.set)
            except RuntimeError:
                wake_event.set()

        _wake_word.on_wake(on_wake)
        log.info("Loop principal ativo — escutando wake word...")
    else:
        # If no audio but Win32 hotkey fallback was registered, we can still listen for it
        if _wake_word.is_fallback:
            def on_wake_hotkey():
                try:
                    loop = asyncio.get_running_loop()
                    loop.call_soon_threadsafe(wake_event.set)
                except RuntimeError:
                    wake_event.set()
            _wake_word.on_wake(on_wake_hotkey)
        log.info("Loop principal ativo em modo TEXTO — digite seus comandos.")

    while not _shutdown_event.is_set():
        try:
            if audio_available:
                # ── 1. Wait for wake word ──
                wake_event.clear()

                # Use a timeout so we can check shutdown and session timeout
                try:
                    await asyncio.wait_for(
                        _wait_for_event(wake_event),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    # Periodic housekeeping
                    await _session_manager.check_timeout()
                    continue

                if _shutdown_event.is_set():
                    break

                log.info("🎤 Wake word detectado!")
            else:
                # In text mode, we check timeout and let stdin block
                await _session_manager.check_timeout()
                await asyncio.sleep(0.05)

            # ── 2. Authenticate ──
            session = _session_manager.current

            if session is None or not _session_manager.is_active:
                session = await _authenticate_user(audio_available)
                if session is None:
                    if not audio_available:
                        await asyncio.sleep(1.0)
                    continue  # Auth failed

            # ── 3. Listen for command ──
            if audio_available:
                log.info(f"Escutando comando de {session.user_name}...")
                if _tts and _tts.is_available:
                    greeting = _llm_client.get_greeting(
                        session.user_name, session.user_level
                    ) if _llm_client else f"Olá, {session.user_name}."
                    # Only greet on new session (first command)
                    if session.elapsed_minutes < 0.1:
                        await _tts.speak(greeting)

            transcription = await _listen_and_transcribe(prompt="digite o comando")
            if not transcription:
                log.debug("Transcrição vazia — voltando a escutar")
                if not audio_available:
                    await asyncio.sleep(1.0)
                continue

            log.info(f"📝 Transcrito: '{transcription}'")

            # ── Track in memory ──
            if _memory_manager:
                _memory_manager.add_message("user", transcription)

            # ── 4. Parse intent ──
            intent = _intent_parser.parse(transcription)
            log.info(
                f"🧠 Intent: {intent.action} "
                f"({intent.category.value}, llm={intent.requires_llm})"
            )

            # Set persona for LLM if needed
            if intent.requires_llm and _llm_client:
                _llm_client.set_persona(
                    session.user_name,
                    session.user_level,
                    _command_executor.current_mode,
                )

            # ── 5. Execute ──
            response = await _command_executor.execute(intent, session)
            log.info(f"💬 Resposta: '{response[:80]}...'")

            # ── Track response in memory ──
            if _memory_manager:
                _memory_manager.add_message("assistant", response)

            # ── 6. Speak ──
            if _tts and _tts.is_available:
                if _command_executor.current_mode != SystemMode.SILENT:
                    await _tts.speak(response)
                else:
                    log.info(f"[SILENT MODE] {response}")
            else:
                print(f"  PENÉLOPE: {response}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"Erro no loop principal: {e}", exc_info=True)
            await asyncio.sleep(1.0)


async def _wait_for_event(event: asyncio.Event) -> None:
    """Wait for an asyncio event to be set."""
    await event.wait()


async def _authenticate_user(audio_available: bool = True):
    """
    Run the authentication flow.

    Asks for passphrase, transcribes it, and authenticates.

    Returns:
        Session object if successful, None if denied.
    """
    if _tts and _tts.is_available:
        await _tts.speak("Olá! Por favor, diga sua chave de acesso.")
    else:
        print("  PENÉLOPE: Olá! Por favor, digite sua chave de acesso.")

    # Record passphrase
    passphrase = await _listen_and_transcribe(max_duration=8.0, prompt="digite sua chave de acesso")
    if not passphrase:
        if _tts and _tts.is_available:
            await _tts.speak("Não entendi. Tente novamente.")
        return None

    log.info(f"Tentativa de autenticação: '{passphrase[:20]}...'")

    # Authenticate
    profile = await _authenticator.authenticate(passphrase)

    if profile is None:
        # Check if locked out
        if _authenticator.profiles.is_locked_out():
            msg = "Muitas tentativas incorretas. Acesso bloqueado temporariamente."
        else:
            msg = "Chave não reconhecida. Acesso negado."

        if _tts and _tts.is_available:
            await _tts.speak(msg)
        else:
            print(f"  PENÉLOPE: {msg}")
        return None

    # Create session
    session = await _session_manager.start_session(profile)

    log.info(
        f"✓ Sessão iniciada: {profile.name} "
        f"(Nível {profile.level.name})"
    )

    return session


async def _listen_and_transcribe(max_duration: float = 10.0, prompt: str = "digite o comando") -> str:
    """
    Record audio and transcribe it.

    Args:
        max_duration: Maximum recording time in seconds.
        prompt: Prompt string used in fallback text mode.

    Returns:
        Transcribed text, or empty string on failure.
    """
    if not _stt or not _stt.is_loaded:
        # Fallback: read from stdin
        print(f"  [Texto — {prompt}]: ", end="", flush=True)
        try:
            loop = asyncio.get_running_loop()
            text = await loop.run_in_executor(None, _read_input_line)
            return text
        except Exception:
            return ""

    # Record a chunk of audio
    audio = _audio_manager.record_chunk(duration_seconds=max_duration)
    if audio is None:
        return ""

    # Transcribe
    text, confidence = _stt.transcribe(audio, sample_rate=16000)
    if confidence < 0.3:
        log.debug(f"Low confidence transcription ({confidence:.2f}): '{text}'")
        return ""

    return text.strip()


def _read_input_line() -> str:
    """Read a line from stdin (blocking, for use in executor)."""
    try:
        return input().strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _signal_handler(signum, frame) -> None:
    """Handle shutdown signals gracefully."""
    log.info(f"Signal {signum} received — initiating shutdown")
    _shutdown_event.set()


def _shutdown() -> None:
    """Shut down all modules gracefully."""
    log.info("Encerrando Penélope...")

    # Save current session to memory before shutdown
    if _memory_manager and _session_manager and _session_manager.current:
        try:
            session = _session_manager.current
            conversation = _memory_manager.get_conversation()
            if conversation:
                _memory_manager.save_session(
                    profile_id=session.profile.id,
                    profile_name=session.user_name,
                    messages=conversation,
                    summary=f"Sessão encerrada por shutdown ({len(conversation)} mensagens)",
                )
                log.info(f"Sessão salva para {session.user_name} ({len(conversation)} msgs)")
            _memory_manager.clear_conversation()
        except Exception as e:
            log.warning(f"Falha ao salvar sessão no shutdown: {e}")

    # Clean up UI components and optimizer
    global _hud, _tray, _radial_menu, _resource_optimizer
    if _resource_optimizer:
        try:
            _resource_optimizer.stop()
        except Exception:
            pass
    if _hud:
        try:
            _hud.cleanup()
        except Exception:
            pass
    if _tray:
        try:
            _tray.cleanup()
        except Exception:
            pass
    if _radial_menu:
        try:
            _radial_menu.cleanup()
        except Exception:
            pass
    if _settings_panel:
        try:
            _settings_panel.close()
            _settings_panel = None
        except Exception:
            pass

    # Stop clipboard manager
    if _command_executor and hasattr(_command_executor, "clipboard_manager") and _command_executor.clipboard_manager:
        try:
            _command_executor.clipboard_manager.stop()
        except Exception:
            pass

    # Stop in reverse order of initialization
    if _health_monitor:
        _health_monitor.stop()

    if _watchdog:
        _watchdog.stop()

    if _wake_word:
        _wake_word.cleanup()

    if _audio_manager:
        _audio_manager.cleanup()

    if _stt:
        _stt.unload()

    if _llm_client:
        _llm_client.clear_history()

    log.info("═══════════════════════════════════════════")
    log.info("  PENÉLOPE OFFLINE — Até mais.")
    log.info("═══════════════════════════════════════════")


if __name__ == "__main__":
    main()
