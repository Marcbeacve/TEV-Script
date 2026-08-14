from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v4_effect_commands import (
    EffectActionR2V4,
    EffectCommandTableV4,
    build_effect_action_r2_v4,
    build_effect_command_table_v4,
    plan_effect_action_r2_v4,
    planned_effect_transition_to_dict_v4,
)
from .ir_v4_effects import (
    CapabilityTableV4,
    EffectScenarioV4,
    StateSchemaV4,
    build_capability_table_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
)
from .ir_v4_pure import hash_type_table_v4
from .ir_v4_values import TypeTableV4, build_type_table_v4, decode_v4_value, encode_v4_value
from .program_ir_v4 import (
    _array,
    _decode_effects_state_wire,
    _descriptor_wire,
    _effects_state_wire,
    _hash,
    _integer,
    _object,
    _sha,
    _string,
)

PROGRAM_IR_V4_EFFECTS_R2_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_R2_V1"
PROGRAM_IR_V4_EFFECTS_R2_PLAN_RECEIPT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_R2_PLAN_RECEIPT_V1"


@dataclass(frozen=True, slots=True)
class ProgramIRV4EffectsR2Validation:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    state_schema_hash: str
    capability_table_hash: str
    command_table_hash: str
    action_hash: str
    scenario_hash: str
    current_state: dict[str, Any]
    arguments: tuple[Any, ...]
    table: TypeTableV4
    states: StateSchemaV4
    capabilities: CapabilityTableV4
    commands: EffectCommandTableV4
    action: EffectActionR2V4
    scenario: EffectScenarioV4


@dataclass(frozen=True, slots=True)
class ProgramIRV4EffectsR2PlanReceipt:
    schema: str
    status: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    state_schema_hash: str
    capability_table_hash: str
    command_table_hash: str
    action_hash: str
    scenario_hash: str
    planning_receipt_hash: str
    command_batch_hash: str
    proposed_final_state_hash: str
    plan_artifact_hash: str
    observation_calls: int
    evaluation_steps: int
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class ProgramIRV4EffectsR2PlanResult:
    receipt: ProgramIRV4EffectsR2PlanReceipt
    plan_artifact: dict[str, Any]


def build_program_ir_v4_effects_r2(
    *,
    program_id: str,
    source_semantic_hash: str,
    table: TypeTableV4,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    commands: EffectCommandTableV4,
    action: EffectActionR2V4,
    scenario: EffectScenarioV4,
    current_state: Mapping[str, Any],
    arguments: Sequence[Any] = (),
) -> dict[str, Any]:
    if not isinstance(program_id, str) or not program_id:
        _fail("TEVS_PROGRAM_IR_V4_R2_SOURCE", "program_id must be non-empty")
    source_hash = _sha(source_semantic_hash, "source_semantic_hash")
    if action.state_schema_hash != states.schema_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_STATE", "R2 action state schema hash mismatch")
    if action.capability_table_hash != capabilities.table_hash or scenario.capability_table_hash != capabilities.table_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_CAPABILITIES", "R2 capability table hash mismatch")
    if action.command_table_hash != commands.table_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_COMMANDS", "R2 command table hash mismatch")
    if len(arguments) != len(action.parameter_names):
        _fail("TEVS_PROGRAM_IR_V4_R2_ARGUMENTS", f"R2 action expects {len(action.parameter_names)} arguments, got {len(arguments)}")

    type_table = {
        "boundary": {"maximum_value_nesting": table.maximum_value_nesting},
        "types": [_descriptor_wire(item) for item in sorted(table.descriptors, key=lambda item: item.type_id)],
    }
    state_wire = [
        {"name": slot.name, "type": slot.type_id, "initial": slot.initial_encoded}
        for slot in states.slots
    ]
    capability_wire = [
        {
            "capability_id": contract.capability_id,
            "parameters": list(contract.parameter_type_ids),
            "return_type": contract.return_type_id,
            "kind": contract.kind,
            "contract_hash": contract.contract_hash,
        }
        for contract in capabilities.contracts
    ]
    command_wire = [
        {
            "command_id": contract.command_id,
            "parameters": list(contract.parameter_type_ids),
            "kind": contract.kind,
            "idempotency_policy": contract.idempotency_policy,
            "contract_hash": contract.contract_hash,
        }
        for contract in commands.contracts
    ]
    action_wire = {
        "action_id": action.action_id,
        "parameters": [
            {"name": name, "type": type_id}
            for name, type_id in zip(action.parameter_names, action.parameter_type_ids, strict=True)
        ],
        "steps": [_r2_step_wire(step) for step in action.steps],
        "static_step_upper_bound": action.static_step_upper_bound,
        "observation_call_upper_bound": action.observation_call_upper_bound,
        "command_request_upper_bound": action.command_request_upper_bound,
        "action_hash": action.action_hash,
    }
    scenario_wire = {
        "capability_table_hash": capabilities.table_hash,
        "capabilities": [
            {
                "capability_id": lane.capability_id,
                "contract_hash": lane.contract_hash,
                "calls": [
                    {"arguments": list(call.argument_encodings), "return": call.return_encoded}
                    for call in lane.calls
                ],
            }
            for lane in scenario.lanes
        ],
        "scenario_hash": scenario.scenario_hash,
    }
    argument_wire = []
    for name, type_id, value in zip(action.parameter_names, action.parameter_type_ids, arguments, strict=True):
        encoded = encode_v4_value(type_id, value, table, context=f"R2 program IR argument {name}")
        decoded = decode_v4_value(type_id, encoded, table, context=f"R2 program IR argument {name}")
        argument_wire.append({"name": name, "type": type_id, "value": encode_v4_value(type_id, decoded, table, context=f"R2 program IR argument {name}")})

    payload: dict[str, Any] = {
        "schema": PROGRAM_IR_V4_EFFECTS_R2_SCHEMA,
        "source": {"program_id": program_id, "language_version": "2.0.0", "semantic_hash": source_hash},
        "profile": "effects_r2_plan",
        "type_table": type_table,
        "type_table_hash": hash_type_table_v4(table),
        "state_schema": {"states": state_wire, "schema_hash": states.schema_hash, "initial_state_hash": states.initial_state_hash},
        "capabilities": {"contracts": capability_wire, "table_hash": capabilities.table_hash},
        "commands": {"contracts": command_wire, "table_hash": commands.table_hash},
        "action": action_wire,
        "scenario": scenario_wire,
        "execution": {"current_state": _effects_state_wire(states, current_state, table), "arguments": argument_wire},
    }
    payload["program_ir_hash"] = _hash(payload)
    validate_program_ir_v4_effects_r2(payload)
    return payload


def validate_program_ir_v4_effects_r2(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4EffectsR2Validation:
    root = _object(raw, "$")
    expected_root = {
        "schema", "source", "profile", "type_table", "type_table_hash", "state_schema",
        "capabilities", "commands", "action", "scenario", "execution", "program_ir_hash",
    }
    if set(root) != expected_root:
        _fail("TEVS_PROGRAM_IR_V4_R2_SHAPE", f"R2 root field set mismatch: {sorted(set(root) ^ expected_root)}")
    if root["schema"] != PROGRAM_IR_V4_EFFECTS_R2_SCHEMA or root["profile"] != "effects_r2_plan":
        _fail("TEVS_PROGRAM_IR_V4_R2_PROFILE", "expected Program IR V4 Effects R2 plan profile")

    source = _object(root["source"], "$.source")
    if set(source) != {"program_id", "language_version", "semantic_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_SOURCE", "R2 source field set mismatch")
    _string(source["program_id"], "$.source.program_id")
    if _string(source["language_version"], "$.source.language_version") != "2.0.0":
        _fail("TEVS_PROGRAM_IR_V4_R2_SOURCE", "R2 source version must be 2.0.0")
    source_hash = _sha(source["semantic_hash"], "$.source.semantic_hash")

    type_table_raw = _object(root["type_table"], "$.type_table")
    if set(type_table_raw) != {"boundary", "types"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_TYPE_TABLE", "R2 type table field set mismatch")
    table = build_type_table_v4(type_table_raw)
    type_hash = hash_type_table_v4(table)
    if _sha(root["type_table_hash"], "$.type_table_hash") != type_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_TYPE_TABLE_HASH", "R2 type table hash mismatch")

    state_raw = _object(root["state_schema"], "$.state_schema")
    if set(state_raw) != {"states", "schema_hash", "initial_state_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_STATE", "R2 state schema field set mismatch")
    states = build_state_schema_v4(_array(state_raw["states"], "$.state_schema.states"), table)
    if _sha(state_raw["schema_hash"], "$.state_schema.schema_hash") != states.schema_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_STATE_HASH", "R2 state schema hash mismatch")
    if _sha(state_raw["initial_state_hash"], "$.state_schema.initial_state_hash") != states.initial_state_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_INITIAL_STATE_HASH", "R2 initial state hash mismatch")

    capabilities_raw = _object(root["capabilities"], "$.capabilities")
    if set(capabilities_raw) != {"contracts", "table_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_CAPABILITIES", "R2 capability table field set mismatch")
    raw_capability_contracts = _array(capabilities_raw["contracts"], "$.capabilities.contracts")
    rebuilt_caps = []
    cap_hashes = []
    for index, raw_contract in enumerate(raw_capability_contracts):
        item = _object(raw_contract, f"$.capabilities.contracts[{index}]")
        if set(item) != {"capability_id", "parameters", "return_type", "kind", "contract_hash"}:
            _fail("TEVS_PROGRAM_IR_V4_R2_CAPABILITIES", "R2 capability contract field set mismatch")
        rebuilt_caps.append({"capability_id": item["capability_id"], "parameters": item["parameters"], "return_type": item["return_type"], "kind": item["kind"]})
        cap_hashes.append(_sha(item["contract_hash"], "R2 capability contract hash"))
    capabilities = build_capability_table_v4(rebuilt_caps, table)
    if _sha(capabilities_raw["table_hash"], "$.capabilities.table_hash") != capabilities.table_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_CAPABILITY_TABLE_HASH", "R2 capability table hash mismatch")
    if tuple(cap_hashes) != tuple(contract.contract_hash for contract in capabilities.contracts):
        _fail("TEVS_PROGRAM_IR_V4_R2_CAPABILITY_CONTRACT_HASH", "R2 capability contract hash mismatch")

    commands_raw = _object(root["commands"], "$.commands")
    if set(commands_raw) != {"contracts", "table_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_COMMANDS", "R2 command table field set mismatch")
    raw_command_contracts = _array(commands_raw["contracts"], "$.commands.contracts")
    rebuilt_commands = []
    command_hashes = []
    for index, raw_contract in enumerate(raw_command_contracts):
        item = _object(raw_contract, f"$.commands.contracts[{index}]")
        if set(item) != {"command_id", "parameters", "kind", "idempotency_policy", "contract_hash"}:
            _fail("TEVS_PROGRAM_IR_V4_R2_COMMANDS", "R2 command contract field set mismatch")
        rebuilt_commands.append({
            "command_id": item["command_id"], "parameters": item["parameters"],
            "kind": item["kind"], "idempotency_policy": item["idempotency_policy"],
        })
        command_hashes.append(_sha(item["contract_hash"], "R2 command contract hash"))
    commands = build_effect_command_table_v4(rebuilt_commands, table)
    if _sha(commands_raw["table_hash"], "$.commands.table_hash") != commands.table_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_COMMAND_TABLE_HASH", "R2 command table hash mismatch")
    if tuple(command_hashes) != tuple(contract.contract_hash for contract in commands.contracts):
        _fail("TEVS_PROGRAM_IR_V4_R2_COMMAND_CONTRACT_HASH", "R2 command contract hash mismatch")

    action_raw = _object(root["action"], "$.action")
    expected_action = {
        "action_id", "parameters", "steps", "static_step_upper_bound", "observation_call_upper_bound",
        "command_request_upper_bound", "action_hash",
    }
    if set(action_raw) != expected_action:
        _fail("TEVS_PROGRAM_IR_V4_R2_ACTION", "R2 action field set mismatch")
    action = build_effect_action_r2_v4(
        {"action_id": action_raw["action_id"], "parameters": action_raw["parameters"], "steps": action_raw["steps"]},
        table, states, capabilities, commands,
    )
    if _integer(action_raw["static_step_upper_bound"], "$.action.static_step_upper_bound", 1, 1_000_000) != action.static_step_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_R2_ACTION_BOUND", "R2 static step bound mismatch")
    for field, actual, maximum in (
        ("observation_call_upper_bound", action.observation_call_upper_bound, 8192),
        ("command_request_upper_bound", action.command_request_upper_bound, 4096),
    ):
        value = action_raw[field]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum or value != actual:
            _fail("TEVS_PROGRAM_IR_V4_R2_ACTION_BOUND", f"R2 {field} mismatch")
    if _sha(action_raw["action_hash"], "$.action.action_hash") != action.action_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_ACTION_HASH", "R2 action hash mismatch")

    scenario_raw = _object(root["scenario"], "$.scenario")
    if set(scenario_raw) != {"capability_table_hash", "capabilities", "scenario_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_SCENARIO", "R2 scenario field set mismatch")
    scenario = build_effect_scenario_v4(
        {"capability_table_hash": scenario_raw["capability_table_hash"], "capabilities": scenario_raw["capabilities"]},
        table, capabilities,
    )
    if _sha(scenario_raw["scenario_hash"], "$.scenario.scenario_hash") != scenario.scenario_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_SCENARIO_HASH", "R2 scenario hash mismatch")

    execution = _object(root["execution"], "$.execution")
    if set(execution) != {"current_state", "arguments"}:
        _fail("TEVS_PROGRAM_IR_V4_R2_EXECUTION", "R2 execution field set mismatch")
    current_state = _decode_effects_state_wire(states, _array(execution["current_state"], "$.execution.current_state"), table)
    raw_arguments = _array(execution["arguments"], "$.execution.arguments")
    if len(raw_arguments) != len(action.parameter_names):
        _fail("TEVS_PROGRAM_IR_V4_R2_ARGUMENTS", "R2 argument count mismatch")
    arguments: list[Any] = []
    for index, (raw_argument, name, type_id) in enumerate(zip(raw_arguments, action.parameter_names, action.parameter_type_ids, strict=True)):
        item = _object(raw_argument, f"$.execution.arguments[{index}]")
        if set(item) != {"name", "type", "value"} or item["name"] != name or item["type"] != type_id:
            _fail("TEVS_PROGRAM_IR_V4_R2_ARGUMENTS", f"R2 argument {index} signature mismatch")
        value = decode_v4_value(type_id, item["value"], table, context=f"R2 program IR argument {name}")
        if encode_v4_value(type_id, value, table, context=f"R2 program IR argument {name}") != item["value"]:
            _fail("TEVS_PROGRAM_IR_V4_R2_ARGUMENT_CANONICAL", f"R2 argument {name!r} is noncanonical")
        arguments.append(value)

    declared_hash = _sha(root["program_ir_hash"], "$.program_ir_hash")
    payload = dict(root); payload.pop("program_ir_hash")
    computed_hash = _hash(payload)
    if declared_hash != computed_hash:
        _fail("TEVS_PROGRAM_IR_V4_R2_HASH", "R2 Program IR hash mismatch")
    if expected_program_ir_hash is not None and computed_hash != _sha(expected_program_ir_hash, "expected_program_ir_hash"):
        _fail("TEVS_PROGRAM_IR_V4_R2_EXPECTED_HASH", "R2 Program IR does not match external hash pin")
    if expected_source_semantic_hash is not None and source_hash != _sha(expected_source_semantic_hash, "expected_source_semantic_hash"):
        _fail("TEVS_PROGRAM_IR_V4_R2_EXPECTED_SOURCE", "R2 source semantic hash does not match external pin")

    return ProgramIRV4EffectsR2Validation(
        PROGRAM_IR_V4_EFFECTS_R2_SCHEMA, computed_hash, source_hash, type_hash,
        states.schema_hash, capabilities.table_hash, commands.table_hash, action.action_hash, scenario.scenario_hash,
        current_state, tuple(arguments), table, states, capabilities, commands, action, scenario,
    )


def plan_program_ir_v4_effects_r2(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4EffectsR2PlanResult:
    validation = validate_program_ir_v4_effects_r2(
        raw,
        expected_program_ir_hash=expected_program_ir_hash,
        expected_source_semantic_hash=expected_source_semantic_hash,
    )
    planned = plan_effect_action_r2_v4(
        validation.action, validation.table, validation.states, validation.capabilities,
        validation.commands, validation.scenario, validation.current_state, validation.arguments,
    )
    artifact = planned_effect_transition_to_dict_v4(planned)
    plan_artifact_hash = artifact["artifact_hash"]
    payload = {
        "schema": PROGRAM_IR_V4_EFFECTS_R2_PLAN_RECEIPT_SCHEMA,
        "status": "PLANNED_NOT_FINALIZED",
        "program_ir_hash": validation.program_ir_hash,
        "source_semantic_hash": validation.source_semantic_hash,
        "type_table_hash": validation.type_table_hash,
        "state_schema_hash": validation.state_schema_hash,
        "capability_table_hash": validation.capability_table_hash,
        "command_table_hash": validation.command_table_hash,
        "action_hash": validation.action_hash,
        "scenario_hash": validation.scenario_hash,
        "planning_receipt_hash": planned.planning_receipt_hash,
        "command_batch_hash": planned.command_batch.batch_hash,
        "proposed_final_state_hash": planned.proposed_final_state_hash,
        "plan_artifact_hash": plan_artifact_hash,
        "observation_calls": planned.observation_calls,
        "evaluation_steps": planned.evaluation_steps,
    }
    receipt = ProgramIRV4EffectsR2PlanReceipt(
        payload["schema"], payload["status"], validation.program_ir_hash, validation.source_semantic_hash,
        validation.type_table_hash, validation.state_schema_hash, validation.capability_table_hash,
        validation.command_table_hash, validation.action_hash, validation.scenario_hash,
        planned.planning_receipt_hash, planned.command_batch.batch_hash, planned.proposed_final_state_hash,
        plan_artifact_hash, planned.observation_calls, planned.evaluation_steps, _hash(payload),
    )
    return ProgramIRV4EffectsR2PlanResult(receipt, artifact)


def canonical_program_ir_v4_effects_r2_bytes(raw: Mapping[str, Any]) -> bytes:
    validate_program_ir_v4_effects_r2(raw)
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _r2_step_wire(step: Mapping[str, Any]) -> dict[str, Any]:
    op = step["op"]
    if op == "OBSERVE":
        return {"op": "OBSERVE", "capability_id": step["capability_id"], "arguments": step["arguments"], "bind": step["bind"]}
    if op == "OBSERVE_ALL":
        return {
            "op": "OBSERVE_ALL",
            "reservation_policy": step["reservation_policy"],
            "observations": [
                {"bind": item["bind"], "capability_id": item["capability_id"], "arguments": item["arguments"]}
                for item in step["observations"]
            ],
        }
    if op == "LET_LOCAL":
        return {"op": "LET_LOCAL", "name": step["name"], "type": step["type"], "value": step["value"]}
    if op == "SET_STATE":
        return {"op": "SET_STATE", "state": step["state"], "value": step["value"]}
    if op == "ASSERT":
        return {"op": "ASSERT", "condition": step["condition"]}
    if op == "REQUEST_EFFECT":
        return {"op": "REQUEST_EFFECT", "command_id": step["command_id"], "arguments": step["arguments"]}
    _fail("TEVS_PROGRAM_IR_V4_R2_ACTION", f"unsupported normalized R2 op {op!r}")


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
