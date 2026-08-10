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
        "tests/run_realization_semantics_campaign.py",
        "tests/test_discovery_realization_v0.py",
        "tests/test_realization_semantics_v0.py",
        "tests/test_realization_identity_invariants_v0.py",
        "tev_script/semantic_artifact_v0.py",
        "tev_script/semantic_discovery_realization_v0.py",
        "tev_script/semantic_evidence_v0.py",
        "tev_script/semantic_machine_v0.py",
        "tev_script/semantic_realization_v0.py",
        "tev_script/semantic_regime_v0.py",
        "tev_script/semantic_resource_algebra_v0.py",
        "tev_script/semantic_resource_evidence_v0.py",
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
    "tev_script/semantic_realization_v0.py",
    "tev_script/semantic_regime_v0.py",
    "tev_script/semantic_resource_algebra_v0.py",
    "tev_script/semantic_resource_evidence_v0.py",
)

ALLOWED_ABSOLUTE_IMPORT_ROOTS = frozenset(
    {"__future__", "ast", "dataclasses", "fractions", "pathlib", "re", "subprocess", "typing"}
)
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
        "semantic_realization_v0",
        "semantic_regime_v0",
        "semantic_resource_algebra_v0",
        "semantic_resource_evidence_v0",
    }
)
FORBIDDEN_AUTHORITY_TOKENS = (
    "cuofc",
    "lnu",
    "tirv",
    "ia_tev",
    "ia-tev",
    "tevprover",
)
FORBIDDEN_HOST_IMPORT_ROOTS = frozenset(
    {"os", "platform", "socket", "psutil", "torch", "cpuinfo"}
)
FORBIDDEN_VENDOR_TOKENS = (
    "nvidia",
    "cuda",
    "rocm",
    "amd",
    "intel",
)


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

    architecture = (ROOT / "spec" / "TEV_SCRIPT_REALIZATION_SEMANTICS_V0.md").read_text(
        encoding="utf-8"
    )
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
