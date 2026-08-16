from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY as cert
from tools import tevprober_max_v3_basis_frontier as frontier
from tools.tevprober_max_basis_v1 import evaluate_basis


EXPECTED_FRONTIER = (
    "RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY.py",
    "docs/superpowers/plans/2026-08-16-tevscript-max-v3-primitive-basis.md",
    "docs/superpowers/specs/2026-08-16-tevscript-max-v3-primitive-basis-design.md",
    "schemas/tev-script-max-v3-basis-certify-receipt.schema.json",
    "tests/test_max_v3_basis_certify.py",
    "tests/test_omega_semantic_basis_v1.py",
    "tests/test_tevprober_max_basis_v1.py",
    "tev_script/omega_semantic_basis_v1.py",
    "tools/tevprober_max_basis_v1.py",
    "tools/tevprober_max_v3_basis_frontier.py",
)


class MaxV3BasisFrontierTests(unittest.TestCase):
    def test_exact_frontier_is_ready_and_non_promotional(self) -> None:
        report = frontier.plan(EXPECTED_FRONTIER)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(tuple(report["changed_paths"]), EXPECTED_FRONTIER)
        self.assertFalse(report["promotion_authority_bool"])
        self.assertFalse(report["language_stable_claim_bool"])
        self.assertTrue(frontier.verify_plan(report))

    def test_extra_path_holds_and_tamper_rejects(self) -> None:
        report = frontier.plan((*EXPECTED_FRONTIER, "tev_script/source_program_v2.py"))
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("out_of_frontier:tev_script/source_program_v2.py", report["reasons"])
        ready = frontier.plan(EXPECTED_FRONTIER)
        tampered = copy.deepcopy(ready)
        tampered["promotion_authority_bool"] = True
        self.assertFalse(frontier.verify_plan(tampered))


class MaxV3BasisCertifierTests(unittest.TestCase):
    def _args(self) -> dict:
        basis = evaluate_basis()
        return dict(
            repository="Marcbeacve/TEV-Script",
            branch="agent/tev-script-omega-kernel-v1",
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            omega0_base_sha=cert.OMEGA0_BASE_SHA,
            omega0_base_tree_sha=cert.OMEGA0_BASE_TREE,
            v2_base_sha=cert.V2_BASE_SHA,
            design_sha256="6" * 64,
            plan_sha256="7" * 64,
            frontier_plan_hash="sha256:" + "8" * 64,
            basis_report_hash=basis["report_hash"],
            basis_test_count=20,
            basis_skipped_tests=0,
            omega0_test_count=30,
            omega0_skipped_tests=0,
            full_test_count=1000,
            full_skipped_tests=0,
            v2_governed_files_unchanged=True,
            omega0_files_unchanged=True,
            v2_authority_validation="PASS",
        )

    def _body(self) -> dict:
        return cert.build_receipt_body(**self._args())

    def test_v2_authority_gate_uses_stable_profile(self) -> None:
        self.assertEqual(cert.V2_AUTHORITY_PROFILE, "stable")

    def test_receipt_is_self_hashed_non_promotional_and_v3_candidate(self) -> None:
        body = self._body()
        self.assertEqual(body["language_version"], "3.0.0")
        self.assertFalse(body["promotion_authority"])
        self.assertFalse(body["language_stable"])
        receipt = cert.seal_receipt(body)
        self.assertTrue(cert.verify_receipt(receipt))
        self.assertEqual(len(receipt["receipt_hash"]), 64)

    def test_receipt_tamper_and_fake_pass_are_rejected(self) -> None:
        receipt = cert.seal_receipt(self._body())
        tampered = copy.deepcopy(receipt)
        tampered["language_stable"] = True
        self.assertFalse(cert.verify_receipt(tampered))
        with self.assertRaises(ValueError):
            cert.build_receipt_body(**{**self._args(), "basis_skipped_tests": 1})

    def test_schema_has_exact_nonpromotion_constants(self) -> None:
        schema = json.loads(
            (cert.ROOT / "schemas" / "tev-script-max-v3-basis-certify-receipt.schema.json")
            .read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["language_version"]["const"], "3.0.0")
        self.assertEqual(schema["properties"]["promotion_authority"]["const"], False)
        self.assertEqual(schema["properties"]["language_stable"]["const"], False)

    def test_receipt_path_is_external_and_create_once(self) -> None:
        with self.assertRaises(ValueError):
            cert.validate_external_receipt_path(cert.ROOT / "basis-receipt.json")
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "basis-receipt.json"
            self.assertEqual(cert.validate_external_receipt_path(candidate), candidate.resolve())
            candidate.write_text("occupied", encoding="utf-8")
            with self.assertRaises(ValueError):
                cert.validate_external_receipt_path(candidate)


if __name__ == "__main__":
    unittest.main()
