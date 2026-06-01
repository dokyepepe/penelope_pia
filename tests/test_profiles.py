"""
Penélope — Tests: ProfileManager
Validates CRUD operations for user profiles stored in SQLite.
"""

import pytest

from penelope.auth.profiles import ProfileManager, UserProfile
from penelope.utils.constants import UserLevel


class TestProfileCreation:
    """Profile creation and retrieval."""

    def test_create_owner_profile(self, profile_manager: ProfileManager):
        profile = profile_manager.create_profile(
            name="Pietro",
            passphrase="sou o pietro",
            level=UserLevel.OWNER,
            session_timeout_minutes=0,
        )
        assert profile.name == "Pietro"
        assert profile.level == UserLevel.OWNER
        assert profile.active is True
        assert profile.session_timeout_minutes == 0
        assert profile.id > 0

    def test_create_common_profile_with_hours(self, profile_manager):
        profile = profile_manager.create_profile(
            name="Guest",
            passphrase="sou guest",
            level=UserLevel.COMMON,
            session_timeout_minutes=15,
            allowed_hours_start="08:00",
            allowed_hours_end="20:00",
        )
        assert profile.level == UserLevel.COMMON
        assert profile.allowed_hours_start == "08:00"
        assert profile.allowed_hours_end == "20:00"

    def test_create_co_owner_profile(self, profile_manager):
        profile = profile_manager.create_profile(
            name="CoOwner",
            passphrase="co owner key",
            level=UserLevel.CO_OWNER,
        )
        assert profile.level == UserLevel.CO_OWNER
        assert len(profile.permissions) > 0

    def test_duplicate_name_raises(self, profile_manager):
        profile_manager.create_profile("Dup", "pass1", UserLevel.COMMON)
        with pytest.raises(ValueError, match="already exists"):
            profile_manager.create_profile("Dup", "pass2", UserLevel.COMMON)

    def test_default_permissions_applied(self, profile_manager):
        profile = profile_manager.create_profile(
            name="DefPerms", passphrase="p", level=UserLevel.OWNER
        )
        assert "open_app" in profile.permissions
        assert "manage_users" in profile.permissions

    def test_custom_permissions_override(self, profile_manager):
        custom_perms = {"open_app", "volume_control"}
        profile = profile_manager.create_profile(
            name="Custom",
            passphrase="pass",
            level=UserLevel.COMMON,
            permissions=custom_perms,
        )
        assert profile.permissions == custom_perms


class TestProfileRetrieval:
    """Profile lookup operations."""

    def test_get_by_id(self, profile_manager):
        created = profile_manager.create_profile("ById", "p", UserLevel.COMMON)
        fetched = profile_manager.get_profile_by_id(created.id)
        assert fetched is not None
        assert fetched.name == "ById"

    def test_get_by_id_nonexistent(self, profile_manager):
        assert profile_manager.get_profile_by_id(9999) is None

    def test_get_by_name_case_insensitive(self, profile_manager):
        profile_manager.create_profile("Alice", "p", UserLevel.COMMON)
        fetched = profile_manager.get_profile_by_name("alice")
        assert fetched is not None
        assert fetched.name == "Alice"

    def test_get_all_profiles(self, profile_manager):
        profile_manager.create_profile("A", "p1", UserLevel.OWNER)
        profile_manager.create_profile("B", "p2", UserLevel.COMMON)
        profiles = profile_manager.get_all_profiles()
        assert len(profiles) == 2

    def test_get_all_excludes_inactive(self, profile_manager):
        p = profile_manager.create_profile("Inactive", "p", UserLevel.COMMON)
        profile_manager.deactivate_profile(p.id)
        assert len(profile_manager.get_all_profiles()) == 0

    def test_get_all_includes_inactive_flag(self, profile_manager):
        p = profile_manager.create_profile("Inactive", "p", UserLevel.COMMON)
        profile_manager.deactivate_profile(p.id)
        assert len(profile_manager.get_all_profiles(include_inactive=True)) == 1


class TestPassphraseAuth:
    """Passphrase verification logic."""

    def test_find_by_correct_passphrase(self, profile_manager):
        profile_manager.create_profile("Auth", "minha senha", UserLevel.OWNER)
        found = profile_manager.find_profile_by_passphrase("minha senha")
        assert found is not None
        assert found.name == "Auth"

    def test_find_by_wrong_passphrase(self, profile_manager):
        profile_manager.create_profile("Auth", "certa", UserLevel.OWNER)
        found = profile_manager.find_profile_by_passphrase("errada")
        assert found is None

    def test_passphrase_is_case_insensitive(self, profile_manager):
        profile_manager.create_profile("CaseTest", "Minha Senha", UserLevel.OWNER)
        found = profile_manager.find_profile_by_passphrase("minha senha")
        assert found is not None

    def test_passphrase_strips_whitespace(self, profile_manager):
        profile_manager.create_profile("WS", "senha secreta", UserLevel.OWNER)
        found = profile_manager.find_profile_by_passphrase("  senha secreta  ")
        assert found is not None


class TestProfileModification:
    """Update and deactivation."""

    def test_deactivate_profile(self, profile_manager):
        p = profile_manager.create_profile("Deact", "p", UserLevel.COMMON)
        result = profile_manager.deactivate_profile(p.id)
        assert result is True
        fetched = profile_manager.get_profile_by_name("Deact")
        assert fetched is None  # inactive profiles excluded by default

    def test_reactivate_profile(self, profile_manager):
        p = profile_manager.create_profile("React", "p", UserLevel.COMMON)
        profile_manager.deactivate_profile(p.id)
        profile_manager.activate_profile(p.id)
        fetched = profile_manager.get_profile_by_name("React")
        assert fetched is not None
        assert fetched.active is True

    def test_update_permissions(self, profile_manager):
        p = profile_manager.create_profile("Perms", "p", UserLevel.COMMON)
        new_perms = {"open_app", "shutdown", "restart"}
        profile_manager.update_permissions(p.id, new_perms)
        fetched = profile_manager.get_profile_by_id(p.id)
        assert fetched.permissions == new_perms

    def test_change_passphrase(self, profile_manager):
        p = profile_manager.create_profile("ChPass", "old", UserLevel.OWNER)
        profile_manager.change_passphrase(p.id, "new passphrase")
        assert profile_manager.find_profile_by_passphrase("old") is None
        assert profile_manager.find_profile_by_passphrase("new passphrase") is not None

    def test_has_owner(self, profile_manager):
        assert profile_manager.has_owner() is False
        profile_manager.create_profile("Owner", "p", UserLevel.OWNER)
        assert profile_manager.has_owner() is True


class TestFailedAttempts:
    """Lockout and failed attempt tracking."""

    def test_record_and_count(self, profile_manager):
        count = profile_manager.record_failed_attempt("wrong")
        assert count == 1
        count = profile_manager.record_failed_attempt("wrong again")
        assert count == 2

    def test_is_locked_out_after_max(self, profile_manager):
        for _ in range(3):
            profile_manager.record_failed_attempt("bad")
        assert profile_manager.is_locked_out(max_attempts=3) is True

    def test_not_locked_under_max(self, profile_manager):
        profile_manager.record_failed_attempt("bad")
        assert profile_manager.is_locked_out(max_attempts=3) is False

    def test_clear_failed_attempts(self, profile_manager):
        for _ in range(5):
            profile_manager.record_failed_attempt("bad")
        profile_manager.clear_failed_attempts()
        assert profile_manager.is_locked_out(max_attempts=3) is False


class TestUserProfileDataclass:
    """UserProfile dataclass methods."""

    def test_to_dict(self, owner_profile: UserProfile):
        d = owner_profile.to_dict()
        assert d["name"] == "Pietro"
        assert d["level"] == UserLevel.OWNER.value
        assert d["active"] is True
        assert isinstance(d["permissions"], list)
