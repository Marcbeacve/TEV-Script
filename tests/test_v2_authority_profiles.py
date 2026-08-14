from __future__ import annotations

import unittest
from unittest.mock import patch

import tools.validate_v2_authority as authority


class V2AuthorityProfileTests(unittest.TestCase):
    def _matrix(self, *, stable: bool, status: str) -> dict:
        return {
            "schema": "TEV_SCRIPT_V2_FEATURE_MATRIX_V1",
            "language_version": "2.0.0",
            "certification_status": status,
            "stable": stable,
            "certified_base_sha": authority.V2_CERTIFIED_BASE_SHA,
            "authority_files": list(authority.AUTHORITY_PATHS),
        }

    def _target(self, *, stable: bool, status: str) -> dict:
        return {
            "language_version": "2.0.0",
            "status": status,
            "stable": stable,
            "certified_base_sha": authority.V2_CERTIFIED_BASE_SHA,
            "authority_files": list(authority.AUTHORITY_PATHS),
            "publication_authorized": False,
            "merge_authorized": False,
        }

    def test_expected_release_state_distinguishes_candidate_and_stable_admission(self) -> None:
        self.assertEqual(
            authority._expected_release_state("candidate"),
            (
                "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
                "CERTIFICATION_REQUIRED",
                False,
            ),
        )
        self.assertEqual(
            authority._expected_release_state("stable"),
            ("STABLE_ADMISSION_REQUESTED", "STABLE_ADMISSION_REQUESTED", True),
        )
        with self.assertRaisesRegex(authority.V2AuthorityFailure, "profile"):
            authority._expected_release_state("preview")

    def test_stable_release_authority_requires_stable_metadata(self) -> None:
        values = {
            "RELEASE_PROFILE": "stable",
            "RELEASE_STATUS": "STABLE_2_0_0",
            "STABLE": True,
            "CURRENT_V2_CERTIFY_FULL_CLAIM": True,
            "CURRENT_V2_LANGUAGE_STABLE_CLAIM": True,
            "TECHNICAL_PARENT_COMMIT": "1" * 40,
            "TECHNICAL_PARENT_CERTIFICATE_SHA256": "2" * 64,
        }
        patches = [
            patch.object(authority.release_metadata, name, value)
            for name, value in values.items()
        ]
        for item in patches:
            item.start()
        try:
            authority._require_release_authority(
                "stable",
                self._matrix(stable=True, status="STABLE_ADMISSION_REQUESTED"),
                self._target(stable=True, status="STABLE_ADMISSION_REQUESTED"),
            )
        finally:
            for item in reversed(patches):
                item.stop()

    def test_mixed_release_profile_fails_closed(self) -> None:
        with self.assertRaisesRegex(authority.V2AuthorityFailure, "release metadata profile"):
            authority._require_release_authority(
                "stable",
                self._matrix(stable=True, status="STABLE_ADMISSION_REQUESTED"),
                self._target(stable=True, status="STABLE_ADMISSION_REQUESTED"),
            )


if __name__ == "__main__":
    unittest.main()
