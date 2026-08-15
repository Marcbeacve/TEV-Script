from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

import RUN_TEV_SCRIPT_V2_CERTIFY_FULL as gate

ROOT = Path(__file__).resolve().parents[1]


class V2CertifyFullV2Tests(unittest.TestCase):
    def test_current_base_collect_identity_is_explicit_and_legacy_wrapper_remains(self) -> None:
        current_base = "3" * 40
        values = {
            ("status", "--porcelain"): "",
            ("symbolic-ref", "--quiet", "--short", "HEAD"): "agent/v2",
            ("rev-parse", "--verify", "HEAD"): "1" * 40,
            ("rev-parse", "--verify", "HEAD^{tree}"): "2" * 40,
            ("rev-parse", "--verify", "origin/main"): current_base,
            ("merge-base", "--is-ancestor", current_base, "HEAD"): "",
        }
        with patch.object(
            gate,
            "_git",
            side_effect=lambda _root, *args: values[tuple(args)],
        ):
            identity = gate.collect_git_identity(ROOT, current_base)
        self.assertEqual(identity.base_sha, current_base)

        values[("rev-parse", "--verify", "origin/main")] = (
            gate.CERTIFIED_BASE_SHA
        )
        values[
            ("merge-base", "--is-ancestor", gate.CERTIFIED_BASE_SHA, "HEAD")
        ] = ""
        with patch.object(
            gate,
            "_git",
            side_effect=lambda _root, *args: values[tuple(args)],
        ):
            legacy = gate.collect_git_identity(ROOT)
        self.assertEqual(legacy.base_sha, gate.CERTIFIED_BASE_SHA)

    def test_current_base_receipt_is_profile_bound_self_hashed_and_never_stable(self) -> None:
        identity = gate.GitIdentity(
            "agent/v2", "1" * 40, "2" * 40, "3" * 40
        )
        receipt = gate.build_receipt_v2(
            identity,
            admission_profile="candidate",
            python_version="3.14.6",
            v2_test_count=123,
            v1_receipt_sha256="4" * 64,
        )
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "tev-script-v2-certify-full-receipt-v2.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
        body = dict(receipt)
        observed = body.pop("receipt_hash")
        self.assertEqual(observed, gate.canonical_hash(body))
        self.assertEqual(receipt["admission_profile"], "candidate")
        self.assertIs(receipt["certify_full"], True)
        self.assertIs(receipt["language_stable"], False)
        self.assertEqual(
            receipt["gates"]["stable_tooling_authority"],
            "PASS",
        )

    def test_historical_receipt_shape_remains_unchanged(self) -> None:
        identity = gate.GitIdentity(
            "agent/v2",
            "1" * 40,
            "2" * 40,
            gate.CERTIFIED_BASE_SHA,
        )
        receipt = gate.build_receipt(
            identity,
            python_version="3.14.6",
            v2_test_count=123,
            v1_receipt_sha256="4" * 64,
        )
        self.assertEqual(
            receipt["schema"],
            "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1",
        )
        self.assertNotIn("admission_profile", receipt)
        self.assertNotIn("certify_full", receipt)
        self.assertNotIn("language_stable", receipt)
        self.assertNotIn("stable_tooling_authority", receipt["gates"])

    def test_v1_non_regression_receipt_binds_announced_hash_and_exact_identity(self) -> None:
        identity = gate.GitIdentity(
            "agent/v2", "1" * 40, "2" * 40, "3" * 40
        )
        receipt = {
            "schema": "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2",
            "admission_profile": "stable",
            "branch": identity.branch,
            "commit": identity.commit_sha,
            "tree": identity.tree_sha,
            "certify_full": True,
            "language_stable": False,
        }
        announced = gate.canonical_hash(receipt)
        self.assertEqual(
            gate._require_v1_non_regression_receipt(
                receipt,
                announced,
                identity,
            ),
            announced,
        )
        with self.assertRaisesRegex(
            gate.V2CertificationFailure,
            "announced hash",
        ):
            gate._require_v1_non_regression_receipt(
                receipt,
                "f" * 64,
                identity,
            )
        for key, value in (
            ("branch", "agent/other"),
            ("tree", "9" * 40),
        ):
            with self.subTest(key=key, value=value):
                substituted = dict(receipt)
                substituted[key] = value
                with self.assertRaisesRegex(
                    gate.V2CertificationFailure,
                    "identity/claims",
                ):
                    gate._require_v1_non_regression_receipt(
                        substituted,
                        gate.canonical_hash(substituted),
                        identity,
                    )

    def test_receipt_output_compatibility_still_requires_external_path(self) -> None:
        with self.assertRaisesRegex(gate.V2CertificationFailure, "outside"):
            gate.require_external_receipt_path(
                ROOT,
                ROOT / "evidence" / "v2.json",
            )
        with tempfile.TemporaryDirectory() as raw:
            external = Path(raw) / "v2.json"
            self.assertEqual(
                gate.require_external_receipt_path(ROOT, external),
                external.resolve(),
            )


if __name__ == "__main__":
    unittest.main()
