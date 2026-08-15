from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tools.validate_v2_stable_governance as governance


class V2StableGovernanceTests(unittest.TestCase):
    def test_candidate_metadata_is_rejected_even_on_a_stable_checkout(self) -> None:
        candidate = {
            "RELEASE_PROFILE": "candidate",
            "RELEASE_STATUS": "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED",
            "STABLE": False,
            "CURRENT_V2_CERTIFY_FULL_CLAIM": False,
            "CURRENT_V2_LANGUAGE_STABLE_CLAIM": False,
            "TECHNICAL_PARENT_COMMIT": "",
            "TECHNICAL_PARENT_CERTIFICATE_SHA256": "",
        }
        patches = [
            patch.object(governance.release_metadata, name, value)
            for name, value in candidate.items()
        ]
        for item in patches:
            item.start()
        try:
            with self.assertRaisesRegex(
                governance.V2StableGovernanceFailure,
                "PROFILE",
            ):
                governance.require_stable_release_metadata()
        finally:
            for item in reversed(patches):
                item.stop()

    def test_stable_metadata_requires_exact_parent_and_claims(self) -> None:
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
            patch.object(governance.release_metadata, name, value)
            for name, value in values.items()
        ]
        for item in patches:
            item.start()
        try:
            parent, certificate = governance.require_stable_release_metadata()
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(parent, "1" * 40)
        self.assertEqual(certificate, "2" * 64)

    def test_required_stable_promotion_gates_are_closed_and_nonempty(self) -> None:
        self.assertEqual(
            governance.REQUIRED_STABLE_PROMOTION_GATES,
            {
                "STABLE_ADMISSION_TOOLING_TECHNICALLY_CERTIFIED_PASS",
                "STABLE_PARENT_CERTIFICATE_BINDING_PASS",
                "STABLE_RELEASE_DIFF_CONFINEMENT_PASS",
                "STABLE_V2_TECHNICAL_RECERTIFICATION_PASS",
                "STABLE_V1_NON_REGRESSION_PASS",
                "STABLE_V2_PYTHON_ARTIFACT_PASS",
                "EXACT_V2_STABLE_ADMISSION_PASS",
            },
        )

    def test_release_documents_require_exact_v2_tokens_and_parent_binding(self) -> None:
        parent = "1" * 40
        certificate = "2" * 64
        tokens = (
            "V2_STABLE_ADMISSION=REQUESTED",
            "V2_LANGUAGE_VERSION=2.0.0",
            "V2_PYTHON_PACKAGE_VERSION=1.0.0",
            "V2_TECHNICAL_PARENT_COMMIT=" + parent,
            "V2_TECHNICAL_PARENT_CERTIFICATE_SHA256=" + certificate,
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for relative in ("README.md", "CHANGELOG.md", "PROJECT_STATE.md"):
                (root / relative).write_text(
                    "\n".join(tokens) + "\n",
                    encoding="utf-8",
                )
            with patch.object(governance, "ROOT", root):
                governance._require_v2_release_documents(parent, certificate)
                text = (root / "README.md").read_text(encoding="utf-8")
                (root / "README.md").write_text(
                    text.replace(
                        "V2_LANGUAGE_VERSION=2.0.0",
                        "2.0.0 STABLE_ADMISSION",
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    governance.V2StableGovernanceFailure,
                    "V2_STABLE_GOVERNANCE_RELEASE_DOCUMENT",
                ):
                    governance._require_v2_release_documents(
                        parent,
                        certificate,
                    )


if __name__ == "__main__":
    unittest.main()
