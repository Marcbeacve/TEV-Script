from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_API = ROOT / "tev_script" / "system_api_v0.py"
SYSTEM_SPEC = ROOT / "spec" / "TEV_SCRIPT_SYSTEM_INTEGRATION_V0.md"
RESOLUTION = ROOT / "tev_script" / "semantic_realization_resolution_v0.py"
HOST = ROOT / "tev_script" / "semantic_host_realization_v1.py"
ROOT_INIT = ROOT / "tev_script" / "__init__.py"
PYPROJECT = ROOT / "pyproject.toml"
BUILDER = ROOT / "tools" / "tev_script_build_backend.py"

FORBIDDEN_ABSOLUTE_IMPORTS = frozenset(
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
REQUIRED_SYSTEM_TOKENS = (
    "SYSTEM_API_CONTRACT_HASH_V0",
    "compile_v1_sources_to_ir_v3",
    "verify_ir_v3_lowering_receipt",
    "ScriptRuntimeV3",
    "SemanticFieldV0",
    "admit_realization",
    "resolve_realization_selection",
    "evaluate_search_coverage",
    "HostExecutionAdmissionV1",
    "evaluate_execution_activation",
    "evaluate_execution_observation",
    "evaluate_execution_grounded_discovery_cycle",
)


def fail(detail: str) -> int:
    print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=FAIL")
    print("TEV_SCRIPT_SYSTEM_INTEGRATION_DETAIL=" + detail)
    return 1


def require(condition: bool, label: str, detail: str = "") -> None:
    if not condition:
        raise RuntimeError(label + (":" + detail if detail else ""))
    print(label + "=PASS")


def main() -> int:
    try:
        for path in (SYSTEM_API, SYSTEM_SPEC, RESOLUTION, HOST, ROOT_INIT, PYPROJECT, BUILDER):
            require(path.is_file(), "SYSTEM_INTEGRATION_REQUIRED_PATH", path.relative_to(ROOT).as_posix())

        source = SYSTEM_API.read_text(encoding="utf-8")
        lowered = source.lower()
        tree = ast.parse(source, filename=str(SYSTEM_API))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    require(root not in FORBIDDEN_ABSOLUTE_IMPORTS, "SYSTEM_API_NO_HOST_INTROSPECTION", alias.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                root = (node.module or "").split(".", 1)[0]
                require(root == "__future__", "SYSTEM_API_ONLY_RELATIVE_PACKAGE_IMPORTS", node.module or "")
        print("SYSTEM_API_IMPORT_BOUNDARY=PASS")

        for token in FORBIDDEN_AUTHORITY_TOKENS:
            require(token not in lowered, "SYSTEM_API_NO_CONSUMER_OR_EXTERNAL_AUTHORITY", token)

        for token in REQUIRED_SYSTEM_TOKENS:
            require(token in source, "SYSTEM_API_REQUIRED_SURFACE", token)

        contract_required = (
            "bind_exact_system_api_contract_hash",
            "bind_exact_distribution_artifact_sha256",
            "do_not_upgrade_proof_required_or_indeterminate_to_pass",
            "do_not_use_backend_identity_as_semantic_identity",
        )
        for token in contract_required:
            require(token in source, "SYSTEM_API_FAIL_CLOSED_CONSUMER_CONTRACT", token)

        root_init = ROOT_INIT.read_text(encoding="utf-8")
        require("system_api_v0" not in root_init, "V1_ROOT_API_NOT_REDEFINED")

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
            "tev_script/semantic_execution_request_v0.py",
            "tev_script/semantic_activation_v0.py",
            "tev_script/semantic_execution_observation_v0.py",
            "tev_script/semantic_grounded_discovery_v0.py",
        ):
            require((ROOT / path_text).is_file(), "SYSTEM_ACTION_LOOP_BOUNDARY_PRESENT", path_text)

        spec = SYSTEM_SPEC.read_text(encoding="utf-8")
        require("Package version text alone is insufficient" in spec, "SYSTEM_ARTIFACT_IDENTITY_NOT_VERSION_ONLY")
        require("SYSTEM_API_CONTRACT_HASH_V0" in spec, "SYSTEM_CONTRACT_DOCUMENTED")
        require("exact distribution artifact SHA-256" in spec, "SYSTEM_ARTIFACT_HASH_DOCUMENTED")

        print("SYSTEM_PUBLIC_RELEASE_PROMOTION=DEFERRED")
        print("LONG_VALIDATION_DEFERRED=PASS")
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=PASS")
        return 0
    except Exception as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
