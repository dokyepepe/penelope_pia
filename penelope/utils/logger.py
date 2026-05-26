"""
Penélope — Logging System
Centralized logging with loguru.
"""

import sys
from pathlib import Path

from loguru import logger

from penelope.utils.constants import LOGS_DIR, MAIN_LOG, CRASH_LOG, WATCHDOG_LOG


def setup_logging(debug: bool = False) -> None:
    """
    Configure the Penélope logging system.

    Sets up multiple log sinks:
    - Console (colorized, INFO+)
    - Main log file (DEBUG+, rotated daily)
    - Crash log (ERROR+, separate file)
    - Watchdog log (WARNING+, separate file)

    Args:
        debug: If True, console output is set to DEBUG level.
    """
    # Ensure log directories exist
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove default logger
    logger.remove()

    # Console sink — colorized output
    console_level = "DEBUG" if debug else "INFO"
    logger.add(
        sys.stderr,
        level=console_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=debug,
    )

    # Main log file — rotated daily, kept for 30 days
    logger.add(
        str(MAIN_LOG),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
        rotation="1 day",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,  # Thread-safe
    )

    # Crash log — errors and above
    logger.add(
        str(CRASH_LOG),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}\n{exception}",
        rotation="10 MB",
        retention="90 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,
    )

    # Watchdog log — warnings about process health
    logger.add(
        str(WATCHDOG_LOG),
        level="WARNING",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        rotation="5 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
        filter=lambda record: "watchdog" in record["name"].lower()
                              or "health" in record["name"].lower(),
    )

    logger.info("🟣 Penélope logging initialized")


def get_logger(module_name: str):
    """
    Get a contextual logger for a specific module.

    Args:
        module_name: Name of the calling module.

    Returns:
        A loguru logger bound to the given module name.
    """
    return logger.bind(name=module_name)
