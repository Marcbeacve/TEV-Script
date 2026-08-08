from __future__ import annotations

import json
from pathlib import Path
import unittest

from tev_script.descriptor_v1 import v1_descriptor

ROOT = Path(__file__).resolve().parents[1]


class V1DescriptorSchemaCardinalityTests(unittest.TestCase):
    def test_descriptor_satisfies_schema_feature_cardinality(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_descriptor_v3.schema.json").read_text(
                encoding="utf-8"
            )
        )
        descriptor = v1_descriptor()
        feature_rule = schema["properties"]["features"]
        self.assertGreaterEqual(
            len(descriptor["features"]),
            feature_rule["minItems"],
        )
        self.assertEqual(
            len(descriptor["features"]),
            len(set(descriptor["features"])),
        )


if __name__ == "__main__":
    unittest.main()
