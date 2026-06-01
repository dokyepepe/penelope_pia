"""
Penelope diagnostics tests.
"""

from penelope.utils.diagnostics import DiagnosticCheck, format_diagnostics, run_diagnostics


def test_run_diagnostics_returns_checks():
    checks = run_diagnostics()

    assert checks
    assert any(check.name == "python-version" for check in checks)
    assert all(check.status in {"OK", "FAIL", "WARN"} for check in checks)


def test_format_diagnostics_includes_summary():
    checks = [
        DiagnosticCheck("required-ok", True, "fine"),
        DiagnosticCheck("optional-missing", False, "missing", required=False),
    ]

    output = format_diagnostics(checks)

    assert "Penelope diagnostics" in output
    assert "[OK" in output
    assert "[WARN" in output
    assert "Required checks passed." in output
    assert "Optional warnings: 1" in output
