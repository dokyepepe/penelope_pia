"""
Penélope — Tests: Authenticator
Validates voice-based authentication flow, lockout, and first owner setup.
"""

import time
from unittest.mock import patch

import pytest

from penelope.auth.authenticator import Authenticator
from penelope.auth.profiles import ProfileManager
from penelope.utils.constants import UserLevel


class TestAuthSuccess:
    """Successful authentication scenarios."""

    @pytest.mark.asyncio
    async def test_authenticate_owner(self, authenticator: Authenticator, owner_profile):
        result = await authenticator.authenticate("sou o pietro")
        assert result is not None
        assert result.name == "Pietro"
        assert result.level == UserLevel.OWNER

    @pytest.mark.asyncio
    async def test_authenticate_common_user(self, authenticator, common_profile):
        with patch.object(authenticator, "_check_allowed_hours", return_value=True):
            result = await authenticator.authenticate("sou o guest")
            assert result is not None
            assert result.name == "Guest"
            assert result.level == UserLevel.COMMON


class TestAuthFailure:
    """Failed authentication scenarios."""

    @pytest.mark.asyncio
    async def test_wrong_passphrase_returns_none(self, authenticator, owner_profile):
        result = await authenticator.authenticate("frase errada")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_passphrase_returns_none(self, authenticator, owner_profile):
        result = await authenticator.authenticate("")
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_passphrase_returns_none(self, authenticator, owner_profile):
        result = await authenticator.authenticate("   ")
        assert result is None


class TestAuthLockout:
    """Lockout mechanism after max failed attempts."""

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(self, authenticator, owner_profile):
        for _ in range(3):
            await authenticator.authenticate("errada")

        # 4th attempt should be blocked by lockout
        result = await authenticator.authenticate("sou o pietro")
        assert result is None  # locked out

    @pytest.mark.asyncio
    async def test_successful_auth_clears_attempts(self, authenticator, owner_profile):
        await authenticator.authenticate("errada")
        await authenticator.authenticate("errada")

        # Successful auth resets counter
        result = await authenticator.authenticate("sou o pietro")
        assert result is not None

        # After success, these should not trigger lockout
        await authenticator.authenticate("errada")
        result2 = await authenticator.authenticate("sou o pietro")
        assert result2 is not None


class TestAllowedHours:
    """Time-based access restrictions."""

    def test_owner_always_allowed(self, authenticator, owner_profile):
        result = authenticator._check_allowed_hours(owner_profile)
        assert result is True

    def test_common_user_within_hours(self, authenticator, common_profile):
        # Mock time to 12:00 (within 08:00–22:00)
        with patch("penelope.auth.authenticator.time") as mock_time:
            mock_time.localtime.return_value = time.struct_time(
                (2025, 6, 1, 12, 0, 0, 0, 152, -1)
            )
            result = authenticator._check_allowed_hours(common_profile)
            assert result is True

    def test_common_user_outside_hours(self, authenticator, common_profile):
        # Mock time to 23:00 (outside 08:00–22:00)
        with patch("penelope.auth.authenticator.time") as mock_time:
            mock_time.localtime.return_value = time.struct_time(
                (2025, 6, 1, 23, 0, 0, 0, 152, -1)
            )
            result = authenticator._check_allowed_hours(common_profile)
            assert result is False

    def test_no_hour_restrictions_allows_all(self, authenticator, profile_manager):
        profile = profile_manager.create_profile(
            name="NoRestrict", passphrase="p", level=UserLevel.COMMON,
        )
        result = authenticator._check_allowed_hours(profile)
        assert result is True


class TestFirstOwnerSetup:
    """First-time owner profile creation."""

    def test_setup_first_owner(self, authenticator):
        profile = authenticator.setup_first_owner("Admin", "minha frase")
        assert profile.name == "Admin"
        assert profile.level == UserLevel.OWNER

    def test_setup_owner_twice_raises(self, authenticator):
        authenticator.setup_first_owner("Admin", "frase")
        with pytest.raises(RuntimeError, match="already exists"):
            authenticator.setup_first_owner("Admin2", "frase2")
