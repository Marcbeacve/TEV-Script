from __future__ import annotations

from pathlib import Path
import unittest

import tev_script

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "v1" / "ErasableToIrV2.tevs"


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

    def test_unversioned_runtime_alias_still_names_v02_runtime(self) -> None:
        self.assertIsNot(tev_script.ScriptRuntime, tev_script.ScriptRuntimeV3)


if __name__ == "__main__":
    unittest.main()
