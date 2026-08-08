from __future__ import annotations

import itertools
import unittest
from fractions import Fraction

from tev_script.ir_v3_values import RecordValueV3, VariantValueV3
from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.lowering_ir_v3_linked_v1 import lower_linked_program_v1_to_ir_v3
from tev_script.runtime_v3 import ScriptRuntimeV3
from tev_script.static_semantics_v1 import analyze_v1_static_semantics


def compile_v3(*sources: tuple[str, str]):
    plan = link_v1_sources(
        SourceInputV1(path, text.encode()) for path, text in sources
    )
    semantics = analyze_v1_static_semantics(plan)
    linked = emit_linked_program_v1(semantics)
    return linked, lower_linked_program_v1_to_ir_v3(linked)


class V1ToIrV3RecordTests(unittest.TestCase):
    def test_record_constructor_field_load_and_assignment_execute(self) -> None:
        source = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
entity E {
  state out: Int = 0;
  state pair: Pair = Pair(a = 1, b = 2);
  on update {
    let next = Pair(a = 3, b = 4);
    pair = next;
    out = pair.a;
  }
}
'''
        linked, target = compile_v3(("root.tevs", source))
        self.assertEqual(target.ir["source_semantic_hash"], linked.semantic_hash)
        runtime = ScriptRuntimeV3(target.ir, expected_source_semantic_hash=linked.semantic_hash)
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["out"], 3)
        self.assertEqual(
            runtime.state("E")["pair"],
            RecordValueV3("Root.Pair", (("a", 3), ("b", Fraction(4, 1)))),
        )

    def test_user_function_can_return_record_and_is_inlined(self) -> None:
        source = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
fn make(x: Int) -> Pair = Pair(a = x, b = x);
entity E {
  state pair: Pair = Pair(a = 0, b = 0);
  on update { pair = make(9); }
}
'''
        _linked, target = compile_v3(("root.tevs", source))
        instructions = target.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertNotIn("Root.make", [item.get("function_id") for item in instructions])
        self.assertIn("MAKE_RECORD", [item["op"] for item in instructions])
        runtime = ScriptRuntimeV3(target.ir)
        runtime.invoke("E", "update")
        self.assertEqual(
            runtime.state("E")["pair"],
            RecordValueV3("Root.Pair", (("a", 9), ("b", Fraction(9, 1)))),
        )


class V1ToIrV3MatchTests(unittest.TestCase):
    def test_option_match_executes_one_arm_and_continues_after_match(self) -> None:
        source = '''script Root version "1.0.0";
entity E {
  state opt: Option<Int> = Some(5);
  state out: Int = 0;
  on update {
    match opt {
      Some(value) => { out = value; }
      None => { out = 100; }
    }
    out = out + 1;
  }
}
'''
        _linked, target = compile_v3(("root.tevs", source))
        instructions = target.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertIn("TEST_VARIANT", [item["op"] for item in instructions])
        self.assertIn("LOAD_VARIANT_PAYLOAD", [item["op"] for item in instructions])
        runtime = ScriptRuntimeV3(target.ir)
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["out"], 6)

    def test_result_match_binds_err_payload(self) -> None:
        source = '''script Root version "1.0.0";
entity E {
  state result: Result<Int, Text> = Err("bad");
  state message: Text = "";
  on update {
    match result {
      Ok(value) => { message = "ok"; }
      Err(error) => { message = error; }
    }
  }
}
'''
        _linked, target = compile_v3(("root.tevs", source))
        runtime = ScriptRuntimeV3(target.ir)
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["message"], "bad")

    def test_enum_match_supports_single_variant_without_schema_artifact(self) -> None:
        source = '''script Root version "1.0.0";
enum Only { A; }
entity E {
  state value: Only = Only::A;
  state hit: Bool = false;
  on update {
    match value { Only::A => { hit = true; } }
  }
}
'''
        _linked, target = compile_v3(("root.tevs", source))
        runtime = ScriptRuntimeV3(target.ir)
        runtime.invoke("E", "update")
        self.assertIs(runtime.state("E")["hit"], True)


class V1ToIrV3CapabilityTests(unittest.TestCase):
    def test_algebraic_capability_input_and_output_cross_runtime_boundary(self) -> None:
        source = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
capability sink.write(Pair) -> Unit effect;
capability world.read() -> Pair observation;
entity E {
  state pair: Pair = Pair(a = 0, b = 0);
  on update {
    pair = world.read();
    call sink.write(pair);
  }
}
'''
        linked, target = compile_v3(("root.tevs", source))
        observed = []
        runtime = ScriptRuntimeV3(
            target.ir,
            {
                "world.read": lambda: {
                    "$record": {
                        "type": "Root.Pair",
                        "fields": [
                            {"name": "a", "value": {"$int": "12"}},
                            {"name": "b", "value": {"$rat": ["1", "4"]}},
                        ],
                    }
                },
                "sink.write": lambda value: observed.append(value),
            },
            expected_source_semantic_hash=linked.semantic_hash,
        )
        runtime.invoke("E", "update")
        pair = RecordValueV3("Root.Pair", (("a", 12), ("b", Fraction(1, 4))))
        self.assertEqual(runtime.state("E")["pair"], pair)
        self.assertEqual(observed, [pair])


class V1ToIrV3CompositionTests(unittest.TestCase):
    def test_behavior_state_and_match_are_expanded_into_entity_runtime(self) -> None:
        source = '''script Root version "1.0.0";
behavior Memory {
  state opt: Option<Int> = Some(2);
  on update {
    match opt {
      Some(value) => { opt = Some(value + 1); }
      None => { opt = Some(1); }
    }
  }
}
entity E { use Memory; on start { return; } }
'''
        _linked, target = compile_v3(("root.tevs", source))
        self.assertEqual(target.ir["entities"][0]["states"][0]["type"], "Option<Int>")
        runtime = ScriptRuntimeV3(target.ir)
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["opt"], VariantValueV3("Option<Int>", "Some", 3))

    def test_static_for_with_variant_construction_is_fully_unrolled(self) -> None:
        source = '''script Root version "1.0.0";
entity E {
  state opt: Option<Int> = None;
  on update {
    for i in 0 .. 3 { opt = Some(i); }
  }
}
'''
        _linked, target = compile_v3(("root.tevs", source))
        instructions = target.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertNotIn("FOR", [item["op"] for item in instructions])
        self.assertEqual([item["op"] for item in instructions].count("MAKE_VARIANT"), 3)
        runtime = ScriptRuntimeV3(target.ir)
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["opt"], VariantValueV3("Option<Int>", "Some", 2))


class V1ToIrV3DeterminismTests(unittest.TestCase):
    def test_source_file_order_and_paths_do_not_change_target_ir_semantics(self) -> None:
        logical = [
            ("root.tevs", 'script Root version "1.0.0"; import model; entity E { state pair: Pair = Pair(a = 1, b = 2); on update { pair = model.make(3); } }'),
            ("model.tevs", 'module model version "1.0.0"; export record Pair { a: Int; b: Rat; } export fn make(x: Int) -> Pair = Pair(a = x, b = x);'),
        ]
        hashes = set()
        source_hashes = set()
        for run, order in enumerate(itertools.permutations(range(2))):
            sources = tuple(
                (f"relocated/{run}/{logical[index][0]}", logical[index][1])
                for index in order
            )
            linked, target = compile_v3(*sources)
            hashes.add(target.ir["semantic_hash"])
            source_hashes.add(linked.semantic_hash)
        self.assertEqual(len(hashes), 1)
        self.assertEqual(len(source_hashes), 1)


if __name__ == "__main__":
    unittest.main()
