from __future__ import annotations

import json
from pathlib import Path
import unittest

import jsonschema

from tev_script.descriptor_v3 import v3_descriptor
from tev_script.program_ir_v5_semantic import (
    checkpoint_to_object,
    initial_process_checkpoint,
    program_to_object,
)
from tev_script.source_semantic_process_v3 import compile_semantic_process_v3
from tev_script.release_metadata_v3 import RELEASE_STATUS, STABLE

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '''
process Door version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["closed"];
field actual = [closed];
label done = halt;
entry done;
'''


class V3SchemaMetadataTests(unittest.TestCase):
    def _json(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_descriptor_schema_accepts_exact_descriptor_and_rejects_promotion(self) -> None:
        schema = self._json("schemas/tev-script-v3-descriptor.schema.json")
        jsonschema.Draft202012Validator.check_schema(schema)
        value = v3_descriptor()
        jsonschema.validate(value, schema)
        tampered = dict(value); tampered["promotion_authority"] = True
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(tampered, schema)

    def test_program_and_checkpoint_schemas_accept_runtime_artifacts(self) -> None:
        schema = self._json("schemas/tev-script-program-ir-v5-semantic-process.schema.json")
        jsonschema.Draft202012Validator.check_schema(schema)
        program = compile_semantic_process_v3(SOURCE)
        jsonschema.validate(program_to_object(program), schema)
        cp_schema = self._json("schemas/tev-script-v3-process-checkpoint.schema.json")
        jsonschema.Draft202012Validator.check_schema(cp_schema)
        jsonschema.validate(checkpoint_to_object(initial_process_checkpoint(program), program), cp_schema)

    def test_feature_matrix_binds_exact_candidate_boundary(self) -> None:
        matrix = self._json("spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json")
        self.assertEqual(matrix["language_version"], "3.0.0")
        self.assertEqual(matrix["program_ir_version"], "5")
        self.assertEqual(matrix["status"], RELEASE_STATUS)
        self.assertIs(matrix["stable"], STABLE)
        self.assertFalse(matrix["publication_authorized"])
        self.assertFalse(matrix["merge_authorized"])
        features = {row["id"]: row["status"] for row in matrix["required_features"]}
        for feature in (
            "MINIMAL_FIELD_TRANSFORMATION_APPLY_BASIS",
            "EPISTEMIC_TYPE_EFFECT_LAYER",
            "BOUNDED_QUANTA_CONTINUATIONS",
            "PROGRAM_IR_V5_SEMANTIC_PROCESS",
            "NATIVE_V3_SOURCE_PROFILE",
            "SOURCE_TO_IR_TRANSLATION_VALIDATION",
            "DERIVED_SEMANTIC_STDLIB",
            "EXPLICIT_V2_COMPATIBILITY_LANE",
        ):
            self.assertEqual(features[feature], "CLOSED")
        self.assertEqual(matrix["native_v3_external_effects"], "NOT_SUPPORTED_IN_SEMANTIC_PROCESS_V1")


if __name__ == "__main__":
    unittest.main()
