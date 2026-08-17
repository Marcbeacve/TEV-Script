from __future__ import annotations

import copy
import json
import unittest

from tev_script.descriptor_v31 import v31_descriptor
from tev_script.release_metadata_v31 import STABLE

from RUN_TEV_SCRIPT_V31_CERTIFY_FULL import (
    EXPECTED_BRANCH,
    POST_CERT_ALLOWED_PATHS,
    RELEASE_MUTABLE_PATHS,
    REPOSITORY,
    ROOT,
    TECHNICAL_REQUIRED_PATHS,
    V3_STABLE_SHA,
    V3_STABLE_TAG,
    V3_STABLE_TREE,
    _canonical_index_predecessor_view,
    evaluate_minimality,
    load_feature_matrix,
    require_predecessor_byte_identity,
    validate_v31_matrix,
)


class V31AuthorityTests(unittest.TestCase):
    def test_matrix_closes_total_core_features_without_operator_authority(self) -> None:
        matrix = load_feature_matrix(ROOT)
        report = validate_v31_matrix(matrix, v31_descriptor())
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertTrue(report["all_required_features_closed"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["merge_authorized"])
        self.assertEqual(report["language_stable"], STABLE)

    def test_matrix_pins_exact_stable_v3_predecessor(self) -> None:
        matrix = load_feature_matrix(ROOT)
        predecessor = matrix["predecessor_v3"]
        self.assertEqual(predecessor["tag"], V3_STABLE_TAG)
        self.assertEqual(predecessor["commit_sha"], V3_STABLE_SHA)
        self.assertEqual(predecessor["tree_sha"], V3_STABLE_TREE)
        self.assertEqual(predecessor["language_version"], "3.0.0")
        self.assertFalse(matrix["compatibility"]["v3_semantics_reinterpreted"])
        self.assertFalse(matrix["compatibility"]["v2_semantics_reinterpreted"])

    def test_technical_governed_paths_are_exact_unique_and_present(self) -> None:
        report = validate_v31_matrix(load_feature_matrix(ROOT), v31_descriptor())
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(
            frozenset(report["technical_governed_paths"]),
            TECHNICAL_REQUIRED_PATHS,
        )
        self.assertEqual(
            len(report["technical_governed_paths"]),
            len(TECHNICAL_REQUIRED_PATHS),
        )
        for relative in report["technical_governed_paths"]:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_only_explicit_release_paths_are_future_allowed(self) -> None:
        report = validate_v31_matrix(load_feature_matrix(ROOT), v31_descriptor())
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(
            frozenset(report["post_cert_allowed_paths"]),
            POST_CERT_ALLOWED_PATHS,
        )
        self.assertEqual(
            TECHNICAL_REQUIRED_PATHS.intersection(POST_CERT_ALLOWED_PATHS),
            RELEASE_MUTABLE_PATHS,
        )
        self.assertEqual(
            frozenset(report["release_mutable_paths"]),
            RELEASE_MUTABLE_PATHS,
        )
        self.assertEqual(
            RELEASE_MUTABLE_PATHS,
            frozenset(
                {
                    "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json",
                    "tev_script/release_metadata_v31.py",
                }
            ),
        )

    def test_current_candidate_is_minimal_against_v3_stable(self) -> None:
        report = evaluate_minimality(ROOT)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["unexpected_paths"], [])
        self.assertEqual(report["missing_technical_paths"], [])
        self.assertEqual(
            frozenset(report["technical_changed_paths"]),
            TECHNICAL_REQUIRED_PATHS,
        )
        self.assertTrue(
            set(report["post_cert_changed_paths"]).issubset(POST_CERT_ALLOWED_PATHS)
        )
        self.assertEqual(
            set(report["changed_paths"]),
            set(report["technical_changed_paths"]).union(report["post_cert_changed_paths"]),
        )

    def test_v3_and_inherited_v2_governed_bytes_are_unchanged(self) -> None:
        report = require_predecessor_byte_identity(ROOT)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["v3_byte_identity"], "PASS")
        self.assertEqual(report["v2_byte_identity"], "PASS")
        self.assertEqual(report["canonical_index_predecessor_identity"], "PASS")
        self.assertGreater(report["v3_governed_path_count"], 0)
        self.assertGreater(report["v2_governed_path_count"], 0)

    def test_canonical_index_view_allows_only_v31_target_addition(self) -> None:
        base = json.loads((ROOT / "CANONICAL_INDEX.json").read_text(encoding="utf-8"))
        baseline = _canonical_index_predecessor_view(base)

        with_v31 = copy.deepcopy(base)
        with_v31.setdefault("candidate_language_targets", []).append(
            {
                "language_version": "3.1.0",
                "status": "STABLE_ADMISSION_REQUESTED",
                "stable": True,
            }
        )
        self.assertEqual(_canonical_index_predecessor_view(with_v31), baseline)

        mutated = copy.deepcopy(base)
        predecessor = next(
            item
            for item in mutated["candidate_language_targets"]
            if item.get("language_version") == "2.0.0"
        )
        predecessor["stable"] = not predecessor["stable"]
        self.assertNotEqual(_canonical_index_predecessor_view(mutated), baseline)

    def test_publication_or_merge_authority_tamper_is_rejected(self) -> None:
        matrix = copy.deepcopy(load_feature_matrix(ROOT))
        matrix["publication_authorized"] = True
        self.assertEqual(validate_v31_matrix(matrix, v31_descriptor())["status"], "FAIL")
        matrix = copy.deepcopy(load_feature_matrix(ROOT))
        matrix["merge_authorized"] = True
        self.assertEqual(validate_v31_matrix(matrix, v31_descriptor())["status"], "FAIL")

    def test_repository_and_branch_identity_are_fixed(self) -> None:
        self.assertEqual(REPOSITORY, "Marcbeacve/TEV-Script")
        self.assertEqual(
            EXPECTED_BRANCH,
            "agent/tevscript-max-3-1-total-core-v1",
        )
        self.assertEqual(len(V3_STABLE_SHA), 40)
        self.assertEqual(len(V3_STABLE_TREE), 40)


if __name__ == "__main__":
    unittest.main()
