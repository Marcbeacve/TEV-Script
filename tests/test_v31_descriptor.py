from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import unittest
from contextlib import redirect_stdout

import tev_script
from tev_script.descriptor_v31 import v31_descriptor, verify_v31_descriptor
from tev_script.describe_v31 import main as describe_main


class V31DescriptorTests(unittest.TestCase):
    def test_descriptor_closes_total_core_surface(self) -> None:
        descriptor = v31_descriptor()
        self.assertEqual(descriptor["schema"], "TEV_SCRIPT_V31_DESCRIPTOR_V1")
        self.assertEqual(descriptor["language_id"], "TEV-Script")
        self.assertEqual(descriptor["language_version"], "3.1.0")
        self.assertEqual(descriptor["program_ir_version"], 5)
        self.assertEqual(descriptor["profiles"], ["total_core"])
        self.assertEqual(descriptor["predecessor_v3"], "3.0.0")
        self.assertTrue(descriptor["v2_units_embedded_without_reinterpretation"])
        self.assertTrue(descriptor["proof_admission_external_only"])
        self.assertFalse(descriptor["physical_effect_commit_inside_runtime"])
        self.assertFalse(descriptor["promotion_authority"])
        self.assertEqual(len(descriptor["descriptor_hash"]), 64)
        self.assertTrue(verify_v31_descriptor(descriptor))

    def test_descriptor_tamper_is_rejected(self) -> None:
        descriptor = copy.deepcopy(v31_descriptor())
        descriptor["physical_effect_commit_inside_runtime"] = True
        self.assertFalse(verify_v31_descriptor(descriptor))

    def test_describe_module_emits_canonical_descriptor(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(describe_main([]), 0)
        observed = json.loads(output.getvalue())
        self.assertEqual(observed, v31_descriptor())
        self.assertEqual(
            output.getvalue().strip(),
            json.dumps(observed, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False),
        )

    def test_descriptor_schema_is_closed_and_version_pinned(self) -> None:
        schema = json.loads(
            Path("schemas/tev-script-v31-descriptor.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(schema["$id"], "TEV_SCRIPT_V31_DESCRIPTOR_V1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["language_version"]["const"], "3.1.0")
        self.assertEqual(schema["properties"]["program_ir_version"]["const"], 5)

    def test_public_api_exports_v31_total_core_surface_additively(self) -> None:
        for name in (
            "TotalCoreProgramV1",
            "TotalCoreUnitV1",
            "VerifiedProofAdmissionV1",
            "compile_total_core_v31",
            "initial_total_core_checkpoint",
            "run_total_core_quantum",
            "validate_total_core_program",
            "v31_descriptor",
        ):
            self.assertTrue(hasattr(tev_script, name), name)


if __name__ == "__main__":
    unittest.main()
