from __future__ import annotations

import copy
import unittest

from tev_script.canonical import canonical_hash
from tev_script.diagnostics import TevScriptError
from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.lowering_ir_v3_linked_v1 import lower_linked_program_v1_to_ir_v3
from tev_script.lowering_receipt_v2 import build_ir_v3_lowering_receipt
from tev_script.semantic_host_realization_v1 import (
    BROWSER_WASM_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1,
    BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1,
    CROSS_HOST_EQUIVALENCE_SCHEMA_V1,
    EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
    EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
    EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
    HOST_EXECUTION_ADMISSION_SCHEMA_V1,
    THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1,
    WASI_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1,
    CrossHostEquivalenceV1,
    HostExecutionAdmissionV1,
    HostExecutionEvidenceV1,
    HostRealizationError,
    HostRuntimeMaterializationV1,
    HostRuntimeProfileV1,
    IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1,
    PROGRAM_IR_V3_MATERIALIZATION_SCHEMA_V1,
    ProgramIRV3MaterializationV1,
    WASI_HTTP_LINKAGE_CAPABILITY_HASH_V1,
    admitted_ir_v3_host_profiles_v1,
    browser_wasm_host_profile_v1,
    conformance_evidence_for_candidate,
    csharp_reference_host_profile_v1,
    ir_v3_evidence_authority_for_profile_v1,
    ir_v3_evidence_ceiling_for_profile_v1,
    is_ir_v3_admitted_host_profile_v1,
    javascript_reference_host_profile_v1,
    known_v1_host_profiles,
    python_reference_host_profile_v1,
    unity_webgl_host_profile_v1,
    wasi_host_profile_v1,
)
from tev_script.semantic_machine_v0 import evaluate_machine_compatibility
from tev_script.static_semantics_v1 import analyze_v1_static_semantics


def h(label: str) -> str:
    return canonical_hash({"test": label})


def compile_pair(source_text: str):
    plan = link_v1_sources([SourceInputV1("root.tevs", source_text.encode())])
    linked = emit_linked_program_v1(analyze_v1_static_semantics(plan))
    target = lower_linked_program_v1_to_ir_v3(linked)
    return linked, target


class HostRealizationV1Tests(unittest.TestCase):
    PROGRAM_SOURCE = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
entity E {
  state pair: Pair = Pair(a = 1, b = 2);
  state opt: Option<Int> = Some(3);
  on update {
    match opt {
      Some(value) => { pair = Pair(a = value, b = value); }
      None => { pair = Pair(a = 0, b = 0); }
    }
  }
}
'''

    def materialization(self, profile=None, content="runtime-a"):
        return HostRuntimeMaterializationV1(
            profile or python_reference_host_profile_v1(),
            h(content),
            provenance_hashes=(h("source-tree"),),
        )

    def candidate(self, materialization=None):
        materialization = materialization or self.materialization()
        return materialization.candidate(
            transformation_regime_binding_hash=h("execution-regime-binding"),
            resource_estimate_claim_hash=h("resource-estimate"),
            regime_preservation_claim_hash=h("regime-preservation"),
            evidence_hashes=(),
        )

    def program_materialization(self, source_text=None):
        linked, target = compile_pair(source_text or self.PROGRAM_SOURCE)
        receipt = build_ir_v3_lowering_receipt(linked, target)
        materialization = ProgramIRV3MaterializationV1(
            receipt=receipt.receipt,
            source=linked,
            target=target,
        )
        return linked, target, receipt, materialization

    def conformance_receipt(self, program, scenario="scenario-a"):
        body = {
            "schema": "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1",
            "scenario_id": "scenario.a",
            "scenario_hash": h(scenario),
            "program_semantic_hash": program.target_semantic_hash,
            "source_semantic_hash": program.source_semantic_hash,
            "initial_state_hash": h("initial-state"),
            "steps": [],
            "capability_calls": [],
            "final_state": [],
            "final_state_hash": h("final-state"),
        }
        return {**body, "receipt_hash": canonical_hash(body)}

    def host_execution_evidence(
        self,
        *,
        profile,
        level,
        program=None,
        scenario="scenario-a",
        runtime="runtime-a",
        verifier_artifact="verifier-a",
        witness="witness-a",
        observed_receipt_hash=None,
    ):
        if program is None:
            _, _, _, program = self.program_materialization()
        receipt = self.conformance_receipt(program, scenario)
        host = self.materialization(profile, runtime)
        evidence = HostExecutionEvidenceV1(
            program=program,
            host=host,
            scenario_hash=receipt["scenario_hash"],
            evidence_level=level,
            observed_receipt_hash=observed_receipt_hash or receipt["receipt_hash"],
            verifier_artifact_sha256=h(verifier_artifact),
            witness_hash=h(witness),
        )
        return host, evidence, receipt

    def host_execution_admission(
        self,
        *,
        profile,
        level,
        program=None,
        scenario="scenario-a",
        runtime="runtime-a",
        verifier_artifact="verifier-a",
        witness="witness-a",
    ):
        if program is None:
            _, _, _, program = self.program_materialization()
        host, evidence, receipt = self.host_execution_evidence(
            profile=profile,
            level=level,
            program=program,
            scenario=scenario,
            runtime=runtime,
            verifier_artifact=verifier_artifact,
            witness=witness,
        )
        admission = HostExecutionAdmissionV1(
            program=program,
            host=host,
            evidence=evidence,
            reference_receipt=receipt,
        )
        return host, evidence, receipt, admission

    def test_program_ir_v3_materialization_accepts_verified_lowering(self):
        linked, target, receipt, materialization = self.program_materialization()
        self.assertEqual(materialization.semantic_object()["schema"], PROGRAM_IR_V3_MATERIALIZATION_SCHEMA_V1)
        self.assertEqual(materialization.receipt_profile, receipt.receipt["profile"])
        self.assertEqual(materialization.lowering_profile, receipt.receipt["target"]["lowering_profile"])
        self.assertEqual(materialization.source_semantic_hash, linked.semantic_hash)
        self.assertEqual(materialization.target_semantic_hash, target.ir["semantic_hash"])
        self.assertEqual(materialization.source_artifact_sha256, receipt.receipt["source"]["artifact_sha256"])
        self.assertEqual(materialization.target_artifact_sha256, receipt.receipt["target"]["artifact_sha256"])
        self.assertEqual(materialization.lowering_receipt_hash, receipt.receipt_hash)
        self.assertEqual(materialization.materialization_hash, canonical_hash(materialization.semantic_object()))
        field = materialization.to_field()
        self.assertTrue(field.has("tev.profile", ("tev.realization.program_ir_v3_materialization.v1",)))
        self.assertTrue(field.has("tev.kv", ("materialization_hash", materialization.materialization_hash)))

    def test_program_ir_v3_materialization_rejects_tampered_receipt(self):
        linked, target = compile_pair(self.PROGRAM_SOURCE)
        receipt = build_ir_v3_lowering_receipt(linked, target)
        tampered = copy.deepcopy(receipt.receipt)
        tampered["target"]["artifact_sha256"] = "0" * 64
        tampered["receipt_hash"] = canonical_hash(
            {key: value for key, value in tampered.items() if key != "receipt_hash"}
        )
        with self.assertRaises(TevScriptError):
            ProgramIRV3MaterializationV1(receipt=tampered, source=linked, target=target)

    def test_program_ir_v3_materialization_rejects_receipt_reuse(self):
        linked, target = compile_pair(self.PROGRAM_SOURCE)
        receipt = build_ir_v3_lowering_receipt(linked, target)
        other_linked, other_target = compile_pair(self.PROGRAM_SOURCE.replace("Some(3)", "Some(4)"))
        with self.assertRaises(TevScriptError):
            ProgramIRV3MaterializationV1(
                receipt=receipt.receipt,
                source=other_linked,
                target=other_target,
            )

    def test_program_ir_v3_materialization_is_host_independent(self):
        _, _, _, program = self.program_materialization()
        python_host = self.materialization(python_reference_host_profile_v1(), "python-runtime")
        javascript_host = self.materialization(javascript_reference_host_profile_v1(), "javascript-runtime")
        self.assertNotEqual(python_host.materialization_hash, javascript_host.materialization_hash)
        self.assertNotEqual(python_host.profile.machine.machine_hash, javascript_host.profile.machine.machine_hash)
        self.assertFalse(
            {
                "profile_id",
                "host_profile_hash",
                "machine_hash",
                "artifact_manifest_hash",
                "runtime_closure_sha256",
            }
            & set(program.semantic_object())
        )
        self.assertEqual(program.materialization_hash, canonical_hash(program.semantic_object()))

    def test_program_ir_v3_materialization_changes_with_program(self):
        _, _, _, first = self.program_materialization(self.PROGRAM_SOURCE)
        _, _, _, second = self.program_materialization(self.PROGRAM_SOURCE.replace("Some(3)", "Some(4)"))
        self.assertNotEqual(first.source_semantic_hash, second.source_semantic_hash)
        self.assertNotEqual(first.target_semantic_hash, second.target_semantic_hash)
        self.assertNotEqual(first.lowering_receipt_hash, second.lowering_receipt_hash)
        self.assertNotEqual(first.materialization_hash, second.materialization_hash)

    def test_known_host_targets_are_separate_from_ir_v3_admission(self):
        known = known_v1_host_profiles()
        admitted = admitted_ir_v3_host_profiles_v1()
        self.assertEqual(len(known), 6)
        self.assertEqual(len(admitted), 5)
        self.assertIn(unity_webgl_host_profile_v1().profile_hash, {item.profile_hash for item in known})
        self.assertNotIn(unity_webgl_host_profile_v1().profile_hash, {item.profile_hash for item in admitted})

    def test_admitted_ir_v3_hosts_realize_one_execution_transformation(self):
        profiles = admitted_ir_v3_host_profiles_v1()
        self.assertEqual(len(profiles), 5)
        for profile in profiles:
            materialization = self.materialization(profile)
            candidate = self.candidate(materialization)
            self.assertEqual(
                candidate.transformation_semantic_hash,
                EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
            )
            self.assertEqual(candidate.semantic_relation, "EXACT_EQUIVALENT")

    def test_host_profiles_are_semantically_distinct_by_substrate_not_label(self):
        profiles = known_v1_host_profiles()
        self.assertEqual(len({item.machine.machine_hash for item in profiles}), len(profiles))
        self.assertEqual(len({item.profile_hash for item in profiles}), len(profiles))

    def test_profile_alias_and_metadata_do_not_change_semantic_identity_or_admission(self):
        original = python_reference_host_profile_v1()
        renamed = HostRuntimeProfileV1(
            "python.alias.ir_v3",
            original.executable_format_semantics_hash,
            original.required_substrate_capability_semantic_hashes,
            interface_hash=original.interface_hash,
            semantic_properties=original.semantic_properties,
            metadata={"operator_label": "renamed"},
        )
        self.assertEqual(original.profile_hash, renamed.profile_hash)
        self.assertEqual(original.machine.machine_hash, renamed.machine.machine_hash)
        self.assertNotEqual(original.record_hash, renamed.record_hash)
        self.assertTrue(is_ir_v3_admitted_host_profile_v1(renamed))
        self.assertEqual(
            ir_v3_evidence_authority_for_profile_v1(original),
            ir_v3_evidence_authority_for_profile_v1(renamed),
        )

    def test_runtime_closure_bytes_change_realization_not_machine_profile(self):
        first = self.materialization(content="runtime-a")
        second = self.materialization(content="runtime-b")
        self.assertEqual(first.profile.machine.machine_hash, second.profile.machine.machine_hash)
        self.assertNotEqual(first.artifact_manifest.manifest_hash, second.artifact_manifest.manifest_hash)
        self.assertNotEqual(self.candidate(first).realization_hash, self.candidate(second).realization_hash)

    def test_provenance_change_does_not_change_materialized_semantic_identity(self):
        profile = python_reference_host_profile_v1()
        left = HostRuntimeMaterializationV1(profile, h("runtime"), (h("build-a"),))
        right = HostRuntimeMaterializationV1(profile, h("runtime"), (h("build-b"),))
        self.assertEqual(left.materialization_hash, right.materialization_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)
        self.assertEqual(self.candidate(left).realization_hash, self.candidate(right).realization_hash)
        self.assertNotEqual(self.candidate(left).candidate_hash, self.candidate(right).candidate_hash)

    def test_artifact_manifest_requirements_are_satisfied_by_admitted_profile_machine(self):
        for profile in admitted_ir_v3_host_profiles_v1():
            materialization = self.materialization(profile)
            compatibility = evaluate_machine_compatibility(
                profile.machine,
                materialization.artifact_manifest.machine_requirement,
            )
            self.assertTrue(compatibility.compatible)
            self.assertEqual(compatibility.machine_hash, profile.machine.machine_hash)
            self.assertIn(
                IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1,
                materialization.artifact_manifest.machine_requirement.required_capability_semantic_hashes,
            )

    def test_wasi_and_browser_profiles_preserve_distinct_host_requirements(self):
        browser = browser_wasm_host_profile_v1()
        wasi = wasi_host_profile_v1()
        self.assertIn(
            BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1,
            browser.required_substrate_capability_semantic_hashes,
        )
        self.assertIn(
            WASI_HTTP_LINKAGE_CAPABILITY_HASH_V1,
            wasi.required_substrate_capability_semantic_hashes,
        )
        self.assertNotEqual(browser.machine.machine_hash, wasi.machine.machine_hash)

    def test_existing_gate_evidence_authorities_are_exact(self):
        for profile in (
            python_reference_host_profile_v1(),
            javascript_reference_host_profile_v1(),
            csharp_reference_host_profile_v1(),
        ):
            self.assertEqual(
                ir_v3_evidence_authority_for_profile_v1(profile),
                (
                    EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
                    THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1,
                ),
            )
            self.assertEqual(
                ir_v3_evidence_ceiling_for_profile_v1(profile),
                EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            )
        self.assertEqual(
            ir_v3_evidence_authority_for_profile_v1(browser_wasm_host_profile_v1()),
            (
                EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
                BROWSER_WASM_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1,
            ),
        )
        self.assertEqual(
            ir_v3_evidence_authority_for_profile_v1(wasi_host_profile_v1()),
            (
                EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
                WASI_RECEIPT_HASH_VERIFIER_CONTRACT_HASH_V1,
            ),
        )
        self.assertIsNone(ir_v3_evidence_authority_for_profile_v1(unity_webgl_host_profile_v1()))
        self.assertIsNone(ir_v3_evidence_ceiling_for_profile_v1(unity_webgl_host_profile_v1()))

    def test_unity_webgl_target_is_not_admitted_by_legacy_gate6a(self):
        unity = unity_webgl_host_profile_v1()
        self.assertFalse(is_ir_v3_admitted_host_profile_v1(unity))
        self.assertIsNone(ir_v3_evidence_ceiling_for_profile_v1(unity))

    def test_unity_webgl_cannot_issue_active_ir_v3_conformance_evidence(self):
        profile = unity_webgl_host_profile_v1()
        candidate = self.candidate(self.materialization(profile))
        with self.assertRaises(HostRealizationError):
            conformance_evidence_for_candidate(
                candidate=candidate,
                profile=profile,
                evidence_id="host.conformance.unity.webgl",
                scope_hash=h("legacy-gate6a-scope"),
                verifier_hash=h("legacy-gate6a-verifier"),
                witness_hash=h("legacy-gate6a-witness"),
            )

    def test_conformance_evidence_targets_candidate_semantic_claim(self):
        profile = javascript_reference_host_profile_v1()
        candidate = self.candidate(self.materialization(profile))
        evidence = conformance_evidence_for_candidate(
            candidate=candidate,
            profile=profile,
            evidence_id="host.conformance.js",
            scope_hash=h("conformance-scope"),
            verifier_hash=h("portable-conformance-verifier"),
            witness_hash=h("portable-conformance-receipt"),
        )
        self.assertEqual(evidence.claim_hash, candidate.semantic_claim_hash)
        self.assertEqual(evidence.method, "DIFFERENTIAL_TEST")
        self.assertEqual(evidence.coverage["host_profile_hash"], profile.profile_hash)
        self.assertEqual(
            evidence.coverage["execution_transformation_hash"],
            EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
        )

    def test_evidence_local_label_does_not_change_evidence_identity(self):
        profile = csharp_reference_host_profile_v1()
        candidate = self.candidate(self.materialization(profile))
        kwargs = dict(
            candidate=candidate,
            profile=profile,
            scope_hash=h("scope"),
            verifier_hash=h("three-runtime-verifier"),
            witness_hash=h("three-runtime-receipt"),
        )
        left = conformance_evidence_for_candidate(evidence_id="host.csharp.a", **kwargs)
        right = conformance_evidence_for_candidate(evidence_id="host.csharp.b", **kwargs)
        self.assertEqual(left.evidence_hash, right.evidence_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_host_execution_evidence_derives_verifier_contract_from_profile(self):
        _, _, _, program = self.program_materialization()
        host, evidence, receipt = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
        )
        self.assertEqual(evidence.program_materialization_hash, program.materialization_hash)
        self.assertEqual(evidence.host_profile_hash, host.profile.profile_hash)
        self.assertEqual(evidence.host_materialization_hash, host.materialization_hash)
        self.assertEqual(evidence.scenario_hash, receipt["scenario_hash"])
        self.assertEqual(evidence.observed_receipt_hash, receipt["receipt_hash"])
        self.assertEqual(
            evidence.verifier_contract_hash,
            THREE_RUNTIME_RECEIPT_BYTES_VERIFIER_CONTRACT_HASH_V1,
        )
        self.assertEqual(evidence.verifier_artifact_sha256, h("verifier-a"))
        self.assertEqual(evidence.evidence_hash, canonical_hash(evidence.semantic_object()))

    def test_evidence_level_cannot_exceed_browser_or_wasi_gate_ceiling(self):
        _, _, _, program = self.program_materialization()
        for profile in (browser_wasm_host_profile_v1(), wasi_host_profile_v1()):
            with self.assertRaises(HostRealizationError):
                self.host_execution_evidence(
                    profile=profile,
                    level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
                    program=program,
                )

    def test_unity_webgl_cannot_issue_ir_v3_execution_evidence(self):
        _, _, _, program = self.program_materialization()
        with self.assertRaises(HostRealizationError):
            self.host_execution_evidence(
                profile=unity_webgl_host_profile_v1(),
                level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
                program=program,
            )

    def test_host_execution_admission_accepts_exact_program_host_scenario_receipt(self):
        _, _, _, program = self.program_materialization()
        host, evidence, receipt, admission = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
        )
        self.assertEqual(admission.semantic_object()["schema"], HOST_EXECUTION_ADMISSION_SCHEMA_V1)
        self.assertEqual(admission.program_materialization_hash, program.materialization_hash)
        self.assertEqual(admission.host_profile_hash, host.profile.profile_hash)
        self.assertEqual(admission.host_materialization_hash, host.materialization_hash)
        self.assertEqual(admission.scenario_hash, receipt["scenario_hash"])
        self.assertEqual(admission.evidence_hash, evidence.evidence_hash)
        self.assertEqual(admission.receipt_hash, receipt["receipt_hash"])
        self.assertEqual(admission.admission_hash, canonical_hash(admission.semantic_object()))

    def test_host_execution_admission_rejects_receipt_for_other_program(self):
        _, _, _, program = self.program_materialization(self.PROGRAM_SOURCE)
        _, _, _, other_program = self.program_materialization(self.PROGRAM_SOURCE.replace("Some(3)", "Some(4)"))
        host, evidence, _ = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
        )
        other_receipt = self.conformance_receipt(other_program)
        with self.assertRaises(HostRealizationError):
            HostExecutionAdmissionV1(
                program=program,
                host=host,
                evidence=evidence,
                reference_receipt=other_receipt,
            )

    def test_host_execution_admission_rejects_source_semantic_mismatch_even_with_rehashed_receipt(self):
        _, _, _, program = self.program_materialization()
        host, evidence, receipt = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
        )
        tampered = dict(receipt)
        tampered["source_semantic_hash"] = h("wrong-source-semantic-hash")
        tampered["receipt_hash"] = canonical_hash(
            {key: value for key, value in tampered.items() if key != "receipt_hash"}
        )
        with self.assertRaises(HostRealizationError):
            HostExecutionAdmissionV1(
                program=program,
                host=host,
                evidence=evidence,
                reference_receipt=tampered,
            )

    def test_host_execution_admission_rejects_tampered_reference_receipt(self):
        _, _, _, program = self.program_materialization()
        host, evidence, receipt = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
        )
        tampered = dict(receipt)
        tampered["final_state_hash"] = h("tampered-final-state")
        with self.assertRaises(HostRealizationError):
            HostExecutionAdmissionV1(
                program=program,
                host=host,
                evidence=evidence,
                reference_receipt=tampered,
            )

    def test_host_execution_admission_rejects_scenario_mismatch(self):
        _, _, _, program = self.program_materialization()
        host, evidence, _ = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
            scenario="scenario-a",
        )
        other_receipt = self.conformance_receipt(program, "scenario-b")
        with self.assertRaises(HostRealizationError):
            HostExecutionAdmissionV1(
                program=program,
                host=host,
                evidence=evidence,
                reference_receipt=other_receipt,
            )

    def test_host_execution_admission_rejects_observed_receipt_mismatch(self):
        _, _, _, program = self.program_materialization()
        host, evidence, receipt = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
            observed_receipt_hash=h("wrong-observed-receipt"),
        )
        with self.assertRaises(HostRealizationError):
            HostExecutionAdmissionV1(
                program=program,
                host=host,
                evidence=evidence,
                reference_receipt=receipt,
            )

    def test_host_execution_admission_rejects_forged_verifier_contract(self):
        _, _, _, program = self.program_materialization()
        host, evidence, receipt = self.host_execution_evidence(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
        )
        object.__setattr__(evidence, "verifier_contract_hash", h("forged-verifier-contract"))
        with self.assertRaises(HostRealizationError):
            HostExecutionAdmissionV1(
                program=program,
                host=host,
                evidence=evidence,
                reference_receipt=receipt,
            )

    def test_cross_host_bytes_parity_accepts_python_javascript_csharp_admissions(self):
        _, _, _, program = self.program_materialization()
        admissions = []
        for index, profile in enumerate(
            (
                python_reference_host_profile_v1(),
                javascript_reference_host_profile_v1(),
                csharp_reference_host_profile_v1(),
            )
        ):
            admission = self.host_execution_admission(
                profile=profile,
                level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
                program=program,
                runtime=f"runtime-{index}",
                verifier_artifact="three-runtime-parity-verifier",
                witness="three-runtime-parity-witness",
            )[3]
            admissions.append(admission)
        equivalence = CrossHostEquivalenceV1(
            admissions=admissions,
            claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
        )
        self.assertEqual(equivalence.semantic_object()["schema"], CROSS_HOST_EQUIVALENCE_SCHEMA_V1)
        self.assertEqual(
            equivalence.equivalence_level,
            EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
        )
        self.assertEqual(len(equivalence.member_bindings), 3)

    def test_cross_host_hash_parity_accepts_browser_and_wasi_admissions(self):
        _, _, _, program = self.program_materialization()
        browser = self.host_execution_admission(
            profile=browser_wasm_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            runtime="browser-runtime",
            verifier_artifact="browser-parity-verifier",
            witness="browser-parity-witness",
        )[3]
        wasi = self.host_execution_admission(
            profile=wasi_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            runtime="wasi-runtime",
            verifier_artifact="wasi-parity-verifier",
            witness="wasi-parity-witness",
        )[3]
        equivalence = CrossHostEquivalenceV1(
            admissions=(browser, wasi),
            claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
        )
        self.assertEqual(
            equivalence.equivalence_level,
            EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
        )

    def test_cross_host_rejects_false_hash_to_bytes_promotion(self):
        _, _, _, program = self.program_materialization()
        python = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            program=program,
            runtime="python-runtime",
        )[3]
        browser = self.host_execution_admission(
            profile=browser_wasm_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            runtime="browser-runtime",
        )[3]
        with self.assertRaises(HostRealizationError):
            CrossHostEquivalenceV1(
                admissions=(python, browser),
                claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_BYTES_PARITY_V1,
            )

    def test_cross_host_rejects_mixed_program_admissions(self):
        _, _, _, first_program = self.program_materialization(self.PROGRAM_SOURCE)
        _, _, _, second_program = self.program_materialization(self.PROGRAM_SOURCE.replace("Some(3)", "Some(4)"))
        python = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=first_program,
            runtime="python-runtime",
        )[3]
        javascript = self.host_execution_admission(
            profile=javascript_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=second_program,
            runtime="javascript-runtime",
        )[3]
        with self.assertRaises(HostRealizationError):
            CrossHostEquivalenceV1(
                admissions=(python, javascript),
                claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            )

    def test_cross_host_rejects_mixed_scenario_admissions(self):
        _, _, _, program = self.program_materialization()
        python = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            scenario="scenario-a",
            runtime="python-runtime",
        )[3]
        javascript = self.host_execution_admission(
            profile=javascript_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            scenario="scenario-b",
            runtime="javascript-runtime",
        )[3]
        with self.assertRaises(HostRealizationError):
            CrossHostEquivalenceV1(
                admissions=(python, javascript),
                claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            )

    def test_cross_host_rejects_duplicate_host_profile_admissions(self):
        _, _, _, program = self.program_materialization()
        left = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            runtime="python-runtime-a",
            witness="python-witness-a",
        )[3]
        right = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
            runtime="python-runtime-b",
            witness="python-witness-b",
        )[3]
        with self.assertRaises(HostRealizationError):
            CrossHostEquivalenceV1(
                admissions=(left, right),
                claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            )

    def test_cross_host_requires_at_least_two_admissions(self):
        _, _, _, program = self.program_materialization()
        python = self.host_execution_admission(
            profile=python_reference_host_profile_v1(),
            level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            program=program,
        )[3]
        with self.assertRaises(HostRealizationError):
            CrossHostEquivalenceV1(
                admissions=(python,),
                claimed_level=EVIDENCE_LEVEL_CANONICAL_RECEIPT_HASH_PARITY_V1,
            )

    def test_known_profile_factories_are_deterministic(self):
        self.assertEqual(
            python_reference_host_profile_v1().profile_hash,
            python_reference_host_profile_v1().profile_hash,
        )
        self.assertEqual(
            javascript_reference_host_profile_v1().profile_hash,
            javascript_reference_host_profile_v1().profile_hash,
        )
        self.assertEqual(
            csharp_reference_host_profile_v1().profile_hash,
            csharp_reference_host_profile_v1().profile_hash,
        )


if __name__ == "__main__":
    unittest.main()
