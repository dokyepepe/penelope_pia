"""
Penélope — Session Manager
Manages active user sessions with timeout and access control.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Set

from penelope.auth.profiles import UserProfile
from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType, UserLevel
from penelope.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class Session:
    """Represents an active user session."""
    profile: UserProfile
    user_name: str
    user_level: UserLevel
    permissions: Set[str]
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    timeout_minutes: int = 30
    token: str = ""

    @property
    def is_owner(self) -> bool:
        return self.user_level == UserLevel.OWNER

    @property
    def is_co_owner(self) -> bool:
        return self.user_level == UserLevel.CO_OWNER

    @property
    def is_common(self) -> bool:
        return self.user_level == UserLevel.COMMON

    @property
    def elapsed_minutes(self) -> float:
        return (time.time() - self.started_at) / 60

    @property
    def idle_minutes(self) -> float:
        return (time.time() - self.last_activity) / 60

    def has_permission(self, permission: str) -> bool:
        """Check if this session has a specific permission."""
        return permission in self.permissions

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()


class SessionManager:
    """
    Manages the currently active user session.

    Handles session creation, expiration, locking, and activity tracking.
    Only one session can be active at a time.
    """

    def __init__(self) -> None:
        self._current_session: Optional[Session] = None
        self.bus = get_event_bus()

    @property
    def current(self) -> Optional[Session]:
        """Get the current active session (may be None)."""
        return self._current_session

    @property
    def is_active(self) -> bool:
        """Check if there's an active, non-expired session."""
        if self._current_session is None:
            return False
        if self._is_expired():
            return False
        return True

    async def start_session(self, profile: UserProfile) -> Session:
        """
        Start a new session for an authenticated user.

        Ends any existing session first.

        Args:
            profile: The authenticated user's profile.

        Returns:
            The new Session object.
        """
        # End existing session if any
        if self._current_session is not None:
            await self.end_session(reason="new_session")

        from penelope.utils.crypto import generate_session_token
        token = generate_session_token()

        session = Session(
            profile=profile,
            user_name=profile.name,
            user_level=profile.level,
            permissions=set(profile.permissions),
            timeout_minutes=profile.session_timeout_minutes,
            token=token,
        )

        self._current_session = session

        log.info(
            f"Session started: {profile.name} "
            f"(Level {profile.level.name}, "
            f"timeout={profile.session_timeout_minutes}min)"
        )

        await self.bus.emit(
            EventType.SESSION_STARTED,
            session=session,
            user_name=profile.name,
            user_level=profile.level,
        )

        return session

    async def end_session(self, reason: str = "manual") -> None:
        """
        End the current session.

        Args:
            reason: Why the session ended (manual, timeout, new_session, lockout).
        """
        if self._current_session is None:
            return

        user_name = self._current_session.user_name
        elapsed = self._current_session.elapsed_minutes

        self._current_session = None

        log.info(
            f"Session ended: {user_name} "
            f"(reason={reason}, duration={elapsed:.1f}min)"
        )

        await self.bus.emit(
            EventType.SESSION_EXPIRED,
            user_name=user_name,
            reason=reason,
            duration_minutes=elapsed,
        )

    async def check_timeout(self) -> bool:
        """
        Check if the current session has timed out.

        Returns:
            True if session was expired, False otherwise.
        """
        if self._current_session is None:
            return False

        if self._is_expired():
            await self.end_session(reason="timeout")
            return True

        return False

    def touch(self) -> None:
        """Update activity timestamp on the current session."""
        if self._current_session is not None:
            self._current_session.touch()

    def _is_expired(self) -> bool:
        """Check if the current session has exceeded its timeout."""
        if self._current_session is None:
            return True

        timeout = self._current_session.timeout_minutes
        if timeout <= 0:
            return False  # No timeout (Owner default)

        return self._current_session.idle_minutes >= timeout

    def get_session_info(self) -> dict:
        """Get summary info about the current session."""
        if self._current_session is None:
            return {"active": False}

        s = self._current_session
        return {
            "active": True,
            "user_name": s.user_name,
            "user_level": s.user_level.name,
            "elapsed_minutes": round(s.elapsed_minutes, 1),
            "idle_minutes": round(s.idle_minutes, 1),
            "timeout_minutes": s.timeout_minutes,
            "permissions_count": len(s.permissions),
        }
