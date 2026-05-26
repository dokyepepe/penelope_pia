"""
Penélope — Health Monitor
Continuous monitoring of system resources (CPU, RAM, GPU, disk).
"""

import threading
import time
from typing import Dict, Optional

import psutil

from penelope.core.event_bus import get_event_bus
from penelope.utils.constants import EventType
from penelope.utils.logger import get_logger
from penelope.utils.system_info import get_gpu_info, get_system_snapshot, SystemSnapshot

log = get_logger("health")


class HealthMonitor:
    """
    Monitors system health and alerts on resource thresholds.

    Tracks CPU, RAM, GPU temperature/VRAM, and disk usage.
    Emits events when thresholds are exceeded.
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        ram_warning_pct: float = 85.0,
        ram_critical_pct: float = 95.0,
        gpu_temp_warning: float = 80.0,
        gpu_temp_critical: float = 90.0,
        disk_warning_pct: float = 85.0,
    ) -> None:
        self.check_interval = check_interval
        self.ram_warning_pct = ram_warning_pct
        self.ram_critical_pct = ram_critical_pct
        self.gpu_temp_warning = gpu_temp_warning
        self.gpu_temp_critical = gpu_temp_critical
        self.disk_warning_pct = disk_warning_pct

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_snapshot: Optional[SystemSnapshot] = None
        self._penelope_process: Optional[psutil.Process] = None
        self.bus = get_event_bus()

    def start(self) -> None:
        """Start the health monitoring loop."""
        if self._running:
            return

        try:
            self._penelope_process = psutil.Process()
        except Exception:
            pass

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="health_monitor",
            daemon=True,
        )
        self._thread.start()
        log.info(f"Health monitor started (interval={self.check_interval}s)")

    def stop(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        log.info("Health monitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_health()
                time.sleep(self.check_interval)
            except Exception as e:
                log.error(f"Health check error: {e}")
                time.sleep(5.0)

    def _check_health(self) -> None:
        """Run all health checks."""
        snapshot = get_system_snapshot()
        self._last_snapshot = snapshot

        # RAM check
        if snapshot.ram_percent >= self.ram_critical_pct:
            log.error(f"CRITICAL: RAM usage at {snapshot.ram_percent:.1f}%")
            self.bus.emit_sync(
                EventType.HEALTH_CRITICAL,
                resource="ram",
                value=snapshot.ram_percent,
                message=f"RAM crítica: {snapshot.ram_percent:.1f}%",
            )
        elif snapshot.ram_percent >= self.ram_warning_pct:
            log.warning(f"WARNING: RAM usage at {snapshot.ram_percent:.1f}%")
            self.bus.emit_sync(
                EventType.HEALTH_WARNING,
                resource="ram",
                value=snapshot.ram_percent,
                message=f"RAM alta: {snapshot.ram_percent:.1f}%",
            )

        # GPU temperature
        if snapshot.gpu.temperature is not None:
            if snapshot.gpu.temperature >= self.gpu_temp_critical:
                log.error(f"CRITICAL: GPU temp at {snapshot.gpu.temperature}°C")
                self.bus.emit_sync(
                    EventType.HEALTH_CRITICAL,
                    resource="gpu_temp",
                    value=snapshot.gpu.temperature,
                    message=f"GPU superaquecendo: {snapshot.gpu.temperature}°C",
                )
            elif snapshot.gpu.temperature >= self.gpu_temp_warning:
                log.warning(f"WARNING: GPU temp at {snapshot.gpu.temperature}°C")
                self.bus.emit_sync(
                    EventType.HEALTH_WARNING,
                    resource="gpu_temp",
                    value=snapshot.gpu.temperature,
                    message=f"GPU quente: {snapshot.gpu.temperature}°C",
                )

        # Disk space
        if snapshot.disk_total_gb > 0:
            disk_pct = (snapshot.disk_used_gb / snapshot.disk_total_gb) * 100
            if disk_pct >= self.disk_warning_pct:
                log.warning(f"WARNING: Disk usage at {disk_pct:.1f}%")
                self.bus.emit_sync(
                    EventType.HEALTH_WARNING,
                    resource="disk",
                    value=disk_pct,
                    message=f"Disco quase cheio: {snapshot.disk_free_gb:.1f}GB livres",
                )

        # Check Penélope's own memory usage
        self._check_self_memory()

    def _check_self_memory(self) -> None:
        """Monitor Penélope's own memory usage for leaks."""
        if self._penelope_process is None:
            return

        try:
            mem = self._penelope_process.memory_info()
            rss_mb = mem.rss / (1024 * 1024)

            # Alert if Penélope itself uses > 2GB RAM (potential leak)
            if rss_mb > 2048:
                log.warning(
                    f"Penélope memory usage high: {rss_mb:.0f}MB — "
                    f"possible memory leak"
                )
                self.bus.emit_sync(
                    EventType.HEALTH_WARNING,
                    resource="penelope_ram",
                    value=rss_mb,
                    message=f"Penélope usando {rss_mb:.0f}MB de RAM",
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def get_snapshot(self) -> Optional[SystemSnapshot]:
        """Get the latest system snapshot."""
        return self._last_snapshot

    def get_penelope_usage(self) -> Dict:
        """Get Penélope's own resource usage."""
        if self._penelope_process is None:
            return {"error": "Process not tracked"}

        try:
            mem = self._penelope_process.memory_info()
            cpu = self._penelope_process.cpu_percent(interval=0.1)
            return {
                "ram_mb": round(mem.rss / (1024 * 1024), 1),
                "cpu_percent": cpu,
                "threads": self._penelope_process.num_threads(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"error": "Process not accessible"}
