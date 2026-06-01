"""
Penélope — Tests: IntentParser
Validates regex-based command extraction from transcribed text.
"""

import pytest

from penelope.ai.intent_parser import IntentParser, ParsedIntent
from penelope.utils.constants import IntentCategory


class TestIntentParserBasic:
    """Basic parsing and edge cases."""

    def test_empty_input_returns_unknown(self, intent_parser: IntentParser):
        result = intent_parser.parse("")
        assert result.category == IntentCategory.UNKNOWN
        assert result.confidence == 0.0

    def test_whitespace_only_returns_unknown(self, intent_parser: IntentParser):
        result = intent_parser.parse("   ")
        assert result.category == IntentCategory.UNKNOWN

    def test_strips_penelope_prefix(self, intent_parser: IntentParser):
        result = intent_parser.parse("Penélope, abre o chrome")
        assert result.action == "open_app"
        assert result.entities.get("app_name") == "chrome"

    def test_strips_penelope_prefix_no_accent(self, intent_parser: IntentParser):
        result = intent_parser.parse("penelope abre o notepad")
        assert result.action == "open_app"
        assert result.entities.get("app_name") == "notepad"


class TestIntentParserSystemCommands:
    """System command pattern matching."""

    @pytest.mark.parametrize(
        "text, expected_action, entity_key, entity_val",
        [
            ("abre o chrome", "open_app", "app_name", "chrome"),
            ("abrir spotify", "open_app", "app_name", "spotify"),
            ("abra o notepad", "open_app", "app_name", "notepad"),
            ("fecha o chrome", "close_app", "app_name", "chrome"),
            ("fechar o discord", "close_app", "app_name", "discord"),
        ],
    )
    def test_open_close_app(
        self, intent_parser, text, expected_action, entity_key, entity_val
    ):
        result = intent_parser.parse(text)
        assert result.action == expected_action
        assert result.category == IntentCategory.SYSTEM_COMMAND
        assert result.entities.get(entity_key) == entity_val
        assert result.confidence == pytest.approx(0.9)

    @pytest.mark.parametrize(
        "text, expected_action",
        [
            ("aumenta o volume", "volume_up"),
            ("sobe volume", "volume_up"),
            ("diminui o volume", "volume_down"),
            ("abaixa volume", "volume_down"),
            ("muta o som", "volume_mute"),
            ("silencia o áudio", "volume_mute"),
        ],
    )
    def test_volume_commands(self, intent_parser, text, expected_action):
        result = intent_parser.parse(text)
        assert result.action == expected_action
        assert result.category == IntentCategory.SYSTEM_COMMAND

    def test_shutdown(self, intent_parser):
        result = intent_parser.parse("desliga o computador")
        assert result.action == "shutdown"

    def test_restart(self, intent_parser):
        result = intent_parser.parse("reinicia o computador")
        assert result.action == "restart"

    def test_screenshot(self, intent_parser):
        result = intent_parser.parse("tira um print")
        assert result.action == "screenshot"

    def test_empty_recycle(self, intent_parser):
        result = intent_parser.parse("esvazia a lixeira")
        assert result.action == "empty_recycle"

    def test_lock_session(self, intent_parser):
        result = intent_parser.parse("travar a sessão")
        assert result.action == "lock_session"
        assert result.category == IntentCategory.SESSION_CONTROL


class TestIntentParserInformation:
    """Information requests."""

    def test_get_time(self, intent_parser):
        result = intent_parser.parse("que horas são")
        assert result.action == "get_time"
        assert result.category == IntentCategory.INFORMATION

    def test_get_date(self, intent_parser):
        result = intent_parser.parse("que dia é hoje")
        assert result.action == "get_date"

    def test_get_battery(self, intent_parser):
        result = intent_parser.parse("como está a bateria")
        assert result.action == "get_battery"

    def test_get_ip(self, intent_parser):
        result = intent_parser.parse("qual é meu ip")
        assert result.action == "get_ip"

    def test_list_commands(self, intent_parser):
        result = intent_parser.parse("o que você pode fazer")
        assert result.action == "list_commands"


class TestIntentParserModeChanges:
    """Operating mode switches."""

    @pytest.mark.parametrize(
        "text, expected_action",
        [
            ("modo trabalho", "mode_work"),
            ("modo silencioso", "mode_silent"),
            ("modo noite", "mode_night"),
            ("modo entretenimento", "mode_entertainment"),
            ("modo game", "mode_game"),
            ("potência total", "mode_power"),
            ("modo normal", "mode_normal"),
        ],
    )
    def test_mode_changes(self, intent_parser, text, expected_action):
        result = intent_parser.parse(text)
        assert result.action == expected_action
        assert result.category == IntentCategory.MODE_CHANGE


class TestIntentParserAppControl:
    """App-specific control commands."""

    def test_spotify_playpause(self, intent_parser):
        result = intent_parser.parse("pausa a música")
        assert result.action == "spotify_playpause"
        assert result.category == IntentCategory.APP_CONTROL

    def test_spotify_next(self, intent_parser):
        result = intent_parser.parse("próxima música")
        assert result.action == "spotify_next"

    def test_browser_search(self, intent_parser):
        result = intent_parser.parse("pesquisa no google por python tutorial")
        assert result.action == "browser_search"
        assert result.entities.get("search_query") == "python tutorial"


class TestIntentParserFallback:
    """Unrecognized input falls through to LLM."""

    def test_unknown_text_requires_llm(self, intent_parser):
        result = intent_parser.parse("conta uma piada sobre programadores")
        assert result.category == IntentCategory.CONVERSATION
        assert result.action == "chat"
        assert result.requires_llm is True
        assert result.confidence == pytest.approx(0.5)


class TestIntentParserMeta:
    """Meta / utility methods."""

    def test_get_supported_commands_not_empty(self, intent_parser):
        commands = intent_parser.get_supported_commands()
        assert len(commands) > 10
        assert all("action" in c for c in commands)
        assert all("category" in c for c in commands)
