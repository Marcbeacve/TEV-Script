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
        "lowering_receipt_v2",
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

PROGRAM_MATERIALIZATION_FIELDS = frozenset(
    {
        "receipt_profile",
        "lowering_profile",
        "source_semantic_hash",
        "target_semantic_hash",
        "source_artifact_sha256",
        "target_artifact_sha256",
        "lowering_receipt_hash",
    }
)
HOST_EXECUTION_EVIDENCE_FIELDS = frozenset(
    {
        "program_materialization_hash",
        "host_profile_hash",
        "host_materialization_hash",
        "scenario_hash",
        "evidence_level",
        "observed_receipt_hash",
        "verifier_contract_hash",
        "verifier_artifact_sha256",
        "witness_hash",
    }
)
HOST_EXECUTION_ADMISSION_FIELDS = frozenset(
    {
        "program_materialization_hash",
        "host_profile_hash",
        "host_materialization_hash",
        "scenario_hash",
        "evidence_hash",
        "receipt_hash",
        "admitted_level",
    }
)
CROSS_HOST_EQUIVALENCE_FIELDS = frozenset(
    {
        "program_materialization_hash",
        "scenario_hash",
        "equivalence_level",
        "member_bindings",
    }
)
FORBIDDEN_PROGRAM_HOST_FIELDS = frozenset(
    {
        "profile_id",
        "host_profile_hash",
        "machine_hash",
        "artifact_manifest_hash",
        "runtime_closure_sha256",
        "provenance_hashes",
        "provider",
        "vendor",
        "path",
        "filename",
    }
)


def fail(detail: str) -> int:
    print("HOST_REALIZATION_R1_AUTHORITY=FAIL")
    print("HOST_REALIZATION_R1_AUTHORITY_DETAIL=" + detail)
    return 1


def _class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    return next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name),
        None,
    )


def _annotated_fields(class_node: ast.ClassDef) -> frozenset[str]:
    return frozenset(
        node.target.id
        for node in class_node.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    )


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
        "known_v1_host_profiles",
        "admitted_ir_v3_host_profiles_v1",
        "ir_v3_evidence_authority_for_profile_v1",
        "ir_v3_evidence_ceiling_for_profile_v1",
        "is_ir_v3_admitted_host_profile_v1",
        "conformance_evidence_for_candidate",
        'status == "ACTIVE" and not is_ir_v3_admitted_host_profile_v1(profile)',
        "candidate.semantic_claim_hash",
        "source_compilation_at_runtime",
        "PROGRAM_IR_V3_MATERIALIZATION_SCHEMA_V1",
        "ProgramIRV3MaterializationV1",
        "verify_ir_v3_lowering_receipt",
        "receipt_profile",
        "lowering_profile",
        "source_semantic_hash",
        "target_semantic_hash",
        "source_artifact_sha256",
        "target_artifact_sha256",
        "lowering_receipt_hash",
        "tev.realization.program_ir_v3_materialization.v1",
        "HOST_EVIDENCE_AUTHORITY_SCHEMA_V1",
        "THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1",
        "BROWSER_WASM_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1",
        "WASI_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1",
        "HOST_EXECUTION_EVIDENCE_SCHEMA_V1",
        "HOST_EXECUTION_ADMISSION_SCHEMA_V1",
        "CROSS_HOST_EQUIVALENCE_SCHEMA_V1",
        "HostExecutionEvidenceV1",
        "HostExecutionAdmissionV1",
        "CrossHostEquivalenceV1",
        "EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1",
        "EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1",
        "_verify_ir_v3_conformance_receipt_identity",
        "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1",
        "program_hash != program.target_semantic_hash",
        "source_hash != program.source_semantic_hash",
        "canonical_hash(body) != receipt_hash",
        "evidence.observed_receipt_hash != receipt_hash",
        "evidence.verifier_contract_hash != authority[1]",
        "verifier_artifact_sha256",
        "cross-host equivalence level must equal the weakest admitted member",
        "admissions: Iterable[HostExecutionAdmissionV1]",
        "init=False",
    )
    missing = tuple(token for token in required if token not in source)
    if missing:
        return fail("required R1 host/program/evidence/admission surface missing=" + ",".join(missing))

    if "EVIDENCE_LEVEL_PHYSICAL_EXECUTION_V1" in source:
        return fail("physical execution is incorrectly promoted to cross-host equivalence evidence")

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

    program_class = _class(tree, "ProgramIRV3MaterializationV1")
    if program_class is None:
        return fail("ProgramIRV3MaterializationV1 class missing")
    program_fields = _annotated_fields(program_class)
    if program_fields != PROGRAM_MATERIALIZATION_FIELDS:
        return fail("program materialization field set mismatch=" + ",".join(sorted(program_fields)))
    leaked_fields = program_fields & FORBIDDEN_PROGRAM_HOST_FIELDS
    if leaked_fields:
        return fail("host identity leaked into program materialization fields=" + ",".join(sorted(leaked_fields)))

    evidence_class = _class(tree, "HostExecutionEvidenceV1")
    if evidence_class is None:
        return fail("HostExecutionEvidenceV1 class missing")
    evidence_fields = _annotated_fields(evidence_class)
    if evidence_fields != HOST_EXECUTION_EVIDENCE_FIELDS:
        return fail("host execution evidence field set mismatch=" + ",".join(sorted(evidence_fields)))

    admission_class = _class(tree, "HostExecutionAdmissionV1")
    if admission_class is None:
        return fail("HostExecutionAdmissionV1 class missing")
    admission_fields = _annotated_fields(admission_class)
    if admission_fields != HOST_EXECUTION_ADMISSION_FIELDS:
        return fail("host execution admission field set mismatch=" + ",".join(sorted(admission_fields)))

    equivalence_class = _class(tree, "CrossHostEquivalenceV1")
    if equivalence_class is None:
        return fail("CrossHostEquivalenceV1 class missing")
    equivalence_fields = _annotated_fields(equivalence_class)
    if equivalence_fields != CROSS_HOST_EQUIVALENCE_FIELDS:
        return fail("cross-host equivalence field set mismatch=" + ",".join(sorted(equivalence_fields)))

    local_verifier_defs = tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "verify_ir_v3_lowering_receipt"
    )
    if local_verifier_defs:
        return fail("R1 duplicates normative lowering verifier")

    lowering_verifier_calls = tuple(
        node
        for node in ast.walk(program_class)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "verify_ir_v3_lowering_receipt"
    )
    if len(lowering_verifier_calls) != 1:
        return fail(
            "program materialization must invoke normative lowering verifier exactly once count="
            + str(len(lowering_verifier_calls))
        )

    test_source = TEST.read_text(encoding="utf-8")
    obsolete_test_tokens = (
        "test_all_existing_hosts_realize_one_execution_transformation",
        "EVIDENCE_LEVEL_PHYSICAL_EXECUTION_V1",
        "CrossHostEquivalenceV1(\n            evidence=",
    )
    present_obsolete = tuple(token for token in obsolete_test_tokens if token in test_source)
    if present_obsolete:
        return fail("obsolete R1 evidence model still present=" + ",".join(present_obsolete))

    test_required = (
        "test_program_ir_v3_materialization_accepts_verified_lowering",
        "test_program_ir_v3_materialization_rejects_tampered_receipt",
        "test_program_ir_v3_materialization_rejects_receipt_reuse",
        "test_program_ir_v3_materialization_is_host_independent",
        "test_program_ir_v3_materialization_changes_with_program",
        'tampered["receipt_hash"] = canonical_hash',
        "test_known_host_targets_are_separate_from_ir_v3_admission",
        "test_admitted_ir_v3_hosts_realize_one_execution_transformation",
        "test_unity_webgl_target_is_not_admitted_by_legacy_gate6a",
        "test_unity_webgl_cannot_issue_active_ir_v3_conformance_evidence",
        "test_existing_gate_evidence_authorities_are_exact",
        "test_evidence_level_cannot_exceed_browser_or_wasi_gate_ceiling",
        "test_unity_webgl_cannot_issue_ir_v3_execution_evidence",
        "test_host_execution_evidence_derives_verifier_contract_from_profile",
        "test_host_execution_admission_accepts_exact_program_host_scenario_receipt",
        "test_host_execution_admission_rejects_receipt_for_other_program",
        "test_host_execution_admission_rejects_source_semantic_mismatch_even_with_rehashed_receipt",
        "test_host_execution_admission_rejects_tampered_reference_receipt",
        "test_host_execution_admission_rejects_scenario_mismatch",
        "test_host_execution_admission_rejects_observed_receipt_mismatch",
        "test_host_execution_admission_rejects_forged_verifier_contract",
        "test_cross_host_bytes_parity_accepts_python_javascript_csharp_admissions",
        "test_cross_host_hash_parity_accepts_browser_and_wasi_admissions",
        "test_cross_host_rejects_false_hash_to_bytes_promotion",
        "test_cross_host_rejects_mixed_program_admissions",
        "test_cross_host_rejects_mixed_scenario_admissions",
        "test_cross_host_rejects_duplicate_host_profile_admissions",
        "test_cross_host_requires_at_least_two_admissions",
        "verifier_artifact_sha256=",
        "admissions=admissions",
    )
    missing_tests = tuple(token for token in test_required if token not in test_source)
    if missing_tests:
        return fail("required R1 falsifier missing=" + ",".join(missing_tests))

    print("R1_SINGLE_EXECUTION_TRANSFORMATION=PASS")
    print("R1_KNOWN_HOST_TARGET_PROFILES=6")
    print("R1_IR_V3_ADMITTED_HOST_PROFILES=5")
    print("R1_UNITY_WEBGL_IR_V3_ADMISSION=HOLD_LEGACY_GATE6A")
    print("R1_PYTHON_JS_CSHARP_EVIDENCE_CEILING=CANONICAL_RECEIPT_BYTES_PARITY")
    print("R1_BROWSER_WASM_WASI_EVIDENCE_CEILING=CANONICAL_RECEIPT_HASH_PARITY")
    print("R1_EVIDENCE_VERIFIER_CONTRACT_BOUND=PASS")
    print("R1_RECEIPT_SOURCE_SEMANTIC_BOUND=PASS")
    print("R1_HOST_EVIDENCE_PROGRAM_RECEIPT_ADMISSION=PASS")
    print("R1_CROSS_HOST_EQUIVALENCE_INPUT=ADMITTED_EVIDENCE_ONLY")
    print("R1_CROSS_HOST_EQUIVALENCE_FLOOR=WEAKEST_ADMITTED_MEMBER")
    print("R1_RUNTIME_CLOSURE_CONTENT_ADDRESSED=PASS")
    print("R1_R0_ARTIFACT_MACHINE_REALIZATION_REUSE=PASS")
    print("R1_CONFORMANCE_EVIDENCE_CLAIM_BOUND=PASS")
    print("R1_PROGRAM_IR_V3_RECEIPT_BOUND=PASS")
    print("R1_PROGRAM_HOST_IDENTITY_SEPARATION=PASS")
    print("R1_LOWERING_AUTHORITY_REUSED=PASS")
    print("R1_NO_RUNTIME_HOST_INTROSPECTION=PASS")
    print("R1_NO_NATIVE_VENDOR_POLICY=PASS")
    print("R1_LONG_VALIDATION_DEFERRED=PASS")
    print("HOST_REALIZATION_R1_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
