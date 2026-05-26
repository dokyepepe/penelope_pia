"""
Penélope — Constants & Enums
Central definitions for the entire system.
"""

from enum import Enum, IntEnum, auto
from pathlib import Path


# ============================================
# System Paths
# ============================================

PENELOPE_ROOT = Path("C:/Penelope")
DATA_DIR = PENELOPE_ROOT / "data"
LOGS_DIR = PENELOPE_ROOT / "logs"
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

PROFILES_DB_PATH = DATA_DIR / "profiles.db"
SESSIONS_DB_PATH = DATA_DIR / "sessions.db"
CLIPBOARD_DB_PATH = DATA_DIR / "clipboard.db"
CHROMA_DIR = DATA_DIR / "chroma"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"

MAIN_LOG = LOGS_DIR / "penelope.log"
CRASH_LOG = LOGS_DIR / "crash.log"
WATCHDOG_LOG = LOGS_DIR / "watchdog.log"

SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
PERSONAS_FILE = CONFIG_DIR / "personas.yaml"


# ============================================
# User Levels
# ============================================

class UserLevel(IntEnum):
    """Access levels for user profiles."""
    OWNER = 1
    CO_OWNER = 2
    COMMON = 3


# ============================================
# System Modes
# ============================================

class SystemMode(str, Enum):
    """Operating modes for Penélope."""
    NORMAL = "normal"
    MORNING = "morning"
    WORK = "work"
    ENTERTAINMENT = "entertainment"
    NIGHT = "night"
    SILENT = "silent"
    GAME = "game"
    POWER = "power"


# ============================================
# Process Status
# ============================================

class ProcessStatus(str, Enum):
    """Status of monitored processes."""
    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    DEGRADED = "degraded"


# ============================================
# Event Types (Event Bus)
# ============================================

class EventType(str, Enum):
    """Internal event types for the pub/sub bus."""
    # Voice pipeline
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING_STARTED = "listening_started"
    LISTENING_STOPPED = "listening_stopped"
    TRANSCRIPTION_READY = "transcription_ready"
    TTS_STARTED = "tts_started"
    TTS_FINISHED = "tts_finished"

    # Authentication
    AUTH_REQUESTED = "auth_requested"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    AUTH_LOCKED = "auth_locked"
    SESSION_STARTED = "session_started"
    SESSION_EXPIRED = "session_expired"
    SESSION_LOCKED = "session_locked"

    # Commands
    COMMAND_RECEIVED = "command_received"
    COMMAND_EXECUTING = "command_executing"
    COMMAND_COMPLETED = "command_completed"
    COMMAND_FAILED = "command_failed"

    # AI
    LLM_RESPONSE_STARTED = "llm_response_started"
    LLM_RESPONSE_CHUNK = "llm_response_chunk"
    LLM_RESPONSE_COMPLETE = "llm_response_complete"
    LLM_OFFLINE = "llm_offline"

    # System
    MODE_CHANGED = "mode_changed"
    PROCESS_CRASHED = "process_crashed"
    PROCESS_RESTARTED = "process_restarted"
    HEALTH_WARNING = "health_warning"
    HEALTH_CRITICAL = "health_critical"
    SYSTEM_SHUTDOWN = "system_shutdown"

    # UI
    HUD_UPDATE = "hud_update"
    RADIAL_MENU_OPENED = "radial_menu_opened"
    RADIAL_MENU_CLOSED = "radial_menu_closed"
    NOTIFICATION = "notification"


# ============================================
# Intent Categories
# ============================================

class IntentCategory(str, Enum):
    """Categories for parsed user intents."""
    SYSTEM_COMMAND = "system_command"       # Open app, volume, shutdown
    APP_CONTROL = "app_control"            # Control specific apps
    CONVERSATION = "conversation"          # Chat with AI
    CONFIGURATION = "configuration"        # Change settings
    USER_MANAGEMENT = "user_management"    # Add/remove profiles
    INFORMATION = "information"            # Ask system info
    AUTOMATION = "automation"              # Routines, chained actions
    MODE_CHANGE = "mode_change"            # Change operating mode
    SESSION_CONTROL = "session_control"    # Lock, logout, etc.
    UNKNOWN = "unknown"


# ============================================
# HUD States
# ============================================

class HudState(str, Enum):
    """Visual states for the system tray icon."""
    IDLE = "idle"                  # Pulsing slow — waiting for wake word
    LISTENING = "listening"        # Pulsing fast — capturing audio
    PROCESSING = "processing"     # Spinning — processing response
    SPEAKING = "speaking"         # Active — TTS playing
    ERROR = "error"               # Static — error/degraded mode


# ============================================
# Managed Processes
# ============================================

MANAGED_PROCESSES = {
    "penelope_core": {
        "description": "AI core and voice pipeline",
        "restart_delay_seconds": 5,
        "critical": True,
    },
    "ollama_server": {
        "description": "Local LLM server",
        "restart_delay_seconds": 5,
        "critical": True,
    },
    "wake_word_daemon": {
        "description": "Wake word detector (always-on)",
        "restart_delay_seconds": 0,
        "critical": True,
    },
    "hud_overlay": {
        "description": "Visual HUD interface",
        "restart_delay_seconds": 3,
        "critical": False,
    },
    "tray_icon": {
        "description": "System tray icon",
        "restart_delay_seconds": 0,
        "critical": False,
    },
}


# ============================================
# Default Permissions by Level
# ============================================

OWNER_PERMISSIONS = [
    "open_app", "close_app", "volume_control", "screenshot",
    "shutdown", "restart", "airplane_mode", "task_manager",
    "empty_recycle_bin", "network_info", "clipboard_history",
    "manage_users", "manage_permissions", "change_settings",
    "change_mode", "view_logs", "file_management",
    "send_email", "window_management", "lock_session",
    "system_info", "conversation", "automation",
]

CO_OWNER_DEFAULT_PERMISSIONS = [
    "open_app", "close_app", "volume_control", "screenshot",
    "network_info", "clipboard_history", "change_mode",
    "window_management", "lock_session", "system_info",
    "conversation", "file_management",
]

COMMON_DEFAULT_PERMISSIONS = [
    "open_app", "volume_control", "network_info",
    "system_info", "conversation",
]
