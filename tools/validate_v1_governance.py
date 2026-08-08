from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_STATUS = "FULL_IMPLEMENTATION_CANDIDATE_PRECERTIFY_REQUIRED"
EXPECTED_MATRIX = "TEV_SCRIPT_V1_FEATURE_MATRIX_V5"
EXPECTED_PRECERTIFY = "TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V5"
EXPECTED_CERTIFY = "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V1"
EXPECTED_PYTHON_CERTIFY = "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V1"
ARTIFACT_POLICY = "EVIDENCE_SAFE_RECEIPT_LAST_V1"

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

REQUIRED_BUILD_TOOLING = {
    "schemas/tev_script_project_v1.schema.json",
    "docs/V1_PROJECT_MANIFEST.md",
}

REQUIRED_INTROSPECTION = {
    "schemas/tev_script_descriptor_v3.schema.json",
    "tev_script/descriptor_v1.py",
    "tev_script/describe_v1.py",
    "tev_script/runtime_cli_v3.py",
    "tests/test_v1_descriptor.py",
    "tests/test_v1_descriptor_schema_cardinality.py",
    "tests/test_v1_runtime_cli_v3.py",
}

REQUIRED_LSP = {
    "tev_script/lsp_v1.py",
    "docs/V1_LSP.md",
    "tests/test_v1_lsp.py",
    "editors/vscode/README.md",
}

REQUIRED_GATE_MAP = {
    "implementation": "RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py",
    "python_production": "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py",
    "python_certify_full": "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
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

REQUIRED_PRODUCT_FILES = {
    "README.md",
    "docs/TEV_SCRIPT_V1_LANGUAGE_REFERENCE.md",
    "docs/TEV_SCRIPT_V1_PROGRAMMING_MODEL.md",
    "docs/V1_PROJECT_MANIFEST.md",
    "docs/V1_PYTHON_PRODUCTION.md",
    "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
    "tev_script/python_host_v1.py",
    "examples/v1/README.md",
    "examples/v1/Calculator.tevs",
    "examples/v1/ErasableToIrV2.tevs",
    "examples/v1/AlgebraicCapability.tevs",
    "examples/v1/ecosystem/main.tevs",
    "examples/v1/ecosystem/model.tevs",
    "examples/v1/ecosystem/rules.tevs",
    "examples/v1/ecosystem/storage.tevs",
    "examples/v1/ecosystem/tevscript.project.json",
    "tests/test_v1_examples.py",
    "tests/test_v1_cli_full.py",
    "tests/test_v1_project.py",
    "tests/test_v1_public_api.py",
    "tests/test_v1_python_host.py",
    "tests/test_v1_linked_program_unit_kind_regression.py",
    "tests/test_v1_artifact_write.py",
    "tests/test_v1_editor_assets.py",
}

REQUIRED_PROMOTION_GATES = {
    "REFERENCE_FRONTEND_DYNAMIC_PASS",
    "DETERMINISTIC_LINKER_DYNAMIC_PASS",
    "STATIC_SEMANTICS_DYNAMIC_PASS",
    "LINKED_CANONICALIZATION_BYTE_LOCK_PASS",
    "IR_V2_ERASABLE_LOWERING_DYNAMIC_PASS",
    "IR_V3_SCHEMA_VALUE_CODEC_AND_TYPED_CFG_DYNAMIC_PASS",
    "V1_TO_IR_V3_END_TO_END_DYNAMIC_PASS",
    "IR_V2_TO_IR_V3_LIFT_DYNAMIC_PASS",
    "PROJECT_MANIFEST_AND_PUBLIC_CLI_DYNAMIC_PASS",
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


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise RuntimeError(code + ":" + detail)


def require_file(relative: str) -> None:
    require((ROOT / relative).is_file(), "V1_GOVERNANCE_FILE_MISSING", relative)


def load_json(relative: str) -> dict[str, object]:
    require_file(relative)
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "V1_GOVERNANCE_JSON_ROOT", relative)
    return value


def require_contains(observed: object, expected: set[str], code: str) -> None:
    require(isinstance(observed, list), code, "expected list")
    values = {str(item) for item in observed}
    missing = sorted(expected - values)
    require(not missing, code, ",".join(missing))


def require_tokens(text: str, tokens: tuple[str, ...], code: str) -> None:
    for token in tokens:
        require(token in text, code, token)


def main() -> int:
    canonical = load_json("CANONICAL_INDEX.json")
    matrix = load_json("spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json")
    pre_text = (ROOT / "RUN_TEV_SCRIPT_V1_PRECERTIFY.py").read_text(encoding="utf-8")
    certify_text = (ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py").read_text(encoding="utf-8")
    python_gate_text = (ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py").read_text(encoding="utf-8")
    python_certify_text = (ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py").read_text(encoding="utf-8")
    protocol_text = (ROOT / "docs/V1_CERTIFICATION_PROTOCOL.md").read_text(encoding="utf-8")
    state_text = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package_text = (ROOT / "tev_script" / "__init__.py").read_text(encoding="utf-8")
    python_host_text = (ROOT / "tev_script" / "python_host_v1.py").read_text(encoding="utf-8")
    cli_text = (ROOT / "tev_script" / "cli_v1.py").read_text(encoding="utf-8")
    project_text = (ROOT / "tev_script" / "project_v1.py").read_text(encoding="utf-8")
    artifact_text = (ROOT / "tev_script" / "artifact_write_v1.py").read_text(encoding="utf-8")
    descriptor_text = (ROOT / "tev_script" / "descriptor_v1.py").read_text(encoding="utf-8")
    describe_text = (ROOT / "tev_script" / "describe_v1.py").read_text(encoding="utf-8")
    runtime_tool_text = (ROOT / "tev_script" / "runtime_cli_v3.py").read_text(encoding="utf-8")
    lsp_text = (ROOT / "tev_script" / "lsp_v1.py").read_text(encoding="utf-8")

    require(canonical.get("schema") == "TEV_SCRIPT_CANONICAL_INDEX_V1", "V1_GOVERNANCE_CANONICAL_SCHEMA", repr(canonical.get("schema")))
    require(canonical.get("stable") is False, "V1_GOVERNANCE_CANONICAL_STABLE", repr(canonical.get("stable")))
    targets = [
        item for item in canonical.get("candidate_language_targets", [])
        if isinstance(item, dict) and item.get("language_version") == "1.0.0"
    ]
    require(len(targets) == 1, "V1_GOVERNANCE_TARGET_COUNT", str(len(targets)))
    target = targets[0]
    require(target.get("status") == EXPECTED_STATUS, "V1_GOVERNANCE_TARGET_STATUS", repr(target.get("status")))
    require(target.get("stable") is False, "V1_GOVERNANCE_TARGET_STABLE", repr(target.get("stable")))
    require_contains(target.get("authority_files"), REQUIRED_AUTHORITY, "V1_GOVERNANCE_AUTHORITY")
    require_contains(target.get("build_tooling_authority"), REQUIRED_BUILD_TOOLING, "V1_GOVERNANCE_BUILD_TOOLING")
    for relative in REQUIRED_AUTHORITY | REQUIRED_BUILD_TOOLING | REQUIRED_PRODUCT_FILES | REQUIRED_INTROSPECTION | REQUIRED_LSP:
        require_file(relative)

    introspection = target.get("introspection_surface")
    require(isinstance(introspection, dict), "V1_GOVERNANCE_INTROSPECTION", "missing")
    for key, expected in {
        "schema": "schemas/tev_script_descriptor_v3.schema.json",
        "generator": "tev_script/descriptor_v1.py",
        "module_cli": "tev_script/describe_v1.py",
        "installed_cli": "tev-script-v1-describe",
        "descriptor_is_generated_from_v1_contract_constants": True,
        "stable_claim": False,
    }.items():
        require(introspection.get(key) == expected, "V1_GOVERNANCE_INTROSPECTION", f"{key}:{introspection.get(key)!r}")

    lsp = target.get("language_server_surface")
    require(isinstance(lsp, dict), "V1_GOVERNANCE_LSP", "missing")
    for key, expected in {
        "implementation": "tev_script/lsp_v1.py",
        "installed_cli": "tev-script-v1-lsp",
        "protocol": "LSP_JSON_RPC_STDIO",
        "position_encoding": "utf-16",
        "document_sync": "FULL_TEXT",
        "standalone_authority": "parse_v1_bytes",
        "project_authority": "analyze_v1_mapping",
        "explicit_project_manifest_only": True,
        "independent_parser_or_type_checker": False,
        "generic_execution_host": False,
        "documentation": "docs/V1_LSP.md",
        "test": "tests/test_v1_lsp.py",
    }.items():
        require(lsp.get(key) == expected, "V1_GOVERNANCE_LSP", f"{key}:{lsp.get(key)!r}")

    python_surface = target.get("python_production_surface")
    require(isinstance(python_surface, dict), "V1_GOVERNANCE_PYTHON_PRODUCTION", "missing")
    for key, expected in {
        "implementation": "tev_script/python_host_v1.py",
        "artifact": "tev_script.PythonProgramArtifactV1",
        "runtime_host": "tev_script.PythonRuntimeHostV1",
        "source_build_api": "tev_script.build_python_program_v1",
        "runtime_accepts_source": False,
        "runtime_ir_schema": "TEV_SCRIPT_PROGRAM_IR_V3",
        "least_authority_default": True,
        "checkpoint_schema": "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2",
        "documentation": "docs/V1_PYTHON_PRODUCTION.md",
        "test": "tests/test_v1_python_host.py",
        "production_gate": "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py",
        "certify_full_gate": "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
        "stable_claim": False,
    }.items():
        require(
            python_surface.get(key) == expected,
            "V1_GOVERNANCE_PYTHON_PRODUCTION",
            f"{key}:{python_surface.get(key)!r}",
        )

    gates = target.get("gates")
    require(isinstance(gates, dict), "V1_GOVERNANCE_GATE_MAP", "missing")
    for key, path in REQUIRED_GATE_MAP.items():
        require(gates.get(key) == path, "V1_GOVERNANCE_GATE_BINDING", f"{key}:{gates.get(key)!r}")
        require_file(path)

    interfaces = target.get("public_interfaces")
    require(isinstance(interfaces, dict), "V1_GOVERNANCE_PUBLIC_INTERFACES", "missing")
    for key, expected in {
        "python_package": "tev_script",
        "v0_2_cli": "tev-script",
        "v1_cli": "tev-script-v1",
        "v1_descriptor_cli": "tev-script-v1-describe",
        "v1_ir_tool_cli": "tev-script-v1-ir",
        "v1_lsp_cli": "tev-script-v1-lsp",
        "v1_module_cli": "python -m tev_script.cli_v1",
        "v1_python_pipeline": "tev_script.pipeline_v1",
        "v1_project_manifest": "tev_script.project_v1",
        "v1_runtime": "tev_script.ScriptRuntimeV3",
        "v1_python_program_artifact": "tev_script.PythonProgramArtifactV1",
        "v1_python_production_host": "tev_script.PythonRuntimeHostV1",
    }.items():
        require(interfaces.get(key) == expected, "V1_GOVERNANCE_PUBLIC_INTERFACE", f"{key}:{interfaces.get(key)!r}")

    require_tokens(pyproject_text, (
        'tev-script = "tev_script.cli:main"',
        'tev-script-v1 = "tev_script.cli_v1:main"',
        'tev-script-v1-describe = "tev_script.describe_v1:main"',
        'tev-script-v1-ir = "tev_script.runtime_cli_v3:main"',
        'tev-script-v1-lsp = "tev_script.lsp_v1:main"',
    ), "V1_GOVERNANCE_CLI_BINDINGS")
    require_tokens(package_text, (
        "compile_v1_paths_auto", "compile_v1_paths_to_ir_v2", "compile_v1_paths_to_ir_v3",
        "ProjectManifestV1", "load_v1_project", "verify_v1_project_inputs",
        "ScriptRuntimeV3", "RuntimeCheckpointV2",
        "PythonCapabilityContractV1", "PythonProgramArtifactV1", "PythonRuntimeHostV1",
        "build_python_program_v1", "build_python_program_v1_paths",
    ), "V1_GOVERNANCE_PUBLIC_API")
    require_tokens(python_host_text, (
        "class PythonProgramArtifactV1", "class PythonRuntimeHostV1",
        "build_python_program_v1", "compile_v1_mapping_to_ir_v3",
        "validate_program_ir_v3", "RuntimeCheckpointV2.capture",
        "restore_exact", "TEVS_PYTHON_V1_CAPABILITY_MISSING",
        "TEVS_PYTHON_V1_CAPABILITY_UNUSED", "reject_unused_capabilities: bool = True",
    ), "V1_GOVERNANCE_PYTHON_PRODUCTION_HOST")
    require_tokens(python_gate_text, (
        'RECEIPT_SCHEMA = "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V1"',
        "RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py", "git", "archive",
        '"--no-deps"', '"--no-build-isolation"', '"PIP_NO_INDEX": "1"',
        "TEV_SCRIPT_V1_PYTHON_WHEEL_REPRODUCIBLE=PASS",
        "TEV_SCRIPT_V1_PYTHON_INSTALLED_CHECKPOINT_RESTART=PASS",
        "TEV_SCRIPT_V1_PYTHON_INSTALLED_LEAST_AUTHORITY=PASS",
        "TEV_SCRIPT_V1_PYTHON_INSTALLED_TYPED_CAPABILITY=PASS",
        "TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE",
        "CERTIFY_FULL=NO", "LANGUAGE_STABLE=NO",
    ), "V1_GOVERNANCE_PYTHON_PRODUCTION_GATE")
    require_tokens(python_certify_text, (
        EXPECTED_PYTHON_CERTIFY,
        "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py",
        "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_JSON=",
        "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_SHA256=",
        '"python_certify_full": True',
        '"global_certify_full": False',
        '"language_stable": False',
        '"stable_release_authorized": False',
        "PYTHON_CERTIFY_FULL=PASS",
        "CERTIFY_FULL=NO",
        "LANGUAGE_STABLE=NO",
    ), "V1_GOVERNANCE_PYTHON_CERTIFY_FULL_GATE")
    require_tokens(cli_text, (
        'choices=("auto", "irv2", "irv3")', '"project-check"', '"build"', '"lower-irv3"',
        '"--receipt"', "write_compilation_artifacts_v1", "write_text_artifact_v1",
        'ARTIFACT_COMMIT_POLICY_V1 = "' + ARTIFACT_POLICY + '"',
        '"TEV_SCRIPT_V1_COMPILE_RESULT_V3"', '"TEV_SCRIPT_V1_PROJECT_BUILD_RESULT_V2"',
    ), "V1_GOVERNANCE_V1_CLI_SURFACE")
    require_tokens(project_text, (
        'PROJECT_SCHEMA_V1 = "TEV_SCRIPT_PROJECT_V1"',
        'PROJECT_INPUT_SCHEMA_V1 = "TEV_SCRIPT_PROJECT_INPUT_V1"',
        "manifest_hash", "project_input_hash", "resolve(strict=True)", "relative_to(base)",
        "verify_v1_project_inputs",
    ), "V1_GOVERNANCE_PROJECT_TOOLING")
    require_tokens(artifact_text, (
        "write_compilation_artifacts_v1", "os.replace(staged_ir, ir)",
        "os.replace(staged_receipt, receipt)", "receipt presence is the final commit",
        "TEVS_V1_ARTIFACT_ROLLBACK", "TEVS_V1_ARTIFACT_PATH_COLLISION",
    ), "V1_GOVERNANCE_ARTIFACT_POLICY")
    require_tokens(descriptor_text, (
        'DESCRIPTOR_SCHEMA_V1 = "TEV_SCRIPT_DESCRIPTOR_V3"',
        '"language_version": V1_LANGUAGE_VERSION',
        '"artifact_commit_policy": "EVIDENCE_SAFE_RECEIPT_LAST_V1"',
        '"current_v1_certify_full_claim": False',
        '"current_v1_language_stable_claim": False',
        "canonical_hash(descriptor)",
    ), "V1_GOVERNANCE_DESCRIPTOR")
    require_tokens(describe_text, (
        "v1_descriptor_json", "print(v1_descriptor_json())",
    ), "V1_GOVERNANCE_DESCRIPTOR_CLI")
    require_tokens(runtime_tool_text, (
        "Read-only TEV Script IR V3 validation/conformance tooling",
        "does not act as a generic production execution host",
        '"describe"', '"validate"', '"conformance"',
        "run_ir_v3_conformance", "validate_program_ir_v3", "write_text_artifact_v1",
    ), "V1_GOVERNANCE_IR_TOOL")
    require_tokens(lsp_text, (
        'LSP_POSITION_ENCODING = "utf-16"',
        '"change": 1',
        '"textDocument/publishDiagnostics"',
        "parse_v1_bytes", "analyze_v1_mapping", "load_v1_project",
        "codepoint_offset_to_lsp_position", "Content-Length",
        "optional explicit TEV_SCRIPT_PROJECT_V1",
        "No independent language semantics are embedded",
    ), "V1_GOVERNANCE_LSP_IMPLEMENTATION")

    require(matrix.get("schema") == EXPECTED_MATRIX, "V1_GOVERNANCE_MATRIX_SCHEMA", repr(matrix.get("schema")))
    require(matrix.get("target_language_version") == "1.0.0", "V1_GOVERNANCE_MATRIX_VERSION", repr(matrix.get("target_language_version")))
    require(matrix.get("stable_release_authorized") is False, "V1_GOVERNANCE_MATRIX_STABLE", repr(matrix.get("stable_release_authorized")))
    require(matrix.get("certification_status") == EXPECTED_STATUS, "V1_GOVERNANCE_MATRIX_STATUS", repr(matrix.get("certification_status")))
    promotion = {str(item) for item in matrix.get("promotion_gates", [])}
    missing = sorted(REQUIRED_PROMOTION_GATES - promotion)
    require(not missing, "V1_GOVERNANCE_PROMOTION_GATES", ",".join(missing))

    require_tokens(pre_text, (
        EXPECTED_PRECERTIFY, "validate_v1_governance.py",
        '"v1_governance": "PASS"', '"certify_full": False', '"language_stable": False',
        '"signed_update_v3_host": "PASS"', '"signed_update_v3_browser_wasm": "PASS"',
        '"signed_update_v3_wasi": "PASS_FRESH_RESTORE"',
    ), "V1_GOVERNANCE_PRECERTIFY")
    require_tokens(certify_text, (
        EXPECTED_PRECERTIFY, EXPECTED_CERTIFY, "RUN_TEV_SCRIPT_V1_PRECERTIFY.py",
        '"v1_governance": "PASS"', '"certify_full": True', '"language_stable": False',
        "V1_PRECERTIFY_RECEIPT_SHA256=", "CERTIFY_FULL=PASS", "LANGUAGE_STABLE=NO",
    ), "V1_GOVERNANCE_CERTIFY")
    require_tokens(protocol_text, (
        "PRECERTIFY(C)=PASS", "CERTIFY_FULL(C)=PASS", "PRECERTIFY(S)=PASS",
        "CERTIFY_FULL(S)=PASS", "No transitive certification", "No skipped mandatory target",
    ), "V1_GOVERNANCE_PROTOCOL")
    require_tokens(state_text, (
        "BRANCH=agent/tev-script-v1-irv3-spec-v1",
        "CURRENT_HEAD_FULL_PRECERTIFY=NOT_EXECUTED_HERE",
        "CURRENT_HEAD_CERTIFY_FULL=NO", "LANGUAGE_STABLE=NO",
    ), "V1_GOVERNANCE_PROJECT_STATE")

    print("TEV_SCRIPT_V1_GOVERNANCE_CANON_MATRIX=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_AUTHORITY_FILES=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_BUILD_TOOLING=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_GATE_BINDINGS=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_PUBLIC_SURFACE=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_INTROSPECTION_SURFACE=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_LSP_SURFACE=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_PYTHON_PRODUCTION_SURFACE=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_PYTHON_CERTIFY_FULL_GATE=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_ARTIFACT_COMMIT_POLICY=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_PRECERTIFY_CERTIFY_PROTOCOL=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE_NO_TRANSITIVE_CERTIFICATION=PASS")
    print("TEV_SCRIPT_V1_GOVERNANCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
