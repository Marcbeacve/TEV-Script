from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import RUN_TEV_SCRIPT_V31_CERTIFY_FULL as technical
from RUN_TEV_SCRIPT_V31_STABLE_ADMISSION import (
    EXPECTED_BRANCH,
    RELEASE_DIFF_WHITELIST,
    REPOSITORY,
    SCHEMA,
    build_receipt_body,
    seal_receipt,
    validate_artifact_dir,
    verify_receipt,
    verify_release_diff_paths,
)


ROOT = Path(__file__).resolve().parents[1]


def _body(**overrides):
    values = {
        "repository": REPOSITORY,
        "branch": EXPECTED_BRANCH,
        "technical_parent_commit": "1" * 40,
        "technical_parent_receipt_sha256": "2" * 64,
        "release_commit_sha": "3" * 40,
        "release_tree_sha": "4" * 40,
        "release_diff_hash": "5" * 64,
        "descriptor_hash": "6" * 64,
        "full_test_count": 100,
        "full_skipped_tests": 0,
        "wheel_filename": "tev_script_portable_reference-3.1.0-py3-none-any.whl",
        "wheel_sha256": "7" * 64,
        "wheel_reproducible": True,
        "installed_v31_smoke": "PASS",
        "installed_v3_compatibility": "PASS",
        "installed_v2_compatibility": "PASS",
    }
    values.update(overrides)
    return build_receipt_body(**values)


class V31StableAdmissionTests(unittest.TestCase):
    def test_release_diff_whitelist_is_exact_and_minimal(self) -> None:
        self.assertEqual(
            RELEASE_DIFF_WHITELIST,
            tuple(
                sorted(
                    (
                        "CANONICAL_INDEX.json",
                        "CHANGELOG.md",
                        "README.md",
                        "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json",
                        "tev_script/release_metadata_v31.py",
                    )
                )
            ),
        )
        self.assertTrue(verify_release_diff_paths(RELEASE_DIFF_WHITELIST))
        self.assertFalse(verify_release_diff_paths(RELEASE_DIFF_WHITELIST[:-1]))
        self.assertFalse(
            verify_release_diff_paths((*RELEASE_DIFF_WHITELIST, "unexpected.txt"))
        )
        self.assertFalse(
            verify_release_diff_paths((*RELEASE_DIFF_WHITELIST, RELEASE_DIFF_WHITELIST[0]))
        )

    def test_stable_receipt_grants_stability_but_not_operator_actions(self) -> None:
        body = _body()
        self.assertEqual(body["schema"], SCHEMA)
        self.assertEqual(body["language_version"], "3.1.0")
        self.assertTrue(body["stable_admission"])
        self.assertTrue(body["language_stable"])
        self.assertTrue(body["publication_eligible"])
        self.assertFalse(body["publication_authorized"])
        self.assertFalse(body["merge_authorized"])
        self.assertEqual(body["technical_parent_commit"], "1" * 40)

    def test_stable_receipt_requires_zero_skips_reproducible_wheel_and_smokes(self) -> None:
        with self.assertRaises(ValueError):
            _body(full_skipped_tests=1)
        with self.assertRaises(ValueError):
            _body(wheel_reproducible=False)
        for field in (
            "installed_v31_smoke",
            "installed_v3_compatibility",
            "installed_v2_compatibility",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    _body(**{field: "FAIL"})
        with self.assertRaises(ValueError):
            _body(wheel_filename="wrong.whl")

    def test_stable_receipt_seal_and_tamper_detection(self) -> None:
        receipt = seal_receipt(_body())
        self.assertTrue(verify_receipt(receipt))
        tampered = copy.deepcopy(receipt)
        tampered["publication_authorized"] = True
        self.assertFalse(verify_receipt(tampered))
        tampered = copy.deepcopy(receipt)
        tampered["wheel_sha256"] = "0" * 64
        self.assertFalse(verify_receipt(tampered))

    def test_artifact_directory_must_be_external_existing_and_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.assertEqual(validate_artifact_dir(directory), directory.resolve())
            (directory / "occupied.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_artifact_dir(directory)
        with self.assertRaises(ValueError):
            validate_artifact_dir(ROOT)

    def test_schema_closes_stability_and_operator_authority(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/tev-script-v31-stable-admission-receipt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["$id"], SCHEMA)
        self.assertFalse(schema["additionalProperties"])
        properties = schema["properties"]
        self.assertEqual(properties["stable_admission"]["const"], True)
        self.assertEqual(properties["language_stable"]["const"], True)
        self.assertEqual(properties["publication_eligible"]["const"], True)
        self.assertEqual(properties["publication_authorized"]["const"], False)
        self.assertEqual(properties["merge_authorized"]["const"], False)

    def test_technical_receipt_verifier_remains_authoritative(self) -> None:
        receipt = technical.seal_receipt(
            technical.build_receipt_body(
                repository=technical.REPOSITORY,
                branch=technical.EXPECTED_BRANCH,
                commit_sha="1" * 40,
                tree_sha="2" * 40,
                v3_stable_sha=technical.V3_STABLE_SHA,
                v3_stable_tree=technical.V3_STABLE_TREE,
                feature_matrix_sha256="3" * 64,
                descriptor_hash="4" * 64,
                conformance_matrix_sha256="5" * 64,
                certification_schema_sha256="6" * 64,
                python_version="3.11.9",
                node_version="v24.18.0",
                v31_core_test_count=1,
                v31_core_skipped_tests=0,
                js_parity_test_count=1,
                js_parity_skipped_tests=0,
                predecessor_test_count=1,
                predecessor_skipped_tests=0,
                v31_core_gate_hash="7" * 64,
                js_parity_gate_hash="8" * 64,
                predecessor_gate_hash="9" * 64,
                v3_authority_gate_hash="a" * 64,
                v2_authority_gate_hash="b" * 64,
                predecessor_identity_hash="c" * 64,
                minimality_report_hash="d" * 64,
                governed_path_manifest_hash="e" * 64,
                governed_path_count=len(technical.TECHNICAL_REQUIRED_PATHS),
                changed_path_count=len(technical.TECHNICAL_REQUIRED_PATHS),
                v3_byte_identity="PASS",
                v2_byte_identity="PASS",
                minimality="PASS",
                js_parity="PASS",
            )
        )
        self.assertTrue(technical.verify_receipt(receipt))


if __name__ == "__main__":
    unittest.main()
