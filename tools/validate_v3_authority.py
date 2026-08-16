from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from tev_script.descriptor_v3 import v3_descriptor, verify_v3_descriptor
from tev_script.release_metadata_v3 import validate_release_metadata_v3

ROOT = Path(__file__).resolve().parents[1]
V2_BASE_SHA = "2bdb047dcad41f9d112219bd65925c25668c02e0"
MATRIX_PATH = "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json"
REQUIRED_FEATURES = frozenset({
    "MINIMAL_FIELD_TRANSFORMATION_APPLY_BASIS",
    "EPISTEMIC_TYPE_EFFECT_LAYER",
    "BOUNDED_QUANTA_CONTINUATIONS",
    "PROGRAM_IR_V5_SEMANTIC_PROCESS",
    "NATIVE_V3_SOURCE_PROFILE",
    "SOURCE_TO_IR_TRANSLATION_VALIDATION",
    "DERIVED_SEMANTIC_STDLIB",
    "EXPLICIT_V2_COMPATIBILITY_LANE",
})
REQUIRED_GOVERNED_PATHS = {
    "implementation": frozenset({
        "tev_script/cli_v3.py", "tev_script/describe_v3.py", "tev_script/descriptor_v3.py",
        "tev_script/omega_semantic_basis_v1.py", "tev_script/omega_type_effect_v1.py",
        "tev_script/program_ir_v5_semantic.py", "tev_script/release_metadata_v3.py",
        "tev_script/runtime_v5_semantic.py", "tev_script/semantic_stdlib_v1.py",
        "tev_script/source_semantic_process_v3.py", "tev_script/translation_validation_v3.py",
    }),
    "specification": frozenset({
        "docs/superpowers/specs/2026-08-16-tevscript-max-v3-primitive-basis-design.md",
        "docs/superpowers/specs/2026-08-16-tevscript-max-v3-semantic-stdlib-design.md",
        "docs/superpowers/specs/2026-08-16-tevscript-max-v3-type-effect-design.md",
        "schemas/tev-script-max-v3-basis-certify-receipt.schema.json",
        "schemas/tev-script-program-ir-v5-semantic-process.schema.json",
        "schemas/tev-script-v3-certify-full-receipt.schema.json", "schemas/tev-script-v3-descriptor.schema.json",
        "schemas/tev-script-v3-process-checkpoint.schema.json", "schemas/tev-script-v3-stable-admission-receipt.schema.json",
        "spec/TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS.md", "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json",
        "spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md",
    }),
    "packaging": frozenset({"packaging/v3/pyproject.toml", "packaging/v3/tools/tev_script_build_backend_v3.py"}),
    "tests": frozenset({
        "tests/test_cli_v3.py", "tests/test_max_v3_basis_certify.py", "tests/test_omega_semantic_basis_v1.py",
        "tests/test_omega_type_effect_v1.py", "tests/test_program_ir_v5_semantic.py", "tests/test_runtime_v5_semantic.py",
        "tests/test_semantic_stdlib_v1.py", "tests/test_source_semantic_process_v3.py", "tests/test_tevprober_max_basis_v1.py",
        "tests/test_translation_validation_v3.py", "tests/test_v3_authority.py", "tests/test_v3_certify_full.py",
        "tests/test_v3_packaging.py", "tests/test_v3_schemas_metadata.py", "tests/test_v3_stable_admission.py",
    }),
    "gates": frozenset({
        "RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY.py", "RUN_TEV_SCRIPT_V3_CERTIFY_FULL.py",
        "RUN_TEV_SCRIPT_V3_STABLE_ADMISSION.py", "tools/tevprober_max_basis_v1.py",
        "tools/tevprober_max_v3_basis_frontier.py", "tools/validate_v3_authority.py",
    }),
}
REQUIRED_AUTHORITY_FILES = frozenset({
    "spec/TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS.md", "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json",
    "spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md", "schemas/tev-script-program-ir-v5-semantic-process.schema.json",
    "schemas/tev-script-v3-certify-full-receipt.schema.json", "schemas/tev-script-v3-descriptor.schema.json",
    "schemas/tev-script-v3-process-checkpoint.schema.json", "schemas/tev-script-v3-stable-admission-receipt.schema.json",
    "tev_script/descriptor_v3.py", "tev_script/release_metadata_v3.py", "RUN_TEV_SCRIPT_V3_CERTIFY_FULL.py",
    "RUN_TEV_SCRIPT_V3_STABLE_ADMISSION.py", "tools/validate_v3_authority.py",
})


def _list_text(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return tuple(value)


def validate_v3_matrix(matrix: Mapping[str, Any], metadata: Mapping[str, Any], descriptor: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if matrix.get("schema") != "TEV_SCRIPT_V3_FEATURE_MATRIX_V1" or matrix.get("language_version") != "3.0.0" or matrix.get("program_ir_version") != "5":
        errors.append("matrix_identity")
    if matrix.get("status") != metadata.get("release_status") or matrix.get("stable") is not metadata.get("stable"):
        errors.append("release_metadata_binding")
    if matrix.get("publication_authorized") is not False or matrix.get("merge_authorized") is not False:
        errors.append("matrix_authority")
    if descriptor.get("language_version") != "3.0.0" or descriptor.get("stable") is not metadata.get("stable") or descriptor.get("promotion_authority") is not False or not verify_v3_descriptor(descriptor):
        errors.append("descriptor_binding")
    if matrix.get("native_v3_external_effects") != "NOT_SUPPORTED_IN_SEMANTIC_PROCESS_V1":
        errors.append("native_effect_boundary")
    if matrix.get("compatibility") != {"v2_semantics_reinterpreted": False, "v2_lane": "EXPLICIT_PASSTHROUGH_ONLY"}:
        errors.append("v2_compatibility_boundary")

    features = matrix.get("required_features")
    feature_map: dict[str, str] = {}
    if not isinstance(features, list):
        errors.append("required_features_shape")
    else:
        for row in features:
            if not isinstance(row, Mapping) or set(row) != {"id", "status"} or not isinstance(row.get("id"), str) or not isinstance(row.get("status"), str):
                errors.append("required_features_shape")
                continue
            if row["id"] in feature_map:
                errors.append("required_features_duplicate")
            feature_map[str(row["id"])] = str(row["status"])
        if frozenset(feature_map) != REQUIRED_FEATURES or any(value != "CLOSED" for value in feature_map.values()):
            errors.append("required_features_not_closed")

    governed = matrix.get("governed_paths")
    flat: list[str] = []
    if not isinstance(governed, Mapping) or set(governed) != set(REQUIRED_GOVERNED_PATHS):
        errors.append("governed_groups")
    else:
        for group, expected in REQUIRED_GOVERNED_PATHS.items():
            values = _list_text(governed.get(group))
            if values is None or frozenset(values) != expected or len(values) != len(set(values)):
                errors.append("governed_group:" + group)
            else:
                flat.extend(values)
    if len(flat) != len(set(flat)):
        errors.append("governed_paths_cross_duplicate")
    authority_files = _list_text(matrix.get("authority_files"))
    if authority_files is None or frozenset(authority_files) != REQUIRED_AUTHORITY_FILES or len(authority_files) != len(set(authority_files)):
        errors.append("authority_files")
    expected_gates = [
        "V3_AUTHORITY_PASS", "V3_SCHEMA_CONTRACTS_PASS", "V3_FOCAL_ZERO_SKIP_PASS", "V2_BYTE_IDENTITY_PASS",
        "V2_REGRESSION_PASS", "FULL_REPOSITORY_REGRESSION_PASS", "V3_PACKAGE_REPRODUCIBLE_PASS", "V3_STABLE_ADMISSION_PASS",
    ]
    if matrix.get("production_gates") != expected_gates:
        errors.append("production_gates")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "all_required_features_closed": not any(error.startswith("required_features") for error in errors),
        "governed_paths_unique": not any(error.startswith("governed_") for error in errors),
        "governed_paths": sorted(flat),
        "publication_authorized": False,
        "merge_authorized": False,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("cannot load " + path.as_posix()) from error
    if not isinstance(value, dict):
        raise RuntimeError("JSON root must be object: " + path.as_posix())
    return value


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(("git", *args), cwd=root, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if result.returncode != 0:
        raise RuntimeError("git failed: " + " ".join(args) + ": " + result.stderr[-4096:])
    return result.stdout.strip()


def _v2_governed_paths(root: Path) -> tuple[str, ...]:
    matrix = _load_json(root / "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json")
    paths: set[str] = {"CANONICAL_INDEX.json", "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json"}
    for key in ("authority_files", "stable_tooling_authority"):
        values = _list_text(matrix.get(key))
        if values is None:
            raise RuntimeError("malformed V2 authority path list: " + key)
        paths.update(values)
    groups = matrix.get("governed_paths")
    if not isinstance(groups, Mapping):
        raise RuntimeError("V2 governed_paths missing")
    for values in groups.values():
        checked = _list_text(values)
        if checked is None:
            raise RuntimeError("malformed V2 governed path group")
        paths.update(checked)
    return tuple(sorted(paths))


def require_v2_byte_identity(root: Path, *, head: str = "HEAD") -> None:
    for relative in _v2_governed_paths(root):
        base_row = _git(root, "ls-tree", V2_BASE_SHA, "--", relative)
        head_row = _git(root, "ls-tree", head, "--", relative)
        if not base_row or base_row != head_row:
            raise RuntimeError("V2 governed file changed or missing: " + relative)


def validate_v3_authority(root: Path = ROOT, *, require_git: bool = True) -> dict[str, Any]:
    matrix = _load_json(root / MATRIX_PATH)
    report = validate_v3_matrix(matrix, validate_release_metadata_v3(), v3_descriptor())
    if report["status"] != "PASS":
        raise RuntimeError("V3 matrix validation failed: " + ",".join(report["errors"]))
    for relative in report["governed_paths"]:
        if not (root / relative).is_file():
            raise RuntimeError("missing V3 governed path: " + relative)
    for relative in REQUIRED_AUTHORITY_FILES:
        if not (root / relative).is_file():
            raise RuntimeError("missing V3 authority file: " + relative)
    if require_git:
        require_v2_byte_identity(root)
    return {**report, "v2_byte_identity": "PASS" if require_git else "NOT_CHECKED"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate TEVScript MAX V3 authority and inherited V2 byte identity")
    parser.add_argument("--no-git", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_v3_authority(ROOT, require_git=not args.no_git)
    except Exception as error:
        print("V3_AUTHORITY=FAIL")
        print("V3_AUTHORITY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print("V3_AUTHORITY=PASS")
    print("V3_V2_BYTE_IDENTITY=" + report["v2_byte_identity"])
    print("V3_PUBLICATION_AUTHORITY=NO")
    print("V3_MERGE_AUTHORITY=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
