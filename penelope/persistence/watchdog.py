"""
Penélope — Process Watchdog
Monitors and auto-restarts critical system processes.
"""

import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import psutil

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType, MANAGED_PROCESSES
from penelope.utils.logger import get_logger

log = get_logger("watchdog")


@dataclass
class WatchedProcess:
    """A process being monitored by the watchdog."""
    name: str
    description: str
    restart_delay_seconds: float = 5.0
    critical: bool = True
    pid: Optional[int] = None
    start_func: Optional[Callable] = None
    process_name: Optional[str] = None  # exe name to find
    restart_count: int = 0
    last_restart: float = 0.0
    max_restarts_per_minute: int = 5
    status: str = "stopped"


class ProcessWatchdog:
    """
    Monitors critical processes and restarts them on failure.

    Detects crashes, loops, and degraded states.
    Runs as a background thread with configurable check intervals.
    """

    def __init__(self, check_interval: float = 5.0) -> None:
        self.check_interval = check_interval
        self._processes: Dict[str, WatchedProcess] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._crash_history: List[Dict] = []
        self.bus = get_event_bus()

    def register_process(
        self,
        name: str,
        description: str = "",
        restart_delay: float = 5.0,
        critical: bool = True,
        start_func: Optional[Callable] = None,
        process_name: Optional[str] = None,
        pid: Optional[int] = None,
    ) -> None:
        """
        Register a process to be monitored.

        Args:
            name: Unique identifier for the process.
            description: Human-readable description.
            restart_delay: Seconds to wait before restarting.
            critical: If True, system enters degraded mode on repeated failures.
            start_func: Callable to start/restart the process.
            process_name: Executable name to find via psutil.
            pid: Process ID to monitor directly.
        """
        self._processes[name] = WatchedProcess(
            name=name,
            description=description,
            restart_delay_seconds=restart_delay,
            critical=critical,
            start_func=start_func,
            process_name=process_name,
            pid=pid,
            status="running" if pid else "registered",
        )
        log.info(f"Watchdog registered: {name} ({description})")

    def update_pid(self, name: str, pid: int) -> None:
        """Update the PID for a watched process."""
        if name in self._processes:
            self._processes[name].pid = pid
            self._processes[name].status = "running"

    def start(self) -> None:
        """Start the watchdog monitoring loop."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="watchdog",
            daemon=True,
        )
        self._thread.start()
        log.info(f"Watchdog started (interval={self.check_interval}s)")

    def stop(self) -> None:
        """Stop the watchdog monitoring loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        log.info("Watchdog stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                for name, proc in list(self._processes.items()):
                    if not self._running:
                        break
                    self._check_process(proc)

                time.sleep(self.check_interval)

            except Exception as e:
                log.error(f"Watchdog error: {e}")
                time.sleep(1.0)

    def _check_process(self, proc: WatchedProcess) -> None:
        """Check if a process is running and restart if needed."""
        is_alive = False

        # Check by PID
        if proc.pid is not None:
            try:
                p = psutil.Process(proc.pid)
                is_alive = p.is_running() and p.status() != psutil.STATUS_ZOMBIE
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                is_alive = False

        # Check by process name
        elif proc.process_name:
            for p in psutil.process_iter(["name"]):
                try:
                    if p.info["name"] and proc.process_name.lower() in p.info["name"].lower():
                        is_alive = True
                        proc.pid = p.pid
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        if is_alive:
            if proc.status != "running":
                proc.status = "running"
            return

        # Process is dead
        if proc.status == "running":
            log.warning(f"Process crashed: {proc.name} (PID: {proc.pid})")
            proc.status = "crashed"
            proc.pid = None

            self._crash_history.append({
                "name": proc.name,
                "timestamp": time.time(),
                "restart_count": proc.restart_count,
            })

            self.bus.emit_sync(
                EventType.PROCESS_CRASHED,
                process_name=proc.name,
                description=proc.description,
                critical=proc.critical,
            )

        # Check for crash loop
        if self._is_crash_loop(proc):
            log.error(
                f"Crash loop detected for {proc.name} — entering degraded mode"
            )
            proc.status = "degraded"
            self.bus.emit_sync(
                EventType.HEALTH_CRITICAL,
                process_name=proc.name,
                message=f"Crash loop: {proc.name} restarted too many times",
            )
            return

        # Restart
        self._restart_process(proc)

    def _is_crash_loop(self, proc: WatchedProcess) -> bool:
        """Check if a process is in a crash loop."""
        now = time.time()
        recent_crashes = [
            c for c in self._crash_history
            if c["name"] == proc.name and now - c["timestamp"] < 60
        ]
        return len(recent_crashes) >= proc.max_restarts_per_minute

    def _restart_process(self, proc: WatchedProcess) -> None:
        """Attempt to restart a crashed process."""
        if proc.start_func is None:
            log.warning(f"No start function for {proc.name} — cannot restart")
            return

        # Respect restart delay
        since_last = time.time() - proc.last_restart
        if since_last < proc.restart_delay_seconds:
            remaining = proc.restart_delay_seconds - since_last
            log.debug(f"Waiting {remaining:.1f}s before restarting {proc.name}")
            time.sleep(remaining)

        try:
            log.info(f"Restarting process: {proc.name} (attempt #{proc.restart_count + 1})")
            proc.status = "restarting"
            proc.start_func()
            proc.restart_count += 1
            proc.last_restart = time.time()
            proc.status = "running"

            self.bus.emit_sync(
                EventType.PROCESS_RESTARTED,
                process_name=proc.name,
                restart_count=proc.restart_count,
            )

        except Exception as e:
            log.error(f"Failed to restart {proc.name}: {e}")
            proc.status = "crashed"

    def get_status(self) -> Dict[str, dict]:
        """Get status of all monitored processes."""
        return {
            name: {
                "description": proc.description,
                "status": proc.status,
                "pid": proc.pid,
                "restart_count": proc.restart_count,
                "critical": proc.critical,
            }
            for name, proc in self._processes.items()
        }

    def get_crash_history(self, limit: int = 20) -> List[Dict]:
        """Get recent crash history."""
        return self._crash_history[-limit:]
