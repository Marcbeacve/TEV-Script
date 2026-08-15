from __future__ import annotations

from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import tools.validate_v2_authority as authority
from tev_script import release_metadata_v2 as release_metadata

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
CANDIDATE = {
    "RELEASE_PROFILE": "candidate",
    "RELEASE_STATUS": "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
    "STABLE": False,
    "CURRENT_V2_CERTIFY_FULL_CLAIM": False,
    "CURRENT_V2_LANGUAGE_STABLE_CLAIM": False,
    "TECHNICAL_PARENT_COMMIT": "",
    "TECHNICAL_PARENT_CERTIFICATE_SHA256": "",
}


def current_expected_state() -> tuple[str, str, bool]:
    if release_metadata.RELEASE_PROFILE == "candidate":
        return (
            "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
            "CERTIFICATION_REQUIRED",
            False,
        )
    if release_metadata.RELEASE_PROFILE == "stable":
        return (
            "STABLE_ADMISSION_REQUESTED",
            "STABLE_ADMISSION_REQUESTED",
            True,
        )
    raise AssertionError(release_metadata.RELEASE_PROFILE)


class V2AuthorityTests(unittest.TestCase):
    def test_inventory_rejects_unlisted_test_importing_governed_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            governed = {
                "implementation": ["tev_script/ir_v4_effect_commands.py"],
                "tests": ["tests/test_listed.py"],
                "conformance": ["conformance/cases.json"],
                "gates": ["tools/gate.py"],
                "public_interfaces": ["pyproject.toml"],
            }
            matrix = {
                "schema": "TEV_SCRIPT_V2_FEATURE_MATRIX_V1",
                "language_version": "2.0.0",
                "certification_status": "CERTIFICATION_REQUIRED",
                "stable": False,
                "certified_base_sha": authority.V2_CERTIFIED_BASE_SHA,
                "authority_files": list(authority.AUTHORITY_PATHS),
                "governed_paths": governed,
            }
            target = {
                "language_version": "2.0.0",
                "status": "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
                "stable": False,
                "authority_files": list(authority.AUTHORITY_PATHS),
                "certified_base_sha": authority.V2_CERTIFIED_BASE_SHA,
                "publication_authorized": False,
                "merge_authorized": False,
            }
            contents = {
                "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json": json.dumps(matrix),
                "CANONICAL_INDEX.json": json.dumps(
                    {"candidate_language_targets": [target]}
                ),
                "tests/test_unlisted.py": (
                    "from tev_script.ir_v4_effect_commands import "
                    "build_effect_action_r2_v4\n"
                ),
            }
            required_paths = set(authority.AUTHORITY_PATHS)
            required_paths.update(
                path for paths in governed.values() for path in paths
            )
            required_paths.update(contents)
            for relative in required_paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    contents.get(relative, "{}\n"), encoding="utf-8"
                )

            with ExitStack() as stack:
                stack.enter_context(patch.object(authority, "ROOT", root))
                for name, value in CANDIDATE.items():
                    stack.enter_context(
                        patch.object(authority.release_metadata, name, value)
                    )
                with self.assertRaisesRegex(
                    authority.V2AuthorityFailure,
                    "tests/test_unlisted.py",
                ):
                    authority._require_inventory("candidate")

    def test_canonical_index_has_one_v2_target_matching_current_profile(self) -> None:
        target_status, _, stable = current_expected_state()
        index = json.loads(
            (ROOT / "CANONICAL_INDEX.json").read_text(encoding="utf-8")
        )
        targets = [
            target
            for target in index["candidate_language_targets"]
            if target["language_version"] == "2.0.0"
        ]
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual(
            target["certified_base_sha"],
            "284ec3ec8c41681825ec1a8421f7ee2a1b012d68",
        )
        self.assertEqual(target["status"], target_status)
        self.assertIs(target["stable"], stable)
        self.assertEqual(tuple(target["authority_files"]), NORMATIVE_PATHS)
        self.assertEqual(
            target["gates"]["certify_full"],
            "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py",
        )
        self.assertEqual(target["public_interfaces"]["v2_cli"], "tev-script-v2")
        self.assertEqual(
            target["public_interfaces"]["v2_descriptor_cli"],
            "tev-script-v2-describe",
        )
        self.assertIs(target["publication_authorized"], False)
        self.assertIs(target["merge_authorized"], False)

    def test_every_normative_path_exists_and_feature_matrix_closes_inventory(self) -> None:
        _, matrix_status, stable = current_expected_state()
        for relative in NORMATIVE_PATHS:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
        matrix = json.loads(
            (ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(matrix["schema"], "TEV_SCRIPT_V2_FEATURE_MATRIX_V1")
        self.assertEqual(matrix["language_version"], "2.0.0")
        self.assertEqual(
            matrix["certified_base_sha"],
            "284ec3ec8c41681825ec1a8421f7ee2a1b012d68",
        )
        self.assertEqual(matrix["certification_status"], matrix_status)
        self.assertIs(matrix["stable"], stable)
        self.assertEqual(tuple(matrix["authority_files"]), NORMATIVE_PATHS)
        governed = matrix["governed_paths"]
        for group in (
            "implementation",
            "tests",
            "conformance",
            "gates",
            "public_interfaces",
        ):
            self.assertTrue(governed[group], group)
            for relative in governed[group]:
                with self.subTest(group=group, relative=relative):
                    self.assertTrue((ROOT / relative).is_file())

    def test_v2_installed_entry_points_are_additive_and_exact(self) -> None:
        project = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        scripts = project["project"]["scripts"]
        self.assertEqual(scripts["tev-script-v2"], "tev_script.cli_v2:main")
        self.assertEqual(
            scripts["tev-script-v2-describe"],
            "tev_script.describe_v2:main",
        )
        self.assertEqual(scripts["tev-script"], "tev_script.cli:main")
        self.assertEqual(scripts["tev-script-v1"], "tev_script.cli_v1:main")

    def test_v2_authority_never_self_authorizes_publication_or_merge(self) -> None:
        _, matrix_status, stable = current_expected_state()
        matrix = json.loads(
            (ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(matrix["certification_status"], matrix_status)
        self.assertIs(matrix["stable"], stable)
        self.assertIs(matrix["publication_authorized"], False)
        self.assertIs(matrix["merge_authorized"], False)

    def test_normative_grammar_covers_every_bounded_control_form(self) -> None:
        language = (ROOT / "spec" / "TEV_SCRIPT_V2_LANGUAGE.md").read_text(
            encoding="utf-8"
        )
        required = (
            '"while" , identifier , ":" , type , "="',
            '"max_iterations" , positive-integer',
            '"task" , "scope"',
            '"spawn" , identifier , ":" , type',
            '"await" , "all"',
            '"within_steps" , positive-integer , "do"',
            '"select" , "first_within"',
            '"for" , identifier',
            '"fold" , identifier , ":" , type',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, language)
        self.assertNotIn(
            "Data-dependent unbounded iteration and `while` are absent",
            language,
        )


if __name__ == "__main__":
    unittest.main()
