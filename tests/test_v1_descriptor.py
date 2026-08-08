from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest

from tev_script.canonical import canonical_hash, canonical_json
from tev_script.contracts_v1 import (
    MAX_ARGUMENTS,
    MAX_EXPRESSION_NESTING,
    MAX_SOURCE_BYTES,
    MAX_STATIC_LOOP_ITERATIONS,
    V1_LANGUAGE_VERSION,
)
from tev_script.describe_v1 import main as describe_main
from tev_script.descriptor_v1 import v1_descriptor, v1_descriptor_json

ROOT = Path(__file__).resolve().parents[1]


class V1DescriptorTests(unittest.TestCase):
    def test_descriptor_hash_is_hash_of_body_without_self_hash(self) -> None:
        descriptor = v1_descriptor()
        observed = descriptor["descriptor_hash"]
        body = dict(descriptor)
        del body["descriptor_hash"]
        self.assertEqual(observed, canonical_hash(body))
        self.assertEqual(v1_descriptor_json(), canonical_json(descriptor))

    def test_descriptor_reports_exact_candidate_identity(self) -> None:
        descriptor = v1_descriptor()
        self.assertEqual(descriptor["schema"], "TEV_SCRIPT_DESCRIPTOR_V3")
        self.assertEqual(descriptor["language_version"], V1_LANGUAGE_VERSION)
        self.assertEqual(descriptor["release_status"], "IMPLEMENTATION_CANDIDATE_UNCERTIFIED")
        self.assertIs(descriptor["stable"], False)
        self.assertIs(descriptor["certification"]["current_v1_certify_full_claim"], False)
        self.assertIs(descriptor["certification"]["current_v1_language_stable_claim"], False)

    def test_descriptor_boundaries_preserve_bounded_language(self) -> None:
        boundaries = v1_descriptor()["boundaries"]
        for name in (
            "async_await",
            "classes_inheritance",
            "dynamic_code",
            "exceptions_as_language_control_flow",
            "host_native_object_references",
            "implicit_concurrency",
            "implicit_physical_effects",
            "reflection",
            "recursion",
            "runtime_source_compilation",
            "threads",
            "unbounded_loops",
            "user_defined_generics",
            "general_map",
            "general_variable_size_collection",
        ):
            self.assertIn(name, boundaries)
            self.assertIs(boundaries[name], False)

    def test_descriptor_budgets_are_derived_from_contract_constants(self) -> None:
        budgets = v1_descriptor()["budgets"]
        self.assertEqual(budgets["source_bytes_per_unit"], MAX_SOURCE_BYTES)
        self.assertEqual(budgets["call_arguments"], MAX_ARGUMENTS)
        self.assertEqual(budgets["expression_nesting"], MAX_EXPRESSION_NESTING)
        self.assertEqual(budgets["static_loop_iterations"], MAX_STATIC_LOOP_ITERATIONS)

    def test_descriptor_reports_linked_and_runtime_profiles(self) -> None:
        descriptor = v1_descriptor()
        semantics = descriptor["canonical_semantics"]
        self.assertEqual(semantics["linked_program_schema"], "TEV_SCRIPT_LINKED_PROGRAM_V1")
        self.assertEqual(
            semantics["runtime_targets"],
            ["TEV_SCRIPT_PROGRAM_IR_V2", "TEV_SCRIPT_PROGRAM_IR_V3"],
        )
        self.assertEqual(
            semantics["automatic_target_selection"],
            "IR_V2_IF_LOSSLESSLY_ERASABLE_ELSE_IR_V3",
        )
        self.assertIn("algebraic_runtime_ir_v3", descriptor["features"])
        self.assertGreaterEqual(len(descriptor["features"]), 18)

    def test_descriptor_reports_project_and_receipt_tooling(self) -> None:
        tooling = v1_descriptor()["build_tooling"]
        self.assertEqual(tooling["project_schema"], "TEV_SCRIPT_PROJECT_V1")
        self.assertEqual(
            tooling["lowering_receipts"],
            ["TEV_SCRIPT_LOWERING_RECEIPT_V1", "TEV_SCRIPT_LOWERING_RECEIPT_V2"],
        )
        self.assertEqual(tooling["artifact_commit_policy"], "EVIDENCE_SAFE_RECEIPT_LAST_V1")
        self.assertIs(tooling["project_globs"], False)
        self.assertIs(tooling["project_network_resolution"], False)

    def test_descriptor_reports_editor_tooling_without_second_semantics(self) -> None:
        tooling = v1_descriptor()["editor_tooling"]
        self.assertEqual(tooling["vscode_static_language_package"], "editors/vscode")
        self.assertEqual(tooling["language_server_cli"], "tev-script-v1-lsp")
        self.assertEqual(tooling["language_server_transport"], "LSP_JSON_RPC_STDIO")
        self.assertEqual(tooling["language_server_position_encoding"], "utf-16")
        self.assertEqual(
            tooling["language_server_project_mode"],
            "EXPLICIT_TEV_SCRIPT_PROJECT_V1",
        )
        self.assertIs(tooling["formatter"], False)
        self.assertIs(tooling["independent_semantic_authority"], False)

    def test_descriptor_schema_asset_matches_descriptor_version(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_descriptor_v3.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["schema"]["const"], "TEV_SCRIPT_DESCRIPTOR_V3")
        self.assertEqual(schema["properties"]["language_version"]["const"], V1_LANGUAGE_VERSION)
        self.assertEqual(schema["properties"]["stable"]["const"], False)
        self.assertIn("editor_tooling", schema["required"])
        self.assertFalse(schema["properties"]["editor_tooling"]["additionalProperties"])

    def test_descriptor_module_cli_prints_one_canonical_json_document(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = describe_main()
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text.count("\n"), 1)
        value = json.loads(text)
        self.assertEqual(text.rstrip("\n"), canonical_json(value))
        self.assertEqual(value["descriptor_hash"], v1_descriptor()["descriptor_hash"])


if __name__ == "__main__":
    unittest.main()
