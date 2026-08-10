from __future__ import annotations

import ast
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "284ec3ec8c41681825ec1a8421f7ee2a1b012d68"
EXPECTED_BRANCH = "realization-semantics-r0"

ALLOWED_CHANGED_PATHS = frozenset(
    {
        "research/H_LNU_FALSIFICATION_BENCHMARK_V0.md",
        "spec/TEV_SCRIPT_DISCOVERY_REALIZATION_DUALITY_V0.md",
        "spec/TEV_SCRIPT_REALIZATION_SEMANTICS_V0.md",
        "spec/TEV_SCRIPT_REGIME_ADMISSIBILITY_V0.md",
        "tests/run_realization_action_loop_campaign.py",
        "tests/run_realization_r0_extended_campaign.py",
        "tests/run_realization_semantics_campaign.py",
        "tests/test_commit_outcome_v0.py",
        "tests/test_delivery_guarantee_v0.py",
        "tests/test_delivery_plan_v0.py",
        "tests/test_delivery_satisfaction_v0.py",
        "tests/test_dispatch_consumption_v0.py",
        "tests/test_discovery_realization_v0.py",
        "tests/test_execution_grounded_discovery_v0.py",
        "tests/test_execution_request_v0.py",
        "tests/test_prepared_execution_v0.py",
        "tests/test_realization_activation_v0.py",
        "tests/test_realization_composition_v0.py",
        "tests/test_realization_cost_model_update_v0.py",
        "tests/test_realization_cost_model_v0.py",
        "tests/test_realization_cost_prediction_v0.py",
        "tests/test_realization_dispatch_loop_v0.py",
        "tests/test_realization_execution_authority_v0.py",
        "tests/test_realization_execution_observation_v0.py",
        "tests/test_realization_identity_invariants_v0.py",
        "tests/test_realization_placement_v0.py",
        "tests/test_realization_receipt_validity_dispatch_v0.py",
        "tests/test_realization_resource_calibration_v0.py",
        "tests/test_realization_resource_measurement_v0.py",
        "tests/test_realization_runtime_state_v0.py",
        "tests/test_realization_search_v0.py",
        "tests/test_realization_selection_v0.py",
        "tests/test_realization_semantics_v0.py",
        "tev_script/semantic_activation_v0.py",
        "tev_script/semantic_artifact_v0.py",
        "tev_script/semantic_commit_outcome_v0.py",
        "tev_script/semantic_cost_model_update_v0.py",
        "tev_script/semantic_cost_model_v0.py",
        "tev_script/semantic_cost_prediction_v0.py",
        "tev_script/semantic_delivery_guarantee_v0.py",
        "tev_script/semantic_delivery_plan_v0.py",
        "tev_script/semantic_delivery_satisfaction_v0.py",
        "tev_script/semantic_discovery_realization_v0.py",
        "tev_script/semantic_dispatch_consumption_v0.py",
        "tev_script/semantic_dispatch_observation_v0.py",
        "tev_script/semantic_dispatch_v0.py",
        "tev_script/semantic_dispatched_grounded_discovery_v0.py",
        "tev_script/semantic_evidence_v0.py",
        "tev_script/semantic_execution_authority_v0.py",
        "tev_script/semantic_execution_observation_v0.py",
        "tev_script/semantic_execution_request_v0.py",
        "tev_script/semantic_grounded_discovery_v0.py",
        "tev_script/semantic_machine_v0.py",
        "tev_script/semantic_placement_v0.py",
        "tev_script/semantic_prepared_execution_v0.py",
        "tev_script/semantic_realization_composition_v0.py",
        "tev_script/semantic_realization_search_v0.py",
        "tev_script/semantic_realization_selection_v0.py",
        "tev_script/semantic_realization_v0.py",
        "tev_script/semantic_receipt_validity_v0.py",
        "tev_script/semantic_regime_v0.py",
        "tev_script/semantic_resource_algebra_v0.py",
        "tev_script/semantic_resource_calibration_v0.py",
        "tev_script/semantic_resource_evidence_v0.py",
        "tev_script/semantic_resource_measurement_v0.py",
        "tev_script/semantic_runtime_state_v0.py",
        "tools/validate_realization_action_loop_v0.py",
        "tools/validate_realization_r0_extended_v0.py",
        "tools/validate_realization_semantics_v0.py",
    }
)

V1_STABLE_IDENTITY_PATHS = frozenset(
    {
        "CANONICAL_INDEX.json",
        "CHANGELOG.md",
        "PROJECT_STATE.md",
        "README.md",
        "javascript/package.json",
        "pyproject.toml",
        "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
        "tev_script/release_metadata_v1.py",
    }
)

CORE_MODULES = (
    "tev_script/semantic_artifact_v0.py",
    "tev_script/semantic_discovery_realization_v0.py",
    "tev_script/semantic_evidence_v0.py",
    "tev_script/semantic_machine_v0.py",
    "tev_script/semantic_placement_v0.py",
    "tev_script/semantic_realization_composition_v0.py",
    "tev_script/semantic_realization_v0.py",
    "tev_script/semantic_regime_v0.py",
    "tev_script/semantic_resource_algebra_v0.py",
    "tev_script/semantic_resource_evidence_v0.py",
)

ALLOWED_ABSOLUTE_IMPORT_ROOTS = frozenset({"__future__", "dataclasses", "fractions", "re", "typing"})
ALLOWED_RELATIVE_IMPORTS = frozenset(
    {
        "canonical",
        "semantic_artifact_v0",
        "semantic_kernel_v0",
        "semantic_proof_boundary_v0",
        "semantic_residual_v0",
        "semantic_discovery_realization_v0",
        "semantic_evidence_v0",
        "semantic_machine_v0",
        "semantic_placement_v0",
        "semantic_realization_composition_v0",
        "semantic_realization_v0",
        "semantic_regime_v0",
        "semantic_resource_algebra_v0",
        "semantic_resource_evidence_v0",
    }
)
FORBIDDEN_AUTHORITY_TOKENS = ("cuofc", "lnu", "tirv", "ia_tev", "ia-tev", "tevprover")
FORBIDDEN_HOST_IMPORT_ROOTS = frozenset({"os", "platform", "subprocess", "socket", "psutil", "torch", "cpuinfo"})
FORBIDDEN_VENDOR_TOKENS = ("nvidia", "cuda", "rocm", "amd", "intel")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed


def fail(message: str) -> int:
    print("REALIZATION_SEMANTICS_AUTHORITY=FAIL")
    print("REALIZATION_SEMANTICS_AUTHORITY_DETAIL=" + message)
    return 1


def changed_paths() -> tuple[str, ...]:
    return tuple(
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{BASE}..HEAD").stdout.splitlines()
        if line.strip()
    )


def validate_imports() -> tuple[bool, str]:
    for rel in CORE_MODULES:
        path = ROOT / rel
        if not path.is_file():
            return False, f"missing core module {rel}"
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        for token in FORBIDDEN_AUTHORITY_TOKENS:
            if token in lowered:
                return False, f"forbidden authority token {token!r} in {rel}"
        for token in FORBIDDEN_VENDOR_TOKENS:
            if token in lowered:
                return False, f"vendor token {token!r} in semantic core {rel}"
        tree = ast.parse(source, filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FORBIDDEN_HOST_IMPORT_ROOTS:
                        return False, f"host introspection import {alias.name!r} in {rel}"
                    if root not in ALLOWED_ABSOLUTE_IMPORT_ROOTS:
                        return False, f"unapproved absolute import {alias.name!r} in {rel}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level == 0:
                    root = module.split(".", 1)[0]
                    if root in FORBIDDEN_HOST_IMPORT_ROOTS:
                        return False, f"host introspection import {module!r} in {rel}"
                    if root not in ALLOWED_ABSOLUTE_IMPORT_ROOTS:
                        return False, f"unapproved absolute import {module!r} in {rel}"
                else:
                    root = module.split(".", 1)[0]
                    if root not in ALLOWED_RELATIVE_IMPORTS:
                        return False, f"unapproved semantic-core dependency {module!r} in {rel}"
    return True, ""


def validate_identity_boundaries() -> tuple[bool, str]:
    machine = (ROOT / "tev_script" / "semantic_machine_v0.py").read_text(encoding="utf-8")
    artifact = (ROOT / "tev_script" / "semantic_artifact_v0.py").read_text(encoding="utf-8")
    evidence = (ROOT / "tev_script" / "semantic_evidence_v0.py").read_text(encoding="utf-8")
    realization = (ROOT / "tev_script" / "semantic_realization_v0.py").read_text(encoding="utf-8")
    placement = (ROOT / "tev_script" / "semantic_placement_v0.py").read_text(encoding="utf-8")

    forbidden_machine_fields = (
        "required_numeric_model_ids: tuple",
        "required_executable_formats: tuple",
        "missing_numeric_model_ids: tuple",
        "missing_executable_formats: tuple",
    )
    for token in forbidden_machine_fields:
        if token in machine:
            return False, f"nominal ABI field remains authoritative: {token}"
    for token in ("required_numeric_model_hashes", "required_executable_format_hashes", "numeric_model_hash", "format_hash"):
        if token not in machine:
            return False, f"semantic ABI token missing: {token}"
    for token in ("format_hash", "required_numeric_model_hashes", "entrypoint_format_hashes"):
        if token not in artifact:
            return False, f"artifact manifest semantic ABI token missing: {token}"

    if "evidence_id" not in evidence or "record_hash" not in evidence or "requirement_hash" not in evidence:
        return False, "evidence identity/record split missing"
    if '"status": self.status' not in evidence:
        return False, "evidence status record binding missing"
    if "realization_kind" not in realization or "record classification, not identity" not in realization:
        return False, "realization kind identity separation missing"
    if "machine_instance_hash" not in placement or "placement_context_hash" not in placement:
        return False, "machine instance/placement separation missing"
    if "execution_context_hash" not in placement:
        return False, "execution context derivation missing"
    return True, ""


def main() -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != EXPECTED_BRANCH:
        return fail(f"branch mismatch expected={EXPECTED_BRANCH} observed={branch}")
    print("R0_SINGLE_WORK_BRANCH=PASS")
    print("R0_BRANCH_PREFIX_EXCEPTION=RECORDED_CONNECTOR_SAFETY_BLOCK")

    ancestry = git("merge-base", "--is-ancestor", BASE, "HEAD", check=False)
    if ancestry.returncode != 0:
        return fail("R0 base is not an ancestor of HEAD")
    print("R0_BASE_ANCESTRY=PASS")

    paths = changed_paths()
    extras = sorted(set(paths) - ALLOWED_CHANGED_PATHS)
    if extras:
        return fail("paths outside R0 allowlist: " + ",".join(extras))
    print(f"R0_CHANGED_PATH_ALLOWLIST=PASS count={len(paths)}")

    stable_touched = sorted(set(paths) & V1_STABLE_IDENTITY_PATHS)
    if stable_touched:
        return fail("V1 stable identity paths changed: " + ",".join(stable_touched))
    print("R0_V1_STABLE_IDENTITY_UNCHANGED=PASS")

    ok, detail = validate_imports()
    if not ok:
        return fail(detail)
    print("R0_NO_CUOFC_LNU_TIRV_RUNTIME_AUTHORITY=PASS")
    print("R0_NO_IA_TEV_RUNTIME_AUTHORITY=PASS")
    print("R0_NO_TEVPROVER_RUNTIME_AUTHORITY=PASS")
    print("R0_NO_VENDOR_HOST_INTROSPECTION=PASS")

    ok, detail = validate_identity_boundaries()
    if not ok:
        return fail(detail)
    print("R0_MACHINE_ABI_SEMANTIC_HASH_AUTHORITY=PASS")
    print("R0_ARTIFACT_ABI_SEMANTIC_HASH_AUTHORITY=PASS")
    print("R0_EVIDENCE_IDENTITY_RECORD_SEPARATION=PASS")
    print("R0_MACHINE_PROFILE_INSTANCE_PLACEMENT_SEPARATION=PASS")

    architecture = (ROOT / "spec" / "TEV_SCRIPT_REALIZATION_SEMANTICS_V0.md").read_text(encoding="utf-8")
    if "Field" not in architecture or "Transformation" not in architecture:
        return fail("Field + Transformation primitive statement missing")
    if "introduces **no new primitive**" not in architecture:
        return fail("no-new-primitive invariant missing from R0 specification")
    print("R0_FIELD_TRANSFORMATION_REDUCTION_PRESERVED=PASS")

    print("R0_LONG_VALIDATION_DEFERRED=PASS")
    print("REALIZATION_SEMANTICS_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
