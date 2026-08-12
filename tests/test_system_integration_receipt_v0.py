from __future__ import annotations

from copy import deepcopy
import unittest

from tev_script.canonical import canonical_hash
from tev_script.system_integration_receipt_v0 import (
    SystemIntegrationReceiptError,
    SystemIntegrationReceiptV0,
    build_system_integration_receipt_v0,
    verify_system_integration_receipt_v0,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


class SystemIntegrationReceiptV0Tests(unittest.TestCase):
    def build(self) -> SystemIntegrationReceiptV0:
        return build_system_integration_receipt_v0(
            branch="realization-semantics-r0",
            head="a" * 40,
            tree="b" * 40,
            source_date_epoch="1786512000",
            language_version="1.0.0",
            system_api_contract_hash=h("system-api"),
            system_canonical_index_schema="TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0",
            system_canonical_index_file_sha256=h("system-index"),
            system_integration_spec_sha256=h("system-spec"),
            distribution_name="tev-script-portable-reference",
            distribution_version="1.0.0",
            wheel_name="tev_script_portable_reference-1.0.0-py3-none-any.whl",
            wheel_sha256=h("wheel"),
        )

    def test_valid_receipt_verifies_exact_binding(self):
        receipt = self.build()
        verified = verify_system_integration_receipt_v0(
            receipt.to_object(),
            expected_language_version="1.0.0",
            expected_system_api_contract_hash=h("system-api"),
            expected_distribution_artifact_sha256=h("wheel"),
            expected_source_head="a" * 40,
            expected_source_tree="b" * 40,
        )
        self.assertEqual(verified.receipt_hash, receipt.receipt_hash)
        verification = receipt.to_object()["verification"]
        self.assertEqual(verification["stable_public_api_preserved"], "PASS")
        self.assertEqual(verification["wheel_complete_python_module_closure"], "PASS")

    def test_wrong_distribution_artifact_is_rejected(self):
        receipt = self.build()
        with self.assertRaises(SystemIntegrationReceiptError):
            verify_system_integration_receipt_v0(
                receipt.to_object(),
                expected_language_version="1.0.0",
                expected_system_api_contract_hash=h("system-api"),
                expected_distribution_artifact_sha256=h("other-wheel"),
            )

    def test_wrong_system_api_contract_is_rejected(self):
        receipt = self.build()
        with self.assertRaises(SystemIntegrationReceiptError):
            verify_system_integration_receipt_v0(
                receipt.to_object(),
                expected_language_version="1.0.0",
                expected_system_api_contract_hash=h("other-system-api"),
                expected_distribution_artifact_sha256=h("wheel"),
            )

    def test_wrong_source_identity_is_rejected(self):
        receipt = self.build()
        with self.assertRaises(SystemIntegrationReceiptError):
            verify_system_integration_receipt_v0(
                receipt.to_object(),
                expected_language_version="1.0.0",
                expected_system_api_contract_hash=h("system-api"),
                expected_distribution_artifact_sha256=h("wheel"),
                expected_source_head="c" * 40,
            )

    def test_tampered_receipt_body_is_rejected(self):
        document = deepcopy(self.build().to_object())
        distribution = dict(document["distribution"])
        distribution["wheel_sha256"] = h("tampered-wheel")
        document["distribution"] = distribution
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)

    def test_extra_unbound_field_is_rejected(self):
        document = self.build().to_object()
        document["consumer_override"] = "PASS"
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)

    def test_deferred_claim_cannot_be_forged_to_pass(self):
        document = deepcopy(self.build().to_object())
        verification = dict(document["verification"])
        verification["certify_full"] = "PASS"
        document["verification"] = verification
        body = {key: value for key, value in document.items() if key != "receipt_hash"}
        document["receipt_hash"] = canonical_hash(body)
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)

    def test_stable_public_api_preservation_cannot_be_downgraded(self):
        document = deepcopy(self.build().to_object())
        verification = dict(document["verification"])
        verification["stable_public_api_preserved"] = "PROOF_REQUIRED"
        document["verification"] = verification
        body = {key: value for key, value in document.items() if key != "receipt_hash"}
        document["receipt_hash"] = canonical_hash(body)
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)

    def test_stable_public_api_preservation_field_is_mandatory(self):
        document = deepcopy(self.build().to_object())
        verification = dict(document["verification"])
        verification.pop("stable_public_api_preserved")
        document["verification"] = verification
        body = {key: value for key, value in document.items() if key != "receipt_hash"}
        document["receipt_hash"] = canonical_hash(body)
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)

    def test_wheel_module_closure_cannot_be_downgraded(self):
        document = deepcopy(self.build().to_object())
        verification = dict(document["verification"])
        verification["wheel_complete_python_module_closure"] = "PROOF_REQUIRED"
        document["verification"] = verification
        body = {key: value for key, value in document.items() if key != "receipt_hash"}
        document["receipt_hash"] = canonical_hash(body)
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)

    def test_wheel_module_closure_field_is_mandatory(self):
        document = deepcopy(self.build().to_object())
        verification = dict(document["verification"])
        verification.pop("wheel_complete_python_module_closure")
        document["verification"] = verification
        body = {key: value for key, value in document.items() if key != "receipt_hash"}
        document["receipt_hash"] = canonical_hash(body)
        with self.assertRaises(SystemIntegrationReceiptError):
            SystemIntegrationReceiptV0(document)


if __name__ == "__main__":
    unittest.main()
