from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_STATUS = "FULL_IMPLEMENTATION_CANDIDATE_PRECERTIFY_REQUIRED"
EXPECTED_MATRIX = "TEV_SCRIPT_V1_FEATURE_MATRIX_V5"
EXPECTED_PRECERTIFY = "TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V5"
EXPECTED_CERTIFY = "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V1"

REQUIRED_AUTHORITY = {
    "spec/TEV_SCRIPT_V1_LEXICAL_PROFILE.md",
    "spec/TEV_SCRIPT_V1.ebnf",
    "spec/TEV_SCRIPT_V1_SEMANTIC_CONTRACT.md",
    "spec/TEV_SCRIPT_V1_LINK_MODEL.md",
    "spec/TEV_SCRIPT_V1_BUDGETS.md",
    "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
    "spec/TEV_SCRIPT_LINKED_CANONICALIZATION_V1.md",
    "spec/TEV_SCRIPT_IR_V3.md",
    "spec/TEV_SCRIPT_IR_V3_VALUE_MODEL.md",
    "spec/TEV_SCRIPT_IR_V3_OPERATIONAL_SEMANTICS.md",
    "spec/TEV_SCRIPT_RUNTIME_CHECKPOINT_V2.md",
    "spec/TEV_SCRIPT_SIGNED_UPDATE_V2.md",
    "schemas/tev_script_linked_program_v1.schema.json",
    "schemas/tev_script_lowering_receipt_v1.schema.json",
    "schemas/tev_script_lowering_receipt_v2.schema.json",
    "schemas/tev_script_program_ir_v3.schema.json",
    "schemas/tev_script_ir_v3_scenario_v1.schema.json",
    "schemas/tev_script_ir_v3_conformance_receipt_v1.schema.json",
    "schemas/tev_script_runtime_checkpoint_v2.schema.json",
    "schemas/tev_script_signed_update_package_v2.schema.json",
    "schemas/tev_script_installed_update_v2.schema.json",
}

REQUIRED_GATE_MAP = {
    "implementation": "RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py",
    "csharp_surface": "tools/validate_ir_v3_csharp_portable_surface.py",
    "cross_runtime": "tools/validate_ir_v3_cross_runtime_parity.py",
    "checkpoint_cross_runtime": "tools/validate_ir_v3_checkpoint_cross_runtime.py",
    "browser_wasm": "tools/validate_ir_v3_browser_wasm.py",
    "wasi": "tools/validate_ir_v3_wasi.py",
    "signed_update_host": "tools/validate_ir_v3_signed_update.py",
    "signed_update_browser_wasm": "tools/validate_ir_v3_browser_signed_update.py",
    "signed_update_wasi": "tools/validate_ir_v3_wasi_signed_update.py",
    "precertify": "RUN_TEV_SCRIPT_V1_PRECERTIFY.py",
    "certify_full": "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py",
}

REQUIRED_PROGRAMMER_DOCS = {
    "README.md",
    "docs/TEV_SCRIPT_V1_LANGUAGE_REFERENCE.md",
    "docs/TEV_SCRIPT_V1_PROGRAMMING_MODEL.md",
    "examples/v1/README.md",
}

REQUIRED_EXAMPLES = {
    "examples/v1/Calculator.tevs",
    "examples/v1/ErasableToIrV2.tevs",
    "examples/v1/AlgebraicCapability.tevs",
    "examples/v1/ecosystem/main.tevs",
    "examples/v1/ecosystem/model.tevs",
    "examples/v1/ecosystem/rules.tevs",
    "examples/v1/ecosystem/storage.tevs",
}

REQUIRED_PRODUCT_TESTS = {
    "tests/test_v1_examples.py",
    "tests/test_v1_cli_full.py",
    "tests/test_v1_public_api.py",
}

REQUIRED_PUBLIC_INTERFACES = {
    "python_package": "tev_script",
    "v0_2_cli": "tev-script",
    "v1_cli": "tev-script-v1",
    "v1_module_cli": "python -m tev_script.cli_v1",
    "v1_python_pipeline": "tev_script.pipeline_v1",
    "v1_runtime": "tev_script.ScriptRuntimeV3",
}

REQUIRED_PRECERTIFY_TOOLS = (
    "validate_v1_governance.py",
    "validate_ir_v3_csharp_portable_surface.py",
    "validate_ir_v3_cross_runtime_parity.py",
    "validate_ir_v3_checkpoint_cross_runtime.py",
    "validate_ir_v3_browser_wasm.py",
    "validate_ir_v3_wasi.py",
    "validate_ir_v3_signed_update.py",
    "validate_ir_v3_browser_signed_update.py",
    "validate_ir_v3_wasi_signed_update.py",
)

REQUIRED_PROMOTION_GATES = {
    "REFERENCE_FRONTEND_DYNAMIC_PASS",
    "DETERMINISTIC_LINKER_DYNAMIC_PASS",
    "STATIC_SEMANTICS_DYNAMIC_PASS",
    "LINKED_CANONICALIZATION_BYTE_LOCK_PASS",
    "IR_V2_ERASABLE_LOWERING_DYNAMIC_PASS",
    "IR_V3_SCHEMA_VALUE_CODEC_AND_TYPED_CFG_DYNAMIC_PASS",
    "V1_TO_IR_V3_END_TO_END_DYNAMIC_PASS",
    "IR_V2_TO_IR_V3_LIFT_DYNAMIC_PASS",
    "PYTHON_JS_CSHARP_IR_V3_RECEIPT_BYTE_LOCK_PASS",
    "RUNTIME_CHECKPOINT_V2_PYTHON_JS_CSHARP_BYTE_LOCK_PASS",
    "BROWSER_WASM_IR_V3_RECEIPT_CHECKPOINT_PARITY_PASS",
    "WASI_IR_V3_RECEIPT_CHECKPOINT_RESTART_PASS",
    "SIGNED_UPDATE_V3_HOST_PASS",
    "SIGNED_UPDATE_V3_BROWSER_WASM_PASS",
    "SIGNED_UPDATE_V3_WASI_FRESH_RESTORE_PASS",
    "V0_2_FULL_PORTABLE_REGRESSION_PASS",
    "EXACT_CLEAN_COMMIT_PRECERTIFY_PASS",
    "EXACT_CLEAN_COMMIT_CERTIFY_FULL_PASS",
}


def fail(code: str, detail: str) -> None:
    raise RuntimeError(code + ":" + detail)


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        fail(code, detail)


def require_file(relative: str) -> None:
    path = ROOT / relative
    require(path.is_file(), "V1_GOVERNANCE_FILE_MISSING", relative)


def load_json(relative: str) -> dict[str, object]:
    require_file(relative)
    try:
        value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail("V1_GOVERNANCE_JSON_INVALID", relative + ":" + str(error))
    require(isinstance(value, dict), "V1_GOVERNANCE_JSON_ROOT", relative)
    return value


def require_exact_set(target: dict[str, object], key: str, expected: set[str]) -> None:
    observed = target.get(key)
    require(isinstance(observed, list), "V1_GOVERNANCE_LIST_MISSING", key)
    observed_set = {str(item) for item in observed}
    missing = sorted(expected - observed_set)
    require(not missing, "V1_GOVERNANCE_LIST_ITEMS_MISSING", key + ":" + ",".join(missing))
    for relative in sorted(expected):
        require_file(relative)


def main() -> int:
    canonical = load_json("CANONICAL_INDEX.json")
    matrix = load_json("spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json")
    pre_text = (ROOT / "RUN_TEV_SCRIPT_V1_PRECERTIFY.py").read_text(encoding="utf-8")
    certify_text = (ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py").read_text(encoding="utf-8")
    protocol_text = (ROOT / "docs/V1_CERTIFICATION_PROTOCOL.md").read_text(encoding="utf-8")
    state_text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package_init_text = (ROOT / "tev_script" / "__init__.py").read_text(encoding="utf-8")
    cli_v1_text = (ROOT / "tev_script" / "cli_v1.py").read_text(encoding="utf-8")

    require(canonical.get("schema") == "TEV_SCRIPT_CANONICAL_INDEX_V1", "V1_GOVERNANCE_CANONICAL_SCHEMA", str(canonical.get("schema")))
    require(canonical.get("stable") is False, "V1_GOVERNANCE_CANONICAL_STABLE", repr(canonical.get("stable")))
    targets = [
        item
        for item in canonical.get("candidate_language_targets", [])
        if isinstance(item, dict) and item.get("language_version") == "1.0.0"
    ]
    require(len(targets) == 1, "V1_GOVERNANCE_TARGET_COUNT", str(len(targets)))
    target = targets[0]
    require(target.get("status") == EXPECTED_STATUS, "V1_GOVERNANCE_TARGET_STATUS", str(target.get("status")))
    require(target.get("stable") is False, "V1_GOVERNANCE_TARGET_STABLE", repr(target.get("stable")))

    authority = set(target.get("authority_files", []))
    missing_authority = sorted(REQUIRED_AUTHORITY - authority)
    require(not missing_authority, "V1_GOVERNANCE_AUTHORITY_MISSING", ",".join(missing_authority))
    for relative in sorted(REQUIRED_AUTHORITY):
        require_file(relative)

    gates = target.get("gates")
    require(isinstance(gates, dict), "V1_GOVERNANCE_GATE_MAP", "missing or non-object")
    for key, relative in REQUIRED_GATE_MAP.items():
        require(gates.get(key) == relative, "V1_GOVERNANCE_GATE_BINDING", f"{key}:{gates.get(key)!r}")
        require_file(relative)

    require_exact_set(target, "non_normative_programmer_documentation", REQUIRED_PROGRAMMER_DOCS)
    require_exact_set(target, "executable_examples", REQUIRED_EXAMPLES)
    require_exact_set(target, "example_and_public_api_tests", REQUIRED_PRODUCT_TESTS)

    public_interfaces = target.get("public_interfaces")
    require(isinstance(public_interfaces, dict), "V1_GOVERNANCE_PUBLIC_INTERFACES", "missing or non-object")
    for key, expected in REQUIRED_PUBLIC_INTERFACES.items():
        require(public_interfaces.get(key) == expected, "V1_GOVERNANCE_PUBLIC_INTERFACE", f"{key}:{public_interfaces.get(key)!r}")

    require('tev-script = "tev_script.cli:main"' in pyproject_text, "V1_GOVERNANCE_V0_2_CLI", "certified CLI binding missing")
    require('tev-script-v1 = "tev_script.cli_v1:main"' in pyproject_text, "V1_GOVERNANCE_V1_CLI", "V1 CLI binding missing")
    for token in (
        "compile_v1_paths_auto",
        "compile_v1_paths_to_ir_v2",
        "compile_v1_paths_to_ir_v3",
        "ScriptRuntimeV3",
        "RuntimeCheckpointV2",
    ):
        require(token in package_init_text, "V1_GOVERNANCE_PUBLIC_API", token)
    for token in (
        'choices=("auto", "irv2", "irv3")',
        '"lower-irv3"',
        '"--receipt"',
        "build_ir_v2_lowering_receipt",
        "build_ir_v3_lowering_receipt",
        '"default_target_ir"',
        '"TEV_SCRIPT_V1_COMPILE_RESULT_V2"',
    ):
        require(token in cli_v1_text, "V1_GOVERNANCE_V1_CLI_SURFACE", token)

    require(target.get("certification_protocol") == "docs/V1_CERTIFICATION_PROTOCOL.md", "V1_GOVERNANCE_PROTOCOL_BINDING", repr(target.get("certification_protocol")))
    require_file("docs/V1_CERTIFICATION_PROTOCOL.md")

    require(matrix.get("schema") == EXPECTED_MATRIX, "V1_GOVERNANCE_MATRIX_SCHEMA", str(matrix.get("schema")))
    require(matrix.get("target_language_version") == "1.0.0", "V1_GOVERNANCE_MATRIX_VERSION", str(matrix.get("target_language_version")))
    require(matrix.get("stable_release_authorized") is False, "V1_GOVERNANCE_MATRIX_STABLE", repr(matrix.get("stable_release_authorized")))
    require(matrix.get("certification_status") == EXPECTED_STATUS, "V1_GOVERNANCE_MATRIX_STATUS", str(matrix.get("certification_status")))

    promotion = set(matrix.get("promotion_gates", []))
    missing_promotion = sorted(REQUIRED_PROMOTION_GATES - promotion)
    require(not missing_promotion, "V1_GOVERNANCE_PROMOTION_GATE_MISSING", ",".join(missing_promotion))

    for token in (
        EXPECTED_PRECERTIFY,
        '"v1_governance": "PASS"',
        '"certify_full": False',
        '"language_stable": False',
        '"signed_update_v3_host": "PASS"',
        '"signed_update_v3_browser_wasm": "PASS"',
        '"signed_update_v3_wasi": "PASS_FRESH_RESTORE"',
        '"browser_wasm_v3": "PASS"',
        '"wasi_v3": "PASS_FRESH_RESTORE"',
    ):
        require(token in pre_text, "V1_GOVERNANCE_PRECERTIFY_TOKEN", token)

    for tool in REQUIRED_PRECERTIFY_TOOLS:
        require(tool in pre_text, "V1_GOVERNANCE_PRECERTIFY_TOOL", tool)

    for token in (
        EXPECTED_PRECERTIFY,
        EXPECTED_CERTIFY,
        "RUN_TEV_SCRIPT_V1_PRECERTIFY.py",
        '"v1_governance": "PASS"',
        '"certify_full": True',
        '"language_stable": False',
        "V1_PRECERTIFY_RECEIPT_SHA256=",
        "CERTIFY_FULL=PASS",
        "LANGUAGE_STABLE=NO",
    ):
        require(token in certify_text, "V1_GOVERNANCE_CERTIFY_TOKEN", token)

    for token in (
        "PRECERTIFY(C)=PASS",
        "CERTIFY_FULL(C)=PASS",
        "PRECERTIFY(S)=PASS",
        "CERTIFY_FULL(S)=PASS",
        "No transitive certification",
        "No skipped mandatory target",
    ):
        require(token in protocol_text, "V1_GOVERNANCE_PROTOCOL_TOKEN", token)

    for token in (
        "BRANCH=agent/tev-script-v1-irv3-spec-v1",
        "CURRENT_HEAD_FULL_PRECERTIFY=NOT_EXECUTED_HERE",
        "CURRENT_HEAD_CERTIFY_FULL=NO",
        "LANGUAGE_STABLE=NO",
    ):
        require(token in state_text, "V1_GOVERNANCE_PROJECT_STATE_TOKEN", token)

    print("TEV_SCRIPT_V1_GOVERNANCE_CANON_MATRIX=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_AUTHORITY_FILES=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_GATE_BINDINGS=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_PUBLIC_SURFACE=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_EXECUTABLE_EXAMPLES=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_PRECERTIFY_CERTIFY_PROTOCOL=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_NO_TRANSITIVE_CERTIFICATION=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
