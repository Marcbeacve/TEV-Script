from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

import RUN_TEV_SCRIPT_V2_CERTIFY_FULL as gate


ROOT = Path(__file__).resolve().parents[1]


class V2CertifyFullTests(unittest.TestCase):
    def test_collect_git_identity_rejects_dirty_worktree_before_gates(self) -> None:
        with patch.object(gate, "_git", return_value=" M changed.py\n"):
            with self.assertRaisesRegex(gate.V2CertificationFailure, "dirty"):
                gate.collect_git_identity(ROOT)

    def test_collect_git_identity_binds_branch_head_tree_and_base(self) -> None:
        values = {
            ("status", "--porcelain"): "",
            ("symbolic-ref", "--quiet", "--short", "HEAD"): "agent/v2",
            ("rev-parse", "--verify", "HEAD"): "1" * 40,
            ("rev-parse", "--verify", "HEAD^{tree}"): "2" * 40,
            ("rev-parse", "--verify", "origin/main"): "3" * 40,
            ("merge-base", "--is-ancestor", "origin/main", "HEAD"): "",
        }

        def fake_git(_root, *arguments):
            return values[tuple(arguments)]

        with patch.object(gate, "_git", side_effect=fake_git):
            identity = gate.collect_git_identity(ROOT)
        self.assertEqual(identity.branch, "agent/v2")
        self.assertEqual(identity.commit_sha, "1" * 40)
        self.assertEqual(identity.tree_sha, "2" * 40)
        self.assertEqual(identity.base_sha, "3" * 40)

    def test_run_checked_requires_exit_zero_and_every_witness(self) -> None:
        missing = subprocess.CompletedProcess(["python"], 0, "A=PASS\n", "")
        with patch.object(gate.subprocess, "run", return_value=missing):
            with self.assertRaisesRegex(gate.V2CertificationFailure, "B=PASS"):
                gate.run_checked("sample", ["python"], ("A=PASS", "B=PASS"))
        failed = subprocess.CompletedProcess(["python"], 7, "A=PASS\nB=PASS\n", "boom")
        with patch.object(gate.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(gate.V2CertificationFailure, "exit=7"):
                gate.run_checked("sample", ["python"], ("A=PASS", "B=PASS"))

    def test_v2_test_module_inventory_excludes_certifier_self_recursion(self) -> None:
        modules = gate.v2_test_modules(ROOT)
        self.assertGreater(len(modules), 40)
        self.assertNotIn("tests.test_v2_certify_full", modules)
        self.assertIn("tests.test_scoped_filesystem_v2", modules)
        self.assertEqual(len(modules), len(set(modules)))

    def test_receipt_is_self_hashing_schema_valid_and_not_a_stable_claim(self) -> None:
        identity = gate.GitIdentity("agent/v2", "1" * 40, "2" * 40, "3" * 40)
        receipt = gate.build_receipt(
            identity,
            python_version="3.14.6",
            v2_test_count=123,
            v1_receipt_sha256="4" * 64,
        )
        schema = json.loads((ROOT / "schemas" / "tev-script-v2-certify-full-receipt.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(receipt)
        body = dict(receipt)
        observed = body.pop("receipt_hash")
        self.assertEqual(observed, gate.canonical_hash(body))
        self.assertNotIn("stable", receipt)
        self.assertNotIn("publication_authorized", receipt)

    def test_receipt_output_must_be_outside_repository(self) -> None:
        with self.assertRaisesRegex(gate.V2CertificationFailure, "outside"):
            gate.require_external_receipt_path(ROOT, ROOT / "evidence" / "v2.json")
        with tempfile.TemporaryDirectory() as raw:
            external = Path(raw) / "v2.json"
            self.assertEqual(gate.require_external_receipt_path(ROOT, external), external.resolve())


if __name__ == "__main__":
    unittest.main()
