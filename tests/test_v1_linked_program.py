from __future__ import annotations

import itertools
import json
import unittest
from pathlib import Path

from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "conformance" / "v1-linked-program-cases.json").read_text()
)


def src(path: str, text: str) -> SourceInputV1:
    return SourceInputV1(path, text.encode())


def linked(sources: list[dict[str, str]]):
    plan = link_v1_sources(
        [src(item["path"], item["source"]) for item in sources]
    )
    semantics = analyze_v1_static_semantics(plan)
    return emit_linked_program_v1(semantics)


class V1LinkedProgramEquivalenceTests(unittest.TestCase):
    def test_equivalent_source_pairs_have_identical_linked_bytes(self) -> None:
        for case in CASES["equivalent_pairs"]:
            with self.subTest(case=case["id"]):
                left = linked(case["left"])
                right = linked(case["right"])
                self.assertEqual(left.semantic_hash, right.semantic_hash)
                self.assertEqual(left.canonical_json, right.canonical_json)

    def test_semantically_different_pairs_have_different_hashes(self) -> None:
        for case in CASES["different_pairs"]:
            with self.subTest(case=case["id"]):
                left = linked(case["left"])
                right = linked(case["right"])
                self.assertNotEqual(left.semantic_hash, right.semantic_hash)

    def test_input_order_and_debug_paths_do_not_change_linked_program(self) -> None:
        logical = [
            (
                "root.tevs",
                'script Root version "1.0.0"; import math; import beh; entity E { use Move; state out: Rat = 1 + 1; on update { out = twice(out); } }',
            ),
            (
                "math.tevs",
                'module math version "1.0.0"; export fn twice(value: Rat) -> Rat = value * 2;',
            ),
            (
                "beh.tevs",
                'module beh version "1.0.0"; export behavior Move { on update { log "move"; } }',
            ),
        ]
        bytes_seen: set[str] = set()
        hashes: set[str] = set()
        for run, permutation in enumerate(itertools.permutations(range(3))):
            inputs = [
                SourceInputV1(
                    f"moved/{run}/{logical[index][0]}",
                    logical[index][1].encode(),
                )
                for index in permutation
            ]
            bundle = emit_linked_program_v1(
                analyze_v1_static_semantics(link_v1_sources(inputs))
            )
            bytes_seen.add(bundle.canonical_json)
            hashes.add(bundle.semantic_hash)
        self.assertEqual(len(bytes_seen), 1)
        self.assertEqual(len(hashes), 1)


class V1LinkedProgramShapeTests(unittest.TestCase):
    def test_top_level_shape_and_hash_are_self_consistent(self) -> None:
        bundle = linked([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; record R { x: Int; } enum K { A; B; } capability world.read() -> Int observation; fn f(x: Int) -> Int = x + 1; behavior B { state speed: Rat = 1; on update { log "b"; } } entity E { use B; state x: Int = 1 + 1; on update { x = f(world.read()); } }',
            }
        ])
        program = bundle.program
        self.assertEqual(program["schema"], "TEV_SCRIPT_LINKED_PROGRAM_V1")
        self.assertEqual(program["language_version"], "1.0.0")
        self.assertEqual(program["program_id"], "Root")
        self.assertEqual(program["semantic_hash"], bundle.semantic_hash)
        self.assertEqual(len(program["records"]), 1)
        self.assertEqual(len(program["enums"]), 1)
        self.assertEqual(len(program["functions"]), 1)
        self.assertEqual(len(program["behaviors"]), 1)
        self.assertEqual(len(program["entities"]), 1)
        self.assertEqual(len(program["capabilities"]), 1)

    def test_state_initializers_are_constant_normal_forms(self) -> None:
        bundle = linked([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; record R { z: Int; a: Rat; } entity E { state r: R = R(z = 2, a = 1); state x: Rat = 0.1 + 0.2; on start { return; } }',
            }
        ])
        states = {
            item["name"]: item
            for item in bundle.program["entities"][0]["states"]
        }
        self.assertEqual(
            states["x"]["initial"],
            {
                "kind": "rat",
                "type": "Rat",
                "numerator": "3",
                "denominator": "10",
            },
        )
        record = states["r"]["initial"]
        self.assertEqual(record["kind"], "record")
        self.assertEqual([item["name"] for item in record["fields"]], ["a", "z"])

    def test_handler_locals_and_parameters_are_alpha_normalized(self) -> None:
        bundle = linked([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; entity E { state out: Int = 0; on pulse(input: Int) { let first = input + 1; if true { let second = first + 1; out = second; } } }',
            }
        ])
        handler = bundle.program["entities"][0]["handlers"][0]
        self.assertEqual(handler["parameters"], [{"name": "_p0", "type": "Int"}])
        first = handler["body"][0]
        self.assertEqual(first["name"], "_l0")
        nested = handler["body"][1]["then"][0]
        self.assertEqual(nested["name"], "_l1")

    def test_sugar_statements_are_normalized_to_capability_calls(self) -> None:
        bundle = linked([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; entity E { on update { log "x"; move vec2(1, 0); animate "Walk"; } }',
            }
        ])
        body = bundle.program["entities"][0]["handlers"][0]["body"]
        self.assertEqual(
            [item["capability_id"] for item in body],
            ["debug.log", "motion.move2d", "animation.play"],
        )

    def test_entity_capability_summary_includes_used_behavior_requirements(self) -> None:
        bundle = linked([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on update { log "A"; } } behavior B { on update { animate "Walk"; } } entity E { use A; use B; on update { move vec2(1, 0); } }',
            }
        ])
        entity = bundle.program["entities"][0]
        self.assertEqual(
            entity["capabilities"],
            ["animation.play", "debug.log", "motion.move2d"],
        )

    def test_identical_repeated_capability_declarations_collapse_to_one_contract(self) -> None:
        bundle = linked([
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; import a; import b; entity E { state x: Int = 0; on update { x = world.read(); } }',
            },
            {
                "path": "a.tevs",
                "source": 'module a version "1.0.0"; export capability world.read() -> Int observation;',
            },
            {
                "path": "b.tevs",
                "source": 'module b version "1.0.0"; export capability world.read() -> Int observation;',
            },
        ])
        self.assertEqual(len(bundle.program["capabilities"]), 1)
        self.assertEqual(bundle.program["capabilities"][0]["capability_id"], "world.read")

    def test_unreachable_module_is_not_part_of_linked_semantics(self) -> None:
        base = [
            {
                "path": "root.tevs",
                "source": 'script Root version "1.0.0"; entity E { on start { return; } }',
            }
        ]
        with_unused = [
            *base,
            {
                "path": "unused.tevs",
                "source": 'module unused version "1.0.0"; export record R { x: Int; }',
            },
        ]
        self.assertEqual(linked(base).canonical_json, linked(with_unused).canonical_json)


if __name__ == "__main__":
    unittest.main()
