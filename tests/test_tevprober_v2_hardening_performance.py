from __future__ import annotations

import copy
import unittest

from tools import tevprober_v2_hardening_performance as probe


EXPECTED_FRONTIER = (
    "docs/superpowers/plans/2026-08-15-tev-script-v2-hardening-performance.md",
    "docs/superpowers/specs/2026-08-15-tev-script-v2-hardening-performance-design.md",
    "tests/test_tevprober_v2_hardening_performance.py",
    "tests/test_v2_hardening_adversarial.py",
    "tools/tevprober_v2_hardening_performance.py",
    "tools/v2_hardening_corpus.py",
)


class V2HardeningProbeContractTests(unittest.TestCase):
    def test_exact_frontier_is_ready_and_non_promotional(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
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
        self.assertEqual(value["mode"], "INFRASTRUCTURE_BASELINE")
        self.assertIs(value["promotion_authority_bool"], False)
        self.assertIs(value["semantic_authority_change_bool"], False)
        self.assertTrue(probe.verify_plan(value))

    def test_semantic_implementation_path_holds(self) -> None:
        value = probe.plan((*EXPECTED_FRONTIER, "tev_script/program_ir_v4.py"))
        self.assertEqual(value["status"], "HOLD")
        self.assertIn(
            "out_of_frontier:tev_script/program_ir_v4.py",
            value["reasons"],
        )
        self.assertFalse(value["promotion_authority_bool"])

    def test_missing_frontier_path_holds(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER[:-1])
        self.assertEqual(value["status"], "HOLD")
        self.assertIn(
            "missing_frontier:tools/v2_hardening_corpus.py",
            value["reasons"],
        )

    def test_plan_tamper_is_rejected(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
        tampered = copy.deepcopy(value)
        tampered["metric_policy"]["trials"] = 1
        self.assertFalse(probe.verify_plan(tampered))

    def test_path_normalization_is_closed(self) -> None:
        self.assertEqual(
            probe.normalize_paths(
                (
                    "./tools/v2_hardening_corpus.py",
                    "tools\\tevprober_v2_hardening_performance.py",
                    "tools/v2_hardening_corpus.py",
                )
            ),
            (
                "tools/tevprober_v2_hardening_performance.py",
                "tools/v2_hardening_corpus.py",
            ),
        )
        for invalid in (
            "../escape.py",
            "/absolute.py",
            "a/../b.py",
            "bad\x00name.py",
            "bad\nname.py",
            "",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    probe.normalize_paths((invalid,))

    def test_environment_fingerprint_is_stable_and_has_no_clock(self) -> None:
        left = probe.environment_fingerprint()
        right = probe.environment_fingerprint()
        self.assertEqual(left, right)
        self.assertEqual(left["fingerprint_hash"], right["fingerprint_hash"])
        self.assertNotIn("timestamp", left)
        self.assertNotIn("time", left)


if __name__ == "__main__":
    unittest.main()
