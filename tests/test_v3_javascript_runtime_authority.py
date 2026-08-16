from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools import validate_v3_authority as authority

ROOT = Path(__file__).resolve().parents[1]


class V3JavaScriptRuntimeAuthorityTests(unittest.TestCase):
    def test_matrix_governs_independent_javascript_runtime_and_parity(self) -> None:
        matrix = json.loads((ROOT / "spec" / "TEV_SCRIPT_V3_FEATURE_MATRIX.json").read_text(encoding="utf-8"))
        feature_map = {row["id"]: row["status"] for row in matrix["required_features"]}
        self.assertEqual(feature_map["INDEPENDENT_JAVASCRIPT_RUNTIME"], "CLOSED")
        self.assertIn("INDEPENDENT_JAVASCRIPT_RUNTIME", authority.REQUIRED_FEATURES)
        self.assertIn("runtime-js/v3/runtime_v5_semantic.mjs", matrix["governed_paths"]["implementation"])
        self.assertIn("runtime-js/v3/runtime_v5_semantic.mjs", authority.REQUIRED_GOVERNED_PATHS["implementation"])
        self.assertIn("tests/test_runtime_v5_javascript_parity.py", matrix["governed_paths"]["tests"])
        self.assertIn("tests/test_runtime_v5_javascript_parity.py", authority.REQUIRED_GOVERNED_PATHS["tests"])
        self.assertIn("V3_INDEPENDENT_JS_PARITY_PASS", matrix["production_gates"])


if __name__ == "__main__":
    unittest.main()
