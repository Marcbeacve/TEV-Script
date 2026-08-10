from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_host_realization_v1 import (
    BROWSER_WEBASSEMBLY_CAPABILITY_HASH_V1,
    EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
    HostRuntimeMaterializationV1,
    HostRuntimeProfileV1,
    IR_V3_EXECUTION_CAPABILITY_SEMANTIC_HASH_V1,
    WASI_HTTP_LINKAGE_CAPABILITY_HASH_V1,
    browser_wasm_host_profile_v1,
    conformance_evidence_for_candidate,
    csharp_reference_host_profile_v1,
    javascript_reference_host_profile_v1,
    known_v1_host_profiles,
    python_reference_host_profile_v1,
    unity_webgl_host_profile_v1,
    wasi_host_profile_v1,
)
from tev_script.semantic_machine_v0 import evaluate_machine_compatibility


def h(label: str) -> str:
    return canonical_hash({"test": label})


class HostRealizationV1Tests(unittest.TestCase):
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

    def test_all_existing_hosts_realize_one_execution_transformation(self):
        profiles = known_v1_host_profiles()
        self.assertEqual(len(profiles), 6)
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

    def test_profile_alias_and_metadata_do_not_change_semantic_identity(self):
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

    def test_artifact_manifest_requirements_are_satisfied_by_its_profile_machine(self):
        for profile in known_v1_host_profiles():
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

    def test_unity_webgl_is_host_projection_not_new_execution_semantics(self):
        unity = unity_webgl_host_profile_v1()
        candidate = self.candidate(self.materialization(unity))
        self.assertEqual(
            candidate.transformation_semantic_hash,
            EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
        )
        self.assertNotEqual(
            unity.machine.machine_hash,
            csharp_reference_host_profile_v1().machine.machine_hash,
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
