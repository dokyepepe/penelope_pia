"""
Penélope — Permissions System
Permission enum and decorator for access control.
"""

import functools
from enum import Enum, auto
from typing import Callable, Optional, Set

from penelope.utils.constants import (
    UserLevel,
    OWNER_PERMISSIONS,
    CO_OWNER_DEFAULT_PERMISSIONS,
    COMMON_DEFAULT_PERMISSIONS,
)
from penelope.utils.logger import get_logger

log = get_logger(__name__)


class Permission(str, Enum):
    """All possible permissions in the Penélope system."""
    # Application control
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"

    # Media
    VOLUME_CONTROL = "volume_control"

    # System
    SCREENSHOT = "screenshot"
    SHUTDOWN = "shutdown"
    RESTART = "restart"
    AIRPLANE_MODE = "airplane_mode"
    TASK_MANAGER = "task_manager"
    EMPTY_RECYCLE_BIN = "empty_recycle_bin"
    NETWORK_INFO = "network_info"
    SYSTEM_INFO = "system_info"

    # Data
    CLIPBOARD_HISTORY = "clipboard_history"
    FILE_MANAGEMENT = "file_management"
    SEND_EMAIL = "send_email"

    # Windows
    WINDOW_MANAGEMENT = "window_management"

    # Session
    LOCK_SESSION = "lock_session"

    # User management (Owner only)
    MANAGE_USERS = "manage_users"
    MANAGE_PERMISSIONS = "manage_permissions"

    # Settings
    CHANGE_SETTINGS = "change_settings"
    CHANGE_MODE = "change_mode"
    VIEW_LOGS = "view_logs"

    # AI
    CONVERSATION = "conversation"
    AUTOMATION = "automation"


def get_default_permissions(level: UserLevel) -> Set[str]:
    """
    Get the default permission set for a user level.

    Args:
        level: The user level.

    Returns:
        Set of permission strings.
    """
    if level == UserLevel.OWNER:
        return set(OWNER_PERMISSIONS)
    elif level == UserLevel.CO_OWNER:
        return set(CO_OWNER_DEFAULT_PERMISSIONS)
    else:
        return set(COMMON_DEFAULT_PERMISSIONS)


def has_permission(user_permissions: Set[str], required: Permission) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user_permissions: The user's permission set.
        required: The permission to check.

    Returns:
        True if the user has the permission.
    """
    return required.value in user_permissions


def requires_permission(permission: Permission) -> Callable:
    """
    Decorator to protect functions with permission checks.

    The decorated function must accept a `session` keyword argument
    (or first positional argument) containing the active session
    with a `permissions` attribute.

    Usage:
        @requires_permission(Permission.SHUTDOWN)
        async def shutdown_computer(session, delay=0):
            ...

    Args:
        permission: The required permission.

    Returns:
        Decorated function that checks permissions before execution.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            session = kwargs.get("session") or (args[0] if args else None)
            if session is None:
                log.warning(f"Permission check failed: no session for {func.__name__}")
                return {"error": "Nenhuma sessão ativa.", "denied": True}

            user_perms = getattr(session, "permissions", set())
            if not has_permission(user_perms, permission):
                log.warning(
                    f"Permission denied: {permission.value} for user "
                    f"{getattr(session, 'user_name', 'unknown')}"
                )
                return {
                    "error": f"Você não tem permissão para '{permission.value}'.",
                    "denied": True,
                }

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            session = kwargs.get("session") or (args[0] if args else None)
            if session is None:
                log.warning(f"Permission check failed: no session for {func.__name__}")
                return {"error": "Nenhuma sessão ativa.", "denied": True}

            user_perms = getattr(session, "permissions", set())
            if not has_permission(user_perms, permission):
                log.warning(
                    f"Permission denied: {permission.value} for user "
                    f"{getattr(session, 'user_name', 'unknown')}"
                )
                return {
                    "error": f"Você não tem permissão para '{permission.value}'.",
                    "denied": True,
                }

            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
