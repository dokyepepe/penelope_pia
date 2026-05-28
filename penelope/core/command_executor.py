"""
Penélope — Command Executor
Bridges parsed intents to real system actions with permission checks.
"""

import time
from typing import Any, Dict, Optional

from penelope.ai.intent_parser import ParsedIntent
from penelope.ai.llm_client import LLMClient
from penelope.auth.session import Session
from penelope.core.event_bus import get_event_bus
from penelope.system.windows_control import WindowsControl
from penelope.utils.constants import EventType, IntentCategory, SystemMode
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
    "mode_power": "change_mode",
    "mode_normal": "change_mode",
    # User management
    "add_co_owner": "manage_users",
    "add_common_user": "manage_users",
    "list_users": "manage_users",
    "deactivate_user": "manage_users",
    "check_permissions": "manage_users",
    # AI / Automation
    "chat": "conversation",
    "sleep_routine": "automation",
    "meeting_routine": "automation",
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
    ) -> None:
        self.windows = windows_control or WindowsControl()
        self.llm = llm_client
        self.audio = audio_manager
        self.bus = get_event_bus()
        self._current_mode = SystemMode.NORMAL

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

        # ── Mode Changes ──
        if action.startswith("mode_"):
            return await self._handle_mode_change(action)

        # ── User Management ──
        if intent.category == IntentCategory.USER_MANAGEMENT:
            return await self._handle_user_management(intent)

        # ── Window Management ──
        if action == "organize_windows":
            return "Organizando janelas. Funcionalidade em desenvolvimento."

        if action == "close_all_except":
            app = entities.get("app_name", "")
            return f"Fechando tudo exceto {app}. Funcionalidade em desenvolvimento."

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
            "mode_power": SystemMode.POWER,
            "mode_normal": SystemMode.NORMAL,
        }

        mode_names = {
            SystemMode.WORK: "Trabalho",
            SystemMode.SILENT: "Silencioso",
            SystemMode.NIGHT: "Noite",
            SystemMode.ENTERTAINMENT: "Entretenimento",
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
        )

        name = mode_names.get(new_mode, new_mode.value)
        log.info(f"Mode changed: {old_mode.value} → {new_mode.value}")
        return f"Modo {name} ativado."

    async def _handle_user_management(self, intent: ParsedIntent) -> str:
        """Handle user management commands (owner only)."""
        action = intent.action

        if action == "list_users":
            try:
                from penelope.auth.profiles import ProfileManager
                pm = ProfileManager()
                profiles = pm.get_all_profiles()
                if not profiles:
                    return "Nenhum usuário cadastrado."
                names = [
                    f"{p.name} ({p.level.name})" for p in profiles
                ]
                return f"Usuários: {', '.join(names)}."
            except Exception as e:
                log.error(f"Failed to list users: {e}")
                return "Erro ao listar usuários."

        if action == "check_permissions":
            user_name = intent.entities.get("user_name", "")
            try:
                from penelope.auth.profiles import ProfileManager
                pm = ProfileManager()
                profile = pm.get_profile_by_name(user_name)
                if profile is None:
                    return f"Usuário '{user_name}' não encontrado."
                perms = ", ".join(sorted(profile.permissions)[:5])
                total = len(profile.permissions)
                return (
                    f"{profile.name} tem {total} permissões. "
                    f"Incluindo: {perms}."
                )
            except Exception as e:
                log.error(f"Failed to check permissions: {e}")
                return "Erro ao verificar permissões."

        # Placeholder for interactive user management
        return (
            "Gerenciamento interativo de usuários ainda em desenvolvimento. "
            "Use o setup wizard para adicionar o proprietário."
        )

    @property
    def current_mode(self) -> SystemMode:
        return self._current_mode
