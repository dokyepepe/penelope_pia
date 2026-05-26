"""
Penélope — Service Manager
Integration with NSSM to register Penélope as a Windows service.
"""

import subprocess
import platform
from pathlib import Path
from typing import Optional

from penelope.utils.logger import get_logger

log = get_logger(__name__)

SERVICE_NAME = "PenelopeAssistant"
SERVICE_DISPLAY = "Penélope AI Assistant"
SERVICE_DESC = "Assistente pessoal de IA local — sempre ativa"


class ServiceManager:
    """
    Manages Penélope as a Windows service using NSSM.

    NSSM (Non-Sucking Service Manager) allows running Python scripts
    as Windows services with auto-restart on failure.
    """

    def __init__(
        self,
        nssm_path: Optional[Path] = None,
        python_exe: Optional[Path] = None,
        script_path: Optional[Path] = None,
    ) -> None:
        self.nssm_path = nssm_path or self._find_nssm()
        self.python_exe = python_exe or Path("python")
        self.script_path = script_path

    def _find_nssm(self) -> Optional[Path]:
        """Try to find NSSM in common locations."""
        common_paths = [
            Path("C:/nssm/nssm.exe"),
            Path("C:/tools/nssm/nssm.exe"),
            Path("C:/Penelope/tools/nssm.exe"),
        ]
        for p in common_paths:
            if p.exists():
                return p

        # Try PATH
        try:
            result = subprocess.run(
                ["where", "nssm"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip().split("\n")[0])
        except Exception:
            pass

        return None

    def _run_nssm(self, *args: str) -> tuple[bool, str]:
        """Run an NSSM command."""
        if self.nssm_path is None:
            return False, "NSSM not found"

        try:
            cmd = [str(self.nssm_path)] + list(args)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            )
            output = result.stdout.strip() or result.stderr.strip()
            return result.returncode == 0, output
        except Exception as e:
            return False, str(e)

    def install_service(self, script_path: Optional[Path] = None) -> bool:
        """
        Install Penélope as a Windows service.

        Args:
            script_path: Path to the main script (penelope/main.py).

        Returns:
            True if installed successfully.
        """
        if platform.system() != "Windows":
            log.warning("Service installation only available on Windows")
            return False

        script = script_path or self.script_path
        if script is None:
            log.error("No script path provided for service installation")
            return False

        # Install the service
        success, msg = self._run_nssm(
            "install", SERVICE_NAME,
            str(self.python_exe), "-m", "penelope.main",
        )
        if not success:
            log.error(f"Failed to install service: {msg}")
            return False

        # Configure service properties
        self._run_nssm("set", SERVICE_NAME, "DisplayName", SERVICE_DISPLAY)
        self._run_nssm("set", SERVICE_NAME, "Description", SERVICE_DESC)
        self._run_nssm("set", SERVICE_NAME, "Start", "SERVICE_AUTO_START")
        self._run_nssm("set", SERVICE_NAME, "AppPriority", "HIGH_PRIORITY_CLASS")
        self._run_nssm("set", SERVICE_NAME, "AppStopMethodSkip", "6")

        # Auto-restart on failure (max 5s delay)
        self._run_nssm("set", SERVICE_NAME, "AppExit", "Default", "Restart")
        self._run_nssm("set", SERVICE_NAME, "AppRestartDelay", "5000")

        # Logging
        self._run_nssm("set", SERVICE_NAME, "AppStdout", "C:\\Penelope\\logs\\service_stdout.log")
        self._run_nssm("set", SERVICE_NAME, "AppStderr", "C:\\Penelope\\logs\\service_stderr.log")
        self._run_nssm("set", SERVICE_NAME, "AppRotateFiles", "1")
        self._run_nssm("set", SERVICE_NAME, "AppRotateBytes", "10485760")  # 10MB

        log.info("Penélope service installed successfully")
        return True

    def uninstall_service(self) -> bool:
        """Remove the Penélope service."""
        self.stop_service()
        success, msg = self._run_nssm("remove", SERVICE_NAME, "confirm")
        if success:
            log.info("Penélope service uninstalled")
        else:
            log.error(f"Failed to uninstall service: {msg}")
        return success

    def start_service(self) -> bool:
        """Start the Penélope service."""
        success, msg = self._run_nssm("start", SERVICE_NAME)
        if success:
            log.info("Penélope service started")
        else:
            log.error(f"Failed to start service: {msg}")
        return success

    def stop_service(self) -> bool:
        """Stop the Penélope service."""
        success, msg = self._run_nssm("stop", SERVICE_NAME)
        if success:
            log.info("Penélope service stopped")
        else:
            log.warning(f"Failed to stop service: {msg}")
        return success

    def restart_service(self) -> bool:
        """Restart the Penélope service."""
        success, msg = self._run_nssm("restart", SERVICE_NAME)
        if success:
            log.info("Penélope service restarted")
        else:
            log.error(f"Failed to restart service: {msg}")
        return success

    def get_status(self) -> str:
        """Get the current service status."""
        success, msg = self._run_nssm("status", SERVICE_NAME)
        if success:
            return msg.strip()
        return "unknown"

    @property
    def is_installed(self) -> bool:
        """Check if the service is installed."""
        status = self.get_status()
        return status != "unknown" and "not installed" not in status.lower()

    @property
    def nssm_available(self) -> bool:
        """Check if NSSM is available."""
        return self.nssm_path is not None and self.nssm_path.exists()
