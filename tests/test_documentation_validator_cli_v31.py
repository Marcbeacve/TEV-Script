from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_documented_validator_command_uses_module_invocation() -> None:
    validation = (ROOT / "docs" / "VALIDATION.md").read_text(encoding="utf-8")
    assert "python -m tools.validate_documentation_v31 --root ." in validation
    assert "python tools/validate_documentation_v31.py --root ." not in validation


def test_validator_module_cli_runs_from_repository_root() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.validate_documentation_v31", "--root", "."],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "PASS", completed.stdout
