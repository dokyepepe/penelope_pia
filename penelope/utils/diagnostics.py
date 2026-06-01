"""
Penelope diagnostics.

Fast, side-effect-light checks for the local development/runtime environment.
"""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, List, Optional

from penelope.utils.constants import DATA_DIR, LOGS_DIR, SETTINGS_FILE


@dataclass
class DiagnosticCheck:
    """One diagnostic result."""

    name: str
    ok: bool
    detail: str = ""
    required: bool = True

    @property
    def status(self) -> str:
        if self.ok:
            return "OK"
        return "FAIL" if self.required else "WARN"


CORE_IMPORTS = (
    "yaml",
    "loguru",
    "psutil",
    "cryptography",
)

OPTIONAL_IMPORTS = (
    "PyQt6",
    "ollama",
    "sounddevice",
    "numpy",
    "faster_whisper",
    "vosk",
    "pyautogui",
    "pyperclip",
    "PIL",
)


def _has_import(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _check_imports(modules: Iterable[str], required: bool) -> List[DiagnosticCheck]:
    checks = []
    for module_name in modules:
        present = _has_import(module_name)
        checks.append(
            DiagnosticCheck(
                name=f"import:{module_name}",
                ok=present,
                detail="available" if present else "missing",
                required=required,
            )
        )
    return checks


def _check_ollama() -> DiagnosticCheck:
    if shutil.which("ollama") is None:
        return DiagnosticCheck("ollama-cli", False, "ollama command not found", required=False)

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )
    except Exception as exc:
        return DiagnosticCheck("ollama-server", False, str(exc), required=False)

    if result.returncode == 0:
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        detail = "server reachable"
        if len(lines) > 1:
            detail = f"{len(lines) - 1} model(s) listed"
        return DiagnosticCheck("ollama-server", True, detail, required=False)

    detail = (result.stderr or result.stdout or "ollama list failed").strip()
    return DiagnosticCheck("ollama-server", False, detail, required=False)


def run_diagnostics() -> List[DiagnosticCheck]:
    """Run quick local diagnostics and return structured results."""
    checks: List[DiagnosticCheck] = [
        DiagnosticCheck(
            "python-version",
            sys.version_info >= (3, 11),
            platform.python_version(),
        ),
        DiagnosticCheck(
            "operating-system",
            platform.system() == "Windows",
            platform.platform(),
            required=False,
        ),
        DiagnosticCheck(
            "settings-file",
            SETTINGS_FILE.exists(),
            str(SETTINGS_FILE),
        ),
        DiagnosticCheck(
            "data-dir-parent",
            DATA_DIR.parent.exists(),
            str(DATA_DIR.parent),
            required=False,
        ),
        DiagnosticCheck(
            "logs-dir-parent",
            LOGS_DIR.parent.exists(),
            str(LOGS_DIR.parent),
            required=False,
        ),
    ]

    checks.extend(_check_imports(CORE_IMPORTS, required=True))
    checks.extend(_check_imports(OPTIONAL_IMPORTS, required=False))
    checks.append(_check_ollama())
    return checks


def format_diagnostics(checks: Optional[List[DiagnosticCheck]] = None) -> str:
    """Format diagnostics for terminal output."""
    checks = checks if checks is not None else run_diagnostics()
    width = max(len(check.name) for check in checks) if checks else 12
    lines = ["Penelope diagnostics", ""]
    for check in checks:
        lines.append(f"[{check.status:<4}] {check.name:<{width}}  {check.detail}")

    required_failures = [check for check in checks if check.required and not check.ok]
    warnings = [check for check in checks if not check.required and not check.ok]

    lines.append("")
    if required_failures:
        lines.append(f"Required failures: {len(required_failures)}")
    else:
        lines.append("Required checks passed.")

    if warnings:
        lines.append(f"Optional warnings: {len(warnings)}")

    return "\n".join(lines)


def main() -> int:
    """CLI entry point for diagnostics."""
    checks = run_diagnostics()
    print(format_diagnostics(checks))
    return 1 if any(check.required and not check.ok for check in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
