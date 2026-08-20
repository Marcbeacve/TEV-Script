from __future__ import annotations

import json
from pathlib import Path

from tools.validate_documentation_v31 import validate_documentation


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

FINAL_LANGUAGE = {
    "apply", "authority", "branch_fact", "capabilities", "comments", "composition",
    "continuations", "declarations", "effects", "entry", "events", "exact_values",
    "expressions", "field", "functions", "halt", "identifiers", "invoke_v4", "jump",
    "label", "literals", "modules", "operators", "process", "proof_admission",
    "quantum_steps", "recursion_bounds", "semantic_process", "source_to_ir", "state",
    "transformation", "types", "unit",
}
FINAL_SOURCE_PROFILES = {
    "2.0.0:v2-compatible",
    "3.0.0:semantic_process",
    "3.1.0:total_core",
}
FINAL_IR_RUNTIME = {
    "program_ir:2:linked",
    "program_ir:3:portable",
    "program_ir:4:effects",
    "program_ir:4:pure",
    "program_ir:4:recursive",
    "program_ir:5:semantic_process",
    "program_ir:5:total_core",
    "runtime_abi:v5-total-v1:total_core",
}
FINAL_INTEGRATIONS = {"browser-wasm", "csharp", "filesystem", "javascript", "python", "unity", "wasi"}


def _identity(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True)
    (root / "spec").mkdir(parents=True)
    (root / "tev_script" / "version.py").write_text(
        'PACKAGE_VERSION = "3.1.2"\n'
        'CURRENT_LANGUAGE_VERSION = "3.1.0"\n'
        'CURRENT_PROFILE = "total_core"\n'
        'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"\n'
        'ARCHIVED_V31_PACKAGE_VERSION = "3.1.0"\n', encoding="utf-8"
    )
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        "package_version = 3.1.2\nlanguage_version = 3.1.0\ncurrent_profile = total_core\npublished_predecessor_package = 3.1.1\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(json.dumps({
        "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
        "current_language": "3.1.0",
        "domains": {"package": [
            {"version":"3.1.2","status":"current"},
            {"version":"3.1.1","status":"compatible","note":"published immutable immediate predecessor v3.1.1"},
            {"version":"3.1.0","status":"compatible","note":"published immutable predecessor v3.1.0"},
        ]},
    }), encoding="utf-8")
    (root / "tev_script" / "cli.py").write_text("__all__ = []\n", encoding="utf-8")
    (root / "tev_script" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (root / "spec" / "AUTHORITY.md").write_text("authority\n", encoding="utf-8")


def _required_docs() -> tuple[str, ...]:
    tutorial = ["README.md"] + [
        "01-values-exactness.md", "02-names-bindings-expressions.md", "03-control-bounds.md",
        "04-functions-types.md", "05-data-models.md", "06-state-events.md",
        "07-capabilities-effects.md", "08-modules-composition.md", "09-field-transformation-apply.md",
        "10-processes-continuations.md", "11-v4-units.md", "12-total-core.md",
        "13-proof-admissions.md", "14-checkpoints-replay.md", "15-complete-application.md",
    ]
    language = [
        "README.md", "lexical.md", "values-and-types.md", "expressions.md",
        "declarations-and-functions.md", "control-and-bounds.md", "state-events-effects.md",
        "modules.md", "semantic-process.md", "field-transformation-apply.md", "total-core.md",
        "proof-admissions.md", "source-to-ir.md",
    ]
    howto = [
        "README.md", "build-and-run.md", "multi-unit.md", "effects-capabilities.md",
        "diagnostics.md", "proof-admissions.md", "checkpoints-replay.md",
    ]
    integrations = [
        "README.md", "python.md", "javascript.md", "csharp.md", "unity.md",
        "browser-wasm.md", "wasi.md", "filesystem.md",
    ]
    internals = [
        "README.md", "pipeline.md", "semantic-identity.md", "ir-strata.md",
        "runtime-boundaries.md", "proof-capability-boundaries.md", "validation-architecture.md",
    ]
    result = ["docs/manual/README.md", "docs/manual/faq.md"]
    result += [f"docs/manual/tutorial/{name}" for name in tutorial]
    result += [f"docs/manual/language-reference/{name}" for name in language]
    result += [f"docs/manual/howto/{name}" for name in howto]
    result += [f"docs/manual/integrations/{name}" for name in integrations]
    result += [f"docs/manual/internals/{name}" for name in internals]
    result += [f"docs/manual/versions/{name}" for name in ("v1.md", "v2.md", "v3.md", "v31.md", "deprecations.md")]
    return tuple(result)


def _write_docs(root: Path) -> None:
    for rel in _required_docs():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = "# Complete\n"
        if rel.endswith("/v1.md") or rel.endswith("/v2.md") or rel.endswith("/v3.md"):
            text += "\nHISTORICAL compatibility.\n"
        elif rel.endswith("/v31.md"):
            text += "\nCURRENT 3.1.0.\n"
        elif rel.endswith("/deprecations.md"):
            text += "\nDEPRECATION compatibility.\n"
        path.write_text(text, encoding="utf-8")


def _row(identifier: str) -> dict[str, str]:
    return {"id": identifier, "status": "DOCUMENTED", "page": "docs/manual/README.md", "authority": "spec/AUTHORITY.md"}


def _write_manifest(root: Path, *, complete: bool) -> None:
    domains: dict[str, list[dict[str, str]]] = {name: [] for name in DOMAINS}
    if complete:
        domains["language_constructs"] = [_row(value) for value in sorted(FINAL_LANGUAGE)]
        domains["source_profiles"] = [_row(value) for value in sorted(FINAL_SOURCE_PROFILES)]
        domains["ir_runtime_profiles"] = [_row(value) for value in sorted(FINAL_IR_RUNTIME)]
        domains["integrations"] = [_row(value) for value in sorted(FINAL_INTEGRATIONS)]
    (root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json").write_text(json.dumps({
        "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
        "package_version": "3.1.2",
        "language_version": "3.1.0",
        "profile": "total_core",
        "phase": "H_COMPLETE",
        "domains": domains,
    }), encoding="utf-8")


def test_phase_h_rejects_incomplete_semantic_and_integration_coverage(tmp_path: Path) -> None:
    _identity(tmp_path)
    _write_docs(tmp_path)
    _write_manifest(tmp_path, complete=False)
    check = validate_documentation(tmp_path)["checks"]["INTERNAL_PATHS"]
    assert check["status"] == "FAIL"
    assert check["reason"] == "INCOMPLETE_FINAL_COVERAGE"
    assert "python" in check["missing_integrations"]
    assert "invoke_v4" in check["missing_language_constructs"]


def test_phase_h_accepts_exact_final_semantic_and_integration_coverage(tmp_path: Path) -> None:
    _identity(tmp_path)
    _write_docs(tmp_path)
    _write_manifest(tmp_path, complete=True)
    check = validate_documentation(tmp_path)["checks"]["INTERNAL_PATHS"]
    assert check["status"] == "PASS"
    assert check["required_count"] == len(_required_docs())
