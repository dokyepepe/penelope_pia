"""
Penélope — System Information Utilities
Detect GPU, RAM, CPU, network info, and other hardware details.
"""

import platform
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import psutil

from penelope.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class GpuInfo:
    """GPU hardware information."""
    name: str = "Unknown"
    vram_total_mb: int = 0
    vram_used_mb: int = 0
    vram_free_mb: int = 0
    temperature: Optional[float] = None
    driver_version: str = "Unknown"
    cuda_available: bool = False


@dataclass
class SystemSnapshot:
    """Complete system state snapshot."""
    # CPU
    cpu_name: str = ""
    cpu_cores: int = 0
    cpu_threads: int = 0
    cpu_percent: float = 0.0
    cpu_freq_mhz: float = 0.0

    # Memory
    ram_total_gb: float = 0.0
    ram_used_gb: float = 0.0
    ram_free_gb: float = 0.0
    ram_percent: float = 0.0

    # Disk
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_free_gb: float = 0.0

    # GPU
    gpu: GpuInfo = field(default_factory=GpuInfo)

    # Network
    ip_address: str = "Unknown"
    hostname: str = "Unknown"

    # OS
    os_name: str = ""
    os_version: str = ""

    # Uptime
    uptime_seconds: float = 0.0


def get_gpu_info() -> GpuInfo:
    """
    Detect NVIDIA GPU information using nvidia-smi.

    Returns:
        GpuInfo dataclass with GPU details.
    """
    info = GpuInfo()

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )

        if result.returncode == 0 and result.stdout.strip():
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            if len(parts) >= 6:
                info.name = parts[0]
                info.vram_total_mb = int(float(parts[1]))
                info.vram_used_mb = int(float(parts[2]))
                info.vram_free_mb = int(float(parts[3]))
                info.temperature = float(parts[4]) if parts[4] != "N/A" else None
                info.driver_version = parts[5]
                info.cuda_available = True
                log.debug(f"GPU detected: {info.name} ({info.vram_total_mb}MB VRAM)")
    except FileNotFoundError:
        log.debug("nvidia-smi not found — no NVIDIA GPU detected")
    except Exception as e:
        log.warning(f"Failed to get GPU info: {e}")

    return info


def get_system_snapshot() -> SystemSnapshot:
    """
    Capture a complete system state snapshot.

    Returns:
        SystemSnapshot with CPU, RAM, disk, GPU, and network info.
    """
    snap = SystemSnapshot()

    # CPU
    try:
        snap.cpu_name = platform.processor() or "Unknown CPU"
        snap.cpu_cores = psutil.cpu_count(logical=False) or 0
        snap.cpu_threads = psutil.cpu_count(logical=True) or 0
        snap.cpu_percent = psutil.cpu_percent(interval=0.1)
        freq = psutil.cpu_freq()
        if freq:
            snap.cpu_freq_mhz = freq.current
    except Exception as e:
        log.warning(f"Failed to get CPU info: {e}")

    # Memory
    try:
        mem = psutil.virtual_memory()
        snap.ram_total_gb = round(mem.total / (1024 ** 3), 2)
        snap.ram_used_gb = round(mem.used / (1024 ** 3), 2)
        snap.ram_free_gb = round(mem.available / (1024 ** 3), 2)
        snap.ram_percent = mem.percent
    except Exception as e:
        log.warning(f"Failed to get memory info: {e}")

    # Disk (system drive)
    try:
        disk = psutil.disk_usage("C:\\")
        snap.disk_total_gb = round(disk.total / (1024 ** 3), 2)
        snap.disk_used_gb = round(disk.used / (1024 ** 3), 2)
        snap.disk_free_gb = round(disk.free / (1024 ** 3), 2)
    except Exception as e:
        log.warning(f"Failed to get disk info: {e}")

    # GPU
    snap.gpu = get_gpu_info()

    # Network
    try:
        snap.hostname = socket.gethostname()
        snap.ip_address = socket.gethostbyname(snap.hostname)
    except Exception:
        snap.ip_address = "Unknown"

    # OS
    snap.os_name = platform.system()
    snap.os_version = platform.version()

    # Uptime
    try:
        snap.uptime_seconds = psutil.boot_time()
        import time
        snap.uptime_seconds = time.time() - snap.uptime_seconds
    except Exception:
        pass

    return snap


def get_recommended_llm_model(gpu: Optional[GpuInfo] = None) -> str:
    """
    Recommend an LLM model based on available VRAM.

    Args:
        gpu: GPU info (if None, will detect automatically).

    Returns:
        Recommended Ollama model name.
    """
    if gpu is None:
        gpu = get_gpu_info()

    if gpu.vram_total_mb >= 8000:
        return "llama3.1:8b"
    elif gpu.vram_total_mb >= 4000:
        return "phi3:mini"
    elif gpu.vram_total_mb >= 2000:
        return "tinyllama:1.1b"
    else:
        # CPU-only fallback
        return "phi3:mini"


def format_uptime(seconds: float) -> str:
    """
    Format uptime in a human-readable string.

    Args:
        seconds: Uptime in seconds.

    Returns:
        Formatted string like "2d 5h 30m".
    """
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return " ".join(parts)
