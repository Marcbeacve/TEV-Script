from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, ValidationError

from tev_script.descriptor_v2 import v2_descriptor
from tev_script.file_observation_acquisition_v2 import (
    acquire_file_read_observations_v2,
    build_file_read_acquisition_request_v2,
)
from tev_script.program_ir_v4 import export_program_ir_v4_pure, export_program_ir_v4_recursive
from tev_script.source_effect_program_v2 import (
    build_effect_command_program_ir_v4,
    build_effect_program_ir_v4,
    compile_effect_command_program_v2,
    compile_effect_program_v2,
)
from tev_script.source_program_v2 import compile_program_v2


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = (
    "schemas/tev-script-v2-descriptor.schema.json",
    "schemas/tev-script-program-ir-v4.schema.json",
    "schemas/tev-script-v2-filesystem-artifacts.schema.json",
    "schemas/tev-script-v2-certify-full-receipt.schema.json",
)


def load_schema(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class V2SchemaTests(unittest.TestCase):
    def test_all_v2_schemas_are_valid_draft_2020_12(self) -> None:
        for relative in SCHEMA_PATHS:
            with self.subTest(relative=relative):
                schema = load_schema(relative)
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                Draft202012Validator.check_schema(schema)

    def test_descriptor_schema_accepts_exact_descriptor_and_rejects_drift(self) -> None:
        validator = Draft202012Validator(load_schema(SCHEMA_PATHS[0]))
        descriptor = v2_descriptor()
        validator.validate(descriptor)
        for mutation in ("unknown", "missing", "uppercase_hash", "stable"):
            changed = copy.deepcopy(descriptor)
            if mutation == "unknown":
                changed["unknown"] = True
            elif mutation == "missing":
                del changed["authority"]
            elif mutation == "uppercase_hash":
                changed["descriptor_hash"] = changed["descriptor_hash"].upper()
            else:
                changed["stable"] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                validator.validate(changed)

    def test_program_ir_schema_closes_all_four_profiles(self) -> None:
        validator = Draft202012Validator(load_schema(SCHEMA_PATHS[1]))
        pure = compile_program_v2('script D version "2.0.0"; entry main:Int=1;')
        recursive = compile_program_v2('script D version "2.0.0"; recursive fn f(n:Int)->Int decreases n max_depth 3 = if n==0 then 0 else self(n-1); entry main:Int=f(2);')
        effects = compile_effect_program_v2('script D version "2.0.0"; state x:Int=0; action a(){set x=1;} entry main=a();')
        effects_scenario = {"capability_table_hash": effects.capabilities.table_hash, "capabilities": []}
        commands = compile_effect_command_program_v2('script D version "2.0.0"; state x:Int=0; command file.replace(Text,Text); action a(){request file.replace("x.txt","x"); set x=1;} entry main=a();')
        command_scenario = {"capability_table_hash": commands.capabilities.table_hash, "capabilities": []}
        programs = (
            export_program_ir_v4_pure(pure),
            export_program_ir_v4_recursive(recursive),
            build_effect_program_ir_v4(effects, effects_scenario),
            build_effect_command_program_ir_v4(commands, command_scenario),
        )
        for program in programs:
            with self.subTest(profile=program["profile"]):
                validator.validate(program)
                unknown = copy.deepcopy(program)
                unknown["unknown"] = True
                with self.assertRaises(ValidationError):
                    validator.validate(unknown)
                uppercase = copy.deepcopy(program)
                uppercase["program_ir_hash"] = uppercase["program_ir_hash"].upper()
                with self.assertRaises(ValidationError):
                    validator.validate(uppercase)

    def test_filesystem_artifact_schema_rejects_unknown_and_bad_hash(self) -> None:
        validator = Draft202012Validator(load_schema(SCHEMA_PATHS[2]))
        artifact = {
            "schema": "TEV_SCRIPT_FILE_EFFECT_SCOPE_V2_V1",
            "root": "c:/authorized",
            "scope_hash": "1" * 64,
        }
        validator.validate(artifact)
        changed = {**artifact, "unknown": 1}
        with self.assertRaises(ValidationError):
            validator.validate(changed)
        changed = {**artifact, "scope_hash": "A" * 64}
        with self.assertRaises(ValidationError):
            validator.validate(changed)

    def test_filesystem_artifact_schema_accepts_real_request_and_evidence(self) -> None:
        validator = Draft202012Validator(load_schema(SCHEMA_PATHS[2]))
        compiled = compile_effect_program_v2(
            'script D version "2.0.0"; state x:Text=""; '
            'capability observation file.read(Text)->Text; '
            'action a(){observe value=file.read("input.txt"); set x=value;} entry main=a();'
        )
        request = build_file_read_acquisition_request_v2(compiled.capabilities, ["input.txt"])
        validator.validate(request)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "input.txt").write_text("bounded", encoding="utf-8")
            evidence = acquire_file_read_observations_v2(request, compiled.capabilities, root)
        validator.validate(evidence)
        mutations = []
        unknown_provider = copy.deepcopy(evidence)
        unknown_provider["provider"]["unknown"] = True
        mutations.append(unknown_provider)
        bad_limit = copy.deepcopy(evidence)
        bad_limit["provider"]["maximum_bytes_per_call"] += 1
        mutations.append(bad_limit)
        bad_call_index = copy.deepcopy(evidence)
        bad_call_index["calls"][0]["call_index"] = -1
        mutations.append(bad_call_index)
        bad_call_hash = copy.deepcopy(evidence)
        bad_call_hash["calls"][0]["call_evidence_hash"] = "A" * 64
        mutations.append(bad_call_hash)
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                validator.validate(mutation)


if __name__ == "__main__":
    unittest.main()
