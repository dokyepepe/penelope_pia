"""
Penélope — Intent Parser
Extracts commands, categories, and entities from transcribed text.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from penelope.utils.constants import IntentCategory
from penelope.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ParsedIntent:
    """Result of intent parsing."""
    raw_text: str = ""
    category: IntentCategory = IntentCategory.UNKNOWN
    action: str = ""
    entities: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    requires_llm: bool = False


# ============================================
# Regex-based command patterns (offline capable)
# ============================================

COMMAND_PATTERNS: List[Tuple[str, IntentCategory, str, List[str]]] = [
    # System commands
    (r"(?:abre|abrir|abra)\s+(?:o\s+)?(.+)", IntentCategory.SYSTEM_COMMAND, "open_app", ["app_name"]),
    (r"(?:fecha|fechar|feche)\s+(?:o\s+)?(.+)", IntentCategory.SYSTEM_COMMAND, "close_app", ["app_name"]),
    (r"(?:aumenta|aumentar|sobe|subir)\s+(?:o\s+)?volume", IntentCategory.SYSTEM_COMMAND, "volume_up", []),
    (r"(?:diminui|diminuir|abaixa|abaixar|desce|descer)\s+(?:o\s+)?volume", IntentCategory.SYSTEM_COMMAND, "volume_down", []),
    (r"(?:muta|mutar|silencia|silenciar)\s+(?:o\s+)?(?:som|volume|áudio)", IntentCategory.SYSTEM_COMMAND, "volume_mute", []),
    (r"(?:desliga|desligar)\s+(?:o\s+)?computador", IntentCategory.SYSTEM_COMMAND, "shutdown", []),
    (r"(?:reinicia|reiniciar|restart)\s+(?:o\s+)?computador", IntentCategory.SYSTEM_COMMAND, "restart", []),
    (r"(?:tira|tirar|captura|capturar)\s+(?:um\s+)?(?:print|screenshot|captura)", IntentCategory.SYSTEM_COMMAND, "screenshot", []),
    (r"(?:esvazia|esvaziar)\s+(?:a\s+)?lixeira", IntentCategory.SYSTEM_COMMAND, "empty_recycle", []),
    (r"(?:travar?|bloquear?)\s+(?:a\s+)?(?:sessão|tela)", IntentCategory.SESSION_CONTROL, "lock_session", []),
    (r"qual\s+(?:[ée]|é)\s+meu\s+ip", IntentCategory.INFORMATION, "get_ip", []),
    (r"que horas?\s+s[aã]o", IntentCategory.INFORMATION, "get_time", []),
    (r"(?:qual\s+(?:[ée]|é)\s+a\s+)?data\s+(?:de\s+)?hoje|que\s+dia\s+(?:[ée]|é)\s+hoje", IntentCategory.INFORMATION, "get_date", []),
    (r"(?:como\s+)?est[aá]\s+(?:a\s+)?bateria|status\s+da\s+bateria|n[ií]vel\s+da\s+bateria", IntentCategory.INFORMATION, "get_battery", []),
    (r"ajuda|lista\s+de\s+comandos|o\s+que\s+voc[eê]\s+pode\s+fazer|comandos\s+dispon[ií]veis", IntentCategory.INFORMATION, "list_commands", []),
    (r"(?:modo\s+)?avi[aã]o", IntentCategory.SYSTEM_COMMAND, "airplane_mode", []),

    # App control
    (r"(?:abre|abrir)\s+(?:o\s+)?task\s*manager", IntentCategory.SYSTEM_COMMAND, "open_task_manager", []),

    # Mode changes
    (r"(?:modo|entra|ativa)\s+(?:no\s+)?(?:modo\s+)?trabalho", IntentCategory.MODE_CHANGE, "mode_work", []),
    (r"(?:modo|entra|ativa)\s+(?:no\s+)?(?:modo\s+)?(?:silencioso|silêncio)", IntentCategory.MODE_CHANGE, "mode_silent", []),
    (r"(?:modo|entra|ativa)\s+(?:no\s+)?(?:modo\s+)?noite", IntentCategory.MODE_CHANGE, "mode_night", []),
    (r"(?:modo|entra|ativa)\s+(?:no\s+)?(?:modo\s+)?(?:entretenimento|game|jogo)", IntentCategory.MODE_CHANGE, "mode_entertainment", []),
    (r"(?:potência total|modo jarvis|autonomia máxima)", IntentCategory.MODE_CHANGE, "mode_power", []),
    (r"(?:modo\s+)?normal", IntentCategory.MODE_CHANGE, "mode_normal", []),

    # User management
    (r"(?:adiciona|adicionar|cria|criar)\s+(?:um\s+)?(?:novo\s+)?coproprietário", IntentCategory.USER_MANAGEMENT, "add_co_owner", []),
    (r"(?:adiciona|adicionar|cria|criar)\s+(?:um\s+)?(?:novo\s+)?usuário\s+comum", IntentCategory.USER_MANAGEMENT, "add_common_user", []),
    (r"(?:lista|listar)\s+(?:os\s+)?usuários", IntentCategory.USER_MANAGEMENT, "list_users", []),
    (r"(?:desativa|desativar|remove|remover)\s+(?:o\s+)?acesso\s+(?:d[eo]\s+)?(.+)", IntentCategory.USER_MANAGEMENT, "deactivate_user", ["user_name"]),
    (r"(?:quais?|que)\s+permiss[oõ]es?\s+(?:o\s+)?(.+)\s+tem", IntentCategory.USER_MANAGEMENT, "check_permissions", ["user_name"]),

    # Window management
    (r"(?:organiza|organizar)\s+(?:as\s+)?janelas", IntentCategory.SYSTEM_COMMAND, "organize_windows", []),
    (r"(?:fecha|fechar)\s+tudo\s+menos\s+(?:o\s+)?(.+)", IntentCategory.SYSTEM_COMMAND, "close_all_except", ["app_name"]),
    (r"(?:modo\s+)?reuni[aã]o", IntentCategory.SYSTEM_COMMAND, "meeting_mode", []),
    (r"(?:modo\s+)?apresenta[cç][aã]o", IntentCategory.SYSTEM_COMMAND, "presentation_mode", []),

    # Clipboard
    (r"(?:o\s+que\s+)?(?:eu\s+)?copiei\s+(?:antes|ontem|agora)", IntentCategory.INFORMATION, "clipboard_history", []),

    # Sleep / shutdown routines
    (r"(?:vai?|hora\s+de)\s+dormir", IntentCategory.AUTOMATION, "sleep_routine", []),
    (r"hora\s+(?:da|de)\s+reuni[aã]o", IntentCategory.AUTOMATION, "meeting_routine", []),
]


class IntentParser:
    """
    Parses transcribed speech into structured intents.

    Uses regex patterns for known commands (works offline)
    and falls back to LLM for complex/ambiguous inputs.
    """

    def __init__(self) -> None:
        self._patterns = COMMAND_PATTERNS

    def parse(self, text: str) -> ParsedIntent:
        """
        Parse transcribed text into a structured intent.

        First tries regex matching for known commands.
        If no match, marks as requiring LLM interpretation.

        Args:
            text: Transcribed speech text.

        Returns:
            ParsedIntent with category, action, and entities.
        """
        normalized = text.strip().lower()

        if not normalized:
            return ParsedIntent(raw_text=text, category=IntentCategory.UNKNOWN)

        # Remove "penélope" prefix
        normalized = re.sub(
            r"^(?:pen[eé]lope|penelope)\s*,?\s*",
            "",
            normalized,
        ).strip()

        # Try regex patterns
        for pattern, category, action, entity_names in self._patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                entities = {}
                for i, name in enumerate(entity_names, 1):
                    if i <= len(match.groups()):
                        entities[name] = match.group(i).strip()

                intent = ParsedIntent(
                    raw_text=text,
                    category=category,
                    action=action,
                    entities=entities,
                    confidence=0.9,
                    requires_llm=False,
                )
                log.debug(
                    f"Intent parsed: {action} ({category.value}) "
                    f"entities={entities}"
                )
                return intent

        # No regex match → needs LLM interpretation
        log.debug(f"No regex match for: '{normalized}' → requires LLM")
        return ParsedIntent(
            raw_text=text,
            category=IntentCategory.CONVERSATION,
            action="chat",
            confidence=0.5,
            requires_llm=True,
        )

    def get_supported_commands(self) -> List[Dict[str, str]]:
        """Get a list of all supported regex commands."""
        return [
            {
                "action": action,
                "category": category.value,
                "pattern": pattern,
            }
            for pattern, category, action, _ in self._patterns
        ]
