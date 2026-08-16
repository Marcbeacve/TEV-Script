from __future__ import annotations

from dataclasses import replace
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import (
    field_fact,
    field_transformation,
    semantic_field,
)
from tev_script.semantic_stdlib_v1 import (
    admission,
    closure_residual,
    compare_residuals,
    decision_candidate,
    decision_field,
    discovery_realization_closure,
    parse_residual,
    residual_field,
    residual_obstruction,
    resolve_candidates,
)


class ResidualStdlibTests(unittest.TestCase):
    def test_closed_iff_no_obstructions_and_canonical_order(self) -> None:
        closed = residual_field(domain="math", judgment_id="J", judgment={"ok": True}, source={"x": 1})
        view = parse_residual(closed)
        self.assertEqual(view.status, "CLOSED")
        self.assertEqual(view.obstructions, ())

        a = residual_obstruction("missing.proof", "lemma-a", expected=True, observed=False)
        b = residual_obstruction("missing.data", "sample-b", expected=3, observed=1)
        left = residual_field(
            domain="math", judgment_id="J", judgment={"ok": True}, source={"x": 1},
            obstructions=(a, b),
        )
        right = residual_field(
            domain="math", judgment_id="J", judgment={"ok": True}, source={"x": 1},
            obstructions=(b, a),
        )
        self.assertEqual(left, right)
        self.assertEqual(parse_residual(left).status, "OPEN")

    def test_progress_requires_exact_boundary(self) -> None:
        a = residual_obstruction("missing.proof", "a")
        b = residual_obstruction("missing.data", "b")
        before = residual_field(domain="d", judgment_id="j", judgment=1, source=2, obstructions=(a, b))
        reduced = residual_field(domain="d", judgment_id="j", judgment=1, source=2, obstructions=(a,))
        closed = residual_field(domain="d", judgment_id="j", judgment=1, source=2)
        changed_boundary = residual_field(domain="d", judgment_id="other", judgment=1, source=2)
        self.assertEqual(compare_residuals(before, reduced).classification, "REDUCED")
        self.assertEqual(compare_residuals(reduced, closed).classification, "CLOSED")
        self.assertEqual(compare_residuals(before, before).classification, "UNCHANGED")
        self.assertEqual(compare_residuals(reduced, before).classification, "REGRESSED")
        self.assertEqual(compare_residuals(before, changed_boundary).classification, "INCOMPARABLE")

    def test_residual_tamper_rejects(self) -> None:
        field = residual_field(domain="d", judgment_id="j", judgment=1, source=2)
        with self.assertRaises(TevScriptError):
            parse_residual(replace(field, field_hash="0" * 64))


class DecisionStdlibTests(unittest.TestCase):
    def _candidates(self):
        return (
            decision_candidate("a", "1" * 64, rank=1),
            decision_candidate("b", "2" * 64, rank=2),
        )

    def test_unique_best_admitted_is_selected(self) -> None:
        a, b = self._candidates()
        result = resolve_candidates(
            (a, b),
            (admission("a", "PASS"), admission("b", "REJECT")),
        )
        self.assertEqual(result.status, "SELECTED")
        self.assertEqual(result.selected_candidate_id, "a")
        field = decision_field((a, b), (admission("a", "PASS"), admission("b", "REJECT")), result)
        self.assertIn("tev.std.selection", {fact.relation for fact in field.facts})

    def test_open_candidate_forces_indeterminate_even_with_current_pass(self) -> None:
        a, b = self._candidates()
        result = resolve_candidates(
            (a, b),
            (admission("a", "PASS"), admission("b", "PROOF_REQUIRED")),
        )
        self.assertEqual(result.status, "INDETERMINATE")
        self.assertIsNone(result.selected_candidate_id)

    def test_all_rejected_is_closed_no_admissible(self) -> None:
        a, b = self._candidates()
        result = resolve_candidates(
            (a, b),
            (admission("a", "REJECT"), admission("b", "REJECT")),
        )
        self.assertEqual(result.status, "NO_ADMISSIBLE_REALIZATION")
        self.assertIsNone(result.selected_candidate_id)

    def test_equal_best_distinct_candidates_do_not_use_hidden_tiebreaker(self) -> None:
        a = decision_candidate("a", "1" * 64, rank=1)
        z = decision_candidate("z", "f" * 64, rank=1)
        left = resolve_candidates((a, z), (admission("a", "PASS"), admission("z", "PASS")))
        right = resolve_candidates((z, a), (admission("z", "PASS"), admission("a", "PASS")))
        self.assertEqual(left.status, "INDETERMINATE")
        self.assertEqual(right.status, "INDETERMINATE")
        self.assertIsNone(left.selected_candidate_id)
        self.assertEqual(left, right)


class DiscoveryRealizationStdlibTests(unittest.TestCase):
    EFFECTS = "1" * 64
    RESOURCES = "2" * 64

    def test_exact_cycle_closes_residual(self) -> None:
        theory_fact = field_fact("theory.value", (1,))
        world_fact = field_fact("world.value", (1,))
        theory = semantic_field((theory_fact,), profile="theory")
        realization = field_transformation(
            transformation_id="realize",
            remove_fact_hashes=(theory_fact.fact_hash,), add_facts=(world_fact,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        discovery = field_transformation(
            transformation_id="discover",
            remove_fact_hashes=(world_fact.fact_hash,), add_facts=(theory_fact,),
            effect_set_hash=self.EFFECTS, resource_vector_hash=self.RESOURCES,
        )
        cycle, residual = discovery_realization_closure(theory, realization, discovery)
        self.assertEqual(parse_residual(residual).status, "CLOSED")
        self.assertEqual(
            {f.relation for f in cycle.facts},
            {"tev.std.discovery_realization"},
        )

    def test_mismatched_recovery_is_open_with_exact_obstruction(self) -> None:
        expected = semantic_field((field_fact("theory.value", (1,)),), profile="theory")
        recovered = semantic_field((field_fact("theory.value", (2,)),), profile="theory")
        residual = closure_residual(expected, recovered)
        view = parse_residual(residual)
        self.assertEqual(view.status, "OPEN")
        self.assertEqual(len(view.obstructions), 2)
        self.assertEqual({o.kind for o in view.obstructions}, {"missing.fact", "unexpected.fact"})


if __name__ == "__main__":
    unittest.main()
