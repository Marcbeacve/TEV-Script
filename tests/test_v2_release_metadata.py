from __future__ import annotations

import unittest
from unittest.mock import patch

import tev_script.release_metadata_v2 as metadata


class V2ReleaseMetadataTests(unittest.TestCase):
    def test_candidate_defaults_are_exact_and_valid(self) -> None:
        self.assertEqual(metadata.RELEASE_PROFILE, "candidate")
        self.assertEqual(
            metadata.RELEASE_STATUS,
            "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
        )
        self.assertIs(metadata.STABLE, False)
        self.assertFalse(metadata.CURRENT_V2_CERTIFY_FULL_CLAIM)
        self.assertFalse(metadata.CURRENT_V2_LANGUAGE_STABLE_CLAIM)
        self.assertEqual(metadata.TECHNICAL_PARENT_COMMIT, "")
        self.assertEqual(metadata.TECHNICAL_PARENT_CERTIFICATE_SHA256, "")
        self.assertEqual(metadata.STABLE_LANGUAGE_VERSION, "2.0.0")
        metadata.validate_release_metadata()

    def test_candidate_rejects_any_stable_claim_or_parent_binding(self) -> None:
        mutations = (
            {"STABLE": True},
            {"CURRENT_V2_CERTIFY_FULL_CLAIM": True},
            {"CURRENT_V2_LANGUAGE_STABLE_CLAIM": True},
            {"TECHNICAL_PARENT_COMMIT": "1" * 40},
            {"TECHNICAL_PARENT_CERTIFICATE_SHA256": "2" * 64},
            {"RELEASE_STATUS": "STABLE_2_0_0"},
        )
        for values in mutations:
            with self.subTest(values=values):
                patches = [patch.object(metadata, name, value) for name, value in values.items()]
                for item in patches:
                    item.start()
                try:
                    with self.assertRaisesRegex(RuntimeError, "TEVS_V2_RELEASE_METADATA_"):
                        metadata.validate_release_metadata()
                finally:
                    for item in reversed(patches):
                        item.stop()

    def test_stable_profile_requires_exact_claims_and_parent_shapes(self) -> None:
        stable = {
            "RELEASE_PROFILE": "stable",
            "RELEASE_STATUS": "STABLE_2_0_0",
            "STABLE": True,
            "CURRENT_V2_CERTIFY_FULL_CLAIM": True,
            "CURRENT_V2_LANGUAGE_STABLE_CLAIM": True,
            "TECHNICAL_PARENT_COMMIT": "1" * 40,
            "TECHNICAL_PARENT_CERTIFICATE_SHA256": "2" * 64,
        }
        patches = [patch.object(metadata, name, value) for name, value in stable.items()]
        for item in patches:
            item.start()
        try:
            metadata.validate_release_metadata()
            for name, invalid in (
                ("RELEASE_STATUS", "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED"),
                ("STABLE", False),
                ("CURRENT_V2_CERTIFY_FULL_CLAIM", False),
                ("CURRENT_V2_LANGUAGE_STABLE_CLAIM", False),
                ("TECHNICAL_PARENT_COMMIT", "A" * 40),
                ("TECHNICAL_PARENT_COMMIT", "1" * 39),
                ("TECHNICAL_PARENT_CERTIFICATE_SHA256", "G" * 64),
                ("TECHNICAL_PARENT_CERTIFICATE_SHA256", "2" * 63),
            ):
                with self.subTest(name=name, invalid=invalid), patch.object(metadata, name, invalid):
                    with self.assertRaisesRegex(RuntimeError, "TEVS_V2_RELEASE_METADATA_"):
                        metadata.validate_release_metadata()
        finally:
            for item in reversed(patches):
                item.stop()

    def test_unknown_profile_fails_closed(self) -> None:
        with patch.object(metadata, "RELEASE_PROFILE", "preview"):
            with self.assertRaisesRegex(RuntimeError, "TEVS_V2_RELEASE_METADATA_PROFILE"):
                metadata.validate_release_metadata()


if __name__ == "__main__":
    unittest.main()
