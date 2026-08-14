from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v4_pure import PureBindingV4, canonical_expression_v4, evaluate_pure_v4, validate_pure_v4
from .ir_v4_values import TypeTableV4, decode_v4_value, encode_v4_value

MAX_EFFECT_STATES_V4 = 256
MAX_EFFECT_CAPABILITIES_V4 = 8192
MAX_EFFECT_ACTION_STEPS_V4 = 4096
MAX_EFFECT_PARAMETERS_V4 = 64
MAX_EFFECT_LOCALS_V4 = 4096
MAX_EFFECT_STATIC_STEPS_V4 = 1_000_000
MAX_SCRIPTED_CALLS_V4 = 8192
MAX_EFFECT_OBSERVE_ALL_V4 = 64
OBSERVE_ALL_RESERVATION_POLICY_V4 = "canonical_bind_then_capability_ordinal_v1"
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CAPABILITY_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


@dataclass(frozen=True, slots=True)
class StateSlotV4:
    name: str
    type_id: str
    initial_value: Any
    initial_encoded: Any


@dataclass(frozen=True, slots=True)
class StateSchemaV4:
    slots: tuple[StateSlotV4, ...]
    schema_hash: str
    initial_state_hash: str


@dataclass(frozen=True, slots=True)
class CapabilityContractV4:
    capability_id: str
    parameter_type_ids: tuple[str, ...]
    return_type_id: str
    kind: str
    contract_hash: str


@dataclass(frozen=True, slots=True)
class CapabilityTableV4:
    contracts: tuple[CapabilityContractV4, ...]
    table_hash: str

    def require(self, capability_id: str) -> CapabilityContractV4:
        for contract in self.contracts:
            if contract.capability_id == capability_id:
                return contract
        _fail("TEVS_IR_V4_EFFECT_CAPABILITY_UNKNOWN", f"undeclared capability {capability_id!r}")


@dataclass(frozen=True, slots=True)
class EffectActionV4:
    action_id: str
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    steps: tuple[dict[str, Any], ...]
    state_schema_hash: str
    capability_table_hash: str
    static_step_upper_bound: int
    observation_call_upper_bound: int
    action_hash: str


@dataclass(frozen=True, slots=True)
class ScriptedCapabilityCallV4:
    argument_values: tuple[Any, ...]
    argument_encodings: tuple[Any, ...]
    return_value: Any
    return_encoded: Any


@dataclass(frozen=True, slots=True)
class ScriptedCapabilityLaneV4:
    capability_id: str
    contract_hash: str
    calls: tuple[ScriptedCapabilityCallV4, ...]


@dataclass(frozen=True, slots=True)
class EffectScenarioV4:
    lanes: tuple[ScriptedCapabilityLaneV4, ...]
    capability_table_hash: str
    scenario_hash: str


@dataclass(frozen=True, slots=True)
class EffectTransitionReceiptV4:
    schema: str
    action_hash: str
    state_schema_hash: str
    capability_table_hash: str
    scenario_hash: str
    initial_state_hash: str
    arguments_hash: str
    capability_transcript: tuple[dict[str, Any], ...]
    capability_transcript_hash: str
    final_state: tuple[dict[str, Any], ...]
    final_state_hash: str
    evaluation_steps: int
    observation_calls: int
    receipt_hash: str


def build_state_schema_v4(raw_states: Sequence[Mapping[str, Any]], table: TypeTableV4) -> StateSchemaV4:
    if not isinstance(raw_states, Sequence) or isinstance(raw_states, (str, bytes, bytearray)):
        _fail("TEVS_IR_V4_EFFECT_STATE_SCHEMA", "states must be a sequence")
    if len(raw_states) > MAX_EFFECT_STATES_V4:
        _fail("TEVS_IR_V4_EFFECT_STATE_SCHEMA", f"states exceed {MAX_EFFECT_STATES_V4}")
    slots: list[StateSlotV4] = []
    previous: str | None = None
    for index, raw in enumerate(raw_states):
        item = _object(raw, f"states[{index}]")
        _exact(item, {"name", "type", "initial"}, f"states[{index}]")
        name = _local_name(item["name"], f"states[{index}].name")
        if previous is not None and name <= previous:
            _fail("TEVS_IR_V4_EFFECT_STATE_ORDER", "state declarations must be strictly sorted by name")
        previous = name
        type_id = _storable_type(table, item["type"], f"states[{index}].type")
        value = decode_v4_value(type_id, item["initial"], table, context=f"state {name} initial")
        encoded = encode_v4_value(type_id, value, table, context=f"state {name} initial")
        if encoded != item["initial"]:
            _fail("TEVS_IR_V4_EFFECT_STATE_CANONICAL", f"initial state {name!r} is not canonically encoded")
        slots.append(StateSlotV4(name, type_id, value, encoded))
    schema_payload = {
        "schema": "TEV_SCRIPT_IR_V4_STATE_SCHEMA_V1",
        "states": [{"name": slot.name, "type": slot.type_id} for slot in slots],
    }
    initial_wire = tuple({"name": slot.name, "type": slot.type_id, "value": slot.initial_encoded} for slot in slots)
    return StateSchemaV4(tuple(slots), _hash(schema_payload), _hash({"schema":"TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1","states":initial_wire}))


def initial_state_v4(schema: StateSchemaV4) -> dict[str, Any]:
    return {slot.name: slot.initial_value for slot in schema.slots}


def build_capability_table_v4(raw_capabilities: Sequence[Mapping[str, Any]], table: TypeTableV4) -> CapabilityTableV4:
    if not isinstance(raw_capabilities, Sequence) or isinstance(raw_capabilities, (str, bytes, bytearray)):
        _fail("TEVS_IR_V4_EFFECT_CAPABILITIES", "capabilities must be a sequence")
    if len(raw_capabilities) > MAX_EFFECT_CAPABILITIES_V4:
        _fail("TEVS_IR_V4_EFFECT_CAPABILITIES", f"capabilities exceed {MAX_EFFECT_CAPABILITIES_V4}")
    contracts: list[CapabilityContractV4] = []
    previous: str | None = None
    for index, raw in enumerate(raw_capabilities):
        item = _object(raw, f"capabilities[{index}]")
        _exact(item, {"capability_id", "parameters", "return_type", "kind"}, f"capabilities[{index}]")
        capability_id = _capability_id(item["capability_id"], f"capabilities[{index}].capability_id")
        if previous is not None and capability_id <= previous:
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_ORDER", "capabilities must be strictly sorted by id")
        previous = capability_id
        params_raw = item["parameters"]
        if not isinstance(params_raw, list) or len(params_raw) > MAX_EFFECT_PARAMETERS_V4:
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_SIGNATURE", "capability parameters must be an array of at most 64 types")
        parameter_types = tuple(_storable_type(table, value, f"capability {capability_id} parameter") for value in params_raw)
        return_type = _storable_type(table, item["return_type"], f"capability {capability_id} return")
        kind = item["kind"]
        if kind != "observation":
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_KIND", "Effects V4 R1 admits observation capabilities only")
        payload = {
            "schema": "TEV_SCRIPT_IR_V4_CAPABILITY_CONTRACT_V1",
            "capability_id": capability_id,
            "parameters": list(parameter_types),
            "return_type": return_type,
            "kind": kind,
        }
        contracts.append(CapabilityContractV4(capability_id, parameter_types, return_type, kind, _hash(payload)))
    table_payload = {
        "schema": "TEV_SCRIPT_IR_V4_CAPABILITY_TABLE_V1",
        "contracts": [
            {
                "capability_id": c.capability_id,
                "parameters": list(c.parameter_type_ids),
                "return_type": c.return_type_id,
                "kind": c.kind,
                "contract_hash": c.contract_hash,
            }
            for c in contracts
        ],
    }
    return CapabilityTableV4(tuple(contracts), _hash(table_payload))


def build_effect_action_v4(
    raw: Mapping[str, Any],
    table: TypeTableV4,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
) -> EffectActionV4:
    item = _object(raw, "action")
    _exact(item, {"action_id", "parameters", "steps"}, "action")
    action_id = _local_name(item["action_id"], "action.action_id")
    raw_parameters = item["parameters"]
    if not isinstance(raw_parameters, list) or len(raw_parameters) > MAX_EFFECT_PARAMETERS_V4:
        _fail("TEVS_IR_V4_EFFECT_ACTION_PARAMETERS", "action parameters must be an array of at most 64 entries")
    state_names = {slot.name for slot in states.slots}
    parameter_names: list[str] = []
    parameter_types: list[str] = []
    for index, raw_parameter in enumerate(raw_parameters):
        parameter = _object(raw_parameter, f"action.parameters[{index}]")
        _exact(parameter, {"name", "type"}, f"action.parameters[{index}]")
        name = _local_name(parameter["name"], f"action.parameters[{index}].name")
        if name in state_names or name in parameter_names:
            _fail("TEVS_IR_V4_EFFECT_ACTION_PARAMETERS", f"duplicate/state-shadowing parameter {name!r}")
        parameter_names.append(name)
        parameter_types.append(_storable_type(table, parameter["type"], f"action parameter {name}"))

    raw_steps = item["steps"]
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_EFFECT_ACTION_STEPS_V4:
        _fail("TEVS_IR_V4_EFFECT_ACTION_STEPS", f"action requires 1..{MAX_EFFECT_ACTION_STEPS_V4} steps")
    locals_: dict[str, str] = {}
    normalized_steps: list[dict[str, Any]] = []
    static_bound = 0
    observation_calls = 0
    for index, raw_step in enumerate(raw_steps):
        path = f"action.steps[{index}]"
        step = _object(raw_step, path)
        op = step.get("op")
        environment = _effect_environment(states, parameter_names, parameter_types, locals_)
        if op == "OBSERVE":
            _exact(step, {"op", "capability_id", "arguments", "bind"}, path)
            capability_id = _capability_id(step["capability_id"], path + ".capability_id")
            contract = capabilities.require(capability_id)
            bind = _local_name(step["bind"], path + ".bind")
            if bind in state_names or bind in parameter_names or bind in locals_:
                _fail("TEVS_IR_V4_EFFECT_LOCAL", f"duplicate/shadowing local {bind!r}")
            arguments = step["arguments"]
            if not isinstance(arguments, list) or len(arguments) != len(contract.parameter_type_ids):
                _fail("TEVS_IR_V4_EFFECT_CAPABILITY_ARITY", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
            canonical_args: list[dict[str, Any]] = []
            for position, (expr, expected_type) in enumerate(zip(arguments, contract.parameter_type_ids, strict=True)):
                canonical, validation = _validate_effect_expression(expr, expected_type, table, environment, path=f"{path}.arguments[{position}]")
                canonical_args.append(canonical)
                static_bound += validation.static_step_upper_bound
            normalized_steps.append({
                "op":"OBSERVE", "capability_id":capability_id, "contract_hash":contract.contract_hash,
                "arguments":canonical_args, "bind":bind, "return_type":contract.return_type_id,
            })
            locals_[bind] = contract.return_type_id
            observation_calls += 1
            static_bound += 1
        elif op == "OBSERVE_ALL":
            _exact(step, {"op", "reservation_policy", "observations"}, path)
            if step["reservation_policy"] != OBSERVE_ALL_RESERVATION_POLICY_V4:
                _fail("TEVS_IR_V4_EFFECT_OBSERVE_ALL_POLICY", "OBSERVE_ALL reservation policy mismatch")
            raw_observations = step["observations"]
            if not isinstance(raw_observations, list) or not 1 <= len(raw_observations) <= MAX_EFFECT_OBSERVE_ALL_V4:
                _fail("TEVS_IR_V4_EFFECT_OBSERVE_ALL_BOUND", f"OBSERVE_ALL requires 1..{MAX_EFFECT_OBSERVE_ALL_V4} observations")
            canonical_observations: list[dict[str, Any]] = []
            pending_binds: dict[str, str] = {}
            for observation_index, raw_observation in enumerate(raw_observations):
                observation_path = f"{path}.observations[{observation_index}]"
                observation = _object(raw_observation, observation_path)
                _exact(observation, {"bind", "capability_id", "arguments"}, observation_path)
                bind = _local_name(observation["bind"], observation_path + ".bind")
                if bind in state_names or bind in parameter_names or bind in locals_ or bind in pending_binds:
                    _fail("TEVS_IR_V4_EFFECT_LOCAL", f"duplicate/shadowing OBSERVE_ALL local {bind!r}")
                capability_id = _capability_id(observation["capability_id"], observation_path + ".capability_id")
                contract = capabilities.require(capability_id)
                arguments = observation["arguments"]
                if not isinstance(arguments, list) or len(arguments) != len(contract.parameter_type_ids):
                    _fail("TEVS_IR_V4_EFFECT_CAPABILITY_ARITY", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
                canonical_args: list[dict[str, Any]] = []
                for position, (expr, expected_type) in enumerate(zip(arguments, contract.parameter_type_ids, strict=True)):
                    canonical, validation = _validate_effect_expression(
                        expr, expected_type, table, environment, path=f"{observation_path}.arguments[{position}]"
                    )
                    canonical_args.append(canonical)
                    static_bound += validation.static_step_upper_bound
                canonical_observations.append({
                    "bind": bind,
                    "capability_id": capability_id,
                    "contract_hash": contract.contract_hash,
                    "return_type": contract.return_type_id,
                    "arguments": canonical_args,
                })
                pending_binds[bind] = contract.return_type_id
                observation_calls += 1
                static_bound += 1
            canonical_observations.sort(key=lambda item: item["bind"])
            normalized_steps.append({
                "op": "OBSERVE_ALL",
                "reservation_policy": OBSERVE_ALL_RESERVATION_POLICY_V4,
                "observations": canonical_observations,
            })
            locals_.update(pending_binds)
        elif op == "LET_LOCAL":
            _exact(step, {"op", "name", "type", "value"}, path)
            name = _local_name(step["name"], path + ".name")
            if name in state_names or name in parameter_names or name in locals_:
                _fail("TEVS_IR_V4_EFFECT_LOCAL", f"duplicate/shadowing local {name!r}")
            if len(locals_) >= MAX_EFFECT_LOCALS_V4:
                _fail("TEVS_IR_V4_EFFECT_LOCAL", f"locals exceed {MAX_EFFECT_LOCALS_V4}")
            type_id = _storable_type(table, step["type"], path + ".type")
            canonical, validation = _validate_effect_expression(step["value"], type_id, table, environment, path=path+".value")
            normalized_steps.append({"op":"LET_LOCAL","name":name,"type":type_id,"value":canonical})
            locals_[name] = type_id
            static_bound += validation.static_step_upper_bound + 1
        elif op == "SET_STATE":
            _exact(step, {"op", "state", "value"}, path)
            state_name = _local_name(step["state"], path + ".state")
            state_type = _state_type(states, state_name)
            canonical, validation = _validate_effect_expression(step["value"], state_type, table, environment, path=path+".value")
            normalized_steps.append({"op":"SET_STATE","state":state_name,"type":state_type,"value":canonical})
            static_bound += validation.static_step_upper_bound + 1
        elif op == "ASSERT":
            _exact(step, {"op", "condition"}, path)
            canonical, validation = _validate_effect_expression(step["condition"], "Bool", table, environment, path=path+".condition")
            normalized_steps.append({"op":"ASSERT","condition":canonical})
            static_bound += validation.static_step_upper_bound + 1
        else:
            _fail("TEVS_IR_V4_EFFECT_ACTION_STEP", f"unsupported effect action op {op!r}")
        if static_bound > MAX_EFFECT_STATIC_STEPS_V4:
            _fail("TEVS_IR_V4_EFFECT_STATIC_BUDGET", f"action static step upper bound exceeds {MAX_EFFECT_STATIC_STEPS_V4}")
    payload = {
        "schema":"TEV_SCRIPT_IR_V4_EFFECT_ACTION_V1",
        "action_id":action_id,
        "state_schema_hash":states.schema_hash,
        "capability_table_hash":capabilities.table_hash,
        "parameters":[{"name":n,"type":t} for n,t in zip(parameter_names,parameter_types,strict=True)],
        "steps":normalized_steps,
        "static_step_upper_bound":static_bound,
        "observation_call_upper_bound":observation_calls,
    }
    return EffectActionV4(
        action_id, tuple(parameter_names), tuple(parameter_types), tuple(normalized_steps),
        states.schema_hash, capabilities.table_hash, static_bound, observation_calls, _hash(payload),
    )


def build_effect_scenario_v4(raw: Mapping[str, Any], table: TypeTableV4, capabilities: CapabilityTableV4) -> EffectScenarioV4:
    item = _object(raw, "scenario")
    _exact(item, {"capability_table_hash", "capabilities"}, "scenario")
    if item["capability_table_hash"] != capabilities.table_hash:
        _fail("TEVS_IR_V4_EFFECT_SCENARIO_CONTRACT", "scenario capability table hash mismatch")
    raw_lanes = item["capabilities"]
    if not isinstance(raw_lanes, list) or len(raw_lanes) > MAX_EFFECT_CAPABILITIES_V4:
        _fail("TEVS_IR_V4_EFFECT_SCENARIO", "scenario capabilities must be a bounded array")
    lanes: list[ScriptedCapabilityLaneV4] = []
    previous: str | None = None
    total_calls = 0
    wire_lanes: list[dict[str, Any]] = []
    for index, raw_lane in enumerate(raw_lanes):
        lane = _object(raw_lane, f"scenario.capabilities[{index}]")
        _exact(lane, {"capability_id", "contract_hash", "calls"}, f"scenario.capabilities[{index}]")
        capability_id = _capability_id(lane["capability_id"], f"scenario.capabilities[{index}].capability_id")
        if previous is not None and capability_id <= previous:
            _fail("TEVS_IR_V4_EFFECT_SCENARIO_ORDER", "scenario capability lanes must be strictly sorted")
        previous = capability_id
        contract = capabilities.require(capability_id)
        if lane["contract_hash"] != contract.contract_hash:
            _fail("TEVS_IR_V4_EFFECT_SCENARIO_CONTRACT", f"scenario contract hash mismatch for {capability_id}")
        calls_raw = lane["calls"]
        if not isinstance(calls_raw, list):
            _fail("TEVS_IR_V4_EFFECT_SCENARIO", f"calls for {capability_id} must be an array")
        calls: list[ScriptedCapabilityCallV4] = []
        wire_calls: list[dict[str, Any]] = []
        for call_index, raw_call in enumerate(calls_raw):
            total_calls += 1
            if total_calls > MAX_SCRIPTED_CALLS_V4:
                _fail("TEVS_IR_V4_EFFECT_SCENARIO", f"scripted calls exceed {MAX_SCRIPTED_CALLS_V4}")
            call = _object(raw_call, f"scenario.{capability_id}.calls[{call_index}]")
            _exact(call, {"arguments", "return"}, f"scenario.{capability_id}.calls[{call_index}]")
            args_raw = call["arguments"]
            if not isinstance(args_raw, list) or len(args_raw) != len(contract.parameter_type_ids):
                _fail("TEVS_IR_V4_EFFECT_SCENARIO_ARITY", f"scripted {capability_id} call arity mismatch")
            arg_values: list[Any] = []
            arg_encoded: list[Any] = []
            for pos, (encoded, type_id) in enumerate(zip(args_raw, contract.parameter_type_ids, strict=True)):
                value = decode_v4_value(type_id, encoded, table, context=f"scripted {capability_id} argument {pos}")
                recoded = encode_v4_value(type_id, value, table, context=f"scripted {capability_id} argument {pos}")
                if recoded != encoded:
                    _fail("TEVS_IR_V4_EFFECT_SCENARIO_CANONICAL", f"scripted {capability_id} argument {pos} is noncanonical")
                arg_values.append(value); arg_encoded.append(recoded)
            return_value = decode_v4_value(contract.return_type_id, call["return"], table, context=f"scripted {capability_id} return")
            return_encoded = encode_v4_value(contract.return_type_id, return_value, table, context=f"scripted {capability_id} return")
            if return_encoded != call["return"]:
                _fail("TEVS_IR_V4_EFFECT_SCENARIO_CANONICAL", f"scripted {capability_id} return is noncanonical")
            calls.append(ScriptedCapabilityCallV4(tuple(arg_values), tuple(arg_encoded), return_value, return_encoded))
            wire_calls.append({"arguments":arg_encoded,"return":return_encoded})
        lanes.append(ScriptedCapabilityLaneV4(capability_id, contract.contract_hash, tuple(calls)))
        wire_lanes.append({"capability_id":capability_id,"contract_hash":contract.contract_hash,"calls":wire_calls})
    payload = {"schema":"TEV_SCRIPT_IR_V4_EFFECT_SCENARIO_V1","capability_table_hash":capabilities.table_hash,"capabilities":wire_lanes}
    return EffectScenarioV4(tuple(lanes), capabilities.table_hash, _hash(payload))


def execute_effect_action_v4(
    action: EffectActionV4,
    table: TypeTableV4,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    scenario: EffectScenarioV4,
    current_state: Mapping[str, Any],
    arguments: Sequence[Any] = (),
) -> EffectTransitionReceiptV4:
    if action.state_schema_hash != states.schema_hash:
        _fail("TEVS_IR_V4_EFFECT_STATE_SCHEMA", "action state schema hash mismatch")
    if action.capability_table_hash != capabilities.table_hash or scenario.capability_table_hash != capabilities.table_hash:
        _fail("TEVS_IR_V4_EFFECT_CAPABILITY_TABLE", "action/scenario capability table hash mismatch")
    working = _validate_state_snapshot(states, current_state, table)
    initial_wire = _state_wire(states, working, table)
    initial_hash = _hash({"schema":"TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1","states":initial_wire})
    if len(arguments) != len(action.parameter_names):
        _fail("TEVS_IR_V4_EFFECT_ACTION_ARITY", f"action expects {len(action.parameter_names)} arguments, got {len(arguments)}")
    params: dict[str, Any] = {}
    args_wire: list[dict[str, Any]] = []
    for name, type_id, raw in zip(action.parameter_names, action.parameter_type_ids, arguments, strict=True):
        encoded = encode_v4_value(type_id, raw, table, context=f"action argument {name}")
        value = decode_v4_value(type_id, encoded, table, context=f"action argument {name}")
        params[name] = value
        args_wire.append({"name":name,"type":type_id,"value":encoded})
    arguments_hash = _hash({"schema":"TEV_SCRIPT_IR_V4_EFFECT_ACTION_ARGUMENTS_V1","arguments":args_wire})
    host = _ScriptedHost(scenario, capabilities, table)
    locals_: dict[str, Any] = {}
    local_types: dict[str, str] = {}
    evaluation_steps = 0
    for step in action.steps:
        op = step["op"]
        bindings = _runtime_bindings(states, working, action, params, local_types, locals_)
        if op == "OBSERVE":
            contract = capabilities.require(step["capability_id"])
            values = []
            encoded_args = []
            for expr, type_id in zip(step["arguments"], contract.parameter_type_ids, strict=True):
                value, steps = _eval_pure(expr, type_id, table, bindings)
                evaluation_steps += steps
                values.append(value)
                encoded_args.append(encode_v4_value(type_id, value, table, context=f"capability {contract.capability_id} argument"))
            observed = host.invoke(contract, tuple(values), tuple(encoded_args))
            locals_[step["bind"]] = observed
            local_types[step["bind"]] = contract.return_type_id
            evaluation_steps += 1
        elif op == "OBSERVE_ALL":
            if step["reservation_policy"] != OBSERVE_ALL_RESERVATION_POLICY_V4:
                _fail("TEVS_IR_V4_EFFECT_OBSERVE_ALL_POLICY", "OBSERVE_ALL runtime reservation policy mismatch")
            requests = []
            return_types: dict[str, str] = {}
            # Every argument observes the same pre-scope state/params/locals snapshot.
            for observation in step["observations"]:
                contract = capabilities.require(observation["capability_id"])
                if observation["contract_hash"] != contract.contract_hash or observation["return_type"] != contract.return_type_id:
                    _fail("TEVS_IR_V4_EFFECT_OBSERVE_ALL_CONTRACT", f"OBSERVE_ALL contract drift for {contract.capability_id!r}")
                values = []
                encoded_args = []
                for expr, type_id in zip(observation["arguments"], contract.parameter_type_ids, strict=True):
                    value, steps = _eval_pure(expr, type_id, table, bindings)
                    evaluation_steps += steps
                    values.append(value)
                    encoded_args.append(encode_v4_value(type_id, value, table, context=f"capability {contract.capability_id} argument"))
                bind = observation["bind"]
                requests.append((bind, contract, tuple(values), tuple(encoded_args)))
                return_types[bind] = contract.return_type_id
            reserved = host.reserve_all(tuple(requests))
            for bind, value in reserved:
                locals_[bind] = value
                local_types[bind] = return_types[bind]
                evaluation_steps += 1
        elif op == "LET_LOCAL":
            value, steps = _eval_pure(step["value"], step["type"], table, bindings)
            evaluation_steps += steps + 1
            locals_[step["name"]] = value
            local_types[step["name"]] = step["type"]
        elif op == "SET_STATE":
            value, steps = _eval_pure(step["value"], step["type"], table, bindings)
            evaluation_steps += steps + 1
            working[step["state"]] = value
        elif op == "ASSERT":
            value, steps = _eval_pure(step["condition"], "Bool", table, bindings)
            evaluation_steps += steps + 1
            if value is not True:
                _fail("TEVS_IR_V4_EFFECT_ASSERT", "effect action assertion failed; transition not committed")
        else:
            raise AssertionError(f"validated effect op {op!r}")
        if evaluation_steps > action.static_step_upper_bound:
            _fail("TEVS_IR_V4_EFFECT_RUNTIME_BUDGET", "runtime steps exceeded static action bound")
    host.require_exact_consumption()
    final_wire = _state_wire(states, working, table)
    final_hash = _hash({"schema":"TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1","states":final_wire})
    transcript = tuple(host.transcript)
    transcript_hash = _hash({"schema":"TEV_SCRIPT_IR_V4_EFFECT_CAPABILITY_TRANSCRIPT_V1","calls":transcript})
    payload = {
        "schema":"TEV_SCRIPT_IR_V4_EFFECT_TRANSITION_RECEIPT_V1",
        "action_hash":action.action_hash,
        "state_schema_hash":states.schema_hash,
        "capability_table_hash":capabilities.table_hash,
        "scenario_hash":scenario.scenario_hash,
        "initial_state_hash":initial_hash,
        "arguments_hash":arguments_hash,
        "capability_transcript_hash":transcript_hash,
        "final_state":final_wire,
        "final_state_hash":final_hash,
        "evaluation_steps":evaluation_steps,
        "observation_calls":len(transcript),
    }
    return EffectTransitionReceiptV4(
        payload["schema"], action.action_hash, states.schema_hash, capabilities.table_hash,
        scenario.scenario_hash, initial_hash, arguments_hash, transcript, transcript_hash,
        tuple(final_wire), final_hash, evaluation_steps, len(transcript), _hash(payload),
    )


class _ScriptedHost:
    def __init__(self, scenario: EffectScenarioV4, capabilities: CapabilityTableV4, table: TypeTableV4) -> None:
        self.scenario = scenario
        self.capabilities = capabilities
        self.table = table
        self.cursors = {lane.capability_id: 0 for lane in scenario.lanes}
        self.lanes = {lane.capability_id: lane for lane in scenario.lanes}
        self.transcript: list[dict[str, Any]] = []

    def invoke(self, contract: CapabilityContractV4, values: tuple[Any, ...], encoded_args: tuple[Any, ...]) -> Any:
        lane = self.lanes.get(contract.capability_id)
        if lane is None:
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_UNSCRIPTED", f"capability {contract.capability_id!r} was invoked without a script")
        cursor = self.cursors[contract.capability_id]
        if cursor >= len(lane.calls):
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_OVERFLOW", f"capability {contract.capability_id!r} invoked more times than scripted")
        call = lane.calls[cursor]
        if call.argument_encodings != encoded_args:
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_ARGUMENTS", f"capability {contract.capability_id!r} arguments diverged from script")
        self.cursors[contract.capability_id] = cursor + 1
        self.transcript.append({
            "capability_id":contract.capability_id,
            "contract_hash":contract.contract_hash,
            "call_index":cursor,
            "arguments":list(encoded_args),
            "return":call.return_encoded,
        })
        return call.return_value

    def reserve_all(
        self,
        requests: Sequence[tuple[str, CapabilityContractV4, tuple[Any, ...], tuple[Any, ...]]],
    ) -> tuple[tuple[str, Any], ...]:
        tentative = dict(self.cursors)
        reservations: list[tuple[str, Any, dict[str, Any]]] = []
        for bind, contract, values, encoded_args in requests:
            lane = self.lanes.get(contract.capability_id)
            if lane is None:
                _fail("TEVS_IR_V4_EFFECT_CAPABILITY_UNSCRIPTED", f"capability {contract.capability_id!r} was invoked without a script")
            cursor = tentative[contract.capability_id]
            if cursor >= len(lane.calls):
                _fail("TEVS_IR_V4_EFFECT_CAPABILITY_OVERFLOW", f"capability {contract.capability_id!r} invoked more times than scripted")
            call = lane.calls[cursor]
            if call.argument_encodings != encoded_args:
                _fail("TEVS_IR_V4_EFFECT_CAPABILITY_ARGUMENTS", f"capability {contract.capability_id!r} arguments diverged from script")
            tentative[contract.capability_id] = cursor + 1
            reservations.append((bind, call.return_value, {
                "capability_id": contract.capability_id,
                "contract_hash": contract.contract_hash,
                "call_index": cursor,
                "arguments": list(encoded_args),
                "return": call.return_encoded,
            }))
        self.cursors = tentative
        self.transcript.extend(entry for _bind, _value, entry in reservations)
        return tuple((bind, value) for bind, value, _entry in reservations)

    def require_exact_consumption(self) -> None:
        pending = {
            capability_id: len(lane.calls) - self.cursors[capability_id]
            for capability_id, lane in self.lanes.items()
            if len(lane.calls) != self.cursors[capability_id]
        }
        if pending:
            _fail("TEVS_IR_V4_EFFECT_CAPABILITY_UNDERFLOW", f"scripted capability calls were not consumed exactly: {pending}")


def _validate_effect_expression(raw: Any, expected_type: str, table: TypeTableV4, environment: Mapping[str, str], *, path: str):
    pure = _lower_effect_refs(raw, environment, path=path)
    canonical = canonical_expression_v4(pure)
    validation = validate_pure_v4(canonical, table, environment)
    if validation.result_type != expected_type:
        _fail("TEVS_IR_V4_EFFECT_EXPRESSION_TYPE", f"{path} expected {expected_type}, got {validation.result_type}")
    return canonical, validation


def _lower_effect_refs(value: Any, environment: Mapping[str, str], *, path: str) -> Any:
    if isinstance(value, Mapping):
        node = dict(value)
        op = node.get("op")
        if op in {"LOAD_STATE", "LOAD_PARAM", "LOAD_LOCAL"}:
            _exact(node, {"op", "name", "type"}, path)
            name = _local_name(node["name"], path+".name")
            type_id = node["type"]
            prefix = "state" if op == "LOAD_STATE" else "param" if op == "LOAD_PARAM" else "local"
            synthetic = _binding_name(prefix, name)
            expected = environment.get(synthetic)
            if expected is None:
                _fail("TEVS_IR_V4_EFFECT_REFERENCE", f"unknown {prefix} reference {name!r}")
            if type_id != expected:
                _fail("TEVS_IR_V4_EFFECT_REFERENCE", f"{prefix} reference {name!r} declares {type_id}, expected {expected}")
            return {"op":"PARAM","name":synthetic,"type":expected}
        return {key:_lower_effect_refs(child, environment, path=f"{path}.{key}") for key, child in node.items()}
    if isinstance(value, list):
        return [_lower_effect_refs(child, environment, path=f"{path}[{index}]") for index, child in enumerate(value)]
    return value


def _effect_environment(states: StateSchemaV4, parameter_names: Sequence[str], parameter_types: Sequence[str], locals_: Mapping[str, str]) -> dict[str, str]:
    env = {_binding_name("state",slot.name):slot.type_id for slot in states.slots}
    env.update({_binding_name("param",name):type_id for name,type_id in zip(parameter_names,parameter_types,strict=True)})
    env.update({_binding_name("local",name):type_id for name,type_id in locals_.items()})
    return env


def _runtime_bindings(states: StateSchemaV4, working: Mapping[str, Any], action: EffectActionV4, params: Mapping[str, Any], local_types: Mapping[str, str], locals_: Mapping[str, Any]) -> tuple[PureBindingV4, ...]:
    values: list[PureBindingV4] = []
    for slot in states.slots:
        values.append(PureBindingV4(_binding_name("state",slot.name),slot.type_id,working[slot.name]))
    for name,type_id in zip(action.parameter_names,action.parameter_type_ids,strict=True):
        values.append(PureBindingV4(_binding_name("param",name),type_id,params[name]))
    for name,type_id in sorted(local_types.items()):
        values.append(PureBindingV4(_binding_name("local",name),type_id,locals_[name]))
    return tuple(values)


def _eval_pure(expr: Mapping[str, Any], expected_type: str, table: TypeTableV4, bindings: Sequence[PureBindingV4]) -> tuple[Any, int]:
    receipt = evaluate_pure_v4(expr, table, bindings, maximum_steps=MAX_EFFECT_STATIC_STEPS_V4)
    if receipt.result_type != expected_type:
        _fail("TEVS_IR_V4_EFFECT_RUNTIME_TYPE", f"pure fragment returned {receipt.result_type}, expected {expected_type}")
    value = decode_v4_value(expected_type, receipt.result_encoded, table, context="effect pure fragment result")
    return value, receipt.evaluation_steps


def _validate_state_snapshot(schema: StateSchemaV4, current_state: Mapping[str, Any], table: TypeTableV4) -> dict[str, Any]:
    if not isinstance(current_state, Mapping):
        _fail("TEVS_IR_V4_EFFECT_STATE", "current state must be a mapping")
    expected = {slot.name for slot in schema.slots}
    if set(current_state) != expected:
        _fail("TEVS_IR_V4_EFFECT_STATE", f"current state keys mismatch: {sorted(set(current_state) ^ expected)}")
    result: dict[str, Any] = {}
    for slot in schema.slots:
        encoded = encode_v4_value(slot.type_id, current_state[slot.name], table, context=f"current state {slot.name}")
        result[slot.name] = decode_v4_value(slot.type_id, encoded, table, context=f"current state {slot.name}")
    return result


def _state_wire(schema: StateSchemaV4, state: Mapping[str, Any], table: TypeTableV4) -> list[dict[str, Any]]:
    return [
        {"name":slot.name,"type":slot.type_id,"value":encode_v4_value(slot.type_id,state[slot.name],table,context=f"state witness {slot.name}")}
        for slot in schema.slots
    ]


def _state_type(schema: StateSchemaV4, name: str) -> str:
    for slot in schema.slots:
        if slot.name == name: return slot.type_id
    _fail("TEVS_IR_V4_EFFECT_STATE_UNKNOWN", f"unknown state {name!r}")


def _binding_name(namespace: str, name: str) -> str:
    return f"__tev_{namespace}_{name}"


def _storable_type(table: TypeTableV4, value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("TEVS_IR_V4_EFFECT_TYPE", f"{path} must be a type id")
    descriptor = table.require(value, context=path)
    if descriptor.kind == "unit":
        _fail("TEVS_IR_V4_EFFECT_TYPE", f"Unit is not storable at {path}")
    return value


def _local_name(value: Any, path: str) -> str:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None or value.startswith("__tev_"):
        _fail("TEVS_IR_V4_EFFECT_NAME", f"{path} must be a non-reserved local name")
    return value


def _capability_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or _CAPABILITY_ID.fullmatch(value) is None:
        _fail("TEVS_IR_V4_EFFECT_CAPABILITY_ID", f"{path} is not a stable capability id")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TEVS_IR_V4_EFFECT_SHAPE", f"{path} must be an object")
    return dict(value)


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        _fail("TEVS_IR_V4_EFFECT_SHAPE", f"{path} field set mismatch: {sorted(set(value) ^ expected)}")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
