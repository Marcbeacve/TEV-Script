from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True

PYTHON_SURFACE = (
    "tev_script/__init__.py",
    "tev_script/artifact_write_v1.py",
    "tev_script/cli_v1.py",
    "tev_script/describe_v1.py",
    "tev_script/descriptor_v1.py",
    "tev_script/lsp_v1.py",
    "tev_script/project_v1.py",
    "tev_script/runtime_cli_v3.py",
    "tools/validate_v1_governance.py",
)

JSON_SURFACE = (
    "CANONICAL_INDEX.json",
    "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
    "schemas/tev_script_descriptor_v3.schema.json",
    "schemas/tev_script_project_v1.schema.json",
    "examples/v1/ecosystem/tevscript.project.json",
    "editors/vscode/package.json",
    "editors/vscode/language-configuration.json",
    "editors/vscode/syntaxes/tevscript.tmLanguage.json",
    "editors/vscode/snippets/tevscript.json",
)

TEST_PATTERNS = (
    "test_v1_artifact_write.py",
    "test_v1_cli_full.py",
    "test_v1_descriptor.py",
    "test_v1_descriptor_schema_cardinality.py",
    "test_v1_editor_assets.py",
    "test_v1_examples.py",
    "test_v1_lsp.py",
    "test_v1_project.py",
    "test_v1_public_api.py",
    "test_v1_runtime_cli_v3.py",
)


def fail(label: str, detail: str) -> int:
    print(label + "=FAIL " + detail)
    print("TEV_SCRIPT_V1_TOOLING_CLOSURE=FAIL")
    return 1


def main() -> int:
    print("TEV_SCRIPT_V1_TOOLING_CLOSURE_SCHEMA=V1")

    try:
        for relative in PYTHON_SURFACE:
            path = ROOT / relative
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
    except (OSError, UnicodeError, SyntaxError) as exc:
        return fail("TEV_SCRIPT_V1_TOOLING_PYTHON_SYNTAX", f"{type(exc).__name__}:{exc}")
    print(f"TEV_SCRIPT_V1_TOOLING_PYTHON_SYNTAX=PASS count={len(PYTHON_SURFACE)}")

    try:
        for relative in JSON_SURFACE:
            value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return fail("TEV_SCRIPT_V1_TOOLING_JSON", relative + ":root_not_object")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return fail("TEV_SCRIPT_V1_TOOLING_JSON", f"{type(exc).__name__}:{exc}")
    print(f"TEV_SCRIPT_V1_TOOLING_JSON=PASS count={len(JSON_SURFACE)}")

    governance = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_v1_governance.py")],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if governance.returncode != 0:
        if governance.stdout:
            print("TEV_SCRIPT_V1_TOOLING_GOVERNANCE_STDOUT=" + governance.stdout[-8000:].replace("\n", "\\n"))
        if governance.stderr:
            print("TEV_SCRIPT_V1_TOOLING_GOVERNANCE_STDERR=" + governance.stderr[-8000:].replace("\n", "\\n"))
        return fail("TEV_SCRIPT_V1_TOOLING_GOVERNANCE", "COMMAND_FAILED")
    if "TEV_SCRIPT_V1_GOVERNANCE=PASS" not in governance.stdout.splitlines():
        return fail("TEV_SCRIPT_V1_TOOLING_GOVERNANCE", "PASS_WITNESS_MISSING")
    print("TEV_SCRIPT_V1_TOOLING_GOVERNANCE=PASS")

    suite = unittest.TestSuite()
    for pattern in TEST_PATTERNS:
        suite.addTests(
            unittest.defaultTestLoader.discover(
                str(ROOT / "tests"),
                pattern=pattern,
                top_level_dir=str(ROOT),
            )
        )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"TEV_SCRIPT_V1_TOOLING_TESTS_RUN={result.testsRun}")
    if result.skipped:
        return fail("TEV_SCRIPT_V1_TOOLING_TESTS", f"unexpected_skips={len(result.skipped)}")
    if not result.wasSuccessful():
        return fail("TEV_SCRIPT_V1_TOOLING_TESTS", "FAILED")
    print("TEV_SCRIPT_V1_TOOLING_TESTS=PASS")

    print("TEV_SCRIPT_V1_TOOLING_DESCRIPTOR=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TOOLING_PROJECT_MANIFEST=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TOOLING_ARTIFACT_COMMIT=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TOOLING_IR_V3_READ_ONLY_CLI=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TOOLING_LSP=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TOOLING_VSCODE_STATIC_SUPPORT=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TOOLING_CLOSURE=PASS_CANDIDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
