from __future__ import annotations

import json
from pathlib import Path
import unittest

from tev_script.descriptor_v3 import v3_descriptor, verify_v3_descriptor

ROOT = Path(__file__).resolve().parents[1]


class V3DescriptorRuntimeTargetsTests(unittest.TestCase):
    def test_descriptor_exposes_exact_independent_runtime_targets(self) -> None:
        descriptor = v3_descriptor()
        self.assertEqual(
            descriptor["runtime_targets"],
            ["python_reference", "javascript_independent"],
        )
        self.assertTrue(verify_v3_descriptor(descriptor))
        schema = json.loads((ROOT / "schemas/tev-script-v3-descriptor.schema.json").read_text(encoding="utf-8"))
        self.assertIn("runtime_targets", schema["required"])
        self.assertEqual(
            schema["properties"]["runtime_targets"]["const"],
            ["python_reference", "javascript_independent"],
        )


if __name__ == "__main__":
    unittest.main()
