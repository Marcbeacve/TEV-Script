from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

import RUN_TEV_SCRIPT_V3_CERTIFY_FULL as cert
from tev_script.release_metadata_v3 import validate_release_metadata_v3


class V3ReleaseMetadataTests(unittest.TestCase):
    def test_candidate_metadata_is_nonstable_nonpromotional(self) -> None:
        value = validate_release_metadata_v3()
        self.assertEqual(value["language_version"], "3.0.0")
        self.assertEqual(value["release_profile"], "candidate")
        self.assertFalse(value["stable"])
        self.assertFalse(value["publication_authority"])


class V3CertifyFullContractTests(unittest.TestCase):
    def _body(self) -> dict:
        return cert.build_receipt_body(
            repository="Marcbeacve/TEV-Script",
            branch="agent/tev-script-omega-kernel-v1",
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            v2_base_sha=cert.V2_BASE_SHA,
            feature_matrix_sha256="3" * 64,
            descriptor_hash="4" * 64,
            basis_report_hash="5" * 64,
            v3_test_count=77,
            v3_skipped_tests=0,
            full_test_count=2000,
            full_skipped_tests=0,
            schema_validation="PASS",
            v2_authority_validation="PASS",
        )

    def test_receipt_is_self_hashed_and_nonpromotional(self) -> None:
        body = self._body()
        self.assertFalse(body["promotion_authority"])
        self.assertFalse(body["language_stable"])
        self.assertTrue(body["certify_full"])
        receipt = cert.seal_receipt(body)
        self.assertTrue(cert.verify_receipt(receipt))

    def test_tamper_and_fake_stability_reject(self) -> None:
        receipt = cert.seal_receipt(self._body())
        tampered = copy.deepcopy(receipt); tampered["language_stable"] = True
        self.assertFalse(cert.verify_receipt(tampered))

    def test_external_receipt_path_is_create_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v3-certify.json"
            self.assertEqual(cert.validate_external_receipt_path(path), path.resolve())
            path.write_text("occupied", encoding="utf-8")
            with self.assertRaises(ValueError):
                cert.validate_external_receipt_path(path)


if __name__ == "__main__":
    unittest.main()
