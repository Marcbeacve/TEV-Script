from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]


def _bundle(source: str):
    plan = link_v1_sources([SourceInputV1("schema.tevs", source.encode())])
    return emit_linked_program_v1(analyze_v1_static_semantics(plan))


class V1LinkedProgramSchemaNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import jsonschema
        except ImportError as exc:
            raise unittest.SkipTest("jsonschema dependency unavailable") from exc
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_linked_program_v1.schema.json").read_text()
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        cls.validator = jsonschema.Draft202012Validator(schema)

    def test_single_variant_enum_match_is_valid(self) -> None:
        bundle = _bundle(
            'script Root version "1.0.0"; '
            'enum Only { A; } '
            'entity E { state k: Only = Only::A; on start { match k { Only::A => { return; } } } }'
        )
        self.validator.validate(bundle.program)

    def test_semantic_hash_is_required(self) -> None:
        bundle = _bundle(
            'script Root version "1.0.0"; entity E { on start { return; } }'
        )
        tampered = copy.deepcopy(bundle.program)
        tampered.pop("semantic_hash")
        self.assertTrue(list(self.validator.iter_errors(tampered)))

    def test_none_pattern_rejects_impossible_binding(self) -> None:
        bundle = _bundle(
            'script Root version "1.0.0"; '
            'entity E { state x: Option<Int> = None; '
            'on start { match x { Some(v) => { return; } None => { return; } } } }'
        )
        tampered = copy.deepcopy(bundle.program)
        match_stmt = tampered["entities"][0]["handlers"][0]["body"][0]
        none_arm = next(arm for arm in match_stmt["arms"] if arm["pattern"]["kind"] == "none")
        none_arm["pattern"]["binding"] = "_l99"
        self.assertTrue(list(self.validator.iter_errors(tampered)))

    def test_some_pattern_requires_binding(self) -> None:
        bundle = _bundle(
            'script Root version "1.0.0"; '
            'entity E { state x: Option<Int> = None; '
            'on start { match x { Some(v) => { return; } None => { return; } } } }'
        )
        tampered = copy.deepcopy(bundle.program)
        match_stmt = tampered["entities"][0]["handlers"][0]["body"][0]
        some_arm = next(arm for arm in match_stmt["arms"] if arm["pattern"]["kind"] == "some")
        some_arm["pattern"].pop("binding")
        self.assertTrue(list(self.validator.iter_errors(tampered)))

    def test_negative_zero_is_not_canonical_integer(self) -> None:
        bundle = _bundle(
            'script Root version "1.0.0"; entity E { state x: Int = 0; on start { return; } }'
        )
        tampered = copy.deepcopy(bundle.program)
        tampered["entities"][0]["states"][0]["initial"]["value"] = "-0"
        self.assertTrue(list(self.validator.iter_errors(tampered)))

    def test_duplicate_import_is_rejected_by_schema(self) -> None:
        plan = link_v1_sources(
            [
                SourceInputV1(
                    "root.tevs",
                    b'script Root version "1.0.0"; import a; entity E { on start { return; } }',
                ),
                SourceInputV1(
                    "a.tevs",
                    b'module a version "1.0.0"; export record R { x: Int; }',
                ),
            ]
        )
        bundle = emit_linked_program_v1(analyze_v1_static_semantics(plan))
        tampered = copy.deepcopy(bundle.program)
        tampered["modules"][0]["imports"] = ["a", "a"]
        self.assertTrue(list(self.validator.iter_errors(tampered)))


if __name__ == "__main__":
    unittest.main()
