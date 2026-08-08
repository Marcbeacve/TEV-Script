from __future__ import annotations

import itertools
import json
import unittest
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "conformance" / "v1-static-semantics-cases.json").read_text())


def src(path: str, text: str) -> SourceInputV1:
    return SourceInputV1(path, text.encode())


def analyze(sources: list[dict[str, str]]):
    plan = link_v1_sources([src(item["path"], item["source"]) for item in sources])
    return analyze_v1_static_semantics(plan)


class V1StaticSemanticsCorpusTests(unittest.TestCase):
    def test_positive_portable_corpus(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                result = analyze(case["sources"])
                self.assertEqual(result.plan.root.language_version, "1.0.0")
                self.assertTrue(result.semantic_hash)

    def test_negative_portable_corpus_has_exact_diagnostic_category(self) -> None:
        for case in CASES["negative"]:
            with self.subTest(case=case["id"]):
                with self.assertRaises(TevScriptError) as captured:
                    analyze(case["sources"])
                self.assertEqual(captured.exception.diagnostic.code, case["code"])


class V1TypeModelTests(unittest.TestCase):
    def test_nominal_record_identity_is_preserved(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; record A { x: Int; } record B { x: Int; } entity E { state a: A = A(x = 1); state b: B = B(x = 1); on start { return; } }',
            }
        ])
        record_ids = [item.type_id for item in result.types.records]
        self.assertEqual(record_ids, ["Root.A", "Root.B"])
        self.assertNotEqual(result.types.records[0].type_id, result.types.records[1].type_id)

    def test_record_field_order_is_not_semantic_in_type_environment(self) -> None:
        left = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; record R { b: Int; a: Rat; } entity E { state r: R = R(a = 1, b = 2); on start { return; } }'}
        ])
        right = analyze([
            {"path":"other.tevs","source":'script Root version "1.0.0"; record R { a: Rat; b: Int; } entity E { state r: R = R(b = 2, a = 1); on start { return; } }'}
        ])
        self.assertEqual(
            [(name, type_ref.type_id) for name, type_ref in left.types.records[0].fields],
            [("a", "Rat"), ("b", "Int")],
        )
        self.assertEqual(
            [(name, type_ref.type_id) for name, type_ref in left.types.records[0].fields],
            [(name, type_ref.type_id) for name, type_ref in right.types.records[0].fields],
        )

    def test_identical_capability_declarations_collapse_to_one_contract(self) -> None:
        result = analyze(next(x for x in CASES["positive"] if x["id"] == "duplicate-identical-capability-contract")["sources"])
        matching = [item for item in result.types.capabilities if item.callable_id == "world.ping"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].kind, "effect")
        self.assertEqual(matching[0].return_type.type_id, "Unit")

    def test_record_recursion_witness_is_deterministic(self) -> None:
        source = {
            "path":"root.tevs",
            "source":'script Root version "1.0.0"; record A { b: B; } record B { c: C; } record C { a: A; } entity E { on start { return; } }',
        }
        messages = set()
        for _ in range(3):
            with self.assertRaises(TevScriptError) as captured:
                analyze([source])
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_TYPE_RECORD_RECURSION")
            messages.add(captured.exception.diagnostic.message)
        self.assertEqual(messages, {"recursive record dependency: Root.A -> Root.B -> Root.C -> Root.A"})


class V1ScopeAndExpressionTests(unittest.TestCase):
    def test_some_infers_option_but_none_requires_context(self) -> None:
        result = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; entity E { on start { let x = Some(1); let y: Option<Int> = None; } }'}
        ])
        self.assertEqual(result.composites[0].composite_id, "Root.E")

    def test_result_constructor_uses_expected_generic_arguments(self) -> None:
        result = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; entity E { state x: Result<Rat, Text> = Ok(1); on start { let y: Result<Int, Text> = Err("bad"); } }'}
        ])
        self.assertEqual(result.composites[0].states, (("x", "Result<Rat,Text>"),))

    def test_dotted_value_path_resolves_record_fields_not_host_properties(self) -> None:
        result = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; record Inner { value: Int; } record Outer { inner: Inner; } entity E { state o: Outer = Outer(inner = Inner(value = 1)); on start { let x = o.inner.value; } }'}
        ])
        self.assertEqual(result.composites[0].states[0][1], "Root.Outer")

    def test_int_widens_to_rat_inside_generic_expected_context(self) -> None:
        analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; entity E { state x: Option<Rat> = Some(1); state y: Result<Rat, Text> = Ok(2); on start { return; } }'}
        ])

    def test_effect_summary_includes_sugar_observations_and_explicit_calls(self) -> None:
        result = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; capability audio.tick(Text) -> Unit effect; entity E { on update { let dir = input.move2d(); move dir; animate "Walk"; log "x"; call audio.tick("t"); } }'}
        ])
        handler = result.composites[0].handlers[0]
        self.assertEqual(
            handler.capabilities,
            ("animation.play", "audio.tick", "debug.log", "input.move2d", "motion.move2d"),
        )

    def test_event_summary_is_canonicalized(self) -> None:
        result = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; entity E { on start { emit z(1); emit a("x"); } }'}
        ])
        handler = result.composites[0].handlers[0]
        self.assertEqual(handler.emitted_events, (("a", ("Text",)), ("z", ("Int",))))


class V1FunctionSemanticsTests(unittest.TestCase):
    def test_function_dependency_summary_is_deterministic(self) -> None:
        result = analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; fn a(x: Int) -> Int = x + 1; fn b(x: Int) -> Int = a(x); fn c(x: Int) -> Int = max(b(x), a(x)); entity E { on start { return; } }'}
        ])
        summaries = {item.function_id: item.calls for item in result.functions}
        self.assertEqual(summaries["Root.a"], ())
        self.assertEqual(summaries["Root.b"], ("Root.a",))
        self.assertEqual(summaries["Root.c"], ("Root.a", "Root.b", "max"))

    def test_overloaded_builtin_resolution_prefers_exact_then_unique_widening(self) -> None:
        analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; entity E { on start { let i: Int = max(1, 2); let r: Rat = max(1, 2.5); } }'}
        ])

    def test_imported_pure_function_accepts_contextual_none_argument(self) -> None:
        analyze([
            {"path":"root.tevs","source":'script Root version "1.0.0"; import lib; entity E { on start { let x = unwrap(None); } }'},
            {"path":"lib.tevs","source":'module lib version "1.0.0"; export fn unwrap(x: Option<Int>) -> Int = 0;'},
        ])


class V1StaticDeterminismTests(unittest.TestCase):
    def test_input_permutation_and_paths_do_not_change_static_analysis(self) -> None:
        logical = [
            ('root.tevs', 'script Root version "1.0.0"; import a; import b; entity E { state x: Int = 0; on start { x = f(1); } }'),
            ('a.tevs', 'module a version "1.0.0"; export fn f(x: Int) -> Int = x + 1;'),
            ('b.tevs', 'module b version "1.0.0"; export record R { x: Int; }'),
        ]
        observed = set()
        for run, permutation in enumerate(itertools.permutations(range(len(logical)))):
            sources = [
                src(f"relocated/{run}/{logical[index][0]}", logical[index][1])
                for index in permutation
            ]
            result = analyze_v1_static_semantics(link_v1_sources(sources))
            observed.add((result.canonical_json, result.semantic_hash))
        self.assertEqual(len(observed), 1)


if __name__ == "__main__":
    unittest.main()
