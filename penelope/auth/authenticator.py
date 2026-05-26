"""
Penélope — Authenticator
Validates spoken passphrases against stored profiles.
"""

import time
from typing import Optional

from penelope.auth.profiles import ProfileManager, UserProfile
from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType, UserLevel
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class Authenticator:
    """
    Handles voice-based authentication for the Penélope system.

    Flow:
    1. Wake word detected → Penélope asks for passphrase
    2. User speaks passphrase → STT transcribes
    3. Authenticator checks against stored hashes
    4. Returns matching profile or denies access
    """

    def __init__(
        self,
        profile_manager: Optional[ProfileManager] = None,
        max_attempts: int = 3,
        lockout_minutes: int = 30,
    ) -> None:
        self.profiles = profile_manager or ProfileManager()
        self.max_attempts = max_attempts
        self.lockout_minutes = lockout_minutes
        self.bus = get_event_bus()

    async def authenticate(self, spoken_text: str) -> Optional[UserProfile]:
        """
        Attempt to authenticate a user by spoken passphrase.

        Args:
            spoken_text: The transcribed passphrase from STT.

        Returns:
            UserProfile if authentication succeeds, None if denied.
        """
        # Check lockout
        if self.profiles.is_locked_out(self.max_attempts):
            log.warning("Authentication attempt during lockout period")
            await self.bus.emit(EventType.AUTH_LOCKED)
            return None

        # Normalize: STT output can vary slightly
        normalized = spoken_text.strip().lower()

        if not normalized:
            log.debug("Empty passphrase received")
            return None

        # Try to find matching profile
        profile = self.profiles.find_profile_by_passphrase(normalized)

        if profile is None:
            # Record failed attempt
            attempts = self.profiles.record_failed_attempt(normalized)

            if attempts >= self.max_attempts:
                log.warning(
                    f"Max attempts ({self.max_attempts}) reached — locking out"
                )
                await self.bus.emit(EventType.AUTH_LOCKED)
                # Notify owner
                await self._notify_owner_lockout()
            else:
                await self.bus.emit(
                    EventType.AUTH_FAILED,
                    remaining_attempts=self.max_attempts - attempts,
                )

            return None

        # Check if within allowed hours
        if not self._check_allowed_hours(profile):
            log.info(
                f"Access denied for {profile.name}: outside allowed hours"
            )
            await self.bus.emit(
                EventType.AUTH_FAILED,
                reason="outside_hours",
                user_name=profile.name,
            )
            return None

        # Success!
        log.info(f"Authentication successful: {profile.name} (Level {profile.level.name})")
        self.profiles.clear_failed_attempts()  # Reset on success

        await self.bus.emit(
            EventType.AUTH_SUCCESS,
            profile=profile,
            user_name=profile.name,
            user_level=profile.level,
        )

        return profile

    def _check_allowed_hours(self, profile: UserProfile) -> bool:
        """
        Check if the current time is within allowed hours for the profile.

        Owners always have access. Common users may have restricted hours.

        Args:
            profile: The user profile to check.

        Returns:
            True if access is allowed at current time.
        """
        if profile.level == UserLevel.OWNER:
            return True  # Owners always have access

        if not profile.allowed_hours_start or not profile.allowed_hours_end:
            return True  # No restriction configured

        now = time.localtime()
        current_minutes = now.tm_hour * 60 + now.tm_min

        start_parts = profile.allowed_hours_start.split(":")
        end_parts = profile.allowed_hours_end.split(":")

        start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
        end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])

        if start_minutes <= end_minutes:
            return start_minutes <= current_minutes <= end_minutes
        else:
            # Wraps around midnight (e.g., 22:00 to 06:00)
            return current_minutes >= start_minutes or current_minutes <= end_minutes

    async def _notify_owner_lockout(self) -> None:
        """Notify the owner about a lockout event."""
        await self.bus.emit(
            EventType.NOTIFICATION,
            title="⚠️ Alerta de Segurança",
            message="Muitas tentativas de autenticação falharam. Sistema bloqueado temporariamente.",
            priority="high",
            target_level=UserLevel.OWNER,
        )

    def setup_first_owner(self, name: str, passphrase: str) -> UserProfile:
        """
        Create the first owner profile during initial setup.

        This should only be called once during first boot.

        Args:
            name: Owner's name.
            passphrase: Owner's passphrase.

        Returns:
            The created owner profile.

        Raises:
            RuntimeError: If an owner already exists.
        """
        if self.profiles.has_owner():
            raise RuntimeError("Owner profile already exists")

        profile = self.profiles.create_profile(
            name=name,
            passphrase=passphrase,
            level=UserLevel.OWNER,
            session_timeout_minutes=0,  # No timeout for owner
        )
        log.info(f"First owner profile created: {name}")
        return profile
