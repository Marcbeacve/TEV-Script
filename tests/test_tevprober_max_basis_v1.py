from __future__ import annotations

import copy
import unittest

from tools.tevprober_max_basis_v1 import evaluate_basis, verify_basis_report


class MaxPrimitiveBasisProbeTests(unittest.TestCase):
    def test_minimal_basis_matches_operational_quotient(self) -> None:
        report = evaluate_basis()
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["minimal"]["sufficient"])
        self.assertTrue(report["minimal"]["minimal"])
        self.assertFalse(report["minimal"]["overrefined"])
        self.assertEqual(report["minimal"]["class_count"], report["operational_quotient"]["class_count"])

    def test_overrefined_basis_is_sufficient_but_not_minimal(self) -> None:
        report = evaluate_basis()
        self.assertTrue(report["overrefined"]["sufficient"])
        self.assertFalse(report["overrefined"]["minimal"])
        self.assertTrue(report["overrefined"]["overrefined"])
        self.assertGreater(
            report["overrefined"]["class_count"],
            report["operational_quotient"]["class_count"],
        )

    def test_field_only_basis_is_insufficient_with_counterexample(self) -> None:
        report = evaluate_basis()
        self.assertFalse(report["insufficient"]["sufficient"])
        self.assertFalse(report["insufficient"]["minimal"])
        self.assertIsInstance(report["insufficient"]["counterexample"], dict)
        self.assertNotEqual(
            report["insufficient"]["counterexample"]["left_outcome_hash"],
            report["insufficient"]["counterexample"]["right_outcome_hash"],
        )

    def test_gate_does_not_expand_tcb_or_promote(self) -> None:
        report = evaluate_basis()
        self.assertFalse(report["kernel_tcb_expanded_bool"])
        self.assertFalse(report["promotion_authority_bool"])
        self.assertFalse(report["language_stable_bool"])
        self.assertTrue(verify_basis_report(report))

    def test_report_tamper_is_rejected(self) -> None:
        report = evaluate_basis()
        tampered = copy.deepcopy(report)
        tampered["overrefined"]["minimal"] = True
        self.assertFalse(verify_basis_report(tampered))


if __name__ == "__main__":
    unittest.main()
