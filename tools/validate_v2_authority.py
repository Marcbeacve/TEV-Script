from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import tomllib
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator, ValidationError  # noqa: E402

from tev_script.canonical import canonical_hash  # noqa: E402
from tev_script.cli_v2 import build_parser  # noqa: E402
from tev_script.descriptor_v2 import V2_COMMANDS, v2_descriptor  # noqa: E402
from tev_script.diagnostics import TevScriptError  # noqa: E402
from tev_script.program_ir_v4 import (  # noqa: E402
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
    validate_program_ir_v4,
)
from tev_script.source_effect_program_v2 import (  # noqa: E402
    build_effect_command_program_ir_v4,
    build_effect_program_ir_v4,
    compile_effect_command_program_v2,
    compile_effect_program_v2,
)
from tev_script.source_program_v2 import compile_program_v2  # noqa: E402
from tev_script.program_ir_v4_effect_commands import (  # noqa: E402
    PROGRAM_IR_V4_EFFECTS_R2_SCHEMA,
    validate_program_ir_v4_effects_r2,
)


AUTHORITY_PATHS = (
    "spec/TEV_SCRIPT_V2_LANGUAGE.md",
    "spec/TEV_SCRIPT_PROGRAM_IR_V4.md",
    "spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md",
    "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
    "schemas/tev-script-v2-descriptor.schema.json",
    "schemas/tev-script-program-ir-v4.schema.json",
    "schemas/tev-script-v2-filesystem-artifacts.schema.json",
    "schemas/tev-script-v2-certify-full-receipt.schema.json",
)


class V2AuthorityFailure(RuntimeError):
    pass


def _load(relative: str) -> Any:
    path = ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2AuthorityFailure(f"cannot load {relative}: {error}") from error


def _require_inventory() -> tuple[dict[str, Any], dict[str, Any]]:
    for relative in AUTHORITY_PATHS:
        if not (ROOT / relative).is_file():
            raise V2AuthorityFailure(f"missing V2 authority path: {relative}")
    matrix = _load("spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json")
    if matrix.get("schema") != "TEV_SCRIPT_V2_FEATURE_MATRIX_V1":
        raise V2AuthorityFailure("V2 feature matrix schema mismatch")
    if matrix.get("language_version") != "2.0.0" or matrix.get("stable") is not False:
        raise V2AuthorityFailure("V2 feature matrix version/stability mismatch")
    if tuple(matrix.get("authority_files", ())) != AUTHORITY_PATHS:
        raise V2AuthorityFailure("V2 feature matrix authority inventory mismatch")
    governed = matrix.get("governed_paths")
    if not isinstance(governed, Mapping):
        raise V2AuthorityFailure("V2 governed path inventory is missing")
    for group in ("implementation", "tests", "conformance", "gates", "public_interfaces"):
        paths = governed.get(group)
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            raise V2AuthorityFailure(f"V2 governed group {group!r} is empty or duplicated")
        missing = [relative for relative in paths if not isinstance(relative, str) or not (ROOT / relative).is_file()]
        if missing:
            raise V2AuthorityFailure(f"V2 governed group {group!r} has missing paths: {missing}")

    index = _load("CANONICAL_INDEX.json")
    targets = [item for item in index.get("candidate_language_targets", []) if item.get("language_version") == "2.0.0"]
    if len(targets) != 1:
        raise V2AuthorityFailure(f"canonical index requires exactly one V2 target, observed={len(targets)}")
    target = targets[0]
    if target.get("status") != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED" or target.get("stable") is not False:
        raise V2AuthorityFailure("canonical V2 target status/stability mismatch")
    if tuple(target.get("authority_files", ())) != AUTHORITY_PATHS:
        raise V2AuthorityFailure("canonical V2 target authority inventory mismatch")
    if target.get("publication_authorized") is not False or target.get("merge_authorized") is not False:
        raise V2AuthorityFailure("canonical V2 target makes an unauthorized promotion claim")
    return matrix, target


def _require_schemas() -> Draft202012Validator:
    descriptor_schema = _load("schemas/tev-script-v2-descriptor.schema.json")
    program_schema = _load("schemas/tev-script-program-ir-v4.schema.json")
    filesystem_schema = _load("schemas/tev-script-v2-filesystem-artifacts.schema.json")
    receipt_schema = _load("schemas/tev-script-v2-certify-full-receipt.schema.json")
    for schema in (descriptor_schema, program_schema, filesystem_schema, receipt_schema):
        Draft202012Validator.check_schema(schema)
    descriptor = v2_descriptor()
    Draft202012Validator(descriptor_schema).validate(descriptor)
    body = dict(descriptor)
    observed = body.pop("descriptor_hash")
    if observed != canonical_hash(body):
        raise V2AuthorityFailure("V2 descriptor self-hash mismatch")
    return Draft202012Validator(program_schema)


def _require_cli() -> None:
    parser = build_parser()
    subparsers = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
    if len(subparsers) != 1:
        raise V2AuthorityFailure("V2 CLI must contain exactly one subparser action")
    observed = tuple(subparsers[0].choices)
    if observed != V2_COMMANDS:
        raise V2AuthorityFailure(f"V2 CLI command order mismatch: {observed}")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = project.get("project", {}).get("scripts", {})
    expected = {
        "tev-script-v2": "tev_script.cli_v2:main",
        "tev-script-v2-describe": "tev_script.describe_v2:main",
    }
    if {name: scripts.get(name) for name in expected} != expected:
        raise V2AuthorityFailure("V2 installed CLI entry points mismatch")


def _require_source_cases() -> int:
    fixture = _load("conformance/v2-source-static-cases.json")
    if fixture.get("schema") != "TEV_SCRIPT_V2_SOURCE_STATIC_CASES_V1":
        raise V2AuthorityFailure("V2 source/static fixture schema mismatch")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise V2AuthorityFailure("V2 source/static fixture is empty")
    ids: set[str] = set()
    for raw in cases:
        if not isinstance(raw, Mapping) or set(raw) not in (
            {"id", "compiler", "source", "expected_status", "expected_semantic_hash"},
            {"id", "compiler", "source", "expected_status", "expected_diagnostic"},
        ):
            raise V2AuthorityFailure("V2 source/static case field set mismatch")
        case_id = raw["id"]
        if not isinstance(case_id, str) or case_id in ids:
            raise V2AuthorityFailure("V2 source/static case IDs must be unique strings")
        ids.add(case_id)
        compiler = raw["compiler"]
        try:
            compiled = (
                compile_program_v2(raw["source"])
                if compiler == "pure"
                else compile_effect_command_program_v2(raw["source"])
                if compiler == "effects_r2"
                else None
            )
            if compiled is None:
                raise V2AuthorityFailure(f"unsupported source/static compiler {compiler!r}")
        except TevScriptError as error:
            if raw["expected_status"] != "FAIL" or error.diagnostic.code != raw.get("expected_diagnostic"):
                raise V2AuthorityFailure(
                    f"source/static case {case_id} failed as {error.diagnostic.code}, expected={raw}"
                ) from error
        else:
            if raw["expected_status"] != "PASS" or compiled.semantic_hash != raw.get("expected_semantic_hash"):
                raise V2AuthorityFailure(
                    f"source/static case {case_id} semantic identity mismatch"
                )
    return len(cases)


def _program_from_case(raw: Mapping[str, Any]) -> dict[str, Any]:
    profile = raw["profile"]
    if profile == "pure":
        return export_program_ir_v4_pure(compile_program_v2(raw["source"]))
    if profile == "recursive":
        return export_program_ir_v4_recursive(compile_program_v2(raw["source"]))
    if profile == "effects":
        compiled = compile_effect_program_v2(raw["source"])
        scenario = {"capability_table_hash": compiled.capabilities.table_hash, "capabilities": []}
        return build_effect_program_ir_v4(compiled, scenario)
    if profile == "effects_r2_plan":
        compiled = compile_effect_command_program_v2(raw["source"])
        scenario = {"capability_table_hash": compiled.capabilities.table_hash, "capabilities": []}
        return build_effect_command_program_ir_v4(compiled, scenario)
    raise V2AuthorityFailure(f"unsupported Program IR V4 fixture profile {profile!r}")


def _mutate_program(program: Mapping[str, Any], mutation: str) -> dict[str, Any]:
    changed = copy.deepcopy(dict(program))
    if mutation == "add_unknown_field":
        changed["unknown"] = True
    elif mutation == "uppercase_program_ir_hash":
        changed["program_ir_hash"] = changed["program_ir_hash"].upper()
    elif mutation == "replace_profile":
        changed["profile"] = "unsupported"
    elif mutation == "zero_type_table_hash":
        changed["type_table_hash"] = "0" * 64
    else:
        raise V2AuthorityFailure(f"unsupported Program IR V4 mutation {mutation!r}")
    return changed


def _validate_program(program: Mapping[str, Any]) -> None:
    if program.get("schema") == PROGRAM_IR_V4_EFFECTS_R2_SCHEMA:
        validate_program_ir_v4_effects_r2(program)
    else:
        validate_program_ir_v4(program)


def _require_program_cases(validator: Draft202012Validator) -> int:
    fixture = _load("conformance/program-ir-v4-cases.json")
    if fixture.get("schema") != "TEV_SCRIPT_PROGRAM_IR_V4_CASES_V1":
        raise V2AuthorityFailure("Program IR V4 fixture schema mismatch")
    valid = fixture.get("valid_profiles")
    negative = fixture.get("negative_mutations")
    if not isinstance(valid, list) or len(valid) != 4 or not isinstance(negative, list) or not negative:
        raise V2AuthorityFailure("Program IR V4 fixture cardinality mismatch")
    programs: list[dict[str, Any]] = []
    for raw in valid:
        program = _program_from_case(raw)
        validator.validate(program)
        _validate_program(program)
        if program["schema"] != raw["expected_schema"] or program["program_ir_hash"] != raw["expected_program_ir_hash"]:
            raise V2AuthorityFailure(f"Program IR V4 fixture identity mismatch: {raw['id']}")
        programs.append(program)
    base = programs[0]
    for raw in negative:
        changed = _mutate_program(base, raw["mutation"])
        schema_rejected = False
        try:
            validator.validate(changed)
        except ValidationError:
            schema_rejected = True
        expected_schema_rejection = raw.get("schema_status") == "FAIL"
        if schema_rejected != expected_schema_rejection:
            raise V2AuthorityFailure(
                f"Program IR schema outcome mismatch for mutation {raw['id']}"
            )
        semantic_rejected = False
        try:
            _validate_program(changed)
        except TevScriptError:
            semantic_rejected = True
        expected_semantic_rejection = raw.get("semantic_status") == "FAIL"
        if semantic_rejected != expected_semantic_rejection:
            raise V2AuthorityFailure(
                f"Program IR semantic outcome mismatch for mutation {raw['id']}"
            )
    return len(valid) + len(negative)


def validate_v2_authority() -> dict[str, int]:
    _require_inventory()
    validator = _require_schemas()
    _require_cli()
    source_cases = _require_source_cases()
    program_cases = _require_program_cases(validator)
    for relative, phrase in (
        ("spec/TEV_SCRIPT_V2_LANGUAGE.md", "normative source-language"),
        ("spec/TEV_SCRIPT_PROGRAM_IR_V4.md", "only V2 runtime input"),
        ("spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md", "concurrently renamed or replaced"),
    ):
        if phrase not in (ROOT / relative).read_text(encoding="utf-8"):
            raise V2AuthorityFailure(f"normative specification closure phrase missing: {relative}")
    return {"source_cases": source_cases, "program_cases": program_cases}


def main() -> int:
    try:
        counts = validate_v2_authority()
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_V2_AUTHORITY=FAIL")
        print("TEV_SCRIPT_V2_AUTHORITY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print("V2_NORMATIVE_SPEC=PASS")
    print("V2_SCHEMAS_CONTRACTS=PASS")
    print("CLI_V2=PASS")
    print(f"V2_SOURCE_STATIC=PASS cases={counts['source_cases']}")
    print(f"V2_PROGRAM_IR_V4=PASS cases={counts['program_cases']}")
    print("TEV_SCRIPT_V2_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
