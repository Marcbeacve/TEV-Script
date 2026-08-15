from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effect_commands import (
    build_effect_action_r2_v4,
    build_effect_command_table_v4,
)
from tev_script.ir_v4_effects import (
    build_capability_table_v4,
    build_effect_action_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
)
from tev_script.ir_v4_values import build_type_table_v4
from tev_script.omega_kernel_v1 import omega_hash, resource_exact, resource_vector
from tev_script.omega_v2_adapter_v1 import (
    omega_epoch_from_v2,
    project_program_ir_v4,
    project_run_receipt_v4,
)
from tev_script.program_ir_v4 import (
    build_program_ir_v4_effects,
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
    run_program_ir_v4_effects,
    run_program_ir_v4_pure,
    run_program_ir_v4_recursive,
)
from tev_script.program_ir_v4_effect_commands import (
    build_program_ir_v4_effects_r2,
    plan_program_ir_v4_effects_r2,
)
from tev_script.source_program_v2 import compile_program_v2


def _base_table():
    return build_type_table_v4(
        {
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
        }
    )


def _cint(value: int) -> dict:
    return {"op": "CONST", "type": "Int", "value": {"$int": str(value)}}


def _load_state(name: str) -> dict:
    return {"op": "LOAD_STATE", "name": name, "type": "Int"}


def _load_param(name: str) -> dict:
    return {"op": "LOAD_PARAM", "name": name, "type": "Int"}


def _load_local(name: str) -> dict:
    return {"op": "LOAD_LOCAL", "name": name, "type": "Int"}


def _plus(left: dict, right: dict) -> dict:
    return {
        "op": "BINARY",
        "operator": "PLUS",
        "left_type": "Int",
        "right_type": "Int",
        "result_type": "Int",
        "left": left,
        "right": right,
    }


def _effects_r1_ir():
    table = _base_table()
    states = build_state_schema_v4(
        [
            {"name": "count", "type": "Int", "initial": {"$int": "0"}},
            {"name": "last", "type": "Int", "initial": {"$int": "0"}},
        ],
        table,
    )
    capabilities = build_capability_table_v4(
        [
            {
                "capability_id": "sensor.read",
                "parameters": ["Int"],
                "return_type": "Int",
                "kind": "observation",
            }
        ],
        table,
    )
    contract = capabilities.require("sensor.read")
    action = build_effect_action_v4(
        {
            "action_id": "tick",
            "parameters": [{"name": "bias", "type": "Int"}],
            "steps": [
                {
                    "op": "OBSERVE",
                    "capability_id": "sensor.read",
                    "arguments": [_load_state("count")],
                    "bind": "sample",
                },
                {"op": "SET_STATE", "state": "last", "value": _load_local("sample")},
                {
                    "op": "SET_STATE",
                    "state": "count",
                    "value": _plus(_load_local("sample"), _load_param("bias")),
                },
            ],
        },
        table,
        states,
        capabilities,
    )
    scenario = build_effect_scenario_v4(
        {
            "capability_table_hash": capabilities.table_hash,
            "capabilities": [
                {
                    "capability_id": "sensor.read",
                    "contract_hash": contract.contract_hash,
                    "calls": [
                        {"arguments": [{"$int": "2"}], "return": {"$int": "10"}}
                    ],
                }
            ],
        },
        table,
        capabilities,
    )
    return build_program_ir_v4_effects(
        program_id="EffectsR1",
        source_semantic_hash="1" * 64,
        table=table,
        states=states,
        capabilities=capabilities,
        action=action,
        scenario=scenario,
        current_state={"count": 2, "last": 0},
        arguments=[3],
    )


def _effects_r2_ir():
    table = _base_table()
    states = build_state_schema_v4(
        [{"name": "count", "type": "Int", "initial": {"$int": "0"}}],
        table,
    )
    capabilities = build_capability_table_v4([], table)
    scenario = build_effect_scenario_v4(
        {"capability_table_hash": capabilities.table_hash, "capabilities": []},
        table,
        capabilities,
    )
    commands = build_effect_command_table_v4(
        [
            {
                "command_id": "file.write",
                "parameters": ["Int"],
                "kind": "effect_command",
                "idempotency_policy": "content_addressed_v1",
            }
        ],
        table,
    )
    action = build_effect_action_r2_v4(
        {
            "action_id": "save",
            "parameters": [{"name": "bias", "type": "Int"}],
            "steps": [
                {
                    "op": "SET_STATE",
                    "state": "count",
                    "value": _plus(_load_state("count"), _load_param("bias")),
                },
                {
                    "op": "REQUEST_EFFECT",
                    "command_id": "file.write",
                    "arguments": [_load_state("count")],
                },
            ],
        },
        table,
        states,
        capabilities,
        commands,
    )
    return build_program_ir_v4_effects_r2(
        program_id="EffectsR2",
        source_semantic_hash="2" * 64,
        table=table,
        states=states,
        capabilities=capabilities,
        commands=commands,
        action=action,
        scenario=scenario,
        current_state={"count": 2},
        arguments=[3],
    )


class OmegaV2AdapterTests(unittest.TestCase):
    PURE = (
        'script Demo version "2.0.0"; '
        'fn f(x:Int)->Int=x+1; '
        'entry main:Int=f(4);'
    )
    RECURSIVE = '''
    script Demo version "2.0.0";
    recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
    entry main:Int=factorial(5);
    '''

    def test_pure_ir_projection_binds_existing_v2_hashes(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.PURE))
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.source_semantic_hash, ir["source"]["semantic_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-pure")

    def test_recursive_ir_projection_uses_recursive_profile(self) -> None:
        ir = export_program_ir_v4_recursive(compile_program_v2(self.RECURSIVE))
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-recursive")

    def test_effects_r1_projection_uses_effects_profile(self) -> None:
        ir = _effects_r1_ir()
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-effects-r1")

    def test_effects_r2_projection_uses_r2_validator_and_profile(self) -> None:
        ir = _effects_r2_ir()
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.source_semantic_hash, ir["source"]["semantic_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-effects-r2")

    def test_tampered_ir_is_rejected_before_projection(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.PURE))
        tampered = copy.deepcopy(ir)
        tampered["program_ir_hash"] = "0" * 64
        with self.assertRaises(TevScriptError):
            project_program_ir_v4(tampered)

    def test_pure_run_projection_uses_explicit_absence_hashes(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.PURE))
        receipt = run_program_ir_v4_pure(ir)
        projected = project_run_receipt_v4(ir, receipt)
        self.assertEqual(projected["program_ir_hash"], ir["program_ir_hash"])
        self.assertEqual(projected["result_hash"], receipt.result_hash)
        self.assertEqual(
            projected["state_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "state"}),
        )
        self.assertEqual(
            projected["observation_transcript_hash"],
            omega_hash(
                {"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "observation_transcript"}
            ),
        )
        self.assertEqual(
            projected["effect_receipt_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "effect_receipt"}),
        )

    def test_effects_r1_run_projection_preserves_real_causal_hashes(self) -> None:
        ir = _effects_r1_ir()
        receipt = run_program_ir_v4_effects(ir)
        projected = project_run_receipt_v4(ir, receipt)
        self.assertEqual(projected["state_hash"], receipt.final_state_hash)
        self.assertEqual(
            projected["observation_transcript_hash"],
            receipt.capability_transcript_hash,
        )
        self.assertEqual(projected["effect_receipt_hash"], receipt.transition_receipt_hash)

    def test_effects_r2_plan_projection_preserves_planning_evidence(self) -> None:
        ir = _effects_r2_ir()
        result = plan_program_ir_v4_effects_r2(ir)
        projected = project_run_receipt_v4(ir, result)
        self.assertEqual(projected["state_hash"], result.receipt.proposed_final_state_hash)
        self.assertEqual(projected["effect_receipt_hash"], result.receipt.planning_receipt_hash)
        self.assertEqual(projected["program_ir_hash"], ir["program_ir_hash"])

    def test_pure_v2_run_can_be_wrapped_as_epoch_and_continuation(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.PURE))
        receipt = run_program_ir_v4_pure(ir)
        resources = resource_vector(cpu=resource_exact(receipt.evaluation_steps))
        epoch, continuation = omega_epoch_from_v2(
            ir,
            receipt,
            epoch_index=0,
            input_state_hash="a" * 64,
            authority_hash="b" * 64,
            previous_continuation_hash=None,
            resources=resources,
        )
        self.assertEqual(epoch.computation_hash, project_program_ir_v4(ir).identity_hash)
        self.assertEqual(continuation.result_hash, receipt.result_hash)
        self.assertEqual(continuation.resources_hash, resources.vector_hash)
        self.assertEqual(continuation.epoch_hash, epoch.epoch_hash)


if __name__ == "__main__":
    unittest.main()
