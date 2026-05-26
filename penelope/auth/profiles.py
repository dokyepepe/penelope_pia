"""
Penélope — Profile Manager
CRUD operations for user profiles stored in SQLite.
"""

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from penelope.auth.permissions import get_default_permissions
from penelope.utils.constants import UserLevel, PROFILES_DB_PATH, DATA_DIR
from penelope.utils.crypto import generate_salt, hash_passphrase
from penelope.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class UserProfile:
    """Represents a user profile in the system."""
    id: int = 0
    name: str = ""
    level: UserLevel = UserLevel.COMMON
    passphrase_hash: str = ""
    salt: str = ""
    permissions: Set[str] = field(default_factory=set)
    active: bool = True
    created_at: float = 0.0
    last_login: Optional[float] = None
    session_timeout_minutes: int = 30
    allowed_hours_start: Optional[str] = None  # "08:00"
    allowed_hours_end: Optional[str] = None    # "20:00"

    def to_dict(self) -> Dict:
        """Convert profile to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level.value,
            "level_name": self.level.name.lower(),
            "permissions": sorted(list(self.permissions)),
            "active": self.active,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }


class ProfileManager:
    """
    Manages user profiles in a SQLite database.

    Handles creation, retrieval, update, and deactivation of
    user profiles with secure passphrase storage.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or PROFILES_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        """Initialize the profiles database schema."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    level INTEGER NOT NULL,
                    passphrase_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    permissions TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    last_login REAL,
                    session_timeout_minutes INTEGER DEFAULT 30,
                    allowed_hours_start TEXT,
                    allowed_hours_end TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS failed_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    spoken_text TEXT,
                    ip_source TEXT DEFAULT 'local'
                )
            """)

            conn.commit()
            log.info(f"Profiles database initialized at {self.db_path}")
        finally:
            conn.close()

    def _row_to_profile(self, row: sqlite3.Row) -> UserProfile:
        """Convert a database row to a UserProfile."""
        return UserProfile(
            id=row["id"],
            name=row["name"],
            level=UserLevel(row["level"]),
            passphrase_hash=row["passphrase_hash"],
            salt=row["salt"],
            permissions=set(json.loads(row["permissions"])),
            active=bool(row["active"]),
            created_at=row["created_at"],
            last_login=row["last_login"],
            session_timeout_minutes=row["session_timeout_minutes"] or 30,
            allowed_hours_start=row["allowed_hours_start"],
            allowed_hours_end=row["allowed_hours_end"],
        )

    def create_profile(
        self,
        name: str,
        passphrase: str,
        level: UserLevel,
        permissions: Optional[Set[str]] = None,
        session_timeout_minutes: int = 30,
        allowed_hours_start: Optional[str] = None,
        allowed_hours_end: Optional[str] = None,
    ) -> UserProfile:
        """
        Create a new user profile.

        Args:
            name: Display name for the user.
            passphrase: Plain text passphrase (will be hashed).
            level: Access level (OWNER, CO_OWNER, COMMON).
            permissions: Custom permissions (None = defaults for level).
            session_timeout_minutes: Session timeout (0 = no timeout).
            allowed_hours_start: Start of allowed access hours.
            allowed_hours_end: End of allowed access hours.

        Returns:
            The created UserProfile.

        Raises:
            ValueError: If name already exists or invalid level.
        """
        if permissions is None:
            permissions = get_default_permissions(level)

        salt = generate_salt()
        phash = hash_passphrase(passphrase, salt)

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                INSERT INTO profiles
                    (name, level, passphrase_hash, salt, permissions, active,
                     created_at, session_timeout_minutes,
                     allowed_hours_start, allowed_hours_end)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    name,
                    level.value,
                    phash,
                    salt,
                    json.dumps(sorted(list(permissions))),
                    time.time(),
                    session_timeout_minutes,
                    allowed_hours_start,
                    allowed_hours_end,
                ),
            )
            conn.commit()

            profile = self.get_profile_by_id(cursor.lastrowid)
            log.info(
                f"Profile created: {name} (Level {level.value} — {level.name})"
            )
            return profile

        except sqlite3.IntegrityError:
            raise ValueError(f"Profile with name '{name}' already exists")
        finally:
            conn.close()

    def get_profile_by_id(self, profile_id: int) -> Optional[UserProfile]:
        """Get a profile by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
            return self._row_to_profile(row) if row else None
        finally:
            conn.close()

    def get_profile_by_name(self, name: str) -> Optional[UserProfile]:
        """Get a profile by name (case-insensitive)."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM profiles WHERE LOWER(name) = LOWER(?) AND active = 1",
                (name,),
            ).fetchone()
            return self._row_to_profile(row) if row else None
        finally:
            conn.close()

    def get_all_profiles(self, include_inactive: bool = False) -> List[UserProfile]:
        """Get all profiles."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM profiles"
            if not include_inactive:
                query += " WHERE active = 1"
            query += " ORDER BY level ASC, name ASC"

            rows = conn.execute(query).fetchall()
            return [self._row_to_profile(row) for row in rows]
        finally:
            conn.close()

    def find_profile_by_passphrase(self, passphrase: str) -> Optional[UserProfile]:
        """
        Find a profile matching the given passphrase.

        Iterates through all active profiles and checks the hash.
        This is the primary authentication method.

        Args:
            passphrase: The spoken/typed passphrase.

        Returns:
            Matching UserProfile or None.
        """
        profiles = self.get_all_profiles()

        for profile in profiles:
            computed_hash = hash_passphrase(passphrase, profile.salt)
            if computed_hash == profile.passphrase_hash:
                # Update last login
                self._update_last_login(profile.id)
                return profile

        return None

    def update_permissions(
        self, profile_id: int, permissions: Set[str]
    ) -> bool:
        """Update permissions for a profile."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE profiles SET permissions = ? WHERE id = ?",
                (json.dumps(sorted(list(permissions))), profile_id),
            )
            conn.commit()
            log.info(f"Permissions updated for profile {profile_id}")
            return True
        finally:
            conn.close()

    def deactivate_profile(self, profile_id: int) -> bool:
        """Deactivate (soft-delete) a profile."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE profiles SET active = 0 WHERE id = ?", (profile_id,)
            )
            conn.commit()
            log.info(f"Profile {profile_id} deactivated")
            return True
        finally:
            conn.close()

    def activate_profile(self, profile_id: int) -> bool:
        """Re-activate a deactivated profile."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE profiles SET active = 1 WHERE id = ?", (profile_id,)
            )
            conn.commit()
            log.info(f"Profile {profile_id} re-activated")
            return True
        finally:
            conn.close()

    def change_passphrase(
        self, profile_id: int, new_passphrase: str
    ) -> bool:
        """Change the passphrase for a profile."""
        new_salt = generate_salt()
        new_hash = hash_passphrase(new_passphrase, new_salt)

        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE profiles SET passphrase_hash = ?, salt = ? WHERE id = ?",
                (new_hash, new_salt, profile_id),
            )
            conn.commit()
            log.info(f"Passphrase changed for profile {profile_id}")
            return True
        finally:
            conn.close()

    def _update_last_login(self, profile_id: int) -> None:
        """Update the last login timestamp."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE profiles SET last_login = ? WHERE id = ?",
                (time.time(), profile_id),
            )
            conn.commit()
        finally:
            conn.close()

    def has_owner(self) -> bool:
        """Check if an owner profile exists."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM profiles WHERE level = ? AND active = 1",
                (UserLevel.OWNER.value,),
            ).fetchone()
            return row["cnt"] > 0
        finally:
            conn.close()

    def record_failed_attempt(self, spoken_text: str = "") -> int:
        """
        Record a failed authentication attempt.

        Returns:
            Number of failed attempts in the last lockout period.
        """
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO failed_attempts (timestamp, spoken_text) VALUES (?, ?)",
                (time.time(), spoken_text),
            )
            conn.commit()

            # Count recent failures (within lockout window)
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM failed_attempts WHERE timestamp > ?",
                (time.time() - 1800,),  # 30 minutes
            ).fetchone()
            count = row["cnt"]
            log.warning(f"Failed auth attempt #{count}: '{spoken_text[:20]}...'")
            return count
        finally:
            conn.close()

    def is_locked_out(self, max_attempts: int = 3) -> bool:
        """Check if authentication is currently locked out."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM failed_attempts WHERE timestamp > ?",
                (time.time() - 1800,),
            ).fetchone()
            return row["cnt"] >= max_attempts
        finally:
            conn.close()

    def clear_failed_attempts(self) -> None:
        """Clear all failed attempt records."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM failed_attempts")
            conn.commit()
        finally:
            conn.close()
