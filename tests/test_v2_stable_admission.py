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
    def test_release_diff_is_exactly_six_paths(self) -> None:
        exact = "\n".join(sorted(gate.REQUIRED_RELEASE_PATHS))
        with patch.object(gate, "git_text", side_effect=["", exact]):
            observed = gate.validate_release_diff("1" * 40, "2" * 40)
        self.assertEqual(set(observed), set(gate.REQUIRED_RELEASE_PATHS))

        with patch.object(gate, "git_text", side_effect=["", exact + "\npyproject.toml"]):
            with self.assertRaisesRegex(gate.V2StableAdmissionFailure, "FORBIDDEN"):
                gate.validate_release_diff("1" * 40, "2" * 40)

        missing = "\n".join(sorted(gate.REQUIRED_RELEASE_PATHS - {"README.md"}))
        with patch.object(gate, "git_text", side_effect=["", missing]):
            with self.assertRaisesRegex(gate.V2StableAdmissionFailure, "MISSING"):
                gate.validate_release_diff("1" * 40, "2" * 40)

    def test_parent_certificate_is_candidate_v2_receipt_bound_to_parent_tree_and_hash(self) -> None:
        parent = "1" * 40
        tree = "2" * 40
        identity = gate.GitIdentity("agent/t", parent, tree, "3" * 40)
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
        self.assertEqual(observed, receipt["receipt_hash"])

    def test_stable_receipt_schema_requires_exact_release_path_set(self) -> None:
        identity = gate.GitIdentity("agent/stable", "1" * 40, "2" * 40, "3" * 40)
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
                wheel_filename="tev_script_portable_reference-1.0.0-py3-none-any.whl",
                wheel_sha256="a" * 64,
                descriptor_hash="b" * 64,
            )
        schema = json.loads(
            (ROOT / "schemas" / "tev-script-v2-stable-admission-receipt.schema.json").read_text(
                encoding="utf-8"
            )
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
        ):
            self.assertNotIn(
                'print("LANGUAGE_STABLE=YES")',
                (ROOT / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
