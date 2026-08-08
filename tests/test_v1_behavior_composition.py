from __future__ import annotations

import json
import unittest
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "conformance" / "v1-behavior-composition-cases.json").read_text()
)


def src(path: str, text: str) -> SourceInputV1:
    return SourceInputV1(path, text.encode())


def analyze(sources: list[dict[str, str]]):
    plan = link_v1_sources(
        [src(item["path"], item["source"]) for item in sources]
    )
    return analyze_v1_static_semantics(plan)


class V1BehaviorCompositionCorpusTests(unittest.TestCase):
    def test_positive_behavior_corpus(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                result = analyze(case["sources"])
                self.assertTrue(result.semantic_hash)

    def test_negative_behavior_corpus(self) -> None:
        for case in CASES["negative"]:
            with self.subTest(case=case["id"]):
                with self.assertRaises(TevScriptError) as captured:
                    analyze(case["sources"])
                self.assertEqual(captured.exception.diagnostic.code, case["code"])


class V1BehaviorVisibilityTests(unittest.TestCase):
    def test_child_behavior_sees_dependency_state(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior Base { state alive: Bool = true; } behavior Child { use Base; state speed: Rat = 1; on update { if alive { speed = speed + 1; } } } entity E { use Child; on start { return; } }',
            }
        ])
        child = result.behavior_model.composite("Root.Child")
        self.assertEqual(child.flattened_behaviors, ("Root.Base",))
        self.assertEqual(
            sorted(child.state_types),
            ["alive", "speed"],
        )

    def test_entity_local_handler_sees_all_used_behavior_states(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior A { state a: Int = 0; } behavior B { state b: Rat = 1; } entity E { use A; use B; on update { a = 2; b = 3; } }',
            }
        ])
        entity = next(item for item in result.composites if item.composite_id == "Root.E")
        self.assertEqual(entity.states, (("a", "Int"), ("b", "Rat")))

    def test_behavior_fragment_does_not_gain_sibling_state_visibility(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            analyze([
                {
                    "path": "root.tevs",
                    "source": 'script Root version "1.0.0"; behavior A { on update { b = 1; } } behavior B { state b: Int = 0; } entity E { use A; use B; on start { return; } }',
                }
            ])
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_TYPE_STATE_UNKNOWN")


class V1BehaviorOrderTests(unittest.TestCase):
    def test_dependency_first_then_explicit_use_order_then_entity_local(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior Base { on update { log "base"; } } behavior A { use Base; on update { log "a"; } } behavior B { on update { log "b"; } } entity E { use A; use B; on update { log "e"; } }',
            }
        ])
        model = result.behavior_model.composite("Root.E")
        self.assertEqual(
            model.flattened_behaviors,
            ("Root.Base", "Root.A", "Root.B"),
        )
        update_fragments = [
            item.component_id
            for item in model.handler_fragments
            if item.declaration.event_id == "update"
        ]
        self.assertEqual(
            update_fragments,
            ("Root.Base", "Root.A", "Root.B", "Root.E"),
        )

    def test_explicit_use_order_changes_semantic_hash(self) -> None:
        common = 'behavior A { on update { log "a"; } } behavior B { on update { log "b"; } }'
        left = analyze([
            {
                "path": "left.tevs",
                "source": f'script Root version "1.0.0"; {common} entity E {{ use A; use B; on start {{ return; }} }}',
            }
        ])
        right = analyze([
            {
                "path": "right.tevs",
                "source": f'script Root version "1.0.0"; {common} entity E {{ use B; use A; on start {{ return; }} }}',
            }
        ])
        self.assertNotEqual(left.semantic_hash, right.semantic_hash)

    def test_state_declaration_order_is_not_semantic(self) -> None:
        left = analyze([
            {
                "path": "left.tevs",
                "source": 'script Root version "1.0.0"; behavior A { state z: Int = 1; state a: Rat = 2; } entity E { use A; on start { return; } }',
            }
        ])
        right = analyze([
            {
                "path": "right.tevs",
                "source": 'script Root version "1.0.0"; behavior A { state a: Rat = 2; state z: Int = 1; } entity E { use A; on start { return; } }',
            }
        ])
        self.assertEqual(left.semantic_hash, right.semantic_hash)


class V1BehaviorAggregateTests(unittest.TestCase):
    def test_entity_handler_effects_are_union_of_all_fragments(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on update { log "a"; } } behavior B { on update { animate "Walk"; } } entity E { use A; use B; on update { move vec2(1, 0); } }',
            }
        ])
        entity = next(item for item in result.composites if item.composite_id == "Root.E")
        update = next(item for item in entity.handlers if item.event_id == "update")
        self.assertEqual(
            update.capabilities,
            ("animation.play", "debug.log", "motion.move2d"),
        )

    def test_sibling_emit_is_normalized_to_composed_handler_signature(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior Producer { on start { emit pulse(1); } } behavior Consumer { on pulse(value: Rat) { log "pulse"; } } entity E { use Producer; use Consumer; on update { return; } }',
            }
        ])
        entity = next(item for item in result.composites if item.composite_id == "Root.E")
        start = next(item for item in entity.handlers if item.event_id == "start")
        self.assertEqual(start.emitted_events, (("pulse", ("Rat",)),))

    def test_local_parameter_names_are_selected_without_affecting_signature(self) -> None:
        result = analyze([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on pulse(x: Int) { log "a"; } } behavior B { on pulse(y: Int) { log "b"; } } entity E { use A; use B; on pulse(z: Int) { log "e"; } }',
            }
        ])
        entity = next(item for item in result.composites if item.composite_id == "Root.E")
        pulse = next(item for item in entity.handlers if item.event_id == "pulse")
        self.assertEqual(pulse.parameters, (("z", "Int"),))


class V1BehaviorBudgetTests(unittest.TestCase):
    def test_flattened_behavior_budget_is_enforced_without_python_recursion(self) -> None:
        declarations = ['behavior B0 { state x0: Int = 0; }']
        for index in range(1, 257):
            declarations.append(
                f'behavior B{index} {{ use B{index - 1}; state x{index}: Int = {index}; }}'
            )
        source = (
            'script Root version "1.0.0"; '
            + ' '.join(declarations)
            + ' entity E { use B256; on start { return; } }'
        )
        with self.assertRaises(TevScriptError) as captured:
            analyze([{"path": "root.tevs", "source": source}])
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V1_BEHAVIOR_FLATTENED_BUDGET",
        )


if __name__ == "__main__":
    unittest.main()
