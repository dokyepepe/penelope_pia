"""
Penélope — Test Fixtures & Configuration
Shared fixtures for the entire test suite.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Event Bus — always start with a fresh singleton per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_event_bus():
    """Reset the global EventBus singleton before each test."""
    import penelope.core.event_bus as eb_mod
    eb_mod._bus = None
    yield
    eb_mod._bus = None


@pytest.fixture
def event_bus():
    """Provide a clean EventBus instance."""
    from penelope.core.event_bus import EventBus
    return EventBus()


# ---------------------------------------------------------------------------
# Temporary database path for ProfileManager tests
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary SQLite database path."""
    return tmp_path / "test_profiles.db"


@pytest.fixture
def profile_manager(tmp_db):
    """ProfileManager backed by a temporary DB."""
    from penelope.auth.profiles import ProfileManager
    return ProfileManager(db_path=tmp_db)


# ---------------------------------------------------------------------------
# Pre-populated profiles
# ---------------------------------------------------------------------------

@pytest.fixture
def owner_profile(profile_manager):
    """Create and return an OWNER profile."""
    from penelope.utils.constants import UserLevel
    return profile_manager.create_profile(
        name="Pietro",
        passphrase="sou o pietro",
        level=UserLevel.OWNER,
        session_timeout_minutes=0,
    )


@pytest.fixture
def common_profile(profile_manager):
    """Create and return a COMMON user profile with restricted hours."""
    from penelope.utils.constants import UserLevel
    return profile_manager.create_profile(
        name="Guest",
        passphrase="sou o guest",
        level=UserLevel.COMMON,
        session_timeout_minutes=15,
        allowed_hours_start="08:00",
        allowed_hours_end="22:00",
    )


# ---------------------------------------------------------------------------
# Authenticator with injected ProfileManager
# ---------------------------------------------------------------------------

@pytest.fixture
def authenticator(profile_manager):
    """Authenticator wired to the temporary ProfileManager."""
    from penelope.auth.authenticator import Authenticator
    return Authenticator(profile_manager=profile_manager, max_attempts=3)


# ---------------------------------------------------------------------------
# IntentParser
# ---------------------------------------------------------------------------

@pytest.fixture
def intent_parser():
    """Fresh IntentParser instance."""
    from penelope.ai.intent_parser import IntentParser
    return IntentParser()


# ---------------------------------------------------------------------------
# SessionManager
# ---------------------------------------------------------------------------

@pytest.fixture
def session_manager():
    """Fresh SessionManager instance."""
    from penelope.auth.session import SessionManager
    return SessionManager()


# ---------------------------------------------------------------------------
# Async event loop for pytest-asyncio
# ---------------------------------------------------------------------------

@pytest.fixture
def event_loop():
    """Create a new event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
