from __future__ import annotations

import json
import unittest
from pathlib import Path

from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]
def linked(source: str):
    plan = link_v1_sources([SourceInputV1("root.tevs", source.encode())])
    return emit_linked_program_v1(analyze_v1_static_semantics(plan))


class V1LinkedProgramSchemaTests(unittest.TestCase):
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

    def test_complete_v1_value_surface_conforms_to_schema(self) -> None:
        bundle = linked(
            'script Root version "1.0.0"; '
            'record R { x: Int; flag: Bool; } '
            'enum K { A; B; } '
            'capability world.read() -> Int observation; '
            'fn f(x: Int) -> Int = x + 1; '
            'behavior Beh { state speed: Rat = 1; on update { log "b"; } } '
            'entity E { '
            'use Beh; '
            'state r: R = R(x = 1, flag = true); '
            'state k: K = K::A; '
            'state option: Option<Int> = Some(2); '
            'state result: Result<Int, Text> = Ok(3); '
            'state out: Int = 0; '
            'on pulse(value: Int) { '
            'let local = f(value); '
            'if local > 0 { out = local; } else { out = 0; } '
            'for i in 0 .. 2 { out = out + i; } '
            'match option { Some(payload) => { out = out + payload; } None => { return; } } '
            '} '
            'on update { out = world.read(); } '
            '}'
        )
        errors = sorted(
            self.validator.iter_errors(bundle.program),
            key=lambda item: list(item.absolute_path),
        )
        self.assertEqual(
            errors,
            [],
            "\n".join(
                f"path={list(error.absolute_path)}: {error.message}"
                for error in errors
            ),
        )

    def test_semantic_hash_property_is_exact_lower_hex_sha256(self) -> None:
        bundle = linked(
            'script Root version "1.0.0"; entity E { on start { return; } }'
        )
        self.assertRegex(bundle.program["semantic_hash"], r"^[0-9a-f]{64}$")
        self.validator.validate(bundle.program)


if __name__ == "__main__":
    unittest.main()
