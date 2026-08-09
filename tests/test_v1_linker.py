from __future__ import annotations

import itertools
import json
import unittest
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.linker_v1 import (
    NAMESPACE_BEHAVIOR,
    NAMESPACE_CAPABILITY,
    NAMESPACE_ENTITY,
    NAMESPACE_FUNCTION,
    NAMESPACE_TYPE,
    SourceInputV1,
    canonical_type_id,
    link_v1_mapping,
    link_v1_sources,
    resolve_symbol,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "conformance" / "v1-linker-cases.json").read_text())


def src(path: str, text: str) -> SourceInputV1:
    return SourceInputV1(path, text.encode())


class V1LinkerConformanceTests(unittest.TestCase):
    def test_positive_corpus_is_byte_locked(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                plan = link_v1_sources([src(x["path"], x["source"]) for x in case["sources"]])
                self.assertEqual(list(plan.module_topological_order), case["expected_topological_modules"])
                self.assertEqual(plan.index_hash, case["expected_index_hash"])
                for query in case.get("resolutions", []):
                    symbol = resolve_symbol(plan, query["unit"], query["reference"], query["namespace"])
                    self.assertEqual(symbol.semantic_id, query["semantic_id"])

    def test_negative_corpus_fails_with_exact_category(self) -> None:
        for case in CASES["negative"]:
            with self.subTest(case=case["id"]):
                sources = [src(x["path"], x["source"]) for x in case["sources"]]
                with self.assertRaises(TevScriptError) as captured:
                    if case["phase"] == "link":
                        link_v1_sources(sources)
                    else:
                        plan = link_v1_sources(sources)
                        query = case["resolve"]
                        resolve_symbol(plan, query["unit"], query["reference"], query["namespace"])
                self.assertEqual(captured.exception.diagnostic.code, case["code"])

    def test_paths_and_input_permutations_do_not_change_index(self) -> None:
        logical = [
            'script Root version "1.0.0"; import a; import b; entity E { on start { return; } }',
            'module a version "1.0.0"; export record A { x: Int; }',
            'module b version "1.0.0"; import a; export fn f(x: Int) -> Int = x;',
        ]
        observed = set()
        for run, order in enumerate(itertools.permutations(range(3))):
            plan = link_v1_sources([src(f"relocated/{run}/{i}.tevs", logical[i]) for i in order])
            observed.add((plan.canonical_index_json, plan.index_hash))
        self.assertEqual(len(observed), 1)

    def test_import_statement_order_is_not_semantic(self) -> None:
        modules = {
            "a.tevs": b'module a version "1.0.0"; export record A { x: Int; }',
            "b.tevs": b'module b version "1.0.0"; export record B { x: Int; }',
        }
        left = link_v1_mapping({
            "root.tevs": b'script Root version "1.0.0"; import a; import b; entity E { on start { return; } }',
            **modules,
        })
        right = link_v1_mapping({
            "root.tevs": b'script Root version "1.0.0"; import b; import a; entity E { on start { return; } }',
            **modules,
        })
        self.assertEqual(left.canonical_index_json, right.canonical_index_json)

    def test_unreachable_module_does_not_enter_semantic_index(self) -> None:
        root = src("root.tevs", 'script Root version "1.0.0"; entity E { on start { return; } }')
        base = link_v1_sources([root])
        with_unused = link_v1_sources([
            root,
            src("unused.tevs", 'module unused version "1.0.0"; import absent; export record Ghost { x: Int; }'),
        ])
        self.assertEqual(base.index_hash, with_unused.index_hash)
        self.assertEqual(with_unused.modules, ())

    def test_reachable_module_budget_is_checked_before_host_recursion_can_grow(self) -> None:
        root = src("root.tevs", 'script Root version "1.0.0"; import m0; entity E { on start { return; } }')
        modules = []
        for i in range(257):
            tail = f" import m{i + 1};" if i < 256 else ""
            modules.append(src(f"m{i}.tevs", f'module m{i} version "1.0.0";{tail}'))
        with self.assertRaises(TevScriptError) as captured:
            link_v1_sources([root, *modules])
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_MODULE_BUDGET")

    def test_cycle_witness_is_deterministic(self) -> None:
        sources = [
            src("root.tevs", 'script Root version "1.0.0"; import a; entity E { on start { return; } }'),
            src("a.tevs", 'module a version "1.0.0"; import b;'),
            src("b.tevs", 'module b version "1.0.0"; import c;'),
            src("c.tevs", 'module c version "1.0.0"; import a;'),
        ]
        messages = set()
        for ordering in (sources, list(reversed(sources))):
            with self.assertRaises(TevScriptError) as captured:
                link_v1_sources(ordering)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_IMPORT_CYCLE")
            messages.add(captured.exception.diagnostic.message)
        self.assertEqual(messages, {"import cycle: a -> b -> c -> a"})

    def test_resolution_respects_local_private_direct_and_transitive_boundaries(self) -> None:
        plan = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; import a; record Point { x: Int; } entity E { on start { return; } }'),
            src("a.tevs", 'module a version "1.0.0"; import b; export record Point { x: Rat; } record Secret { x: Int; }'),
            src("b.tevs", 'module b version "1.0.0"; export record Deep { x: Int; }'),
        ])
        self.assertEqual(resolve_symbol(plan, "Root", "Point", NAMESPACE_TYPE).semantic_id, "Root.Point")
        self.assertEqual(resolve_symbol(plan, "Root", "a.Point", NAMESPACE_TYPE).semantic_id, "a.Point")
        with self.assertRaises(TevScriptError) as private:
            resolve_symbol(plan, "Root", "a.Secret", NAMESPACE_TYPE)
        self.assertEqual(private.exception.diagnostic.code, "TEVS_V1_LINK_PRIVATE_SYMBOL")
        with self.assertRaises(TevScriptError) as transitive:
            resolve_symbol(plan, "Root", "Deep", NAMESPACE_TYPE)
        self.assertEqual(transitive.exception.diagnostic.code, "TEVS_V1_LINK_NAME_UNKNOWN")
        self.assertEqual(resolve_symbol(plan, "a", "Deep", NAMESPACE_TYPE).semantic_id, "b.Deep")

    def test_longest_direct_module_prefix_wins(self) -> None:
        plan = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; import game; import game.math; entity E { on start { return; } }'),
            src("game.tevs", 'module game version "1.0.0"; export record Point { x: Int; }'),
            src("math.tevs", 'module game.math version "1.0.0"; export record Point { x: Rat; }'),
        ])
        self.assertEqual(resolve_symbol(plan, "Root", "game.math.Point", NAMESPACE_TYPE).owner_id, "game.math")

    def test_capability_ids_are_global_not_module_qualification(self) -> None:
        plan = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; import world; import api; entity E { on start { call world.read(); } }'),
            src("world.tevs", 'module world version "1.0.0"; export record Marker { x: Int; }'),
            src("api.tevs", 'module api version "1.0.0"; export capability world.read() -> Unit effect;'),
        ])
        symbol = resolve_symbol(plan, "Root", "world.read", NAMESPACE_CAPABILITY)
        self.assertEqual((symbol.semantic_id, symbol.owner_id), ("world.read", "api"))

    def test_identical_capability_contracts_collapse_deterministically(self) -> None:
        plan = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; import a; import b; entity E { on start { call world.read(); } }'),
            src("a.tevs", 'module a version "1.0.0"; export capability world.read() -> Int observation;'),
            src("b.tevs", 'module b version "1.0.0"; export capability world.read() -> Int observation;'),
        ])
        self.assertEqual(resolve_symbol(plan, "Root", "world.read", NAMESPACE_CAPABILITY).owner_id, "a")

    def test_conflicting_capability_contracts_fail_even_when_unused(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            link_v1_sources([
                src("root.tevs", 'script Root version "1.0.0"; import a; import b; entity E { on start { return; } }'),
                src("a.tevs", 'module a version "1.0.0"; export capability world.read() -> Int observation;'),
                src("b.tevs", 'module b version "1.0.0"; export capability world.read() -> Rat observation;'),
            ])
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_CAPABILITY_CONFLICT")

    def test_qualified_builtin_capability_has_no_implicit_short_alias(self) -> None:
        plan = link_v1_sources([src("root.tevs", 'script Root version "1.0.0"; entity E { on start { return; } }')])
        self.assertEqual(resolve_symbol(plan, "Root", "time.delta", NAMESPACE_CAPABILITY).origin, "builtin")
        with self.assertRaises(TevScriptError) as captured:
            resolve_symbol(plan, "Root", "delta", NAMESPACE_CAPABILITY)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_NAME_UNKNOWN")

    def test_namespaces_are_distinct_but_predeclared_collisions_fail(self) -> None:
        plan = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; record X { v: Int; } fn X(v: Int) -> Int = v; entity E { on start { return; } }'),
        ])
        self.assertEqual(resolve_symbol(plan, "Root", "X", NAMESPACE_TYPE).semantic_id, "Root.X")
        self.assertEqual(resolve_symbol(plan, "Root", "X", NAMESPACE_FUNCTION).semantic_id, "Root.X")
        self.assertEqual(resolve_symbol(plan, "Root", "E", NAMESPACE_ENTITY).semantic_id, "Root.E")
        for text in (
            'script Root version "1.0.0"; record Int { x: Int; } entity E { on start { return; } }',
            'script Root version "1.0.0"; fn max(x: Int) -> Int = x; entity E { on start { return; } }',
            'script Root version "1.0.0"; capability time.delta() -> Rat observation; entity E { on start { return; } }',
        ):
            with self.assertRaises(TevScriptError) as captured:
                link_v1_sources([src("root.tevs", text)])
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_PREDECLARED_COLLISION")

    def test_nested_nominal_type_ids_are_canonical(self) -> None:
        plan = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; import types; entity E { state x: Option<Result<Damage, Text>> = None; on start { return; } }'),
            src("types.tevs", 'module types version "1.0.0"; export record Damage { amount: Int; }'),
        ])
        type_ref = plan.root.entities[0].states[0].type_ref
        self.assertEqual(canonical_type_id(plan, "Root", type_ref), "Option<Result<types.Damage,Text>>")

    def test_namespace_determined_ast_references_are_resolved_during_link(self) -> None:
        invalid = (
            'script Root version "1.0.0"; entity E { state x: Missing = 0; on start { return; } }',
            'script Root version "1.0.0"; entity E { use Missing; on start { return; } }',
            'script Root version "1.0.0"; entity E { on start { call world.missing(); } }',
            'script Root version "1.0.0"; entity E { on start { let x = Missing(value = 1); } }',
            'script Root version "1.0.0"; entity E { on start { let x = Missing::A; } }',
        )
        for text in invalid:
            with self.subTest(text=text):
                with self.assertRaises(TevScriptError) as captured:
                    link_v1_sources([src("root.tevs", text)])
                self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_NAME_UNKNOWN")

    def test_direct_imported_type_is_visible_inside_module_but_transitive_only_type_is_not(self) -> None:
        valid = link_v1_sources([
            src("root.tevs", 'script Root version "1.0.0"; import b; entity E { on start { return; } }'),
            src("a.tevs", 'module a version "1.0.0"; export record A { x: Int; }'),
            src("b.tevs", 'module b version "1.0.0"; import a; export record B { child: A; }'),
        ])
        symbol = resolve_symbol(valid, "Root", "b.B", NAMESPACE_TYPE)
        self.assertEqual(canonical_type_id(valid, "b", symbol.declaration.fields[0].type_ref), "a.A")

        with self.assertRaises(TevScriptError) as captured:
            link_v1_sources([
                src("root.tevs", 'script Root version "1.0.0"; import c; entity E { on start { return; } }'),
                src("a.tevs", 'module a version "1.0.0"; export record A { x: Int; }'),
                src("b.tevs", 'module b version "1.0.0"; import a; export record B { x: Int; }'),
                src("c.tevs", 'module c version "1.0.0"; import b; export record C { child: A; }'),
            ])
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LINK_NAME_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
