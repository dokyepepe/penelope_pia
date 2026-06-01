"""
Penélope — Command Executor
Bridges parsed intents to real system actions with permission checks.
"""

import asyncio
import time
from typing import Any, Callable, Dict, Optional

from penelope.ai.intent_parser import ParsedIntent
from penelope.ai.llm_client import LLMClient
from penelope.ai.memory import MemoryManager
from penelope.auth.session import Session
from penelope.core.event_bus import get_event_bus
from penelope.system.windows_control import WindowsControl
from penelope.utils.constants import EventType, IntentCategory, SystemMode, UserLevel
from penelope.utils.logger import get_logger

log = get_logger(__name__)


# Permission mapping: action → required permission string
ACTION_PERMISSIONS: Dict[str, str] = {
    "open_app": "open_app",
    "close_app": "close_app",
    "volume_up": "volume_control",
    "volume_down": "volume_control",
    "volume_mute": "volume_control",
    "screenshot": "screenshot",
    "shutdown": "shutdown",
    "restart": "restart",
    "empty_recycle": "empty_recycle_bin",
    "airplane_mode": "airplane_mode",
    "open_task_manager": "task_manager",
    "get_ip": "network_info",
    "get_time": "system_info",
    "get_date": "system_info",
    "get_battery": "system_info",
    "list_commands": "conversation",
    "lock_session": "lock_session",
    "organize_windows": "window_management",
    "close_all_except": "window_management",
    "meeting_mode": "window_management",
    "presentation_mode": "window_management",
    "clipboard_history": "clipboard_history",
    # Mode changes
    "mode_work": "change_mode",
    "mode_silent": "change_mode",
    "mode_night": "change_mode",
    "mode_entertainment": "change_mode",
    "mode_game": "change_mode",
    "mode_power": "change_mode",
    "mode_normal": "change_mode",
    # User management
    "add_co_owner": "manage_users",
    "add_common_user": "manage_users",
    "list_users": "manage_users",
    "deactivate_user": "manage_users",
    "check_permissions": "manage_users",
    "chat": "conversation",
    "sleep_routine": "automation",
    "meeting_routine": "automation",
    "open_settings": "change_settings",
    "spotify_playpause": "open_app",
    "spotify_next": "open_app",
    "spotify_prev": "open_app",
    "whatsapp_send": "open_app",
    "browser_search": "open_app",
    "browser_new_tab": "open_app",
    "browser_close_tab": "open_app",
}


class CommandExecutor:
    """
    Executes parsed intents by dispatching to the appropriate subsystem.

    Handles permission checks, action routing, and response generation.
    Works with WindowsControl for system commands and LLMClient for
    conversational/complex queries.
    """

    def __init__(
        self,
        windows_control: Optional[WindowsControl] = None,
        llm_client: Optional[LLMClient] = None,
        audio_manager: Optional[Any] = None,
        window_manager: Optional[Any] = None,
        clipboard_manager: Optional[Any] = None,
        memory_manager: Optional[MemoryManager] = None,
    ) -> None:
        self.windows = windows_control or WindowsControl()
        self.llm = llm_client
        self.audio = audio_manager
        self.memory = memory_manager
        
        # Instantiate window and clipboard managers natively
        from penelope.system.window_manager import WindowManager
        from penelope.system.clipboard_manager import ClipboardManager
        self.window_manager = window_manager or WindowManager()
        self.clipboard_manager = clipboard_manager or ClipboardManager()
        
        # Start monitoring clipboard history in background
        self.clipboard_manager.start()
        
        self.bus = get_event_bus()
        self._current_mode = SystemMode.NORMAL

        # Callback for requesting text input from the user (set by main.py)
        self._input_callback: Optional[Callable] = None

    def set_input_callback(self, callback: Callable) -> None:
        """Set the callback used to request text/voice input from the user."""
        self._input_callback = callback

    async def execute(
        self,
        intent: ParsedIntent,
        session: Session,
    ) -> str:
        """
        Execute a parsed intent within the context of a session.

        Checks permissions, dispatches to the right handler,
        and returns a text response for TTS.

        Args:
            intent: The parsed intent from IntentParser.
            session: The active user session.

        Returns:
            Response text to speak back to the user.
        """
        session.touch()

        await self.bus.emit(
            EventType.COMMAND_RECEIVED,
            action=intent.action,
            category=intent.category.value,
            user_name=session.user_name,
        )

        # --- Intercept custom easter egg commands ---
        raw = intent.raw_text.strip().lower()
        if any(trigger in raw for trigger in ["mostre sua forma", "mostre seu avatar", "mostre sua cara", "mostrar avatar", "mostrar holograma"]):
            try:
                from penelope.utils.ascii_art import show_hologram_command
                show_hologram_command()
                return f"Holograma do meu núcleo ativo exibido no terminal principal. Como posso ajudar, {session.user_name}?"
            except Exception as e:
                log.error(f"Failed to show avatar: {e}")
                return "Não consegui carregar a matriz do holograma."

        if any(trigger in raw for trigger in ["autodiagnóstico", "diagnóstico completo", "diagnostico completo", "fazer diagnostico"]):
            try:
                from penelope.utils.ascii_art import run_full_diagnostics
                run_full_diagnostics()
                return "Diagnóstico concluído com sucesso. Todos os subsistemas estão operando com 100% de integridade."
            except Exception as e:
                log.error(f"Failed to run diagnostics: {e}")
                return "Houve uma falha ao rodar os protocolos de diagnóstico."

        # --- Permission check ---
        required_perm = ACTION_PERMISSIONS.get(intent.action)
        if required_perm and not session.has_permission(required_perm):
            log.warning(
                f"Permission denied: {intent.action} for {session.user_name}"
            )
            return "Você não tem permissão para essa ação."

        # --- Route to LLM if needed ---
        if intent.requires_llm:
            return await self._handle_chat(intent.raw_text)

        # --- Dispatch by action ---
        await self.bus.emit(
            EventType.COMMAND_EXECUTING,
            action=intent.action,
        )

        try:
            response = await self._dispatch(intent)

            await self.bus.emit(
                EventType.COMMAND_COMPLETED,
                action=intent.action,
                response=response,
            )
            return response

        except Exception as e:
            log.error(f"Command execution failed: {intent.action} — {e}")
            await self.bus.emit(
                EventType.COMMAND_FAILED,
                action=intent.action,
                error=str(e),
            )
            return f"Desculpe, ocorreu um erro ao executar esse comando."

    async def _dispatch(self, intent: ParsedIntent) -> str:
        """Dispatch an intent to the correct handler."""
        action = intent.action
        entities = intent.entities

        # ── System Commands ──
        if action == "open_app":
            result = self.windows.open_app(entities.get("app_name", ""))
            return result.get("message", "Pronto.")

        if action == "close_app":
            result = self.windows.close_app(entities.get("app_name", ""))
            return result.get("message", "Pronto.")

        if action == "volume_up":
            if self.audio:
                level = self.audio.change_volume(0.1)
                return f"Volume em {level:.0%}."
            return "Controle de volume não disponível."

        if action == "volume_down":
            if self.audio:
                level = self.audio.change_volume(-0.1)
                return f"Volume em {level:.0%}."
            return "Controle de volume não disponível."

        if action == "volume_mute":
            if self.audio:
                self.audio.set_system_volume(0.0)
                return "Áudio silenciado."
            return "Controle de volume não disponível."

        if action == "screenshot":
            result = self.windows.take_screenshot()
            return result.get("message", "Pronto.")

        if action == "shutdown":
            result = self.windows.shutdown(delay_seconds=30)
            return result.get("message", "Pronto.")

        if action == "restart":
            result = self.windows.restart(delay_seconds=30)
            return result.get("message", "Pronto.")

        if action == "empty_recycle":
            result = self.windows.empty_recycle_bin()
            return result.get("message", "Pronto.")

        if action == "airplane_mode":
            result = self.windows.toggle_airplane_mode()
            return result.get("message", "Pronto.")

        if action == "open_task_manager":
            result = self.windows.open_app("task manager")
            return result.get("message", "Pronto.")

        if action == "lock_session":
            result = self.windows.lock_screen()
            return result.get("message", "Pronto.")

        # ── Information ──
        if action == "get_ip":
            result = self.windows.get_ip_address()
            return result.get("message", "Não consegui verificar.")

        if action == "get_time":
            result = self.windows.get_current_time()
            return result.get("message", "Não sei que horas são.")

        if action == "get_date":
            import datetime
            d = datetime.datetime.now()
            semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            weekday = semana[d.weekday()]
            month = meses[d.month - 1]
            return f"Hoje é {weekday}, dia {d.day} de {month} de {d.year}."

        if action == "get_battery":
            try:
                import psutil
                battery = psutil.sensors_battery()
                if battery:
                    percent = battery.percent
                    plugged = battery.power_plugged
                    plugged_str = "conectada à tomada" if plugged else "desconectada da tomada"
                    return f"A bateria está em {percent}% e está atualmente {plugged_str}."
                else:
                    return "Não consegui detectar uma bateria neste computador. Ele pode ser um desktop."
            except Exception:
                try:
                    import subprocess
                    result = subprocess.run(
                        ["wmic", "path", "Win32_Battery", "get", "EstimatedChargeRemaining"],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                    if len(lines) > 1 and lines[1].isdigit():
                        return f"O nível da bateria é {lines[1]}%."
                except Exception:
                    pass
                return "Não foi possível obter o status da bateria."

        if action == "list_commands":
            return (
                "Estes são alguns dos comandos locais que posso executar: "
                "abrir ou fechar aplicativos, ajustar e silenciar o volume, "
                "tirar capturas de tela (screenshot), bloquear a sessão do computador, "
                "esvaziar a lixeira, informar as horas ou a data de hoje, "
                "verificar o status da bateria e o seu endereço IP, "
                "e alternar entre os modos de operação como Trabalho, Silencioso e Noite."
            )

        if action == "clipboard_history":
            try:
                history = self.clipboard_manager.get_history(limit=3)
                if not history:
                    return "Seu histórico da área de transferência está vazio."
                items = []
                for idx, entry in enumerate(history, 1):
                    content = entry.get("content", "").strip()
                    if len(content) > 60:
                        content = content[:57] + "..."
                    items.append(f"{idx}: \"{content}\"")
                return "Últimos itens copiados: " + "; ".join(items)
            except Exception as e:
                log.error(f"Failed to get clipboard history: {e}")
                return "Não consegui ler o histórico da área de transferência."

        if action == "open_settings":
            await self.bus.emit(EventType.HUD_UPDATE, action="open_settings")
            return "Abrindo painel de configurações."

        # ── Spotify Controls ──
        if action == "spotify_playpause":
            result = self.windows.media_play_pause()
            return result.get("message", "Mídia controlada.")

        if action == "spotify_next":
            result = self.windows.media_next()
            return result.get("message", "Passei a música.")

        if action == "spotify_prev":
            result = self.windows.media_prev()
            return result.get("message", "Voltei a música.")

        # ── Browser Controls ──
        if action == "browser_search":
            query = entities.get("search_query", "")
            result = self.windows.browser_search(query)
            return result.get("message", "Pesquisando.")

        if action == "browser_new_tab":
            result = self.windows.browser_new_tab()
            return result.get("message", "Nova aba.")

        if action == "browser_close_tab":
            result = self.windows.browser_close_tab()
            return result.get("message", "Aba fechada.")

        # ── WhatsApp Controls ──
        if action == "whatsapp_send":
            contact = entities.get("contact_name", "")
            msg_text = entities.get("message_text", "")
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self.windows.whatsapp_send, contact, msg_text)
            return result.get("message", "Mensagem enviada.")

        # ── Mode Changes ──
        if action.startswith("mode_"):
            return await self._handle_mode_change(action)

        # ── User Management ──
        if intent.category == IntentCategory.USER_MANAGEMENT:
            return await self._handle_user_management(intent)

        # ── Window Management ──
        if action == "organize_windows":
            result = self.window_manager.organize_windows()
            return result.get("message", "Pronto.")

        if action == "close_all_except":
            app = entities.get("app_name", "")
            result = self.window_manager.close_all_except(app)
            return result.get("message", "Pronto.")

        if action == "meeting_mode":
            result = self.window_manager.enter_meeting_mode()
            return result.get("message", "Pronto.")

        if action == "presentation_mode":
            result = self.window_manager.enter_presentation_mode()
            return result.get("message", "Pronto.")

        # ── Automation / Routines ──
        if action == "sleep_routine":
            return await self._handle_chat(
                "O usuário quer ir dormir. Sugira salvar documentos e encerrar."
            )

        if action == "meeting_routine":
            return await self._handle_chat(
                "O usuário tem uma reunião agora. Sugira abrir o app de reunião."
            )

        # ── Fallback to chat ──
        return await self._handle_chat(intent.raw_text)

    async def _handle_chat(self, text: str) -> str:
        """Send text to the LLM for a conversational response."""
        if self.llm is None or not self.llm.is_connected:
            # Use fallback rules
            if self.llm:
                return self.llm._fallback_response(text)
            return (
                "Desculpe, estou em modo limitado. "
                "O modelo de linguagem está offline."
            )

        await self.bus.emit(EventType.LLM_RESPONSE_STARTED, text=text)

        response = await self.llm.chat(text)

        await self.bus.emit(
            EventType.LLM_RESPONSE_COMPLETE,
            response=response,
        )
        return response

    async def _handle_mode_change(self, action: str) -> str:
        """Handle operating mode changes."""
        mode_map = {
            "mode_work": SystemMode.WORK,
            "mode_silent": SystemMode.SILENT,
            "mode_night": SystemMode.NIGHT,
            "mode_entertainment": SystemMode.ENTERTAINMENT,
            "mode_game": SystemMode.GAME,
            "mode_power": SystemMode.POWER,
            "mode_normal": SystemMode.NORMAL,
        }

        mode_names = {
            SystemMode.WORK: "Trabalho",
            SystemMode.SILENT: "Silencioso",
            SystemMode.NIGHT: "Noite",
            SystemMode.ENTERTAINMENT: "Entretenimento",
            SystemMode.GAME: "Jogos",
            SystemMode.POWER: "Potência Total",
            SystemMode.NORMAL: "Normal",
        }

        new_mode = mode_map.get(action, SystemMode.NORMAL)
        old_mode = self._current_mode
        self._current_mode = new_mode

        await self.bus.emit(
            EventType.MODE_CHANGED,
            old_mode=old_mode.value,
            new_mode=new_mode.value,
            source="user",
        )

        name = mode_names.get(new_mode, new_mode.value)
        log.info(f"Mode changed: {old_mode.value} → {new_mode.value}")
        return f"Modo {name} ativado."

    async def _request_input(self, prompt: str) -> str:
        """Request text/voice input from the user via the main loop."""
        if self._input_callback:
            return await self._input_callback(prompt=prompt)
        # Fallback: read from stdin directly
        print(f"  [Penélope — {prompt}]: ", end="", flush=True)
        loop = asyncio.get_running_loop()
        try:
            text = await loop.run_in_executor(None, lambda: input().strip())
            return text
        except Exception:
            return ""

    async def _handle_user_management(self, intent: ParsedIntent) -> str:
        """Handle user management commands (owner only)."""
        action = intent.action

        if action == "list_users":
            try:
                from penelope.auth.profiles import ProfileManager
                pm = ProfileManager()
                profiles = pm.get_all_profiles(include_inactive=True)
                if not profiles:
                    return "Nenhum usuário cadastrado."
                parts = []
                for p in profiles:
                    status = "ativo" if p.active else "inativo"
                    parts.append(f"{p.name} ({p.level.name}, {status})")
                return f"Usuários cadastrados: {', '.join(parts)}."
            except Exception as e:
                log.error(f"Failed to list users: {e}")
                return "Erro ao listar usuários."

        if action == "check_permissions":
            user_name = intent.entities.get("user_name", "").strip()
            try:
                from penelope.auth.profiles import ProfileManager
                pm = ProfileManager()
                profile = pm.get_profile_by_name(user_name)
                if profile is None:
                    return f"Usuário '{user_name}' não encontrado."
                perms = ", ".join(sorted(profile.permissions)[:8])
                total = len(profile.permissions)
                return (
                    f"{profile.name} ({profile.level.name}) tem {total} permissões. "
                    f"Incluindo: {perms}."
                )
            except Exception as e:
                log.error(f"Failed to check permissions: {e}")
                return "Erro ao verificar permissões."

        if action == "add_co_owner":
            return await self._interactive_add_user(UserLevel.CO_OWNER)

        if action == "add_common_user":
            return await self._interactive_add_user(UserLevel.COMMON)

        if action == "deactivate_user":
            user_name = intent.entities.get("user_name", "").strip()
            return await self._interactive_deactivate_user(user_name)

        return "Comando de gerenciamento de usuários não reconhecido."

    async def _interactive_add_user(self, level: UserLevel) -> str:
        """
        Interactive flow to add a new user via voice/text.

        Steps:
        1. Ask for the user's name
        2. Ask for the passphrase
        3. Create the profile
        """
        level_name = {
            UserLevel.CO_OWNER: "coproprietário",
            UserLevel.COMMON: "usuário comum",
        }.get(level, "usuário")

        # Step 1: Get name
        name = await self._request_input(f"Qual o nome do novo {level_name}?")
        if not name:
            return "Operação cancelada. Nenhum nome informado."

        # Step 2: Get passphrase
        passphrase = await self._request_input(
            f"Qual será a frase-chave de acesso para {name}?"
        )
        if not passphrase:
            return "Operação cancelada. Nenhuma frase-chave informada."

        # Step 3: Create profile
        try:
            from penelope.auth.profiles import ProfileManager
            from penelope.auth.permissions import get_default_permissions

            pm = ProfileManager()

            # Check if already exists
            existing = pm.get_profile_by_name(name)
            if existing:
                return f"Já existe um usuário com o nome '{name}'."

            # Determine timeout and hours
            timeout = 60 if level == UserLevel.CO_OWNER else 30
            hours_start = None if level == UserLevel.CO_OWNER else "08:00"
            hours_end = None if level == UserLevel.CO_OWNER else "20:00"

            profile = pm.create_profile(
                name=name,
                passphrase=passphrase,
                level=level,
                session_timeout_minutes=timeout,
                allowed_hours_start=hours_start,
                allowed_hours_end=hours_end,
            )

            log.info(f"User created via voice: {profile.name} (Level {level.name})")

            # Remember in long-term memory
            if self.memory:
                self.memory.remember(
                    key=f"user_created_{name.lower()}",
                    value=f"{name} criado como {level_name}",
                    category="user_management",
                )

            return (
                f"Pronto! {name} foi adicionado como {level_name}. "
                f"A frase-chave está configurada."
            )

        except ValueError as e:
            return f"Não foi possível criar o usuário: {e}"
        except Exception as e:
            log.error(f"Failed to create user: {e}", exc_info=True)
            return "Ocorreu um erro ao criar o usuário. Verifique os logs."

    async def _interactive_deactivate_user(self, user_name: str) -> str:
        """
        Deactivate a user profile with confirmation.
        """
        if not user_name:
            user_name = await self._request_input(
                "Qual o nome do usuário que deseja desativar?"
            )
            if not user_name:
                return "Operação cancelada."

        try:
            from penelope.auth.profiles import ProfileManager
            pm = ProfileManager()

            profile = pm.get_profile_by_name(user_name)
            if profile is None:
                return f"Usuário '{user_name}' não encontrado."

            if profile.level == UserLevel.OWNER:
                return "Não é possível desativar o proprietário do sistema."

            # Confirm
            confirm = await self._request_input(
                f"Tem certeza que deseja desativar o acesso de {profile.name}? (sim/não)"
            )
            if confirm.lower() not in ("sim", "s", "yes", "y", "confirmo"):
                return "Operação cancelada."

            pm.deactivate_profile(profile.id)
            log.info(f"User deactivated via voice: {profile.name}")

            if self.memory:
                self.memory.remember(
                    key=f"user_deactivated_{user_name.lower()}",
                    value=f"{profile.name} desativado",
                    category="user_management",
                )

            return f"Acesso de {profile.name} foi desativado."

        except Exception as e:
            log.error(f"Failed to deactivate user: {e}")
            return "Erro ao desativar o usuário."

    @property
    def current_mode(self) -> SystemMode:
        return self._current_mode
