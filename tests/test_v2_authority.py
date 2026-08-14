from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
NORMATIVE_PATHS = (
    "spec/TEV_SCRIPT_V2_LANGUAGE.md",
    "spec/TEV_SCRIPT_PROGRAM_IR_V4.md",
    "spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md",
    "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
    "schemas/tev-script-v2-descriptor.schema.json",
    "schemas/tev-script-program-ir-v4.schema.json",
    "schemas/tev-script-v2-filesystem-artifacts.schema.json",
    "schemas/tev-script-v2-certify-full-receipt.schema.json",
)


class V2AuthorityTests(unittest.TestCase):
    def test_canonical_index_has_one_nonstable_v2_target_with_exact_authority(self) -> None:
        index = json.loads((ROOT / "CANONICAL_INDEX.json").read_text(encoding="utf-8"))
        targets = [
            target
            for target in index["candidate_language_targets"]
            if target["language_version"] == "2.0.0"
        ]
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual(target["status"], "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED")
        self.assertIs(target["stable"], False)
        self.assertEqual(tuple(target["authority_files"]), NORMATIVE_PATHS)
        self.assertEqual(target["gates"]["certify_full"], "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py")
        self.assertEqual(target["public_interfaces"]["v2_cli"], "tev-script-v2")
        self.assertEqual(target["public_interfaces"]["v2_descriptor_cli"], "tev-script-v2-describe")

    def test_every_normative_path_exists_and_feature_matrix_closes_inventory(self) -> None:
        for relative in NORMATIVE_PATHS:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
        matrix = json.loads((ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["schema"], "TEV_SCRIPT_V2_FEATURE_MATRIX_V1")
        self.assertEqual(matrix["language_version"], "2.0.0")
        self.assertIs(matrix["stable"], False)
        self.assertEqual(tuple(matrix["authority_files"]), NORMATIVE_PATHS)
        governed = matrix["governed_paths"]
        for group in ("implementation", "tests", "conformance", "gates", "public_interfaces"):
            self.assertTrue(governed[group], group)
            for relative in governed[group]:
                with self.subTest(group=group, relative=relative):
                    self.assertTrue((ROOT / relative).is_file())

    def test_v2_installed_entry_points_are_additive_and_exact(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = project["project"]["scripts"]
        self.assertEqual(scripts["tev-script-v2"], "tev_script.cli_v2:main")
        self.assertEqual(scripts["tev-script-v2-describe"], "tev_script.describe_v2:main")
        self.assertEqual(scripts["tev-script"], "tev_script.cli:main")
        self.assertEqual(scripts["tev-script-v1"], "tev_script.cli_v1:main")

    def test_v2_authority_does_not_make_a_stable_or_publication_claim(self) -> None:
        matrix = json.loads((ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(encoding="utf-8"))
        self.assertEqual(matrix["certification_status"], "CERTIFICATION_REQUIRED")
        self.assertIs(matrix["stable"], False)
        self.assertIs(matrix["publication_authorized"], False)
        self.assertIs(matrix["merge_authorized"], False)


if __name__ == "__main__":
    unittest.main()
