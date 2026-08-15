from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

import RUN_TEV_SCRIPT_V2_CERTIFY_FULL as technical
import RUN_TEV_SCRIPT_V2_STABLE_ADMISSION as gate

ROOT = Path(__file__).resolve().parents[1]


class V2StableAdmissionTests(unittest.TestCase):
    def _exact_git(self, head: str):
        exact = "\n".join(sorted(gate.REQUIRED_RELEASE_PATHS))

        def fake(*args: str) -> str:
            if args[:2] == ("merge-base", "--is-ancestor"):
                return ""
            if args[:2] == ("diff", "--name-only"):
                return exact
            if args[:2] == ("ls-tree", head):
                relative = args[-1]
                return f"100644 blob {'a' * 40}\t{relative}"
            raise AssertionError(args)

        return fake

    def test_release_diff_is_exactly_six_regular_blob_paths(self) -> None:
        head = "2" * 40
        with patch.object(gate, "git_text", side_effect=self._exact_git(head)):
            observed = gate.validate_release_diff("1" * 40, head)
        self.assertEqual(set(observed), set(gate.REQUIRED_RELEASE_PATHS))

        exact = "\n".join(sorted(gate.REQUIRED_RELEASE_PATHS))

        def forbidden(*args: str) -> str:
            if args[:2] == ("merge-base", "--is-ancestor"):
                return ""
            if args[:2] == ("diff", "--name-only"):
                return exact + "\npyproject.toml"
            raise AssertionError(args)

        with patch.object(gate, "git_text", side_effect=forbidden):
            with self.assertRaisesRegex(gate.V2StableAdmissionFailure, "FORBIDDEN"):
                gate.validate_release_diff("1" * 40, head)

        missing = "\n".join(
            sorted(gate.REQUIRED_RELEASE_PATHS - {"README.md"})
        )

        def missing_git(*args: str) -> str:
            if args[:2] == ("merge-base", "--is-ancestor"):
                return ""
            if args[:2] == ("diff", "--name-only"):
                return missing
            raise AssertionError(args)

        with patch.object(gate, "git_text", side_effect=missing_git):
            with self.assertRaisesRegex(gate.V2StableAdmissionFailure, "MISSING"):
                gate.validate_release_diff("1" * 40, head)

    def test_release_diff_rejects_symlink_or_nonregular_git_mode(self) -> None:
        head = "2" * 40
        exact = "\n".join(sorted(gate.REQUIRED_RELEASE_PATHS))

        def symlink_git(*args: str) -> str:
            if args[:2] == ("merge-base", "--is-ancestor"):
                return ""
            if args[:2] == ("diff", "--name-only"):
                return exact
            if args[:2] == ("ls-tree", head):
                relative = args[-1]
                mode = "120000" if relative == "README.md" else "100644"
                return f"{mode} blob {'a' * 40}\t{relative}"
            raise AssertionError(args)

        with patch.object(gate, "git_text", side_effect=symlink_git):
            with self.assertRaisesRegex(
                gate.V2StableAdmissionFailure,
                "V2_STABLE_RELEASE_PATH_NOT_REGULAR_BLOB:README.md",
            ):
                gate.validate_release_diff("1" * 40, head)

    def test_parent_certificate_is_canonical_candidate_receipt(self) -> None:
        parent = "1" * 40
        tree = "2" * 40
        identity = gate.GitIdentity("agent/t", parent, tree, parent)
        receipt = technical.build_receipt_v2(
            identity,
            admission_profile="candidate",
            python_version="3.14.6",
            v2_test_count=1,
            v1_receipt_sha256="4" * 64,
        )
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "parent.json"
            path.write_text(gate.canonical_json(receipt), encoding="utf-8")
            with patch.object(gate, "git_text", return_value=tree):
                loaded, observed = gate.load_parent_certificate(
                    path,
                    parent,
                    str(receipt["receipt_hash"]),
                )
        self.assertEqual(loaded["commit_sha"], parent)
        self.assertEqual(loaded["base_sha"], parent)
        self.assertEqual(observed, receipt["receipt_hash"])

        premerge = dict(receipt)
        premerge["base_sha"] = "3" * 40
        body = dict(premerge)
        body.pop("receipt_hash")
        premerge["receipt_hash"] = gate.canonical_hash(body)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "premerge.json"
            path.write_text(gate.canonical_json(premerge), encoding="utf-8")
            with patch.object(gate, "git_text", return_value=tree):
                with self.assertRaisesRegex(
                    gate.V2StableAdmissionFailure,
                    "base mismatch",
                ):
                    gate.load_parent_certificate(
                        path,
                        parent,
                        str(premerge["receipt_hash"]),
                    )

    def test_generated_receipts_bind_announced_hash_and_exact_identity(self) -> None:
        current = gate.GitIdentity(
            "agent/stable", "1" * 40, "2" * 40, "3" * 40
        )
        technical_receipt = {
            "schema": "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2",
            "admission_profile": "stable",
            "branch": current.branch,
            "commit_sha": current.commit_sha,
            "tree_sha": current.tree_sha,
            "base_sha": current.base_sha,
            "dirty": False,
            "certify_full": True,
            "language_stable": False,
        }
        technical_receipt["receipt_hash"] = gate.canonical_hash(
            technical_receipt
        )
        observed = gate._require_v2_technical_receipt(
            technical_receipt,
            str(technical_receipt["receipt_hash"]),
            current,
        )
        self.assertEqual(observed, technical_receipt["receipt_hash"])
        with self.assertRaisesRegex(
            gate.V2StableAdmissionFailure,
            "announced hash",
        ):
            gate._require_v2_technical_receipt(
                technical_receipt, "f" * 64, current
            )
        bad_branch = dict(technical_receipt)
        bad_branch["branch"] = "agent/other"
        body = dict(bad_branch)
        body.pop("receipt_hash")
        bad_branch["receipt_hash"] = gate.canonical_hash(body)
        with self.assertRaisesRegex(
            gate.V2StableAdmissionFailure,
            "identity/claims",
        ):
            gate._require_v2_technical_receipt(
                bad_branch,
                str(bad_branch["receipt_hash"]),
                current,
            )

        python_receipt = {
            "schema": "TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL_RECEIPT_V1",
            "admission_profile": "stable",
            "branch": current.branch,
            "commit_sha": current.commit_sha,
            "tree_sha": current.tree_sha,
            "base_sha": current.base_sha,
            "dirty": False,
            "python_v2_certify_full": True,
            "language_stable": False,
        }
        python_receipt["receipt_hash"] = gate.canonical_hash(python_receipt)
        gate._require_v2_python_receipt(
            python_receipt,
            str(python_receipt["receipt_hash"]),
            current,
        )
        substituted = dict(python_receipt)
        substituted["branch"] = "agent/other"
        body = dict(substituted)
        body.pop("receipt_hash")
        substituted["receipt_hash"] = gate.canonical_hash(body)
        with self.assertRaisesRegex(
            gate.V2StableAdmissionFailure,
            "identity/claims",
        ):
            gate._require_v2_python_receipt(
                substituted,
                str(substituted["receipt_hash"]),
                current,
            )

        v1 = {
            "schema": "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2",
            "admission_profile": "stable",
            "branch": current.branch,
            "commit": current.commit_sha,
            "tree": current.tree_sha,
            "certify_full": True,
            "language_stable": False,
        }
        v1_hash = gate.canonical_hash(v1)
        gate._require_v1_receipt(v1, v1_hash, current)
        substituted_v1 = dict(v1)
        substituted_v1["branch"] = "agent/other"
        with self.assertRaisesRegex(
            gate.V2StableAdmissionFailure,
            "identity/claims",
        ):
            gate._require_v1_receipt(
                substituted_v1,
                gate.canonical_hash(substituted_v1),
                current,
            )
        with self.assertRaisesRegex(
            gate.V2StableAdmissionFailure,
            "announced hash",
        ):
            gate._require_v1_receipt(v1, "e" * 64, current)

    def test_stable_receipt_schema_requires_exact_release_path_set(self) -> None:
        identity = gate.GitIdentity(
            "agent/stable", "1" * 40, "2" * 40, "3" * 40
        )
        with patch.object(gate, "_file_sha256", return_value="4" * 64):
            receipt = gate.build_receipt(
                identity,
                parent="3" * 40,
                parent_tree="5" * 40,
                parent_certificate_sha256="6" * 64,
                changed_paths=sorted(gate.REQUIRED_RELEASE_PATHS),
                v2_technical_receipt_sha256="7" * 64,
                v1_receipt_sha256="8" * 64,
                v2_python_receipt_sha256="9" * 64,
                wheel_filename=(
                    "tev_script_portable_reference-1.0.0-py3-none-any.whl"
                ),
                wheel_sha256="a" * 64,
                descriptor_hash="b" * 64,
            )
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "tev-script-v2-stable-admission-receipt.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
        self.assertIs(receipt["language_stable"], True)
        body = dict(receipt)
        observed = body.pop("receipt_hash")
        self.assertEqual(observed, gate.canonical_hash(body))

    def test_only_stable_admission_gate_emits_language_stable_yes(self) -> None:
        self.assertIn(
            'print("LANGUAGE_STABLE=YES")',
            Path(gate.__file__).read_text(encoding="utf-8"),
        )
        for relative in (
            "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py",
            "RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py",
            "tools/validate_v2_stable_governance.py",
            "tools/validate_v2_authority.py",
            "tools/validate_v2_stable_tooling_authority.py",
        ):
            self.assertNotIn(
                'print("LANGUAGE_STABLE=YES")',
                (ROOT / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
