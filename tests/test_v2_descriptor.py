from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import unittest

from tev_script.canonical import canonical_hash, canonical_json
from tev_script.cli_v2 import main as cli_main
from tev_script.describe_v2 import main as describe_main
from tev_script.descriptor_v2 import v2_descriptor, v2_descriptor_json


class V2DescriptorTests(unittest.TestCase):
    def test_descriptor_is_canonical_and_self_hashing(self) -> None:
        descriptor = v2_descriptor()
        body = dict(descriptor)
        observed = body.pop("descriptor_hash")
        self.assertEqual(observed, canonical_hash(body))
        self.assertEqual(v2_descriptor_json(), canonical_json(descriptor))

    def test_descriptor_reports_independent_nonstable_v2_authority(self) -> None:
        descriptor = v2_descriptor()
        self.assertEqual(descriptor["certification"]["certified_base_sha"], "284ec3ec8c41681825ec1a8421f7ee2a1b012d68")
        self.assertEqual(descriptor["schema"], "TEV_SCRIPT_V2_DESCRIPTOR_V1")
        self.assertEqual(descriptor["language_version"], "2.0.0")
        self.assertEqual(descriptor["release_profile"], "candidate")
        self.assertEqual(descriptor["release_status"], "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED")
        self.assertIs(descriptor["stable"], False)
        certification = descriptor["certification"]
        self.assertEqual(certification["certify_full_gate"], "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py")
        self.assertEqual(certification["receipt_schema"], "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1")
        self.assertEqual(certification["historical_receipt_schema"], "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1")
        self.assertEqual(certification["current_receipt_schema"], "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2")
        self.assertEqual(certification["python_certify_full_gate"], "RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py")
        self.assertEqual(certification["stable_admission_gate"], "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py")
        self.assertEqual(certification["technical_parent_commit"], "")
        self.assertEqual(certification["technical_parent_certificate_sha256"], "")
        self.assertIs(certification["current_v2_certify_full_claim"], False)
        self.assertIs(certification["current_v2_language_stable_claim"], False)
        self.assertIs(certification["v1_certificate_is_v2_authority"], False)
        stable_surface = descriptor["stable_release_surface"]
        self.assertEqual(stable_surface["admission_gate"], "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py")
        self.assertIs(stable_surface["stable_claim"], False)

    def test_descriptor_reports_handle_safety_and_pre_admission_budget(self) -> None:
        safety = v2_descriptor()["filesystem_safety"]
        self.assertEqual(safety["authority_anchor"], "OPEN_DIRECTORY_OBJECT_IDENTITY_V1")
        self.assertEqual(safety["path_resolution"], "HANDLE_RELATIVE_NO_FOLLOW_V1")
        self.assertEqual(safety["maximum_file_read_bytes"], 1024 * 1024)
        self.assertEqual(safety["oversize_witness_bytes"], 1)
        self.assertTrue(safety["unsupported_platform_fails_closed"])

    def test_module_and_primary_cli_descriptors_are_byte_identical(self) -> None:
        module_output = StringIO()
        with redirect_stdout(module_output):
            self.assertEqual(describe_main(), 0)
        cli_output = StringIO()
        with redirect_stdout(cli_output):
            self.assertEqual(cli_main(["descriptor"]), 0)
        self.assertEqual(module_output.getvalue(), cli_output.getvalue())
        self.assertEqual(module_output.getvalue().rstrip("\n"), v2_descriptor_json())
        self.assertEqual(json.loads(module_output.getvalue())["descriptor_hash"], v2_descriptor()["descriptor_hash"])


if __name__ == "__main__":
    unittest.main()
