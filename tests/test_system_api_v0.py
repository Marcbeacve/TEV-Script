from __future__ import annotations

import unittest

import tev_script
from tev_script.canonical import canonical_hash
import tev_script.system_api_v0 as system_api


class SystemApiV0Tests(unittest.TestCase):
    def test_contract_hash_is_canonical_and_language_version_is_explicit(self):
        self.assertEqual(system_api.V1_LANGUAGE_VERSION, "1.0.0")
        self.assertEqual(
            system_api.SYSTEM_API_CONTRACT_HASH_V0,
            canonical_hash(system_api.system_api_contract_object_v0()),
        )

    def test_all_declared_exports_are_present_and_unique(self):
        self.assertEqual(
            system_api.SYSTEM_API_EXPORTS_V0,
            tuple(sorted(set(system_api.SYSTEM_API_EXPORTS_V0))),
        )
        for name in system_api.SYSTEM_API_EXPORTS_V0:
            self.assertTrue(hasattr(system_api, name), name)
        self.assertEqual(set(system_api.__all__), set(system_api.SYSTEM_API_EXPORTS_V0))

    def test_complete_high_level_surfaces_are_bound(self):
        contract = system_api.system_api_contract_object_v0()
        surfaces = contract["surfaces"]
        self.assertIn("compile_v1_sources_to_ir_v3", surfaces["language"])
        self.assertIn("verify_ir_v3_lowering_receipt", surfaces["ir_v3"])
        self.assertIn("apply_rule", surfaces["semantic_calculus"])
        self.assertIn("admit_realization", surfaces["realization"])
        self.assertIn("resolve_realization_selection", surfaces["realization"])
        self.assertIn("evaluate_search_coverage", surfaces["realization"])
        self.assertIn("HostExecutionAdmissionV1", surfaces["host_realization"])
        self.assertIn("evaluate_execution_activation", surfaces["execution_governance"])
        self.assertIn("evaluate_execution_observation", surfaces["execution_governance"])
        self.assertIn("evaluate_execution_grounded_discovery_cycle", surfaces["execution_governance"])

    def test_consumer_contract_requires_exact_artifact_and_fail_closed_outcomes(self):
        requirements = set(system_api.system_api_contract_object_v0()["consumer_requirements"])
        self.assertIn("bind_exact_system_api_contract_hash", requirements)
        self.assertIn("bind_exact_distribution_artifact_sha256", requirements)
        self.assertIn("do_not_upgrade_proof_required_or_indeterminate_to_pass", requirements)
        self.assertIn("do_not_use_backend_identity_as_semantic_identity", requirements)

    def test_system_api_is_opt_in_and_does_not_redefine_v1_package_root(self):
        root_exports = set(getattr(tev_script, "__all__", ()))
        self.assertNotIn("SYSTEM_API_CONTRACT_HASH_V0", root_exports)
        self.assertNotIn("resolve_realization_selection", root_exports)

    def test_no_release_or_repository_mutation_authority_is_exported(self):
        lowered = tuple(name.lower() for name in system_api.SYSTEM_API_EXPORTS_V0)
        forbidden = ("merge", "publish", "release", "tag", "repository_write", "stable_promotion")
        for token in forbidden:
            self.assertFalse(any(token in name for name in lowered), token)

    def test_host_execution_identity_is_part_of_system_contract(self):
        contract = system_api.system_api_contract_object_v0()
        self.assertEqual(
            contract["host_execution_transformation_hash"],
            system_api.EXECUTE_PROGRAM_IR_V3_TRANSFORMATION_HASH_V1,
        )
        self.assertEqual(
            contract["host_interface_hash"],
            system_api.PROGRAM_IR_V3_HOST_INTERFACE_HASH_V1,
        )


if __name__ == "__main__":
    unittest.main()
