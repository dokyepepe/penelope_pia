"""
Penélope — LLM Client
Wrapper for the Ollama API with persona management and fallback.
"""

import asyncio
import re
import time
from typing import AsyncGenerator, Dict, List, Optional

import yaml

from penelope.utils.constants import PERSONAS_FILE, SystemMode, UserLevel
from penelope.utils.logger import get_logger
from penelope.utils.system_info import get_gpu_info, get_recommended_llm_model

log = get_logger(__name__)


# Hardcoded fallback rules for when LLM is offline
FALLBACK_RULES: Dict[str, str] = {
    r"(abre|abrir|abra)\s+(o\s+)?(.+)": "Vou abrir {match} para você.",
    r"(fecha|fechar|feche)\s+(o\s+)?(.+)": "Vou fechar {match} para você.",
    r"(aumenta|aumentar|sobe)\s+(o\s+)?volume": "Volume aumentado.",
    r"(diminui|diminuir|abaixa)\s+(o\s+)?volume": "Volume diminuído.",
    r"que horas? s[aã]o": "Deixe-me verificar... São {time}.",
    r"(desliga|desligar)\s+(o\s+)?computador": "Vou desligar o computador em 30 segundos.",
    r"(tira|tirar|captura)\s+(um\s+)?(print|screenshot|captura)": "Capturando a tela agora.",
    r"qual\s+([eé]|é)\s+meu\s+ip": "Vou verificar seu IP.",
}


class LLMClient:
    """
    Client for the Ollama local LLM server.

    Handles chat interactions with dynamic persona/system prompts
    based on the authenticated user profile.
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: Optional[str] = None,
        fallback_model: str = "phi3:mini",
    ) -> None:
        self.host = host
        self.fallback_model = fallback_model
        self._model = model
        self._ollama = None
        self._personas: Dict = {}
        self._system_prompt: str = ""
        self._conversation: List[Dict[str, str]] = []
        self._max_history = 20
        self._connected = False
        self._load_personas()

    def _load_personas(self) -> None:
        """Load persona definitions from YAML config."""
        try:
            if PERSONAS_FILE.exists():
                with open(PERSONAS_FILE, "r", encoding="utf-8") as f:
                    self._personas = yaml.safe_load(f)
                log.debug("Personas loaded from config")
            else:
                log.warning(f"Personas file not found: {PERSONAS_FILE}")
                self._personas = {}
        except Exception as e:
            log.error(f"Failed to load personas: {e}")
            self._personas = {}

    async def connect(self) -> bool:
        """
        Connect to the Ollama server and verify availability.

        Returns:
            True if connected successfully.
        """
        try:
            import ollama as ollama_lib
            self._ollama = ollama_lib

            # Test connection by listing models
            models = ollama_lib.list()
            available = [m.model for m in models.models] if models.models else []
            log.info(f"Ollama connected. Available models: {available}")

            # Auto-select model if not specified
            if self._model is None:
                self._model = get_recommended_llm_model()
                log.info(f"Auto-selected model: {self._model}")

            # Check if selected model is available
            if self._model not in available and available:
                log.warning(
                    f"Model {self._model} not found. "
                    f"Available: {available}. Trying fallback."
                )
                if self.fallback_model in available:
                    self._model = self.fallback_model
                elif available:
                    self._model = available[0]

            self._connected = True
            return True

        except Exception as e:
            log.error(f"Failed to connect to Ollama at {self.host}: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def model(self) -> str:
        return self._model or "unknown"

    def set_persona(
        self,
        user_name: str,
        user_level: UserLevel,
        mode: SystemMode = SystemMode.NORMAL,
    ) -> None:
        """
        Set the system prompt based on user profile and mode.

        Args:
            user_name: The user's display name.
            user_level: The user's access level.
            mode: The current operating mode.
        """
        parts = []

        # Base persona
        base = self._personas.get("base_persona", "")
        if base:
            parts.append(base.strip())

        # Profile-specific prompt
        level_key = {
            UserLevel.OWNER: "owner",
            UserLevel.CO_OWNER: "co_owner",
            UserLevel.COMMON: "common",
        }.get(user_level, "common")

        profile_config = self._personas.get("profiles", {}).get(level_key, {})
        profile_prompt = profile_config.get("system_prompt", "")
        if profile_prompt:
            parts.append(profile_prompt.format(name=user_name).strip())

        # Mode-specific additions
        mode_config = self._personas.get("modes", {}).get(mode.value, {})
        mode_prompt = mode_config.get("extra_prompt", "")
        if mode_prompt:
            parts.append(mode_prompt.strip())

        self._system_prompt = "\n\n".join(parts)
        log.debug(f"Persona set for {user_name} ({level_key}, mode={mode.value})")

    def get_greeting(self, user_name: str, user_level: UserLevel) -> str:
        """
        Get the appropriate greeting for a user.

        Args:
            user_name: The user's name.
            user_level: The user's access level.

        Returns:
            Greeting string.
        """
        level_key = {
            UserLevel.OWNER: "owner",
            UserLevel.CO_OWNER: "co_owner",
            UserLevel.COMMON: "common",
        }.get(user_level, "common")

        profile_config = self._personas.get("profiles", {}).get(level_key, {})
        greeting_template = profile_config.get("greeting", "Olá!")
        return greeting_template.format(name=user_name)

    async def chat(self, message: str) -> str:
        """
        Send a message and get a complete response.

        Falls back to rule-based responses if LLM is offline.

        Args:
            message: User's message text.

        Returns:
            AI response text.
        """
        if not self._connected or self._ollama is None:
            return self._fallback_response(message)

        # Add to conversation history
        self._conversation.append({"role": "user", "content": message})

        # Trim history
        if len(self._conversation) > self._max_history:
            self._conversation = self._conversation[-self._max_history:]

        try:
            messages = []
            if self._system_prompt:
                messages.append({"role": "system", "content": self._system_prompt})
            messages.extend(self._conversation)

            response = self._ollama.chat(
                model=self._model,
                messages=messages,
            )

            assistant_msg = response.message.content
            self._conversation.append({"role": "assistant", "content": assistant_msg})

            return assistant_msg

        except Exception as e:
            log.error(f"LLM chat failed: {e}")
            self._connected = False
            return self._fallback_response(message)

    async def chat_stream(self, message: str) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response token by token.

        Args:
            message: User's message text.

        Yields:
            Response text chunks.
        """
        if not self._connected or self._ollama is None:
            yield self._fallback_response(message)
            return

        self._conversation.append({"role": "user", "content": message})

        if len(self._conversation) > self._max_history:
            self._conversation = self._conversation[-self._max_history:]

        try:
            messages = []
            if self._system_prompt:
                messages.append({"role": "system", "content": self._system_prompt})
            messages.extend(self._conversation)

            full_response = []
            stream = self._ollama.chat(
                model=self._model,
                messages=messages,
                stream=True,
            )

            for chunk in stream:
                token = chunk.message.content
                full_response.append(token)
                yield token

            self._conversation.append({
                "role": "assistant",
                "content": "".join(full_response),
            })

        except Exception as e:
            log.error(f"LLM stream failed: {e}")
            self._connected = False
            yield self._fallback_response(message)

    def _fallback_response(self, message: str) -> str:
        """
        Generate a response using hardcoded rules when LLM is offline.

        Args:
            message: User's message.

        Returns:
            Best-effort response string.
        """
        normalized = message.strip().lower()

        for pattern, response_template in FALLBACK_RULES.items():
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                response = response_template
                if "{match}" in response:
                    response = response.replace("{match}", match.group(match.lastindex or 0))
                if "{time}" in response:
                    response = response.replace(
                        "{time}",
                        time.strftime("%H:%M"),
                    )
                return response

        return (
            "Desculpe, estou em modo limitado no momento. "
            "O modelo de linguagem está offline. "
            "Posso executar comandos básicos como abrir apps e controlar o volume."
        )

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._conversation.clear()
        log.debug("Conversation history cleared")

    async def get_models(self) -> List[str]:
        """
        Get list of available models from Ollama.

        Returns:
            List of model names.
        """
        try:
            if self._ollama is None:
                import ollama as ollama_lib
                self._ollama = ollama_lib

            models = self._ollama.list()
            return [m.model for m in models.models] if models.models else []
        except Exception as e:
            log.error(f"Failed to list models: {e}")
            return []

    async def suspend(self) -> None:
        """Suspend LLM (for Game Mode) — clears context to free VRAM."""
        self.clear_history()
        self._connected = False
        log.info("LLM suspended (Game Mode)")

    async def resume(self) -> None:
        """Resume LLM after suspension."""
        await self.connect()
        log.info("LLM resumed")
