from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tools.v2_certification_support as support


ROOT = Path(__file__).resolve().parents[1]


class V2CertificationSupportTests(unittest.TestCase):
    def test_current_base_identity_is_exact_and_rejects_drift(self) -> None:
        expected = "3" * 40
        values = {
            ("status", "--porcelain"): "",
            ("symbolic-ref", "--quiet", "--short", "HEAD"): "agent/v2",
            ("rev-parse", "--verify", "HEAD"): "1" * 40,
            ("rev-parse", "--verify", "HEAD^{tree}"): "2" * 40,
            ("rev-parse", "--verify", "origin/main"): expected,
            ("merge-base", "--is-ancestor", expected, "HEAD"): "",
        }
        with patch.object(support, "_git", side_effect=lambda _root, *args: values[tuple(args)]):
            identity = support.collect_git_identity(ROOT, expected)
        self.assertEqual(identity.base_sha, expected)
        self.assertEqual(identity.commit_sha, "1" * 40)
        self.assertEqual(identity.tree_sha, "2" * 40)

        values[("rev-parse", "--verify", "origin/main")] = "4" * 40
        with patch.object(support, "_git", side_effect=lambda _root, *args: values[tuple(args)]):
            with self.assertRaisesRegex(support.V2CertificationFailure, "origin/main drift"):
                support.collect_git_identity(ROOT, expected)

    def test_expected_base_must_be_lowercase_exact_git_sha(self) -> None:
        for value in ("A" * 40, "1" * 39, "1" * 41, "not-a-sha"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(support.V2CertificationFailure, "expected base"):
                    support.collect_git_identity(ROOT, value)

    def test_external_file_and_directory_helpers_fail_closed(self) -> None:
        with self.assertRaisesRegex(support.V2CertificationFailure, "outside"):
            support.require_external_output_path(ROOT, ROOT / "receipt.json")
        with self.assertRaisesRegex(support.V2CertificationFailure, "outside"):
            support.require_external_empty_dir(ROOT, ROOT / "artifacts")
        with tempfile.TemporaryDirectory() as raw:
            external_file = Path(raw) / "receipt.json"
            self.assertEqual(
                support.require_external_output_path(ROOT, external_file),
                external_file.resolve(),
            )
            external_dir = Path(raw) / "artifacts"
            self.assertEqual(
                support.require_external_empty_dir(ROOT, external_dir),
                external_dir.resolve(),
            )
            (external_dir / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(support.V2CertificationFailure, "empty"):
                support.require_external_empty_dir(ROOT, external_dir)


if __name__ == "__main__":
    unittest.main()
