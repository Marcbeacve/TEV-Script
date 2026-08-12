from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_API = ROOT / "tev_script" / "system_api_v0.py"
SYSTEM_RECEIPT = ROOT / "tev_script" / "system_integration_receipt_v0.py"
SYSTEM_SPEC = ROOT / "spec" / "TEV_SCRIPT_SYSTEM_INTEGRATION_V0.md"
SYSTEM_INDEX = ROOT / "spec" / "TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json"
SYSTEM_ARTIFACT_GATE = ROOT / "RUN_TEV_SCRIPT_SYSTEM_INTEGRATION_V0.py"
RESOLUTION = ROOT / "tev_script" / "semantic_realization_resolution_v0.py"
HOST = ROOT / "tev_script" / "semantic_host_realization_v1.py"
ROOT_INIT = ROOT / "tev_script" / "__init__.py"
PYPROJECT = ROOT / "pyproject.toml"
BUILDER = ROOT / "tools" / "tev_script_build_backend.py"

ALLOWED_ABSOLUTE_IMPORT_ROOTS = frozenset({"__future__", "importlib"})
FORBIDDEN_HOST_INTROSPECTION_IMPORTS = frozenset(
    {
        "os",
        "platform",
        "subprocess",
        "socket",
        "psutil",
        "torch",
        "cpuinfo",
        "ctypes",
    }
)
FORBIDDEN_AUTHORITY_TOKENS = (
    "ia_tev",
    "ia-tev",
    "tevprover",
    "from cuofc",
    "import cuofc",
)
FORBIDDEN_ARTIFACT_GATE_TOKENS = (
    "merge_pull_request",
    "git push",
    "git tag",
    "manage_library",
    "/TEV-Script/Current",
    "\\TEV-Script\\Current",
)
REQUIRED_SYSTEM_TOKENS = (
    "SYSTEM_API_CONTRACT_HASH_V0",
    "SYSTEM_CANONICAL_INDEX_SCHEMA_V0",
    "SYSTEM_CAUSAL_MODULE_PATHS_V0",
    "load_system_causal_subsystem_v0",
    "SYSTEM_SUBSYSTEM_MODULE_PATHS_V0",
    "load_system_subsystem_v0",
    "stable_public_api",
    "compile_v1_sources_to_ir_v3",
    "verify_ir_v3_lowering_receipt",
    "ScriptRuntimeV3",
    "PythonRuntimeHostV1",
    "SemanticFieldV0",
    "admit_realization",
    "resolve_realization_selection",
    "evaluate_search_coverage",
    "HostExecutionAdmissionV1",
    "evaluate_execution_activation",
    "evaluate_execution_observation",
    "evaluate_execution_grounded_discovery_cycle",
    "verify_system_integration_receipt_v0",
)


def fail(detail: str) -> int:
    print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=FAIL")
    print("TEV_SCRIPT_SYSTEM_INTEGRATION_DETAIL=" + detail)
    return 1


def require(condition: bool, label: str, detail: str = "") -> None:
    if not condition:
        raise RuntimeError(label + (":" + detail if detail else ""))
    print(label + "=PASS")


def require_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    for token in tokens:
        require(token in text, label, token)


def assignment_node(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
    raise RuntimeError("missing assignment: " + name)


def literal_assignment(tree: ast.Module, name: str):
    return ast.literal_eval(assignment_node(tree, name))


def sorted_set_assignment(tree: ast.Module, name: str) -> set[str]:
    value = assignment_node(tree, name)
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "tuple" or len(value.args) != 1:
        raise RuntimeError(name + " must be tuple(sorted({...}))")
    sorted_call = value.args[0]
    if not isinstance(sorted_call, ast.Call) or not isinstance(sorted_call.func, ast.Name) or sorted_call.func.id != "sorted" or len(sorted_call.args) != 1:
        raise RuntimeError(name + " must be tuple(sorted({...}))")
    set_node = sorted_call.args[0]
    observed = ast.literal_eval(set_node)
    if not isinstance(observed, set) or any(not isinstance(item, str) for item in observed):
        raise RuntimeError(name + " must contain string literals")
    return observed


def imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def main() -> int:
    try:
        for path in (
            SYSTEM_API,
            SYSTEM_RECEIPT,
            SYSTEM_SPEC,
            SYSTEM_INDEX,
            SYSTEM_ARTIFACT_GATE,
            RESOLUTION,
            HOST,
            ROOT_INIT,
            PYPROJECT,
            BUILDER,
        ):
            require(path.is_file(), "SYSTEM_INTEGRATION_REQUIRED_PATH", path.relative_to(ROOT).as_posix())

        source = SYSTEM_API.read_text(encoding="utf-8")
        lowered = source.lower()
        tree = ast.parse(source, filename=str(SYSTEM_API))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    require(root not in FORBIDDEN_HOST_INTROSPECTION_IMPORTS, "SYSTEM_API_NO_HOST_INTROSPECTION", alias.name)
                    require(root in ALLOWED_ABSOLUTE_IMPORT_ROOTS, "SYSTEM_API_ABSOLUTE_IMPORT_ALLOWLIST", alias.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                root = (node.module or "").split(".", 1)[0]
                require(root not in FORBIDDEN_HOST_INTROSPECTION_IMPORTS, "SYSTEM_API_NO_HOST_INTROSPECTION", node.module or "")
                require(root in ALLOWED_ABSOLUTE_IMPORT_ROOTS, "SYSTEM_API_ABSOLUTE_IMPORT_ALLOWLIST", node.module or "")
        print("SYSTEM_API_IMPORT_BOUNDARY=PASS")

        for token in FORBIDDEN_AUTHORITY_TOKENS:
            require(token not in lowered, "SYSTEM_API_NO_CONSUMER_OR_EXTERNAL_AUTHORITY", token)

        for token in REQUIRED_SYSTEM_TOKENS:
            require(token in source, "SYSTEM_API_REQUIRED_SURFACE", token)

        contract_required = (
            "bind_exact_system_api_contract_hash",
            "bind_exact_distribution_artifact_sha256",
            "verify_system_integration_receipt_before_use",
            "preserve_stable_public_api_surface",
            "do_not_upgrade_proof_required_or_indeterminate_to_pass",
            "do_not_treat_no_admissible_realization_as_selection",
            "do_not_use_backend_identity_as_semantic_identity",
            '"exports": list(SYSTEM_API_EXPORTS_V0)',
            '"causal_modules"',
            '"subsystem_modules"',
            '"stable_public_api"',
            '"causal_reaction_registry"',
            '"complete_semantic_registry"',
            '"integration_binding"',
        )
        require_tokens(source, contract_required, "SYSTEM_API_FAIL_CLOSED_CONSUMER_CONTRACT")

        root_source = ROOT_INIT.read_text(encoding="utf-8")
        root_tree = ast.parse(root_source, filename=str(ROOT_INIT))
        stable_root_exports = tuple(literal_assignment(root_tree, "__all__"))
        require(bool(stable_root_exports), "SYSTEM_STABLE_PUBLIC_API_NONEMPTY")
        require(len(set(stable_root_exports)) == len(stable_root_exports), "SYSTEM_STABLE_PUBLIC_API_UNIQUE")
        surfaces = literal_assignment(tree, "_SYSTEM_SURFACES_V0")
        require(isinstance(surfaces, dict), "SYSTEM_API_SURFACES_OBJECT")
        stable_surface = tuple(surfaces.get("stable_public_api", ()))
        require(stable_surface == stable_root_exports, "SYSTEM_STABLE_PUBLIC_API_EXACT_SURFACE")
        system_export_literals = sorted_set_assignment(tree, "SYSTEM_API_EXPORTS_V0")
        require(set(stable_root_exports).issubset(system_export_literals), "SYSTEM_STABLE_PUBLIC_API_EXPORT_SUPERSET")
        bound_imports = imported_names(tree)
        require(set(stable_root_exports).issubset(bound_imports), "SYSTEM_STABLE_PUBLIC_API_IMPORT_SUPERSET")
        print("SYSTEM_STABLE_PUBLIC_API_PRESERVATION=PASS")

        package_root = ROOT / "tev_script"

        causal_registry = literal_assignment(tree, "SYSTEM_CAUSAL_MODULE_PATHS_V0")
        require(isinstance(causal_registry, dict), "SYSTEM_COMPLETE_CAUSAL_REGISTRY_OBJECT")
        causal_files = tuple(sorted(package_root.glob("causal_*_v1.py")))
        expected_causal_registry = {path.stem: "tev_script." + path.stem for path in causal_files}
        require(bool(expected_causal_registry), "SYSTEM_COMPLETE_CAUSAL_REGISTRY_NONEMPTY")
        require(causal_registry == expected_causal_registry, "SYSTEM_COMPLETE_CAUSAL_REGISTRY_CLOSED")
        require(len(set(causal_registry.values())) == len(causal_registry), "SYSTEM_COMPLETE_CAUSAL_REGISTRY_UNIQUE_PATHS")

        semantic_registry = literal_assignment(tree, "SYSTEM_SUBSYSTEM_MODULE_PATHS_V0")
        require(isinstance(semantic_registry, dict), "SYSTEM_COMPLETE_SEMANTIC_REGISTRY_OBJECT")
        semantic_files = tuple(sorted(package_root.glob("semantic_*.py")))
        expected_semantic_registry = {path.stem: "tev_script." + path.stem for path in semantic_files}
        require(bool(expected_semantic_registry), "SYSTEM_COMPLETE_SEMANTIC_REGISTRY_NONEMPTY")
        require(semantic_registry == expected_semantic_registry, "SYSTEM_COMPLETE_SEMANTIC_REGISTRY_CLOSED")
        require(len(set(semantic_registry.values())) == len(semantic_registry), "SYSTEM_COMPLETE_SEMANTIC_REGISTRY_UNIQUE_PATHS")

        receipt_source = SYSTEM_RECEIPT.read_text(encoding="utf-8")
        require_tokens(
            receipt_source,
            (
                'SYSTEM_INTEGRATION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_SYSTEM_INTEGRATION_RECEIPT_V0"',
                "canonical_hash(body)",
                "expected_system_api_contract_hash",
                "expected_distribution_artifact_sha256",
                "expected_source_head",
                "expected_source_tree",
                "stable_public_api_preserved",
                "wheel_complete_python_module_closure",
                "installed_complete_causal_registry",
                "installed_complete_semantic_registry",
                "installed_receipt_verifier",
                "package version must not be sole system identity",
            ),
            "SYSTEM_RECEIPT_CONTRACT_BOUND",
        )

        system_index = json.loads(SYSTEM_INDEX.read_text(encoding="utf-8"))
        require(system_index.get("schema") == "TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0", "SYSTEM_CANONICAL_INDEX_SCHEMA")
        require(system_index.get("profile") == "POST_V1_REALIZATION_SYSTEM_V0", "SYSTEM_CANONICAL_INDEX_PROFILE")
        require(system_index.get("stable") is False, "SYSTEM_CANONICAL_INDEX_NOT_STABLE")
        require(system_index.get("language_version") == "1.0.0", "SYSTEM_CANONICAL_INDEX_LANGUAGE_VERSION")
        require(system_index.get("language_authority_index") == "CANONICAL_INDEX.json", "SYSTEM_LANGUAGE_AUTHORITY_INDEX_PRESERVED")

        api_index = system_index.get("system_api")
        require(isinstance(api_index, dict), "SYSTEM_CANONICAL_INDEX_API_OBJECT")
        require(api_index.get("implementation") == "tev_script/system_api_v0.py", "SYSTEM_CANONICAL_INDEX_API_BINDING")
        require(api_index.get("schema") == "TEV_SCRIPT_SYSTEM_API_V0", "SYSTEM_CANONICAL_INDEX_API_SCHEMA")
        require(api_index.get("contract_hash_symbol") == "SYSTEM_API_CONTRACT_HASH_V0", "SYSTEM_CANONICAL_INDEX_API_HASH_SYMBOL")
        require(api_index.get("root_api_redefined") is False, "SYSTEM_CANONICAL_INDEX_ROOT_API_UNCHANGED")
        require(api_index.get("stable_public_api_source") == "tev_script.__all__", "SYSTEM_CANONICAL_INDEX_STABLE_API_SOURCE")
        require(api_index.get("stable_public_api_surface") == "stable_public_api", "SYSTEM_CANONICAL_INDEX_STABLE_API_SURFACE")
        require(api_index.get("stable_public_api_superset_required") is True, "SYSTEM_CANONICAL_INDEX_STABLE_API_SUPERSET")
        require(api_index.get("stable_public_api_object_identity_preserved") is True, "SYSTEM_CANONICAL_INDEX_STABLE_API_IDENTITY")

        causal_index = system_index.get("complete_causal_registry")
        require(isinstance(causal_index, dict), "SYSTEM_CANONICAL_INDEX_CAUSAL_REGISTRY_OBJECT")
        require(causal_index.get("source_glob") == "tev_script/causal_*_v1.py", "SYSTEM_CANONICAL_INDEX_CAUSAL_REGISTRY_GLOB")
        require(causal_index.get("api_symbol") == "SYSTEM_CAUSAL_MODULE_PATHS_V0", "SYSTEM_CANONICAL_INDEX_CAUSAL_REGISTRY_SYMBOL")
        require(causal_index.get("loader_symbol") == "load_system_causal_subsystem_v0", "SYSTEM_CANONICAL_INDEX_CAUSAL_REGISTRY_LOADER")
        require(causal_index.get("closed_world") is True, "SYSTEM_CANONICAL_INDEX_CAUSAL_REGISTRY_CLOSED")
        require(causal_index.get("semantic_authority_replaced") is False, "SYSTEM_CANONICAL_INDEX_CAUSAL_AUTHORITY_PRESERVED")

        semantic_index = system_index.get("complete_semantic_registry")
        require(isinstance(semantic_index, dict), "SYSTEM_CANONICAL_INDEX_COMPLETE_REGISTRY_OBJECT")
        require(semantic_index.get("source_glob") == "tev_script/semantic_*.py", "SYSTEM_CANONICAL_INDEX_COMPLETE_REGISTRY_GLOB")
        require(semantic_index.get("api_symbol") == "SYSTEM_SUBSYSTEM_MODULE_PATHS_V0", "SYSTEM_CANONICAL_INDEX_COMPLETE_REGISTRY_SYMBOL")
        require(semantic_index.get("loader_symbol") == "load_system_subsystem_v0", "SYSTEM_CANONICAL_INDEX_COMPLETE_REGISTRY_LOADER")
        require(semantic_index.get("closed_world") is True, "SYSTEM_CANONICAL_INDEX_COMPLETE_REGISTRY_CLOSED")
        require(semantic_index.get("backend_identity_is_semantic_identity") is False, "SYSTEM_CANONICAL_INDEX_BACKEND_NOT_SEMANTIC_IDENTITY")

        receipt_index = system_index.get("system_integration_receipt")
        require(isinstance(receipt_index, dict), "SYSTEM_CANONICAL_INDEX_RECEIPT_OBJECT")
        require(receipt_index.get("implementation") == "tev_script/system_integration_receipt_v0.py", "SYSTEM_CANONICAL_INDEX_RECEIPT_BINDING")
        require(receipt_index.get("schema") == "TEV_SCRIPT_SYSTEM_INTEGRATION_RECEIPT_V0", "SYSTEM_CANONICAL_INDEX_RECEIPT_SCHEMA")
        require(receipt_index.get("verifier") == "verify_system_integration_receipt_v0", "SYSTEM_CANONICAL_INDEX_RECEIPT_VERIFIER")
        require(receipt_index.get("canonical_hash_required") is True, "SYSTEM_CANONICAL_INDEX_RECEIPT_CANONICAL")
        require(receipt_index.get("exact_distribution_sha256_required") is True, "SYSTEM_CANONICAL_INDEX_RECEIPT_ARTIFACT_BINDING")
        require(receipt_index.get("stable_public_api_preserved_required") is True, "SYSTEM_CANONICAL_INDEX_RECEIPT_STABLE_API")
        require(receipt_index.get("wheel_complete_python_module_closure_required") is True, "SYSTEM_CANONICAL_INDEX_RECEIPT_MODULE_CLOSURE")

        implementation_surfaces = system_index.get("implementation_surfaces")
        require(isinstance(implementation_surfaces, dict), "SYSTEM_CANONICAL_INDEX_IMPLEMENTATION_SURFACES")
        for key in (
            "language_pipeline",
            "ir_v3_runtime",
            "semantic_kernel",
            "realization",
            "realization_resolution",
            "realization_search",
            "host_realization",
            "execution_request",
            "activation",
            "execution_observation",
            "grounded_discovery",
            "system_integration_receipt",
        ):
            relative = str(implementation_surfaces.get(key, ""))
            require(bool(relative) and (ROOT / relative).is_file(), "SYSTEM_CANONICAL_INDEX_SURFACE_FILE", key)

        gates = system_index.get("gates")
        require(isinstance(gates, dict), "SYSTEM_CANONICAL_INDEX_GATES")
        require(gates.get("system_focal") == "tests/run_system_integration_v0_focal.py", "SYSTEM_CANONICAL_INDEX_FOCAL_GATE")
        require(gates.get("system_static") == "tools/validate_system_integration_v0.py", "SYSTEM_CANONICAL_INDEX_STATIC_GATE")
        require(gates.get("system_artifact") == "RUN_TEV_SCRIPT_SYSTEM_INTEGRATION_V0.py", "SYSTEM_CANONICAL_INDEX_ARTIFACT_GATE")
        require(gates.get("causal_reaction") == "tests/run_causal_reaction_campaign.py", "SYSTEM_CANONICAL_INDEX_CAUSAL_GATE")
        require(gates.get("post_v1_causal_semantic") == "tests/run_post_v1_integration_campaign.py", "SYSTEM_CANONICAL_INDEX_CAUSAL_SEMANTIC_GATE")

        consumer = system_index.get("consumer_binding")
        require(isinstance(consumer, dict), "SYSTEM_CANONICAL_INDEX_CONSUMER_BINDING")
        for key in (
            "language_version_required",
            "system_api_contract_hash_required",
            "distribution_artifact_sha256_required",
            "integration_receipt_verification_required",
            "stable_public_api_preservation_required",
        ):
            require(consumer.get(key) is True, "SYSTEM_CANONICAL_INDEX_REQUIRED_BINDING", key)
        require(consumer.get("package_version_alone_is_identity") is False, "SYSTEM_CANONICAL_INDEX_NOT_VERSION_ONLY")
        require(consumer.get("consumer_is_semantic_authority") is False, "SYSTEM_CANONICAL_INDEX_CONSUMER_NOT_AUTHORITY")
        require(consumer.get("proof_required_may_be_upgraded") is False, "SYSTEM_CANONICAL_INDEX_PROOF_REQUIRED_PRESERVED")
        require(consumer.get("indeterminate_may_be_implicitly_selected") is False, "SYSTEM_CANONICAL_INDEX_INDETERMINACY_PRESERVED")
        require(consumer.get("no_admissible_realization_may_implicitly_fallback") is False, "SYSTEM_CANONICAL_INDEX_NO_ADMISSIBLE_FALLBACK_FORBIDDEN")

        distribution = system_index.get("distribution")
        require(isinstance(distribution, dict), "SYSTEM_CANONICAL_INDEX_DISTRIBUTION")
        require(distribution.get("python_runtime_dependencies") == 0, "SYSTEM_CANONICAL_INDEX_ZERO_DEPENDENCIES")
        require(distribution.get("whole_tev_script_python_package_required") is True, "SYSTEM_CANONICAL_INDEX_WHOLE_PACKAGE")
        require(distribution.get("exact_python_module_closure_required") is True, "SYSTEM_CANONICAL_INDEX_EXACT_PYTHON_MODULE_CLOSURE")
        require(distribution.get("exact_artifact_hash_required") is True, "SYSTEM_CANONICAL_INDEX_EXACT_ARTIFACT")
        require(distribution.get("installed_complete_causal_registry_required") is True, "SYSTEM_CANONICAL_INDEX_INSTALLED_CAUSAL_REGISTRY")
        require(distribution.get("installed_complete_semantic_registry_required") is True, "SYSTEM_CANONICAL_INDEX_INSTALLED_SEMANTIC_REGISTRY")
        require(distribution.get("installed_receipt_verifier_required") is True, "SYSTEM_CANONICAL_INDEX_INSTALLED_RECEIPT_VERIFIER")
        require(distribution.get("receipt_is_final_admission_artifact") is True, "SYSTEM_CANONICAL_INDEX_RECEIPT_LAST")

        require("system_api_v0" not in root_source, "V1_ROOT_API_NOT_REDEFINED")

        pyproject = PYPROJECT.read_text(encoding="utf-8")
        require("dependencies = []" in pyproject, "SYSTEM_ZERO_RUNTIME_DEPENDENCIES")

        builder = BUILDER.read_text(encoding="utf-8")
        require("package_root.rglob(\"*\")" in builder, "SYSTEM_WHEEL_RECURSIVE_PACKAGE_COLLECTION")
        require("path.suffix != \".py\"" in builder, "SYSTEM_WHEEL_PYTHON_MODULE_FILTER")
        require("entries.append((relative, path.read_bytes()))" in builder, "SYSTEM_WHEEL_MODULE_BYTES_BOUND")

        resolution = RESOLUTION.read_text(encoding="utf-8")
        for token in (
            "SELECTED",
            "INDETERMINATE",
            "NO_ADMISSIBLE_REALIZATION",
            "selection.preference_required",
            "selection.lexicographic_tie",
            "selection.admission_open",
        ):
            require(token in resolution, "R2_INDETERMINACY_PRESERVED", token)

        host = HOST.read_text(encoding="utf-8")
        for token in (
            "HostExecutionEvidenceV1",
            "HostExecutionAdmissionV1",
            "CrossHostEquivalenceV1",
            "receipt_hashes",
            "canonical receipt",
        ):
            require(token in host, "R1_HOST_EVIDENCE_BOUNDARY_PRESENT", token)

        for path_text in (
            "tev_script/causal_analysis_v1.py",
            "tev_script/causal_model_v1.py",
            "tev_script/causal_refinement_v1.py",
            "tev_script/causal_runtime_v1.py",
            "tev_script/semantic_causal_bridge_v0.py",
            "tev_script/semantic_execution_request_v0.py",
            "tev_script/semantic_activation_v0.py",
            "tev_script/semantic_execution_observation_v0.py",
            "tev_script/semantic_grounded_discovery_v0.py",
        ):
            require((ROOT / path_text).is_file(), "SYSTEM_ACTION_LOOP_BOUNDARY_PRESENT", path_text)

        artifact_gate = SYSTEM_ARTIFACT_GATE.read_text(encoding="utf-8")
        for token in FORBIDDEN_ARTIFACT_GATE_TOKENS:
            require(token not in artifact_gate, "SYSTEM_ARTIFACT_GATE_NO_PUBLICATION_OR_CURRENT_MUTATION", token)
        require_tokens(
            artifact_gate,
            (
                "require_clean_checkout",
                "SOURCE_DATE_EPOCH",
                'build_wheel(str(build_a))',
                'build_wheel(str(build_b))',
                "source_python_module_paths",
                "wheel_python_module_paths",
                "SYSTEM_WHEEL_COMPLETE_PYTHON_MODULE_CLOSURE=PASS",
                "venv.EnvBuilder(with_pip=True, clear=True)",
                '"--no-index"',
                '"--no-deps"',
                "SYSTEM_INSTALLED_STABLE_PUBLIC_API=PASS",
                "SYSTEM_CAUSAL_MODULE_PATHS_V0",
                "load_system_causal_subsystem_v0",
                "SYSTEM_INSTALLED_COMPLETE_CAUSAL_REGISTRY=PASS",
                "SYSTEM_SUBSYSTEM_MODULE_PATHS_V0",
                "load_system_subsystem_v0",
                "SYSTEM_INSTALLED_COMPLETE_SEMANTIC_REGISTRY=PASS",
                "build_system_integration_receipt_v0",
                "verify_system_integration_receipt_v0",
                "SYSTEM_INSTALLED_RECEIPT_VERIFIER=PASS",
                "SYSTEM_ARTIFACT_RECEIPT_LAST=PASS",
            ),
            "SYSTEM_ARTIFACT_GATE_BOUNDARY",
        )
        wheel_copy = artifact_gate.find("shutil.copyfile(wheel_a, target_wheel)")
        receipt_copy = artifact_gate.find("shutil.copyfile(staged_receipt, receipt_path)")
        require(wheel_copy >= 0 and receipt_copy > wheel_copy, "SYSTEM_ARTIFACT_RECEIPT_LAST_ORDER")

        spec = SYSTEM_SPEC.read_text(encoding="utf-8")
        require("Package version text alone is insufficient" in spec, "SYSTEM_ARTIFACT_IDENTITY_NOT_VERSION_ONLY")
        require("SYSTEM_API_CONTRACT_HASH_V0" in spec, "SYSTEM_CONTRACT_DOCUMENTED")
        require("TEV_SCRIPT_SYSTEM_INTEGRATION_RECEIPT_V0" in spec, "SYSTEM_RECEIPT_DOCUMENTED")
        require("RUN_TEV_SCRIPT_SYSTEM_INTEGRATION_V0.py" in spec, "SYSTEM_ARTIFACT_GATE_DOCUMENTED")
        require("receipt last" in spec.lower(), "SYSTEM_RECEIPT_LAST_DOCUMENTED")
        require("SYSTEM_CAUSAL_MODULE_PATHS_V0" in spec, "SYSTEM_COMPLETE_CAUSAL_REGISTRY_DOCUMENTED")
        require("SYSTEM_SUBSYSTEM_MODULE_PATHS_V0" in spec, "SYSTEM_COMPLETE_SEMANTIC_REGISTRY_DOCUMENTED")
        require("stable_public_api" in spec, "SYSTEM_STABLE_PUBLIC_API_DOCUMENTED")
        require("stable_public_api_preserved" in spec, "SYSTEM_STABLE_PUBLIC_API_RECEIPT_DOCUMENTED")
        require("wheel_complete_python_module_closure" in spec, "SYSTEM_WHEEL_MODULE_CLOSURE_RECEIPT_DOCUMENTED")

        print("SYSTEM_PUBLIC_RELEASE_PROMOTION=DEFERRED")
        print("LONG_VALIDATION_DEFERRED=PASS")
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=PASS")
        return 0
    except Exception as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
