from __future__ import annotations

from pathlib import Path
import unittest

import tev_script

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "v1" / "ErasableToIrV2.tevs"
ALGEBRAIC = ROOT / "examples" / "v1" / "Calculator.tevs"
PROJECT = ROOT / "examples" / "v1" / "ecosystem" / "tevscript.project.json"


class V1PublicApiTests(unittest.TestCase):
    def test_v02_public_names_remain_available(self) -> None:
        for name in (
            "CompilationBundle",
            "IR_SCHEMA",
            "LANGUAGE_VERSION",
            "ScriptRuntime",
            "compile_bytes",
            "compile_path",
            "run_conformance",
        ):
            self.assertTrue(hasattr(tev_script, name), name)
            self.assertIn(name, tev_script.__all__)

    def test_v1_public_names_are_explicitly_versioned(self) -> None:
        for name in (
            "V1AnalysisBundle",
            "V1AutoCompilationBundle",
            "V1IrV2CompilationBundle",
            "V1IrV3CompilationBundle",
            "analyze_v1_paths",
            "compile_v1_paths_auto",
            "compile_v1_paths_to_ir_v2",
            "compile_v1_paths_to_ir_v3",
            "ProjectManifestV1",
            "ProjectSourceV1",
            "load_v1_project",
            "verify_v1_project_inputs",
            "LoweringReceiptBundleV1",
            "LoweringReceiptBundleV2",
            "build_ir_v2_lowering_receipt",
            "build_ir_v3_lowering_receipt",
            "verify_ir_v2_lowering_receipt",
            "verify_ir_v3_lowering_receipt",
            "RecordValueV3",
            "VariantValueV3",
            "TypeTableV3",
            "build_type_table_v3",
            "encode_v3_value",
            "decode_v3_value",
            "validate_program_ir_v3",
            "IrV3ConformanceReceiptBundle",
            "run_ir_v3_conformance",
            "ScriptRuntimeV3",
            "RuntimeCheckpointV2",
        ):
            self.assertTrue(hasattr(tev_script, name), name)
            self.assertIn(name, tev_script.__all__)

    def test_public_auto_compile_uses_same_boundary_policy_as_cli(self) -> None:
        result = tev_script.compile_v1_paths_auto([EXAMPLE])
        self.assertEqual(result.target_ir, "TEV_SCRIPT_PROGRAM_IR_V2")
        self.assertEqual(result.target.ir["schema"], result.target_ir)
        self.assertEqual(
            result.target.linked_semantic_hash,
            result.analysis.linked_program.semantic_hash,
        )

    def test_public_project_manifest_loads_explicit_source_set(self) -> None:
        project = tev_script.load_v1_project(PROJECT)
        self.assertEqual(project.default_target, "auto")
        self.assertEqual(len(project.sources), 4)
        self.assertRegex(project.manifest_hash, r"^[0-9a-f]{64}$")
        self.assertRegex(project.project_input_hash, r"^[0-9a-f]{64}$")
        tev_script.verify_v1_project_inputs(project, project.input_witness())

    def test_public_api_builds_and_verifies_ir_v2_lowering_receipt(self) -> None:
        compiled = tev_script.compile_v1_paths_to_ir_v2([EXAMPLE])
        receipt = tev_script.build_ir_v2_lowering_receipt(
            compiled.analysis.linked_program,
            compiled.target,
        )
        self.assertEqual(receipt.receipt["schema"], "TEV_SCRIPT_LOWERING_RECEIPT_V1")
        tev_script.verify_ir_v2_lowering_receipt(
            receipt.receipt,
            compiled.analysis.linked_program,
            compiled.target,
        )

    def test_public_api_builds_and_verifies_ir_v3_lowering_receipt(self) -> None:
        compiled = tev_script.compile_v1_paths_to_ir_v3([ALGEBRAIC])
        tev_script.validate_program_ir_v3(
            compiled.target.ir,
            expected_source_semantic_hash=compiled.analysis.linked_program.semantic_hash,
        )
        receipt = tev_script.build_ir_v3_lowering_receipt(
            compiled.analysis.linked_program,
            compiled.target,
        )
        self.assertEqual(receipt.receipt["schema"], "TEV_SCRIPT_LOWERING_RECEIPT_V2")
        tev_script.verify_ir_v3_lowering_receipt(
            receipt.receipt,
            compiled.analysis.linked_program,
            compiled.target,
        )

    def test_unversioned_runtime_alias_still_names_v02_runtime(self) -> None:
        self.assertIsNot(tev_script.ScriptRuntime, tev_script.ScriptRuntimeV3)


if __name__ == "__main__":
    unittest.main()
