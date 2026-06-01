"""
Penélope — Tests: ResourceOptimizer
Validates mode-based resource adjustments (mocked, no real system changes).
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from penelope.core.resource_optimizer import ResourceOptimizer
from penelope.utils.constants import SystemMode, EventType


def _make_mock_main():
    """Build a mock main_module with all expected sub-components."""
    main = MagicMock()
    main._wake_word = MagicMock()
    main._hud = MagicMock()
    main._llm_client = MagicMock()
    main._command_executor = MagicMock()
    main._command_executor.clipboard_manager = MagicMock()
    return main


class TestModeChanged:
    """Test _on_mode_changed adjusts resources correctly."""

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_game_mode_hides_hud(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.GAME.value,
            source="auto",
        )

        main._hud.hide.assert_called_once()

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_normal_mode_shows_hud(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.GAME.value,
            new_mode=SystemMode.NORMAL.value,
            source="auto",
        )

        main._hud.show.assert_called_once()

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_game_mode_stops_clipboard(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.GAME.value,
            source="auto",
        )

        main._command_executor.clipboard_manager.stop.assert_called_once()

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_normal_mode_restarts_clipboard(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.GAME.value,
            new_mode=SystemMode.NORMAL.value,
            source="auto",
        )

        main._command_executor.clipboard_manager.start.assert_called_once()

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_game_mode_clears_llm_history(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.GAME.value,
        )

        main._llm_client.clear_history.assert_called_once()

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_wake_word_interval_game(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.GAME.value,
        )

        main._wake_word.set_interval.assert_called_with(500)

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_wake_word_interval_power(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.POWER.value,
        )

        main._wake_word.set_interval.assert_called_with(50)

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_silent_mode_shows_message(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.SILENT.value,
        )

        main._hud.set_response.assert_called_once_with("[Modo Silencioso Ativo]")


class TestManualOverride:
    """Manual mode override prevents auto-switching."""

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_user_source_sets_manual_override(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.WORK.value,
            source="user",
        )

        assert opt._manual_mode_override is True

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_auto_game_does_not_set_manual_override(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt._adjust_process_priority = MagicMock()

        opt._on_mode_changed(
            old_mode=SystemMode.NORMAL.value,
            new_mode=SystemMode.GAME.value,
            source="",
        )

        assert opt._manual_mode_override is False


class TestStartStop:
    """Start/stop lifecycle (no real threads in tests)."""

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_start_registers_event(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)

        with patch.object(opt.bus, "on") as mock_on:
            opt.start()
            mock_on.assert_called_with(EventType.MODE_CHANGED, opt._on_mode_changed)

        opt.stop()

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_stop_unregisters_event(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt.start()

        with patch.object(opt.bus, "off") as mock_off:
            opt.stop()
            mock_off.assert_called_with(EventType.MODE_CHANGED, opt._on_mode_changed)

    @patch("penelope.core.resource_optimizer.ResourceOptimizer._load_config")
    def test_double_start_is_noop(self, _mock_cfg):
        main = _make_mock_main()
        opt = ResourceOptimizer(main)
        opt.start()
        first_thread = opt._thread
        opt.start()
        assert opt._thread is first_thread
        opt.stop()
