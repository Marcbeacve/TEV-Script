from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from tev_script.canonical import canonical_hash
from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effects import (
    build_capability_table_v4,
    build_effect_action_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
)
from tev_script.ir_v4_values import build_type_table_v4
from tev_script.omega_semantic_basis_v1 import semantic_field
from tev_script.program_ir_v4 import (
    build_program_ir_v4_effects,
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
    run_program_ir_v4_effects,
    run_program_ir_v4_pure,
    run_program_ir_v4_recursive,
)
from tev_script.program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    TotalCoreUnitV1,
)
from tev_script.runtime_v5_total import (
    TotalCoreCheckpointV1,
    initial_total_core_checkpoint,
    run_total_core_quantum,
)
from tev_script.source_program_v2 import compile_program_v2


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def _base_program(unit: TotalCoreUnitV1, *, quantum_steps: int = 8) -> TotalCoreProgramV1:
    return TotalCoreProgramV1.build(
        program_id="Demo",
        source_semantic_hash=HEX_B,
        initial_field=semantic_field((), profile="actual"),
        transformations=(),
        v4_units=(unit,),
        proof_admissions=(),
        instructions=(
            TotalCoreInstructionV1.invoke_v4(
                unit_hash=unit.unit_hash,
                result_relation="tev.total.result",
                next_pc=1,
            ),
            TotalCoreInstructionV1.halt(),
        ),
        entry_pc=0,
        quantum_step_limit=quantum_steps,
        authority_hash=HEX_A,
    )


def _bridge_payload(result) -> dict:
    facts = tuple(f for f in result.field.facts if f.relation == "tev.total.result")
    if len(facts) != 1:
        raise AssertionError(f"expected one bridge fact, got {len(facts)}")
    if len(facts[0].arguments) != 1 or not isinstance(facts[0].arguments[0], dict):
        raise AssertionError("bridge fact must contain one canonical object argument")
    return facts[0].arguments[0]


class RuntimeV5TotalCoreTests(unittest.TestCase):
    def pure_unit(self) -> TotalCoreUnitV1:
        source = (
            'script Calc version "2.0.0"; '
            'fn add1(x:Int)->Int=x+1; '
            'entry main:Int=add1(4);'
        )
        return TotalCoreUnitV1.build(
            "Calc", "pure", export_program_ir_v4_pure(compile_program_v2(source))
        )

    def recursive_unit(self) -> TotalCoreUnitV1:
        source = '''
        script Rec version "2.0.0";
        recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
        entry main:Int=factorial(5);
        '''
        return TotalCoreUnitV1.build(
            "Rec", "recursive", export_program_ir_v4_recursive(compile_program_v2(source))
        )

    def effects_unit(self) -> TotalCoreUnitV1:
        table = build_type_table_v4({
            "boundary": {"maximum_value_nesting": 128},
            "types": [
                {"type_id": "Bool", "kind": "primitive"},
                {"type_id": "Int", "kind": "primitive"},
                {"type_id": "Rat", "kind": "primitive"},
                {"type_id": "Text", "kind": "primitive"},
                {"type_id": "Unit", "kind": "unit"},
                {"type_id": "Vec2", "kind": "primitive"},
                {"type_id": "Vec3", "kind": "primitive"},
            ],
        })
        states = build_state_schema_v4(
            [{"name": "count", "type": "Int", "initial": {"$int": "0"}}],
            table,
        )
        caps = build_capability_table_v4(
            [{
                "capability_id": "sensor.read",
                "parameters": ["Int"],
                "return_type": "Int",
                "kind": "observation",
            }],
            table,
        )
        action = build_effect_action_v4(
            {
                "action_id": "tick",
                "parameters": [],
                "steps": [
                    {
                        "op": "OBSERVE",
                        "capability_id": "sensor.read",
                        "arguments": [{"op": "LOAD_STATE", "name": "count", "type": "Int"}],
                        "bind": "sample",
                    },
                    {
                        "op": "SET_STATE",
                        "state": "count",
                        "value": {"op": "LOAD_LOCAL", "name": "sample", "type": "Int"},
                    },
                ],
            },
            table,
            states,
            caps,
        )
        contract = caps.contracts[0]
        scenario = build_effect_scenario_v4(
            {
                "capability_table_hash": caps.table_hash,
                "capabilities": [{
                    "capability_id": "sensor.read",
                    "contract_hash": contract.contract_hash,
                    "calls": [{"arguments": [{"$int": "0"}], "return": {"$int": "9"}}],
                }],
            },
            table,
            caps,
        )
        ir = build_program_ir_v4_effects(
            program_id="Effects",
            source_semantic_hash=HEX_C,
            table=table,
            states=states,
            capabilities=caps,
            action=action,
            scenario=scenario,
            current_state={"count": 0},
            arguments=[],
        )
        return TotalCoreUnitV1.build("Effects", "effects", ir)

    def test_pure_invoke_v4_bridges_exact_receipt_and_result(self) -> None:
        unit = self.pure_unit()
        direct = run_program_ir_v4_pure(unit.program_ir_v4)
        program = _base_program(unit)
        result = run_total_core_quantum(program, initial_total_core_checkpoint(program))

        self.assertEqual(result.status, "HALTED")
        self.assertEqual(result.steps_used, 2)
        self.assertEqual(result.v4_evaluation_steps, direct.evaluation_steps)
        payload = _bridge_payload(result)
        self.assertEqual(payload["unit_id"], unit.unit_id)
        self.assertEqual(payload["unit_hash"], unit.unit_hash)
        self.assertEqual(payload["program_ir_hash"], unit.program_ir_hash)
        self.assertEqual(payload["run_receipt_hash"], direct.receipt_hash)
        self.assertEqual(payload["result_type"], direct.result_type)
        self.assertEqual(payload["result_encoded"], direct.result_encoded)
        self.assertEqual(payload["result_hash"], direct.result_hash)
        self.assertEqual(payload["evaluation_steps"], direct.evaluation_steps)
        self.assertEqual(
            result.continuation.resources_hash,
            canonical_hash({"v5_steps": 2, "v4_evaluation_steps": direct.evaluation_steps}),
        )

    def test_recursive_invoke_v4_bridges_exact_receipt_and_result(self) -> None:
        unit = self.recursive_unit()
        direct = run_program_ir_v4_recursive(unit.program_ir_v4)
        program = _base_program(unit)
        result = run_total_core_quantum(program, initial_total_core_checkpoint(program))

        payload = _bridge_payload(result)
        self.assertEqual(payload["run_receipt_hash"], direct.receipt_hash)
        self.assertEqual(payload["result_encoded"], {"$int": "120"})
        self.assertEqual(payload["result_hash"], direct.result_hash)
        self.assertEqual(payload["evaluation_steps"], direct.evaluation_steps)

    def test_effects_invoke_v4_binds_state_and_observation_transcript(self) -> None:
        unit = self.effects_unit()
        direct = run_program_ir_v4_effects(unit.program_ir_v4)
        program = _base_program(unit)
        result = run_total_core_quantum(program, initial_total_core_checkpoint(program))

        payload = _bridge_payload(result)
        self.assertEqual(payload["run_receipt_hash"], direct.receipt_hash)
        self.assertEqual(payload["final_state_hash"], direct.final_state_hash)
        self.assertEqual(payload["capability_transcript_hash"], direct.capability_transcript_hash)
        self.assertEqual(payload["evaluation_steps"], direct.evaluation_steps)
        self.assertEqual(payload["observation_calls"], direct.observation_calls)
        self.assertEqual(
            result.continuation.observations_hash,
            canonical_hash([direct.capability_transcript_hash]),
        )

    def test_quantum_limit_suspends_finite_loop_and_resume_is_linked(self) -> None:
        program = TotalCoreProgramV1.build(
            program_id="Loop",
            source_semantic_hash=HEX_B,
            initial_field=semantic_field((), profile="actual"),
            transformations=(),
            v4_units=(),
            proof_admissions=(),
            instructions=(TotalCoreInstructionV1.jump(0),),
            entry_pc=0,
            quantum_step_limit=3,
            authority_hash=HEX_A,
        )
        first = run_total_core_quantum(program, initial_total_core_checkpoint(program))
        self.assertEqual(first.status, "SUSPENDED")
        self.assertEqual(first.steps_used, 3)
        self.assertEqual(first.pc, 0)
        second = run_total_core_quantum(program, first.next_checkpoint)
        self.assertEqual(second.status, "SUSPENDED")
        self.assertEqual(second.epoch.epoch_index, 1)
        self.assertEqual(second.continuation.previous_continuation_hash, first.continuation.continuation_hash)

    def test_checkpoint_from_other_program_is_rejected(self) -> None:
        left = _base_program(self.pure_unit())
        right = TotalCoreProgramV1.build(
            program_id="Other",
            source_semantic_hash=HEX_C,
            initial_field=semantic_field((), profile="actual"),
            transformations=(),
            v4_units=(),
            proof_admissions=(),
            instructions=(TotalCoreInstructionV1.halt(),),
            entry_pc=0,
            quantum_step_limit=1,
            authority_hash=HEX_A,
        )
        with self.assertRaises(TevScriptError):
            run_total_core_quantum(right, initial_total_core_checkpoint(left))

    def test_invalid_checkpoint_pc_is_rejected_before_execution(self) -> None:
        program = _base_program(self.pure_unit())
        checkpoint = initial_total_core_checkpoint(program)
        forged = replace(checkpoint, pc=999)
        with self.assertRaises(TevScriptError):
            run_total_core_quantum(program, forged)

    def test_previous_continuation_mismatch_is_rejected(self) -> None:
        def loop(program_id: str, source_hash: str) -> TotalCoreProgramV1:
            return TotalCoreProgramV1.build(
                program_id=program_id,
                source_semantic_hash=source_hash,
                initial_field=semantic_field((), profile="actual"),
                transformations=(),
                v4_units=(),
                proof_admissions=(),
                instructions=(TotalCoreInstructionV1.jump(0),),
                entry_pc=0,
                quantum_step_limit=1,
                authority_hash=HEX_A,
            )

        left = loop("Left", HEX_B)
        right = loop("Right", HEX_C)
        left_first = run_total_core_quantum(left, initial_total_core_checkpoint(left))
        right_first = run_total_core_quantum(right, initial_total_core_checkpoint(right))
        forged = replace(
            left_first.next_checkpoint,
            previous_continuation=right_first.continuation,
        )
        with self.assertRaises(TevScriptError):
            run_total_core_quantum(left, forged)

    def test_child_execution_failure_is_fail_closed(self) -> None:
        unit = self.pure_unit()
        program = _base_program(unit)
        with patch(
            "tev_script.runtime_v5_total.run_program_ir_v4_pure",
            side_effect=TevScriptError("TEST_CHILD_FAILURE", "synthetic child failure"),
        ):
            with self.assertRaises(TevScriptError) as captured:
                run_total_core_quantum(program, initial_total_core_checkpoint(program))
        self.assertEqual(captured.exception.diagnostic.code, "TEST_CHILD_FAILURE")


if __name__ == "__main__":
    unittest.main()
