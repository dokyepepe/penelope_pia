"""
Penélope — Tests: SessionManager
Validates session lifecycle, timeout, and activity tracking.
"""

import time
from unittest.mock import patch, MagicMock

import pytest

from penelope.auth.session import Session, SessionManager
from penelope.auth.profiles import UserProfile
from penelope.utils.constants import UserLevel


def _make_profile(
    name: str = "TestUser",
    level: UserLevel = UserLevel.OWNER,
    timeout: int = 0,
) -> UserProfile:
    """Helper to build a minimal UserProfile for testing."""
    return UserProfile(
        id=1,
        name=name,
        level=level,
        passphrase_hash="fake_hash",
        salt="fake_salt",
        permissions={"open_app", "volume_control", "conversation"},
        session_timeout_minutes=timeout,
        created_at=time.time(),
    )


class TestSessionDataclass:
    """Session dataclass properties."""

    def test_is_owner(self):
        s = Session(
            profile=_make_profile(),
            user_name="Owner",
            user_level=UserLevel.OWNER,
            permissions=set(),
        )
        assert s.is_owner is True
        assert s.is_co_owner is False
        assert s.is_common is False

    def test_is_co_owner(self):
        s = Session(
            profile=_make_profile(level=UserLevel.CO_OWNER),
            user_name="Co",
            user_level=UserLevel.CO_OWNER,
            permissions=set(),
        )
        assert s.is_co_owner is True

    def test_is_common(self):
        s = Session(
            profile=_make_profile(level=UserLevel.COMMON),
            user_name="Common",
            user_level=UserLevel.COMMON,
            permissions=set(),
        )
        assert s.is_common is True

    def test_has_permission(self):
        s = Session(
            profile=_make_profile(),
            user_name="X",
            user_level=UserLevel.OWNER,
            permissions={"open_app", "shutdown"},
        )
        assert s.has_permission("open_app") is True
        assert s.has_permission("manage_users") is False

    def test_touch_updates_activity(self):
        s = Session(
            profile=_make_profile(),
            user_name="X",
            user_level=UserLevel.OWNER,
            permissions=set(),
        )
        old_activity = s.last_activity
        time.sleep(0.05)
        s.touch()
        assert s.last_activity > old_activity

    def test_elapsed_and_idle_minutes(self):
        s = Session(
            profile=_make_profile(),
            user_name="X",
            user_level=UserLevel.OWNER,
            permissions=set(),
        )
        assert s.elapsed_minutes >= 0.0
        assert s.idle_minutes >= 0.0


class TestSessionManagerLifecycle:
    """Session creation and termination."""

    @pytest.mark.asyncio
    async def test_start_session(self, session_manager: SessionManager):
        profile = _make_profile()
        session = await session_manager.start_session(profile)

        assert session is not None
        assert session.user_name == "TestUser"
        assert session_manager.is_active is True
        assert session_manager.current is session

    @pytest.mark.asyncio
    async def test_end_session(self, session_manager):
        await session_manager.start_session(_make_profile())
        assert session_manager.is_active is True

        await session_manager.end_session(reason="manual")
        assert session_manager.is_active is False
        assert session_manager.current is None

    @pytest.mark.asyncio
    async def test_end_nonexistent_session_is_noop(self, session_manager):
        # Should not raise
        await session_manager.end_session()

    @pytest.mark.asyncio
    async def test_new_session_replaces_old(self, session_manager):
        p1 = _make_profile(name="User1")
        p2 = _make_profile(name="User2")

        await session_manager.start_session(p1)
        assert session_manager.current.user_name == "User1"

        await session_manager.start_session(p2)
        assert session_manager.current.user_name == "User2"


class TestSessionTimeout:
    """Timeout expiration logic."""

    @pytest.mark.asyncio
    async def test_owner_no_timeout(self, session_manager):
        profile = _make_profile(timeout=0)
        await session_manager.start_session(profile)
        # Even with old activity, owner should not expire (timeout=0)
        session_manager.current.last_activity = time.time() - 99999
        assert session_manager._is_expired() is False

    @pytest.mark.asyncio
    async def test_common_user_expires(self, session_manager):
        profile = _make_profile(level=UserLevel.COMMON, timeout=15)
        await session_manager.start_session(profile)

        # Simulate 20 minutes idle
        session_manager.current.last_activity = time.time() - (20 * 60)
        assert session_manager._is_expired() is True

    @pytest.mark.asyncio
    async def test_check_timeout_ends_expired(self, session_manager):
        profile = _make_profile(level=UserLevel.COMMON, timeout=1)
        await session_manager.start_session(profile)

        # Simulate 2 minutes idle
        session_manager.current.last_activity = time.time() - 120
        expired = await session_manager.check_timeout()
        assert expired is True
        assert session_manager.current is None

    @pytest.mark.asyncio
    async def test_check_timeout_keeps_active(self, session_manager):
        profile = _make_profile(level=UserLevel.COMMON, timeout=30)
        await session_manager.start_session(profile)
        expired = await session_manager.check_timeout()
        assert expired is False
        assert session_manager.current is not None

    @pytest.mark.asyncio
    async def test_touch_prevents_timeout(self, session_manager):
        profile = _make_profile(level=UserLevel.COMMON, timeout=1)
        await session_manager.start_session(profile)
        session_manager.touch()
        assert session_manager._is_expired() is False


class TestSessionInfo:
    """Session info reporting."""

    @pytest.mark.asyncio
    async def test_info_when_active(self, session_manager):
        profile = _make_profile()
        await session_manager.start_session(profile)
        info = session_manager.get_session_info()
        assert info["active"] is True
        assert info["user_name"] == "TestUser"
        assert info["user_level"] == "OWNER"
        assert "elapsed_minutes" in info
        assert "permissions_count" in info

    def test_info_when_inactive(self, session_manager):
        info = session_manager.get_session_info()
        assert info == {"active": False}
