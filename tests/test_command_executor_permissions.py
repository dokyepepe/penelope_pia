"""
Penelope command permission mapping tests.
"""

from penelope.core.command_executor import ACTION_PERMISSIONS


def test_game_mode_requires_change_mode_permission():
    assert ACTION_PERMISSIONS["mode_game"] == "change_mode"
