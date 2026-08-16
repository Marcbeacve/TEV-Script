from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

import RUN_TEV_SCRIPT_V3_STABLE_ADMISSION as stable


class V3StableAdmissionContractTests(unittest.TestCase):
    def _body(self) -> dict:
        return stable.build_receipt_body(
            repository="Marcbeacve/TEV-Script",
            branch="agent/tev-script-omega-kernel-v1",
            technical_parent_commit="1" * 40,
            technical_parent_receipt_sha256="2" * 64,
            release_commit_sha="3" * 40,
            release_tree_sha="4" * 40,
            release_diff_hash="5" * 64,
            descriptor_hash="6" * 64,
            v3_test_count=90,
            v3_skipped_tests=0,
            full_test_count=2000,
            full_skipped_tests=0,
            wheel_filename="tev_script_portable_reference-3.0.0-py3-none-any.whl",
            wheel_sha256="7" * 64,
            wheel_reproducible=True,
            installed_v3_smoke="PASS",
            installed_v2_compatibility="PASS",
        )

    def test_receipt_authorizes_exact_publication_but_not_merge(self) -> None:
        body = self._body()
        self.assertTrue(body["stable_admission"])
        self.assertTrue(body["language_stable"])
        self.assertTrue(body["publication_authorized"])
        self.assertFalse(body["merge_authority"])
        receipt = stable.seal_receipt(body)
        self.assertTrue(stable.verify_receipt(receipt))

    def test_tamper_and_fake_merge_authority_reject(self) -> None:
        receipt = stable.seal_receipt(self._body())
        tampered = copy.deepcopy(receipt); tampered["merge_authority"] = True
        self.assertFalse(stable.verify_receipt(tampered))

    def test_release_diff_whitelist_is_exact(self) -> None:
        self.assertTrue(stable.verify_release_diff_paths(stable.RELEASE_DIFF_WHITELIST))
        self.assertFalse(stable.verify_release_diff_paths(stable.RELEASE_DIFF_WHITELIST[:-1]))
        self.assertFalse(stable.verify_release_diff_paths((*stable.RELEASE_DIFF_WHITELIST, "unexpected.txt")))

    def test_artifact_directory_must_be_external_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release"; path.mkdir()
            self.assertEqual(stable.validate_artifact_dir(path), path.resolve())
            (path / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError): stable.validate_artifact_dir(path)


if __name__ == "__main__": unittest.main()
