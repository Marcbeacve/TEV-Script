from __future__ import annotations

import json
from pathlib import Path

from tev_script import TevScriptError
from tev_script.source_total_core_v31 import compile_total_core_v31
from tools.validate_documentation_v31 import validate_documentation


ROOT = Path(__file__).resolve().parents[1]
DOMAINS = (
    "language_constructs",
    "cli_surface",
    "python_api",
    "source_profiles",
    "ir_runtime_profiles",
    "diagnostics",
    "integrations",
    "version_domains",
)


def _write_foundation(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "manual").mkdir(parents=True, exist_ok=True)
    (root / "examples" / "docs" / "v31" / "run_halt").mkdir(parents=True, exist_ok=True)
    (root / "tev_script" / "version.py").write_text(
        'PACKAGE_VERSION = "3.1.2"\n'
        'CURRENT_LANGUAGE_VERSION = "3.1.0"\n'
        'CURRENT_PROFILE = "total_core"\n'
        'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"\n'
        'ARCHIVED_V31_PACKAGE_VERSION = "3.1.0"\n',
        encoding="utf-8",
    )
    (root / "tev_script" / "cli.py").write_text("__all__ = []\n", encoding="utf-8")
    (root / "tev_script" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        "package_version = 3.1.2\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n"
        "published_predecessor_package = 3.1.1\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
                "current_language": "3.1.0",
                "domains": {
                    "package": [
                        {"version": "3.1.2", "status": "current"},
                        {"version": "3.1.1", "status": "compatible", "note": "published immutable immediate predecessor v3.1.1"},
                        {"version": "3.1.0", "status": "compatible", "note": "published immutable predecessor v3.1.0"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "manual" / "README.md").write_text("# Manual\n", encoding="utf-8")
    (root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
                "package_version": "3.1.2",
                "language_version": "3.1.0",
                "profile": "total_core",
                "phase": "TEST",
                "domains": {name: [] for name in DOMAINS},
            }
        ),
        encoding="utf-8",
    )


def test_run_case_executes_quantum_and_observes_halted(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    case_dir = tmp_path / "examples" / "docs" / "v31" / "run_halt"
    (case_dir / "main.tevs").write_text(
        'process RunHalt version "3.1.0";\n'
        'authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;\n'
        'quantum_steps 1;\n'
        'field actual = [];\n'
        'label done = halt;\n'
        'entry done;\n',
        encoding="utf-8",
    )
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_DOCUMENTATION_CASE_V1",
                "operation": "run",
                "source": "main.tevs",
                "units": {},
                "effect_inputs": {},
                "proof_admissions": [],
                "epochs": 1,
                "expected_returncode": 0,
                "expected_status": "HALTED",
                "expected_diagnostic_code": None,
            }
        ),
        encoding="utf-8",
    )
    assert validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"] == {
        "status": "PASS",
        "case_count": 1,
    }


def test_total_core_source_path_rejects_r2_effect_command_children() -> None:
    root_source = (
        'process EffectBoundary version "3.1.0";\n'
        'authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;\n'
        'quantum_steps 4;\n'
        'unit Fs profile effects;\n'
        'field actual = [];\n'
        'label Start = invoke_v4 Fs result tev.test.filesystem End;\n'
        'label End = halt;\n'
        'entry Start;\n'
    )
    child_source = (
        'script Fs version "2.0.0";\n'
        'command file.replace(Text,Text);\n'
        'action publish() {\n'
        '    request file.replace("out.txt","hello");\n'
        '}\n'
        'entry main=publish();\n'
    )

    try:
        compile_total_core_v31(
            root_source,
            unit_sources={"Fs": child_source},
            effect_inputs={"Fs": {"scenario": {}}},
        )
    except TevScriptError as exc:
        assert exc.diagnostic.code == "TEVS_V2_EFFECT_R2_REQUIRED"
    else:
        raise AssertionError("Total-Core source path must reject Effects R2 command/request children")

    filesystem = (ROOT / "docs" / "manual" / "integrations" / "filesystem.md").read_text(encoding="utf-8")
    tutorial = (ROOT / "docs" / "manual" / "tutorial" / "07-capabilities-effects.md").read_text(encoding="utf-8")
    total_core = (ROOT / "docs" / "manual" / "language-reference" / "total-core.md").read_text(encoding="utf-8")
    effects = (ROOT / "docs" / "manual" / "language-reference" / "state-events-effects.md").read_text(encoding="utf-8")

    assert "Effects R1" in filesystem and "Effects R2" in filesystem
    assert "no admite Effects R2" in filesystem
    assert "no admite children R2" in tutorial
    assert "Effects R1" in total_core and "Effects R2" in total_core
    assert "no admite Effects R2" in total_core
    assert "Effects R1" in effects and "Effects R2" in effects
    assert "no incorpora Effects R2" in effects
