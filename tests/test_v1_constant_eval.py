from __future__ import annotations

import json
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script.constant_eval_v1 import evaluate_v1_state_constants
from tev_script.diagnostics import TevScriptError
from tev_script.linker_v1 import link_v1_mapping
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "conformance" / "v1-constant-cases.json").read_text())


def evaluate(source: str):
    plan = link_v1_mapping({"root.tevs": source.encode()})
    semantics = analyze_v1_static_semantics(plan)
    return evaluate_v1_state_constants(semantics)


class V1ConstantCorpusTests(unittest.TestCase):
    def test_positive_portable_constant_corpus(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                result = evaluate(case["source"])
                self.assertTrue(result.states)

    def test_negative_portable_constant_corpus(self) -> None:
        for case in CASES["negative"]:
            with self.subTest(case=case["id"]):
                with self.assertRaises(TevScriptError) as captured:
                    evaluate(case["source"])
                self.assertEqual(captured.exception.diagnostic.code, case["code"])


class V1ConstantValueTests(unittest.TestCase):
    def test_exact_rational_values_are_not_float_coerced(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; entity E { state a: Rat = 0.1 + 0.2; state b: Rat = 1 / 3; on start { return; } }'
        )
        self.assertEqual(result.state("C.E", "a").value, Fraction(3, 10))
        self.assertEqual(result.state("C.E", "b").value, Fraction(1, 3))

    def test_int_to_rat_widening_is_materialized_in_constant_value(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; entity E { state x: Rat = 2; state o: Option<Rat> = Some(3); on start { return; } }'
        )
        self.assertEqual(result.state("C.E", "x").value, Fraction(2, 1))
        option = result.state("C.E", "o")
        self.assertEqual(option.value[0], "Some")
        self.assertEqual(option.value[1].value, Fraction(3, 1))

    def test_record_fields_are_stored_in_canonical_field_order(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; record R { z: Int; a: Rat; } entity E { state r: R = R(z = 2, a = 1); on start { return; } }'
        )
        record = result.state("C.E", "r")
        self.assertEqual([name for name, _ in record.value], ["a", "z"])
        self.assertEqual(record.value[0][1].value, Fraction(1, 1))
        self.assertEqual(record.value[1][1].value, 2)

    def test_enum_option_result_tags_are_nominal_and_explicit(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; enum K { A; B; } entity E { state k: K = K::B; state n: Option<Int> = None; state ok: Result<Int, Text> = Ok(1); state err: Result<Int, Text> = Err("x"); on start { return; } }'
        )
        self.assertEqual(result.state("C.E", "k").value, "B")
        self.assertEqual(result.state("C.E", "n").value, ("None", None))
        self.assertEqual(result.state("C.E", "ok").value[0], "Ok")
        self.assertEqual(result.state("C.E", "err").value[0], "Err")

    def test_vector_constant_arithmetic_is_exact(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; entity E { state a: Vec2 = vec2(1, 2) * 3; state b: Vec3 = vec3(6, 9, 12) / 3; on start { return; } }'
        )
        self.assertEqual(result.state("C.E", "a").value, (Fraction(3), Fraction(6)))
        self.assertEqual(result.state("C.E", "b").value, (Fraction(2), Fraction(3), Fraction(4)))

    def test_short_circuit_avoids_dead_constant_error_but_not_nonconstant_syntax(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; entity E { state a: Bool = false and (1 / 0 > 0); state b: Bool = true or (1 / 0 > 0); on start { return; } }'
        )
        self.assertFalse(result.state("C.E", "a").value)
        self.assertTrue(result.state("C.E", "b").value)

    def test_pure_function_can_consume_record_and_return_field(self) -> None:
        result = evaluate(
            'script C version "1.0.0"; record R { x: Int; } fn get(r: R) -> Int = r.x; entity E { state x: Int = get(R(x = 9)); on start { return; } }'
        )
        self.assertEqual(result.state("C.E", "x").value, 9)


class V1ConstantBudgetTests(unittest.TestCase):
    def test_pure_function_call_graph_depth_budget(self) -> None:
        declarations = ['fn f0(x: Int) -> Int = x;']
        for i in range(1, 65):
            declarations.append(f'fn f{i}(x: Int) -> Int = f{i-1}(x);')
        source = (
            'script Deep version "1.0.0"; '
            + ' '.join(declarations)
            + ' entity E { state x: Int = f64(1); on start { return; } }'
        )
        with self.assertRaises(TevScriptError) as captured:
            evaluate(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PURITY_CALL_DEPTH")

    def test_constant_step_budget_stops_exponential_pure_expansion(self) -> None:
        declarations = ['fn f0(x: Int) -> Int = x;']
        for i in range(1, 18):
            declarations.append(f'fn f{i}(x: Int) -> Int = f{i-1}(x) + f{i-1}(x);')
        source = (
            'script Steps version "1.0.0"; '
            + ' '.join(declarations)
            + ' entity E { state x: Int = f17(1); on start { return; } }'
        )
        with self.assertRaises(TevScriptError) as captured:
            evaluate(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_CONSTANT_STEP_BUDGET")


if __name__ == "__main__":
    unittest.main()
