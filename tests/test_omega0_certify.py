from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import RUN_TEV_SCRIPT_OMEGA0_CERTIFY as cert


class Omega0CertifierContractTests(unittest.TestCase):
    def _body(self) -> dict:
        return cert.build_receipt_body(
            repository="Marcbeacve/TEV-Script",
            branch="agent/tev-script-omega-kernel-v1",
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            base_sha="3" * 40,
            base_tree_sha="4" * 40,
            omega_master_design_sha256="5" * 64,
            omega_plan_sha256="6" * 64,
            omega_frontier_plan_hash="sha256:" + "7" * 64,
            omega_test_count=27,
            omega_skipped_tests=0,
            full_test_count=1234,
            full_skipped_tests=0,
            v2_governed_files_unchanged=True,
            v2_authority_validation="PASS",
        )

    def test_receipt_is_non_promotional_and_self_hashed(self) -> None:
        body = self._body()
        self.assertEqual(body["schema"], "TEV_SCRIPT_OMEGA0_CERTIFY_RECEIPT_V1")
        self.assertFalse(body["promotion_authority"])
        self.assertFalse(body["language_stable"])
        self.assertTrue(body["certify_full"])
        receipt = cert.seal_receipt(body)
        self.assertTrue(cert.verify_receipt(receipt))
        self.assertEqual(len(receipt["receipt_hash"]), 64)

    def test_receipt_tamper_is_rejected(self) -> None:
        receipt = cert.seal_receipt(self._body())
        tampered = copy.deepcopy(receipt)
        tampered["language_stable"] = True
        self.assertFalse(cert.verify_receipt(tampered))

    def test_schema_requires_exact_authority_claims(self) -> None:
        schema_path = cert.ROOT / "schemas" / "tev-script-omega0-certify-receipt.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "TEV_SCRIPT_OMEGA0_CERTIFY_RECEIPT_V1")
        self.assertFalse(schema["additionalProperties"])
        required = set(schema["required"])
        self.assertEqual(
            required,
            {
                "schema",
                "repository",
                "branch",
                "commit_sha",
                "tree_sha",
                "base_sha",
                "base_tree_sha",
                "omega_master_design_sha256",
                "omega_plan_sha256",
                "omega_frontier_plan_hash",
                "omega_test_count",
                "omega_skipped_tests",
                "full_test_count",
                "full_skipped_tests",
                "v2_governed_files_unchanged",
                "v2_authority_validation",
                "promotion_authority",
                "language_stable",
                "certify_full",
                "receipt_hash",
            },
        )
        properties = schema["properties"]
        self.assertEqual(properties["promotion_authority"]["const"], False)
        self.assertEqual(properties["language_stable"]["const"], False)
        self.assertEqual(properties["certify_full"]["const"], True)

    def test_receipt_path_must_be_external_create_once(self) -> None:
        with self.assertRaises(ValueError):
            cert.validate_external_receipt_path(cert.ROOT / "omega0-certify.json")
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "omega0-certify.json"
            resolved = cert.validate_external_receipt_path(candidate)
            self.assertEqual(resolved, candidate.resolve())
            candidate.write_text("already exists", encoding="utf-8")
            with self.assertRaises(ValueError):
                cert.validate_external_receipt_path(candidate)


if __name__ == "__main__":
    unittest.main()
