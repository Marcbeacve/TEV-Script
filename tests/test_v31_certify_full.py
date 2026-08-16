from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from RUN_TEV_SCRIPT_V31_CERTIFY_FULL import (
    EXPECTED_BRANCH,
    REPOSITORY,
    ROOT,
    SCHEMA,
    TECHNICAL_REQUIRED_PATHS,
    V3_STABLE_SHA,
    V3_STABLE_TREE,
    build_receipt_body,
    seal_receipt,
    validate_external_receipt_path,
    verify_receipt,
    _require_git_identity,
    _run_v3_authority_gate,
)


def _body(**overrides):
    values = {
        "repository": REPOSITORY,
        "branch": EXPECTED_BRANCH,
        "commit_sha": "1" * 40,
        "tree_sha": "2" * 40,
        "v3_stable_sha": V3_STABLE_SHA,
        "v3_stable_tree": V3_STABLE_TREE,
        "feature_matrix_sha256": "3" * 64,
        "descriptor_hash": "4" * 64,
        "conformance_matrix_sha256": "5" * 64,
        "certification_schema_sha256": "6" * 64,
        "python_version": "3.11.9",
        "node_version": "v24.18.0",
        "v31_core_test_count": 42,
        "v31_core_skipped_tests": 0,
        "js_parity_test_count": 11,
        "js_parity_skipped_tests": 0,
        "predecessor_test_count": 9,
        "predecessor_skipped_tests": 0,
        "v31_core_gate_hash": "7" * 64,
        "js_parity_gate_hash": "8" * 64,
        "predecessor_gate_hash": "9" * 64,
        "v3_authority_gate_hash": "a" * 64,
        "v2_authority_gate_hash": "b" * 64,
        "predecessor_identity_hash": "c" * 64,
        "minimality_report_hash": "d" * 64,
        "governed_path_count": len(TECHNICAL_REQUIRED_PATHS),
        "changed_path_count": len(TECHNICAL_REQUIRED_PATHS),
        "v3_byte_identity": "PASS",
        "v2_byte_identity": "PASS",
        "minimality": "PASS",
        "js_parity": "PASS",
    }
    values.update(overrides)
    return build_receipt_body(**values)


class V31CertifyFullTests(unittest.TestCase):
    def test_receipt_is_technical_only_and_binds_versions_and_gates(self) -> None:
        body = _body()
        self.assertEqual(body["schema"], SCHEMA)
        self.assertEqual(body["language_version"], "3.1.0")
        self.assertEqual(body["v3_stable_sha"], V3_STABLE_SHA)
        self.assertEqual(body["v3_stable_tree"], V3_STABLE_TREE)
        self.assertEqual(body["python_version"], "3.11.9")
        self.assertEqual(body["node_version"], "v24.18.0")
        self.assertFalse(body["publication_authorized"])
        self.assertFalse(body["merge_authorized"])
        self.assertFalse(body["language_stable"])
        self.assertTrue(body["certify_full"])

    def test_zero_skip_requirement_is_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            _body(v31_core_skipped_tests=1)
        with self.assertRaises(ValueError):
            _body(js_parity_skipped_tests=1)
        with self.assertRaises(ValueError):
            _body(predecessor_skipped_tests=1)

    def test_gate_and_identity_failures_are_rejected(self) -> None:
        for field in (
            "v3_byte_identity",
            "v2_byte_identity",
            "minimality",
            "js_parity",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    _body(**{field: "FAIL"})

    def test_receipt_seal_and_tamper_detection(self) -> None:
        receipt = seal_receipt(_body())
        self.assertTrue(verify_receipt(receipt))
        tampered = copy.deepcopy(receipt)
        tampered["publication_authorized"] = True
        self.assertFalse(verify_receipt(tampered))
        tampered = copy.deepcopy(receipt)
        tampered["v31_core_gate_hash"] = "0" * 64
        self.assertFalse(verify_receipt(tampered))

    def test_external_receipt_is_create_once_and_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "v31-certify.json"
            resolved = validate_external_receipt_path(target)
            self.assertEqual(resolved, target.resolve())
            target.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_external_receipt_path(target)
        with self.assertRaises(ValueError):
            validate_external_receipt_path(ROOT / "forbidden-v31-receipt.json")

    def test_git_identity_resolves_origin_main_in_single_branch_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            seed = base / "seed"
            remote = base / "remote.git"
            clone = base / "clone"
            seed.mkdir()

            def run(*args: str, cwd: Path) -> str:
                completed = subprocess.run(
                    ("git", *args),
                    cwd=cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=completed.stdout + "\n" + completed.stderr,
                )
                return completed.stdout.strip()

            run("init", "-b", "main", cwd=seed)
            run("config", "user.name", "TEV Test", cwd=seed)
            run("config", "user.email", "tev-test@example.invalid", cwd=seed)
            (seed / "stable.txt").write_text("v3\n", encoding="utf-8")
            run("add", "stable.txt", cwd=seed)
            run("commit", "-m", "stable", cwd=seed)
            stable_sha = run("rev-parse", "HEAD", cwd=seed)
            stable_tree = run("rev-parse", "HEAD^{tree}", cwd=seed)
            run("tag", "v3.0.0", cwd=seed)

            run("checkout", "-b", "candidate", cwd=seed)
            (seed / "candidate.txt").write_text("v31\n", encoding="utf-8")
            run("add", "candidate.txt", cwd=seed)
            run("commit", "-m", "candidate", cwd=seed)

            run("init", "--bare", str(remote), cwd=base)
            run("remote", "add", "origin", str(remote), cwd=seed)
            run("push", "origin", "main", "candidate", "v3.0.0", cwd=seed)

            run(
                "clone",
                "--single-branch",
                "--branch",
                "candidate",
                str(remote),
                str(clone),
                cwd=base,
            )
            missing = subprocess.run(
                ("git", "rev-parse", "--verify", "refs/remotes/origin/main"),
                cwd=clone,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(missing.returncode, 0)

            with (
                patch("RUN_TEV_SCRIPT_V31_CERTIFY_FULL.EXPECTED_BRANCH", "candidate"),
                patch("RUN_TEV_SCRIPT_V31_CERTIFY_FULL.V3_STABLE_SHA", stable_sha),
                patch("RUN_TEV_SCRIPT_V31_CERTIFY_FULL.V3_STABLE_TREE", stable_tree),
                patch("RUN_TEV_SCRIPT_V31_CERTIFY_FULL.V3_STABLE_TAG", "v3.0.0"),
            ):
                branch, head, tree = _require_git_identity(clone)

            self.assertEqual(branch, "candidate")
            self.assertEqual(head, run("rev-parse", "HEAD", cwd=clone))
            self.assertEqual(tree, run("rev-parse", "HEAD^{tree}", cwd=clone))

    def test_v3_authority_subprocess_has_repo_import_root_in_clean_environment(self) -> None:
        with patch.dict(os.environ, {"PYTHONPATH": ""}, clear=False):
            gate_hash = _run_v3_authority_gate()
        self.assertRegex(gate_hash, r"^[0-9a-f]{64}$")

    def test_receipt_schema_closes_release_authority(self) -> None:
        path = ROOT / "schemas/tev-script-v31-certify-full-receipt.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], SCHEMA)
        self.assertFalse(schema["additionalProperties"])
        properties = schema["properties"]
        self.assertEqual(properties["publication_authorized"]["const"], False)
        self.assertEqual(properties["merge_authorized"]["const"], False)
        self.assertEqual(properties["language_stable"]["const"], False)
        self.assertEqual(properties["certify_full"]["const"], True)


if __name__ == "__main__":
    unittest.main()
