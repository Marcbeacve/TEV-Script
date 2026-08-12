from __future__ import annotations

import json
from pathlib import Path
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
        self.assertEqual(
            system_api.system_api_contract_object_v0()["exports"],
            list(system_api.SYSTEM_API_EXPORTS_V0),
        )

    def test_system_api_preserves_exact_stable_public_surface(self):
        root_exports = tuple(getattr(tev_script, "__all__", ()))
        self.assertTrue(root_exports)
        stable_surface = tuple(
            system_api.system_api_contract_object_v0()["surfaces"]["stable_public_api"]
        )
        self.assertEqual(stable_surface, root_exports)
        self.assertTrue(set(root_exports).issubset(set(system_api.SYSTEM_API_EXPORTS_V0)))
        for name in root_exports:
            self.assertIs(getattr(system_api, name), getattr(tev_script, name), name)

    def test_system_canonical_index_requires_complete_handoff_preservation(self):
        root = Path(system_api.__file__).resolve().parents[1]
        document = json.loads(
            (root / "spec" / "TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json").read_text(
                encoding="utf-8"
            )
        )
        api = document["system_api"]
        self.assertEqual(api["stable_public_api_source"], "tev_script.__all__")
        self.assertEqual(api["stable_public_api_surface"], "stable_public_api")
        self.assertIs(api["stable_public_api_superset_required"], True)
        self.assertIs(api["stable_public_api_object_identity_preserved"], True)
        receipt = document["system_integration_receipt"]
        self.assertIs(receipt["exact_receipt_hash_required"], True)
        self.assertIs(receipt["stable_public_api_preserved_required"], True)
        self.assertIs(receipt["wheel_complete_python_module_closure_required"], True)
        consumer = document["consumer_binding"]
        self.assertIs(consumer["integration_receipt_hash_required"], True)
        self.assertIs(consumer["stable_public_api_preservation_required"], True)
        distribution = document["distribution"]
        self.assertIs(distribution["whole_tev_script_python_package_required"], True)
        self.assertIs(distribution["exact_python_module_closure_required"], True)

    def test_complete_high_level_surfaces_are_bound(self):
        contract = system_api.system_api_contract_object_v0()
        surfaces = contract["surfaces"]
        self.assertIn("compile_v1_sources_to_ir_v3", surfaces["stable_public_api"])
        self.assertIn("verify_ir_v3_lowering_receipt", surfaces["stable_public_api"])
        self.assertIn("ScriptRuntimeV3", surfaces["stable_public_api"])
        self.assertIn("PythonRuntimeHostV1", surfaces["stable_public_api"])
        self.assertIn("SYSTEM_CAUSAL_MODULE_PATHS_V0", surfaces["causal_reaction_registry"])
        self.assertIn("load_system_causal_subsystem_v0", surfaces["causal_reaction_registry"])
        self.assertIn("apply_rule", surfaces["semantic_calculus"])
        self.assertIn("admit_realization", surfaces["realization"])
        self.assertIn("resolve_realization_selection", surfaces["realization"])
        self.assertIn("evaluate_search_coverage", surfaces["realization"])
        self.assertIn("HostExecutionAdmissionV1", surfaces["host_realization"])
        self.assertIn("evaluate_execution_activation", surfaces["execution_governance"])
        self.assertIn("evaluate_execution_observation", surfaces["execution_governance"])
        self.assertIn("evaluate_execution_grounded_discovery_cycle", surfaces["execution_governance"])
        self.assertIn("SystemIntegrationReceiptV0", surfaces["integration_binding"])
        self.assertIn("verify_system_integration_receipt_v0", surfaces["integration_binding"])
        self.assertIn("SYSTEM_SUBSYSTEM_MODULE_PATHS_V0", surfaces["complete_semantic_registry"])
        self.assertIn("load_system_subsystem_v0", surfaces["complete_semantic_registry"])

    def test_complete_causal_registry_matches_package_causal_modules(self):
        package_root = Path(system_api.__file__).resolve().parent
        observed = {path.stem for path in package_root.glob("causal_*_v1.py")}
        registered = set(system_api.SYSTEM_CAUSAL_MODULE_PATHS_V0)
        self.assertEqual(registered, observed)
        self.assertEqual(
            system_api.system_api_contract_object_v0()["causal_modules"],
            {key: system_api.SYSTEM_CAUSAL_MODULE_PATHS_V0[key] for key in sorted(registered)},
        )
        for subsystem_id, module_path in system_api.SYSTEM_CAUSAL_MODULE_PATHS_V0.items():
            self.assertEqual(module_path, "tev_script." + subsystem_id)

    def test_causal_subsystem_loader_is_closed_and_loads_complete_reaction_line(self):
        for subsystem_id in sorted(system_api.SYSTEM_CAUSAL_MODULE_PATHS_V0):
            loaded = system_api.load_system_causal_subsystem_v0(subsystem_id)
            self.assertEqual(loaded.__name__, system_api.SYSTEM_CAUSAL_MODULE_PATHS_V0[subsystem_id])
        with self.assertRaises(KeyError):
            system_api.load_system_causal_subsystem_v0("consumer_causal_override")

    def test_complete_semantic_registry_matches_package_semantic_modules(self):
        package_root = Path(system_api.__file__).resolve().parent
        observed = {path.stem for path in package_root.glob("semantic_*.py")}
        registered = set(system_api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0)
        self.assertEqual(registered, observed)
        self.assertEqual(
            system_api.system_api_contract_object_v0()["subsystem_modules"],
            {key: system_api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0[key] for key in sorted(registered)},
        )
        for subsystem_id, module_path in system_api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0.items():
            self.assertEqual(module_path, "tev_script." + subsystem_id)

    def test_semantic_subsystem_loader_is_closed_and_loads_every_registered_layer(self):
        for subsystem_id in sorted(system_api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0):
            loaded = system_api.load_system_subsystem_v0(subsystem_id)
            self.assertEqual(loaded.__name__, system_api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0[subsystem_id])
        with self.assertRaises(KeyError):
            system_api.load_system_subsystem_v0("consumer_private_module")

    def test_consumer_contract_requires_exact_artifact_receipt_and_fail_closed_outcomes(self):
        requirements = set(system_api.system_api_contract_object_v0()["consumer_requirements"])
        self.assertIn("bind_exact_system_api_contract_hash", requirements)
        self.assertIn("bind_exact_distribution_artifact_sha256", requirements)
        self.assertIn("bind_exact_system_integration_receipt_hash", requirements)
        self.assertIn("verify_system_integration_receipt_before_use", requirements)
        self.assertIn("preserve_stable_public_api_surface", requirements)
        self.assertIn("do_not_upgrade_proof_required_or_indeterminate_to_pass", requirements)
        self.assertIn("do_not_treat_no_admissible_realization_as_selection", requirements)
        self.assertIn("do_not_use_backend_identity_as_semantic_identity", requirements)

    def test_system_api_is_opt_in_and_does_not_redefine_v1_package_root(self):
        root_exports = set(getattr(tev_script, "__all__", ()))
        self.assertNotIn("SYSTEM_API_CONTRACT_HASH_V0", root_exports)
        self.assertNotIn("resolve_realization_selection", root_exports)
        self.assertNotIn("verify_system_integration_receipt_v0", root_exports)
        self.assertNotIn("load_system_causal_subsystem_v0", root_exports)
        self.assertNotIn("load_system_subsystem_v0", root_exports)

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
        self.assertEqual(
            contract["system_canonical_index_schema"],
            system_api.SYSTEM_CANONICAL_INDEX_SCHEMA_V0,
        )


if __name__ == "__main__":
    unittest.main()
