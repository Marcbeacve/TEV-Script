from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tev_script" / "semantic_host_realization_v1.py"
TEST = ROOT / "tests" / "test_host_realization_v1.py"

ALLOWED_ABSOLUTE_IMPORTS = frozenset({"__future__", "dataclasses", "re", "typing"})
ALLOWED_RELATIVE_IMPORTS = frozenset(
    {
        "canonical",
        "semantic_artifact_v0",
        "semantic_evidence_v0",
        "semantic_kernel_v0",
        "semantic_machine_v0",
        "semantic_realization_v0",
        "semantic_resource_algebra_v0",
    }
)
FORBIDDEN_HOST_IMPORTS = frozenset(
    {"os", "platform", "subprocess", "socket", "psutil", "torch", "cpuinfo", "ctypes"}
)
FORBIDDEN_AUTHORITY_TOKENS = ("cuofc", "lnu", "tirv", "ia_tev", "ia-tev", "tevprover")
FORBIDDEN_NATIVE_VENDOR_TOKENS = ("nvidia", "cuda", "rocm", "directx", "metal_backend")


def fail(detail: str) -> int:
    print("HOST_REALIZATION_R1_AUTHORITY=FAIL")
    print("HOST_REALIZATION_R1_AUTHORITY_DETAIL=" + detail)
    return 1


def main() -> int:
    if not MODULE.is_file() or not TEST.is_file():
        return fail("R1 host realization module/test missing")

    source = MODULE.read_text(encoding="utf-8")
    lowered = source.lower()

    for token in FORBIDDEN_AUTHORITY_TOKENS:
        if token in lowered:
            return fail(f"forbidden external semantic authority token={token}")
    for token in FORBIDDEN_NATIVE_VENDOR_TOKENS:
        if token in lowered:
            return fail(f"native/vendor policy leaked into R1 host projection token={token}")

    tree = ast.parse(source, filename=str(MODULE))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_HOST_IMPORTS:
                    return fail(f"host introspection import={alias.name}")
                if root not in ALLOWED_ABSOLUTE_IMPORTS:
                    return fail(f"unapproved absolute import={alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if node.level == 0:
                if root in FORBIDDEN_HOST_IMPORTS:
                    return fail(f"host introspection import={module}")
                if root not in ALLOWED_ABSOLUTE_IMPORTS:
                    return fail(f"unapproved absolute import={module}")
            elif root not in ALLOWED_RELATIVE_IMPORTS:
                return fail(f"unapproved R1 dependency={module}")

    required = (
        "EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1",
        "TEV_SCRIPT_PROGRAM_IR_V3",
        "runtime_closure_sha256",
        "ArtifactManifestV0",
        "MachineFieldV0",
        "RealizationCandidateV0",
        'semantic_relation="EXACT_EQUIVALENT"',
        "python_reference_host_profile_v1",
        "javascript_reference_host_profile_v1",
        "csharp_reference_host_profile_v1",
        "browser_wasm_host_profile_v1",
        "wasi_host_profile_v1",
        "unity_webgl_host_profile_v1",
        "conformance_evidence_for_candidate",
        "candidate.semantic_claim_hash",
        "source_compilation_at_runtime",
    )
    missing = tuple(token for token in required if token not in source)
    if missing:
        return fail("required R1 host surface missing=" + ",".join(missing))

    forbidden_identity_fields = (
        '"path"',
        '"filename"',
        '"absolute_path"',
        '"repository_root"',
    )
    semantic_sections = source[source.index("class HostRuntimeProfileV1") :]
    if any(token in semantic_sections for token in forbidden_identity_fields):
        return fail("physical path/name leaked into host semantic projection")

    if "runtime_closure_sha256" not in source or "content_hash=self.runtime_closure_sha256" not in source:
        return fail("materialized host bytes are not bound into ArtifactManifest")

    if "profile_id" not in source or "metadata" not in source or "profile_hash" not in source:
        return fail("profile semantic/record identity split missing")

    print("R1_SINGLE_EXECUTION_TRANSFORMATION=PASS")
    print("R1_EXISTING_HOST_PROFILES=6")
    print("R1_RUNTIME_CLOSURE_CONTENT_ADDRESSED=PASS")
    print("R1_R0_ARTIFACT_MACHINE_REALIZATION_REUSE=PASS")
    print("R1_CONFORMANCE_EVIDENCE_CLAIM_BOUND=PASS")
    print("R1_NO_RUNTIME_HOST_INTROSPECTION=PASS")
    print("R1_NO_NATIVE_VENDOR_POLICY=PASS")
    print("R1_LONG_VALIDATION_DEFERRED=PASS")
    print("HOST_REALIZATION_R1_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
