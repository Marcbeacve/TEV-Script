from __future__ import annotations

from dataclasses import asdict
import copy
import json
from pathlib import Path
import subprocess
import unittest

from tev_script.canonical import canonical_json
from tev_script.omega_semantic_basis_v1 import field_fact, field_transformation, semantic_field
from tev_script.program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    VerifiedProofAdmissionV1,
    total_core_program_to_mapping,
)
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
from tev_script.source_effect_program_v2 import compile_effect_program_v2
from tev_script.source_total_core_v31 import compile_total_core_v31


ROOT = Path(__file__).resolve().parents[1]
JS_RUNTIME = ROOT / "runtime_js_v31" / "runtime_v5_total.mjs"
MATRIX_PATH = ROOT / "conformance" / "v31-total-core-parity.json"

AUTHORITY = "a" * 64
SOURCE_HASH = "b" * 64
REQUIREMENT = "c" * 64
VERIFICATION_RECEIPT = "d" * 64
VERIFIER = "e" * 64

PURE_SOURCE = (
    'script Calc version "2.0.0"; '
    'fn add1(x:Int)->Int=x+1; '
    'entry main:Int=add1(4);'
)
RECURSIVE_SOURCE = '''
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
'''
EFFECT_SOURCE = '''
script Effects version "2.0.0";
state count:Int=0;
capability observation sensor.read(Int)->Int;
action tick() {
    observe sample=sensor.read(count);
    set count=sample;
}
entry main=tick();
'''
UNSUPPORTED_SOURCE = '''
script Arrays version "2.0.0";
generic fn middle<T>(xs:Array<T,3>)->T=array.get(xs,1);
entry main:Int=middle<Int>([4,9,7]);
'''

PROCESS_PURE = f'''
process JsPure version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.total.result End;
label End = halt;
entry Start;
'''
PROCESS_RECURSIVE = f'''
process JsRecursive version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Rec result tev.total.result End;
label End = halt;
entry Start;
'''
PROCESS_EFFECTS = f'''
process JsEffects version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Effects profile effects;
field actual = [];
label Start = invoke_v4 Effects result tev.total.result End;
label End = halt;
entry Start;
'''
PROCESS_UNSUPPORTED = f'''
process JsUnsupported version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Arrays profile pure;
field actual = [];
label Start = invoke_v4 Arrays result tev.total.result End;
label End = halt;
entry Start;
'''
PROCESS_CYCLE = f'''
process JsCycle version "3.1.0";
authority {AUTHORITY};
quantum_steps 3;
field actual = [];
label Loop = jump Loop;
entry Loop;
'''


class JavaScriptRuntimeV5TotalCoreParityTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def _effect_scenario(result: int = 9) -> dict:
        compiled = compile_effect_program_v2(EFFECT_SOURCE)
        contract = compiled.capabilities.require("sensor.read")
        return {
            "capability_table_hash": compiled.capabilities.table_hash,
            "capabilities": [{
                "capability_id": "sensor.read",
                "contract_hash": contract.contract_hash,
                "calls": [{
                    "arguments": [{"$int": "0"}],
                    "return": {"$int": str(result)},
                }],
            }],
        }

    @staticmethod
    def _python_bytes(result) -> str:
        return canonical_json(asdict(result)) + "\n"

    def _node_raw(self, program_mapping: dict, checkpoint_mapping: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("node", str(JS_RUNTIME)),
            input=canonical_json({"program": program_mapping, "checkpoint": checkpoint_mapping}),
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=30,
            check=False,
        )

    def _node(self, program, checkpoint) -> subprocess.CompletedProcess[str]:
        return self._node_raw(total_core_program_to_mapping(program), asdict(checkpoint))

    def _assert_parity(self, program) -> None:
        checkpoint = initial_total_core_checkpoint(program)
        expected = run_total_core_quantum(program, checkpoint)
        completed = self._node(program, checkpoint)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, self._python_bytes(expected))

    def test_conformance_matrix_pins_governed_independent_subset(self) -> None:
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(matrix["language_version"], "3.1.0")
        self.assertEqual(matrix["profile"], "total_core")
        self.assertEqual(matrix["unsupported_v4_behavior"], "FAIL_CLOSED")
        self.assertEqual(
            matrix["v5_instruction_kinds"],
            ["apply", "branch_fact", "halt", "invoke_v4", "jump"],
        )
        self.assertIn("SELF_CALL", matrix["v4_governed_subset"]["recursive"]["expression_ops"])
        self.assertIn("OBSERVE", matrix["v4_governed_subset"]["effects"]["action_ops"])

    def test_pure_v4_child_is_byte_identical_to_python(self) -> None:
        program = compile_total_core_v31(
            PROCESS_PURE,
            unit_sources={"Calc": PURE_SOURCE},
        )
        self._assert_parity(program)

    def test_recursive_v4_child_is_byte_identical_to_python(self) -> None:
        program = compile_total_core_v31(
            PROCESS_RECURSIVE,
            unit_sources={"Rec": RECURSIVE_SOURCE},
        )
        self._assert_parity(program)

    def test_effects_v4_child_is_byte_identical_to_python(self) -> None:
        program = compile_total_core_v31(
            PROCESS_EFFECTS,
            unit_sources={"Effects": EFFECT_SOURCE},
            effect_inputs={"Effects": {"scenario": self._effect_scenario()}},
        )
        self._assert_parity(program)

    def test_exact_proof_admission_apply_is_byte_identical_to_python(self) -> None:
        fact = field_fact("tev.proof.accepted", ({"value": "verified"},))
        transformation = field_transformation(
            transformation_id="proof.gated.transition",
            add_facts=(fact,),
            effect_set_hash="1" * 64,
            resource_vector_hash="2" * 64,
            proof_requirement_hashes=(REQUIREMENT,),
        )
        admission = VerifiedProofAdmissionV1.build(
            requirement_hash=REQUIREMENT,
            verification_receipt_hash=VERIFICATION_RECEIPT,
            verifier_identity_hash=VERIFIER,
            authority_hash=AUTHORITY,
        )
        program = TotalCoreProgramV1.build(
            program_id="JsProof",
            source_semantic_hash=SOURCE_HASH,
            initial_field=semantic_field((), profile="actual"),
            transformations=(transformation,),
            v4_units=(),
            proof_admissions=(admission,),
            instructions=(
                TotalCoreInstructionV1.apply(transformation.transformation_hash, next_pc=1),
                TotalCoreInstructionV1.halt(),
            ),
            entry_pc=0,
            quantum_step_limit=4,
            authority_hash=AUTHORITY,
        )
        self._assert_parity(program)

    def test_two_epoch_cycle_matches_continuation_chain_byte_for_byte(self) -> None:
        program = compile_total_core_v31(PROCESS_CYCLE, unit_sources={})
        initial = initial_total_core_checkpoint(program)
        first = run_total_core_quantum(program, initial)
        js_first = self._node(program, initial)
        self.assertEqual(js_first.returncode, 0, js_first.stderr)
        self.assertEqual(js_first.stdout, self._python_bytes(first))

        js_first_object = json.loads(js_first.stdout)
        second = run_total_core_quantum(program, first.next_checkpoint)
        js_second = self._node_raw(
            total_core_program_to_mapping(program),
            js_first_object["next_checkpoint"],
        )
        self.assertEqual(js_second.returncode, 0, js_second.stderr)
        self.assertEqual(js_second.stdout, self._python_bytes(second))
        self.assertEqual(
            json.loads(js_second.stdout)["continuation"]["previous_continuation_hash"],
            first.continuation.continuation_hash,
        )

    def test_tampered_embedded_v4_unit_fails_before_execution(self) -> None:
        program = compile_total_core_v31(
            PROCESS_PURE,
            unit_sources={"Calc": PURE_SOURCE},
        )
        checkpoint = initial_total_core_checkpoint(program)
        raw = copy.deepcopy(total_core_program_to_mapping(program))
        raw["v4_units"][0]["program_ir_v4"]["program_ir_hash"] = "0" * 64
        completed = self._node_raw(raw, asdict(checkpoint))
        self.assertNotEqual(completed.returncode, 0)
        self.assertRegex(completed.stderr, r"V4|UNIT")

    def test_tampered_proof_admission_fails_before_execution(self) -> None:
        fact = field_fact("tev.proof.accepted", ({"value": "verified"},))
        transformation = field_transformation(
            transformation_id="proof.gated.transition",
            add_facts=(fact,),
            effect_set_hash="1" * 64,
            resource_vector_hash="2" * 64,
            proof_requirement_hashes=(REQUIREMENT,),
        )
        admission = VerifiedProofAdmissionV1.build(
            requirement_hash=REQUIREMENT,
            verification_receipt_hash=VERIFICATION_RECEIPT,
            verifier_identity_hash=VERIFIER,
            authority_hash=AUTHORITY,
        )
        program = TotalCoreProgramV1.build(
            program_id="JsProofTamper",
            source_semantic_hash=SOURCE_HASH,
            initial_field=semantic_field((), profile="actual"),
            transformations=(transformation,),
            v4_units=(),
            proof_admissions=(admission,),
            instructions=(
                TotalCoreInstructionV1.apply(transformation.transformation_hash, next_pc=1),
                TotalCoreInstructionV1.halt(),
            ),
            entry_pc=0,
            quantum_step_limit=4,
            authority_hash=AUTHORITY,
        )
        checkpoint = initial_total_core_checkpoint(program)
        raw = copy.deepcopy(total_core_program_to_mapping(program))
        raw["proof_admissions"][0]["admission_hash"] = "0" * 64
        completed = self._node_raw(raw, asdict(checkpoint))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("PROOF", completed.stderr)

    def test_tampered_checkpoint_fails_before_execution(self) -> None:
        program = compile_total_core_v31(PROCESS_CYCLE, unit_sources={})
        checkpoint = asdict(initial_total_core_checkpoint(program))
        checkpoint["pc"] = 99
        completed = self._node_raw(total_core_program_to_mapping(program), checkpoint)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("CHECKPOINT", completed.stderr)

    def test_v4_outside_governed_subset_fails_closed(self) -> None:
        program = compile_total_core_v31(
            PROCESS_UNSUPPORTED,
            unit_sources={"Arrays": UNSUPPORTED_SOURCE},
        )
        checkpoint = initial_total_core_checkpoint(program)
        completed = self._node(program, checkpoint)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("V4_UNSUPPORTED", completed.stderr)

    def test_javascript_runtime_has_no_python_or_process_delegation(self) -> None:
        source = JS_RUNTIME.read_text(encoding="utf-8").lower()
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        for token in matrix["forbidden_delegation_tokens"]:
            self.assertNotIn(token.lower(), source)
        self.assertNotIn("http://", source)
        self.assertNotIn("https://", source)


if __name__ == "__main__":
    unittest.main()
