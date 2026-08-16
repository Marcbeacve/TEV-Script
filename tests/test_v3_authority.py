from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from tools.validate_v3_authority import validate_v3_matrix
from tev_script.descriptor_v3 import v3_descriptor
from tev_script.release_metadata_v3 import validate_release_metadata_v3

ROOT = Path(__file__).resolve().parents[1]


class V3AuthorityTests(unittest.TestCase):
    def _matrix(self) -> dict:
        return json.loads((ROOT / "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json").read_text(encoding="utf-8"))

    def test_matrix_closes_exact_v3_authority_surface(self) -> None:
        report = validate_v3_matrix(self._matrix(), validate_release_metadata_v3(), v3_descriptor())
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["all_required_features_closed"])
        self.assertTrue(report["governed_paths_unique"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["merge_authorized"])
        self.assertIn("RUN_TEV_SCRIPT_V3_STABLE_ADMISSION.py", report["governed_paths"])
        self.assertIn("packaging/v3/pyproject.toml", report["governed_paths"])
        self.assertIn("tev_script/translation_validation_v3.py", report["governed_paths"])

    def test_matrix_tamper_and_missing_governed_path_reject(self) -> None:
        matrix = self._matrix()
        tampered = copy.deepcopy(matrix)
        tampered["required_features"][0]["status"] = "OPEN"
        self.assertEqual(validate_v3_matrix(tampered, validate_release_metadata_v3(), v3_descriptor())["status"], "FAIL")
        missing = copy.deepcopy(matrix)
        missing["governed_paths"]["implementation"] = missing["governed_paths"]["implementation"][:-1]
        self.assertEqual(validate_v3_matrix(missing, validate_release_metadata_v3(), v3_descriptor())["status"], "FAIL")

    def test_release_status_and_descriptor_must_match_metadata(self) -> None:
        matrix = self._matrix()
        wrong = copy.deepcopy(matrix); wrong["stable"] = not matrix["stable"]
        self.assertEqual(validate_v3_matrix(wrong, validate_release_metadata_v3(), v3_descriptor())["status"], "FAIL")
        descriptor = dict(v3_descriptor()); descriptor["stable"] = not descriptor["stable"]
        self.assertEqual(validate_v3_matrix(matrix, validate_release_metadata_v3(), descriptor)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
