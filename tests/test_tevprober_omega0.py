from __future__ import annotations

import copy
import unittest

from tools import tevprober_omega0 as probe


EXPECTED_FRONTIER = (
    "RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py",
    "docs/superpowers/plans/2026-08-15-tev-script-omega0-kernel-contract.md",
    "docs/superpowers/specs/2026-08-15-tev-script-omega-master-design.md",
    "schemas/tev-script-omega0-certify-receipt.schema.json",
    "tests/test_omega0_certify.py",
    "tests/test_omega_kernel_v1.py",
    "tests/test_omega_v2_adapter_v1.py",
    "tests/test_tevprober_omega0.py",
    "tev_script/omega_kernel_v1.py",
    "tev_script/omega_v2_adapter_v1.py",
    "tools/tevprober_omega0.py",
)


class Omega0ProbeTests(unittest.TestCase):
    def test_exact_frontier_is_ready_and_non_promotional(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
        self.assertEqual(value["schema"], "tev-script-omega0-plan/v1")
        self.assertEqual(value["status"], "READY")
        self.assertEqual(tuple(value["changed_paths"]), EXPECTED_FRONTIER)
        self.assertEqual(
            value["base_sha"],
            "2bdb047dcad41f9d112219bd65925c25668c02e0",
        )
        self.assertEqual(
            value["base_tree"],
            "aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8",
        )
        self.assertIs(value["promotion_authority_bool"], False)
        self.assertIs(value["language_stable_claim_bool"], False)
        self.assertTrue(probe.verify_plan(value))

    def test_v2_semantic_authority_change_holds(self) -> None:
        for path in (
            "tev_script/program_ir_v4.py",
            "tev_script/source_program_v2.py",
            "tev_script/release_metadata_v2.py",
            "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
            "CANONICAL_INDEX.json",
        ):
            with self.subTest(path=path):
                value = probe.plan((*EXPECTED_FRONTIER, path))
                self.assertEqual(value["status"], "HOLD")
                self.assertIn(f"out_of_frontier:{path}", value["reasons"])
                self.assertFalse(value["promotion_authority_bool"])

    def test_missing_frontier_path_holds(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER[:-1])
        self.assertEqual(value["status"], "HOLD")
        self.assertIn(
            "missing_frontier:tools/tevprober_omega0.py",
            value["reasons"],
        )

    def test_plan_tamper_is_rejected(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
        tampered = copy.deepcopy(value)
        tampered["promotion_authority_bool"] = True
        self.assertFalse(probe.verify_plan(tampered))

    def test_path_normalization_is_closed(self) -> None:
        self.assertEqual(
            probe.normalize_paths(
                (
                    "./tools/tevprober_omega0.py",
                    "tools\\tevprober_omega0.py",
                    "tests/test_omega0_certify.py",
                )
            ),
            ("tests/test_omega0_certify.py", "tools/tevprober_omega0.py"),
        )
        for invalid in (
            "",
            "../escape.py",
            "/absolute.py",
            "a/../b.py",
            "bad\x00name.py",
            "bad\nname.py",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    probe.normalize_paths((invalid,))


if __name__ == "__main__":
    unittest.main()
