from __future__ import annotations

from contextlib import ExitStack
import unittest
from unittest.mock import patch

import tev_script.release_metadata_v2 as metadata

CANDIDATE = {
    "RELEASE_PROFILE": "candidate",
    "RELEASE_STATUS": "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
    "STABLE": False,
    "CURRENT_V2_CERTIFY_FULL_CLAIM": False,
    "CURRENT_V2_LANGUAGE_STABLE_CLAIM": False,
    "TECHNICAL_PARENT_COMMIT": "",
    "TECHNICAL_PARENT_CERTIFICATE_SHA256": "",
}
STABLE_FIXTURE = {
    "RELEASE_PROFILE": "stable",
    "RELEASE_STATUS": "STABLE_2_0_0",
    "STABLE": True,
    "CURRENT_V2_CERTIFY_FULL_CLAIM": True,
    "CURRENT_V2_LANGUAGE_STABLE_CLAIM": True,
    "TECHNICAL_PARENT_COMMIT": "1" * 40,
    "TECHNICAL_PARENT_CERTIFICATE_SHA256": "2" * 64,
}


class V2ReleaseMetadataTests(unittest.TestCase):
    def test_current_profile_is_exact_and_valid(self) -> None:
        metadata.validate_release_metadata()
        self.assertEqual(metadata.STABLE_LANGUAGE_VERSION, "2.0.0")
        self.assertIn(metadata.RELEASE_PROFILE, {"candidate", "stable"})
        if metadata.RELEASE_PROFILE == "candidate":
            for name, value in CANDIDATE.items():
                self.assertEqual(getattr(metadata, name), value)
            return

        self.assertEqual(metadata.RELEASE_STATUS, "STABLE_2_0_0")
        self.assertIs(metadata.STABLE, True)
        self.assertIs(metadata.CURRENT_V2_CERTIFY_FULL_CLAIM, True)
        self.assertIs(metadata.CURRENT_V2_LANGUAGE_STABLE_CLAIM, True)
        self.assertRegex(metadata.TECHNICAL_PARENT_COMMIT, r"^[0-9a-f]{40}$")
        self.assertRegex(
            metadata.TECHNICAL_PARENT_CERTIFICATE_SHA256,
            r"^[0-9a-f]{64}$",
        )

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
            with self.subTest(values=values), ExitStack() as stack:
                for name, value in CANDIDATE.items():
                    stack.enter_context(patch.object(metadata, name, value))
                for name, value in values.items():
                    stack.enter_context(patch.object(metadata, name, value))
                with self.assertRaisesRegex(RuntimeError, "TEVS_V2_RELEASE_METADATA_"):
                    metadata.validate_release_metadata()

    def test_stable_profile_requires_exact_claims_and_parent_shapes(self) -> None:
        with ExitStack() as stack:
            for name, value in STABLE_FIXTURE.items():
                stack.enter_context(patch.object(metadata, name, value))
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
                with self.subTest(name=name, invalid=invalid), patch.object(
                    metadata, name, invalid
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "TEVS_V2_RELEASE_METADATA_"
                    ):
                        metadata.validate_release_metadata()

    def test_unknown_profile_fails_closed(self) -> None:
        with patch.object(metadata, "RELEASE_PROFILE", "preview"):
            with self.assertRaisesRegex(RuntimeError, "TEVS_V2_RELEASE_METADATA_PROFILE"):
                metadata.validate_release_metadata()


if __name__ == "__main__":
    unittest.main()
