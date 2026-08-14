from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .diagnostics import TevScriptError
from .ir_v4_effects import (
    MAX_EFFECT_ACTION_STEPS_V4,
    MAX_EFFECT_OBSERVE_ALL_V4,
    OBSERVE_ALL_RESERVATION_POLICY_V4,
    MAX_EFFECT_LOCALS_V4,
    MAX_EFFECT_PARAMETERS_V4,
    MAX_EFFECT_STATIC_STEPS_V4,
    CapabilityTableV4,
    EffectScenarioV4,
    StateSchemaV4,
    _ScriptedHost,
    _effect_environment,
    _eval_pure,
    _runtime_bindings,
    _state_type,
    _state_wire,
    _validate_effect_expression,
    _validate_state_snapshot,
)
from .ir_v4_values import TypeTableV4, decode_v4_value, encode_v4_value

MAX_EFFECT_COMMANDS_V4 = 4096
MAX_EFFECT_PROVIDER_CONTRACTS_V4 = 4096
_COMMAND_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class EffectCommandContractV4:
    command_id: str
    parameter_type_ids: tuple[str, ...]
    kind: str
    idempotency_policy: str
    contract_hash: str


@dataclass(frozen=True, slots=True)
class EffectCommandTableV4:
    contracts: tuple[EffectCommandContractV4, ...]
    table_hash: str

    def require(self, command_id: str) -> EffectCommandContractV4:
        for contract in self.contracts:
            if contract.command_id == command_id:
                return contract
        _fail("TEVS_IR_V4_COMMAND_UNKNOWN", f"undeclared effect command {command_id!r}")


@dataclass(frozen=True, slots=True)
class EffectActionR2V4:
    action_id: str
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    steps: tuple[dict[str, Any], ...]
    state_schema_hash: str
    capability_table_hash: str
    command_table_hash: str
    static_step_upper_bound: int
    observation_call_upper_bound: int
    command_request_upper_bound: int
    action_hash: str


@dataclass(frozen=True, slots=True)
class EffectCommandIntentV4:
    intent_index: int
    command_id: str
    contract_hash: str
    argument_encodings: tuple[Any, ...]
    plan_context_hash: str
    idempotency_key: str
    intent_hash: str


@dataclass(frozen=True, slots=True)
class EffectCommandBatchV4:
    plan_context_hash: str
    command_table_hash: str
    intents: tuple[EffectCommandIntentV4, ...]
    batch_hash: str


@dataclass(frozen=True, slots=True)
class PlannedEffectTransitionV4:
    schema: str
    action_hash: str
    state_schema_hash: str
    capability_table_hash: str
    command_table_hash: str
    scenario_hash: str
    initial_state_hash: str
    arguments_hash: str
    plan_context_hash: str
    capability_transcript: tuple[dict[str, Any], ...]
    capability_transcript_hash: str
    proposed_final_state: tuple[dict[str, Any], ...]
    proposed_final_state_hash: str
    command_batch: EffectCommandBatchV4
    evaluation_steps: int
    observation_calls: int
    planning_receipt_hash: str


@dataclass(frozen=True, slots=True)
class EffectProviderDescriptorV4:
    provider_id: str
    provider_version: str
    provider_implementation_hash: str
    supported_contract_hashes: tuple[str, ...]
    commit_semantics: str
    descriptor_hash: str


@dataclass(frozen=True, slots=True)
class EffectAuthorityGrantV4:
    provider_descriptor_hash: str
    batch_hash: str
    allowed_contract_hashes: tuple[str, ...]
    authority_scope_hash: str
    grant_hash: str


@dataclass(frozen=True, slots=True)
class ProviderIntentReceiptV4:
    intent_hash: str
    provider_effect_receipt_hash: str


@dataclass(frozen=True, slots=True)
class ProviderBatchObservationV4:
    batch_hash: str
    provider_descriptor_hash: str
    authority_grant_hash: str
    status: str
    intent_receipts: tuple[ProviderIntentReceiptV4, ...]
    provider_batch_receipt_hash: str
    observation_hash: str


@dataclass(frozen=True, slots=True)
class EffectCommandBatchCommitReceiptV4:
    schema: str
    batch_hash: str
    plan_context_hash: str
    command_table_hash: str
    provider_descriptor_hash: str
    authority_grant_hash: str
    status: str
    intent_receipts: tuple[ProviderIntentReceiptV4, ...]
    provider_batch_receipt_hash: str
    provider_observation_hash: str
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class FinalizedEffectTransitionReceiptV4:
    schema: str
    planning_receipt_hash: str
    commit_receipt_hash: str
    batch_hash: str
    provider_descriptor_hash: str
    authority_grant_hash: str
    final_state: tuple[dict[str, Any], ...]
    final_state_hash: str
    receipt_hash: str


class AtomicEffectProviderV4(Protocol):
    @property
    def descriptor(self) -> EffectProviderDescriptorV4: ...

    def commit_batch(
        self,
        batch: EffectCommandBatchV4,
        authority: EffectAuthorityGrantV4,
    ) -> ProviderBatchObservationV4: ...


class EffectCommitLedgerV4:
    """In-memory idempotency ledger. A persistent adapter can implement the same lookup/record shape later."""

    def __init__(self) -> None:
        self._receipts: dict[str, EffectCommandBatchCommitReceiptV4] = {}

    def lookup(self, batch_hash: str) -> EffectCommandBatchCommitReceiptV4 | None:
        return self._receipts.get(batch_hash)

    def record(self, receipt: EffectCommandBatchCommitReceiptV4) -> None:
        existing = self._receipts.get(receipt.batch_hash)
        if existing is not None and existing.receipt_hash != receipt.receipt_hash:
            _fail("TEVS_IR_V4_COMMAND_LEDGER_CONFLICT", "same batch hash cannot acquire two different commit receipts")
        self._receipts[receipt.batch_hash] = receipt


def build_effect_command_table_v4(
    raw_commands: Sequence[Mapping[str, Any]],
    table: TypeTableV4,
) -> EffectCommandTableV4:
    if not isinstance(raw_commands, Sequence) or isinstance(raw_commands, (str, bytes, bytearray)):
        _fail("TEVS_IR_V4_COMMAND_TABLE", "effect commands must be a sequence")
    if not 1 <= len(raw_commands) <= MAX_EFFECT_COMMANDS_V4:
        _fail("TEVS_IR_V4_COMMAND_TABLE", f"effect commands require 1..{MAX_EFFECT_COMMANDS_V4} entries")
    contracts: list[EffectCommandContractV4] = []
    previous: str | None = None
    for index, raw in enumerate(raw_commands):
        item = _object(raw, f"commands[{index}]")
        _exact(item, {"command_id", "parameters", "kind", "idempotency_policy"}, f"commands[{index}]")
        command_id = _command_id(item["command_id"], f"commands[{index}].command_id")
        if previous is not None and command_id <= previous:
            _fail("TEVS_IR_V4_COMMAND_ORDER", "effect commands must be strictly sorted by id")
        previous = command_id
        raw_parameters = item["parameters"]
        if not isinstance(raw_parameters, list) or len(raw_parameters) > MAX_EFFECT_PARAMETERS_V4:
            _fail("TEVS_IR_V4_COMMAND_SIGNATURE", "command parameters must be a bounded array")
        parameter_types = tuple(_storable_type(table, value, f"command {command_id} parameter") for value in raw_parameters)
        if item["kind"] != "effect_command":
            _fail("TEVS_IR_V4_COMMAND_KIND", "R2 physical command kind must be 'effect_command'")
        if item["idempotency_policy"] != "content_addressed_v1":
            _fail("TEVS_IR_V4_COMMAND_IDEMPOTENCY", "R2 requires content_addressed_v1 idempotency")
        payload = {
            "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_CONTRACT_V1",
            "command_id": command_id,
            "parameters": list(parameter_types),
            "kind": "effect_command",
            "idempotency_policy": "content_addressed_v1",
        }
        contracts.append(
            EffectCommandContractV4(
                command_id,
                parameter_types,
                "effect_command",
                "content_addressed_v1",
                _hash(payload),
            )
        )
    table_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_TABLE_V1",
        "contracts": [
            {
                "command_id": item.command_id,
                "parameters": list(item.parameter_type_ids),
                "kind": item.kind,
                "idempotency_policy": item.idempotency_policy,
                "contract_hash": item.contract_hash,
            }
            for item in contracts
        ],
    }
    return EffectCommandTableV4(tuple(contracts), _hash(table_payload))


def build_effect_action_r2_v4(
    raw: Mapping[str, Any],
    table: TypeTableV4,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    commands: EffectCommandTableV4,
) -> EffectActionR2V4:
    item = _object(raw, "action_r2")
    _exact(item, {"action_id", "parameters", "steps"}, "action_r2")
    action_id = _local_name(item["action_id"], "action_r2.action_id")
    raw_parameters = item["parameters"]
    if not isinstance(raw_parameters, list) or len(raw_parameters) > MAX_EFFECT_PARAMETERS_V4:
        _fail("TEVS_IR_V4_COMMAND_ACTION_PARAMETERS", "R2 action parameters must be a bounded array")
    state_names = {slot.name for slot in states.slots}
    parameter_names: list[str] = []
    parameter_types: list[str] = []
    for index, raw_parameter in enumerate(raw_parameters):
        parameter = _object(raw_parameter, f"action_r2.parameters[{index}]")
        _exact(parameter, {"name", "type"}, f"action_r2.parameters[{index}]")
        name = _local_name(parameter["name"], f"action_r2.parameters[{index}].name")
        if name in state_names or name in parameter_names:
            _fail("TEVS_IR_V4_COMMAND_ACTION_PARAMETERS", f"duplicate/state-shadowing parameter {name!r}")
        parameter_names.append(name)
        parameter_types.append(_storable_type(table, parameter["type"], f"R2 action parameter {name}"))

    raw_steps = item["steps"]
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_EFFECT_ACTION_STEPS_V4:
        _fail("TEVS_IR_V4_COMMAND_ACTION_STEPS", f"R2 action requires 1..{MAX_EFFECT_ACTION_STEPS_V4} steps")
    locals_: dict[str, str] = {}
    normalized_steps: list[dict[str, Any]] = []
    static_bound = 0
    observation_calls = 0
    command_requests = 0
    for index, raw_step in enumerate(raw_steps):
        path = f"action_r2.steps[{index}]"
        step = _object(raw_step, path)
        op = step.get("op")
        environment = _effect_environment(states, parameter_names, parameter_types, locals_)
        if op == "OBSERVE":
            _exact(step, {"op", "capability_id", "arguments", "bind"}, path)
            capability_id = _command_id(step["capability_id"], path + ".capability_id")
            contract = capabilities.require(capability_id)
            bind = _local_name(step["bind"], path + ".bind")
            if bind in state_names or bind in parameter_names or bind in locals_:
                _fail("TEVS_IR_V4_COMMAND_LOCAL", f"duplicate/shadowing local {bind!r}")
            arguments = step["arguments"]
            if not isinstance(arguments, list) or len(arguments) != len(contract.parameter_type_ids):
                _fail("TEVS_IR_V4_COMMAND_CAPABILITY_ARITY", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
            canonical_args: list[dict[str, Any]] = []
            for position, (expr, expected_type) in enumerate(zip(arguments, contract.parameter_type_ids, strict=True)):
                canonical, validation = _validate_effect_expression(expr, expected_type, table, environment, path=f"{path}.arguments[{position}]")
                canonical_args.append(canonical)
                static_bound += validation.static_step_upper_bound
            normalized_steps.append({
                "op": "OBSERVE",
                "capability_id": capability_id,
                "contract_hash": contract.contract_hash,
                "arguments": canonical_args,
                "bind": bind,
                "return_type": contract.return_type_id,
            })
            locals_[bind] = contract.return_type_id
            observation_calls += 1
            static_bound += 1
        elif op == "OBSERVE_ALL":
            _exact(step, {"op", "reservation_policy", "observations"}, path)
            if step["reservation_policy"] != OBSERVE_ALL_RESERVATION_POLICY_V4:
                _fail("TEVS_IR_V4_COMMAND_OBSERVE_ALL_POLICY", "R2 OBSERVE_ALL reservation policy mismatch")
            raw_observations = step["observations"]
            if not isinstance(raw_observations, list) or not 1 <= len(raw_observations) <= MAX_EFFECT_OBSERVE_ALL_V4:
                _fail("TEVS_IR_V4_COMMAND_OBSERVE_ALL_BOUND", f"R2 OBSERVE_ALL requires 1..{MAX_EFFECT_OBSERVE_ALL_V4} observations")
            canonical_observations: list[dict[str, Any]] = []
            pending_binds: dict[str, str] = {}
            for observation_index, raw_observation in enumerate(raw_observations):
                observation_path = f"{path}.observations[{observation_index}]"
                observation = _object(raw_observation, observation_path)
                _exact(observation, {"bind", "capability_id", "arguments"}, observation_path)
                bind = _local_name(observation["bind"], observation_path + ".bind")
                if bind in state_names or bind in parameter_names or bind in locals_ or bind in pending_binds:
                    _fail("TEVS_IR_V4_COMMAND_LOCAL", f"duplicate/shadowing R2 OBSERVE_ALL local {bind!r}")
                capability_id = _command_id(observation["capability_id"], observation_path + ".capability_id")
                contract = capabilities.require(capability_id)
                arguments = observation["arguments"]
                if not isinstance(arguments, list) or len(arguments) != len(contract.parameter_type_ids):
                    _fail("TEVS_IR_V4_COMMAND_CAPABILITY_ARITY", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
                canonical_args: list[dict[str, Any]] = []
                for position, (expr, expected_type) in enumerate(zip(arguments, contract.parameter_type_ids, strict=True)):
                    canonical, validation = _validate_effect_expression(expr, expected_type, table, environment, path=f"{observation_path}.arguments[{position}]")
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
                _fail("TEVS_IR_V4_COMMAND_LOCAL", f"duplicate/shadowing local {name!r}")
            if len(locals_) >= MAX_EFFECT_LOCALS_V4:
                _fail("TEVS_IR_V4_COMMAND_LOCAL", f"locals exceed {MAX_EFFECT_LOCALS_V4}")
            type_id = _storable_type(table, step["type"], path + ".type")
            canonical, validation = _validate_effect_expression(step["value"], type_id, table, environment, path=path + ".value")
            normalized_steps.append({"op": "LET_LOCAL", "name": name, "type": type_id, "value": canonical})
            locals_[name] = type_id
            static_bound += validation.static_step_upper_bound + 1
        elif op == "SET_STATE":
            _exact(step, {"op", "state", "value"}, path)
            state_name = _local_name(step["state"], path + ".state")
            state_type = _state_type(states, state_name)
            canonical, validation = _validate_effect_expression(step["value"], state_type, table, environment, path=path + ".value")
            normalized_steps.append({"op": "SET_STATE", "state": state_name, "type": state_type, "value": canonical})
            static_bound += validation.static_step_upper_bound + 1
        elif op == "ASSERT":
            _exact(step, {"op", "condition"}, path)
            canonical, validation = _validate_effect_expression(step["condition"], "Bool", table, environment, path=path + ".condition")
            normalized_steps.append({"op": "ASSERT", "condition": canonical})
            static_bound += validation.static_step_upper_bound + 1
        elif op == "REQUEST_EFFECT":
            _exact(step, {"op", "command_id", "arguments"}, path)
            command_id = _command_id(step["command_id"], path + ".command_id")
            contract = commands.require(command_id)
            arguments = step["arguments"]
            if not isinstance(arguments, list) or len(arguments) != len(contract.parameter_type_ids):
                _fail("TEVS_IR_V4_COMMAND_ARITY", f"{command_id} expects {len(contract.parameter_type_ids)} arguments")
            canonical_args = []
            for position, (expr, expected_type) in enumerate(zip(arguments, contract.parameter_type_ids, strict=True)):
                canonical, validation = _validate_effect_expression(expr, expected_type, table, environment, path=f"{path}.arguments[{position}]")
                canonical_args.append(canonical)
                static_bound += validation.static_step_upper_bound
            normalized_steps.append({
                "op": "REQUEST_EFFECT",
                "command_id": command_id,
                "contract_hash": contract.contract_hash,
                "arguments": canonical_args,
            })
            command_requests += 1
            static_bound += 1
        else:
            _fail("TEVS_IR_V4_COMMAND_ACTION_STEP", f"unsupported R2 action op {op!r}")
        if static_bound > MAX_EFFECT_STATIC_STEPS_V4:
            _fail("TEVS_IR_V4_COMMAND_STATIC_BUDGET", f"R2 action static steps exceed {MAX_EFFECT_STATIC_STEPS_V4}")
    if command_requests == 0:
        _fail("TEVS_IR_V4_COMMAND_ACTION_PROFILE", "R2 action requires at least one REQUEST_EFFECT; use Effects R1 otherwise")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_ACTION_R2_V1",
        "action_id": action_id,
        "state_schema_hash": states.schema_hash,
        "capability_table_hash": capabilities.table_hash,
        "command_table_hash": commands.table_hash,
        "parameters": [{"name": name, "type": type_id} for name, type_id in zip(parameter_names, parameter_types, strict=True)],
        "steps": normalized_steps,
        "static_step_upper_bound": static_bound,
        "observation_call_upper_bound": observation_calls,
        "command_request_upper_bound": command_requests,
    }
    return EffectActionR2V4(
        action_id,
        tuple(parameter_names),
        tuple(parameter_types),
        tuple(normalized_steps),
        states.schema_hash,
        capabilities.table_hash,
        commands.table_hash,
        static_bound,
        observation_calls,
        command_requests,
        _hash(payload),
    )


def plan_effect_action_r2_v4(
    action: EffectActionR2V4,
    table: TypeTableV4,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    commands: EffectCommandTableV4,
    scenario: EffectScenarioV4,
    current_state: Mapping[str, Any],
    arguments: Sequence[Any] = (),
) -> PlannedEffectTransitionV4:
    if action.state_schema_hash != states.schema_hash:
        _fail("TEVS_IR_V4_COMMAND_STATE_SCHEMA", "R2 action state schema hash mismatch")
    if action.capability_table_hash != capabilities.table_hash or scenario.capability_table_hash != capabilities.table_hash:
        _fail("TEVS_IR_V4_COMMAND_CAPABILITY_TABLE", "R2 action/scenario capability table hash mismatch")
    if action.command_table_hash != commands.table_hash:
        _fail("TEVS_IR_V4_COMMAND_TABLE", "R2 action command table hash mismatch")
    working = _validate_state_snapshot(states, current_state, table)
    initial_wire = _state_wire(states, working, table)
    initial_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1", "states": initial_wire})
    if len(arguments) != len(action.parameter_names):
        _fail("TEVS_IR_V4_COMMAND_ACTION_ARITY", f"R2 action expects {len(action.parameter_names)} arguments, got {len(arguments)}")
    params: dict[str, Any] = {}
    args_wire: list[dict[str, Any]] = []
    for name, type_id, raw in zip(action.parameter_names, action.parameter_type_ids, arguments, strict=True):
        encoded = encode_v4_value(type_id, raw, table, context=f"R2 action argument {name}")
        value = decode_v4_value(type_id, encoded, table, context=f"R2 action argument {name}")
        params[name] = value
        args_wire.append({"name": name, "type": type_id, "value": encoded})
    arguments_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_EFFECT_ACTION_ARGUMENTS_V1", "arguments": args_wire})
    host = _ScriptedHost(scenario, capabilities, table)
    locals_: dict[str, Any] = {}
    local_types: dict[str, str] = {}
    pending_commands: list[tuple[EffectCommandContractV4, tuple[Any, ...]]] = []
    evaluation_steps = 0
    for step in action.steps:
        op = step["op"]
        bindings = _runtime_bindings(states, working, action, params, local_types, locals_)
        if op == "OBSERVE":
            contract = capabilities.require(step["capability_id"])
            encoded_args: list[Any] = []
            values: list[Any] = []
            for expr, type_id in zip(step["arguments"], contract.parameter_type_ids, strict=True):
                value, steps = _eval_pure(expr, type_id, table, bindings)
                evaluation_steps += steps
                values.append(value)
                encoded_args.append(encode_v4_value(type_id, value, table, context=f"R2 observation {contract.capability_id} argument"))
            observed = host.invoke(contract, tuple(values), tuple(encoded_args))
            locals_[step["bind"]] = observed
            local_types[step["bind"]] = contract.return_type_id
            evaluation_steps += 1
        elif op == "OBSERVE_ALL":
            if step["reservation_policy"] != OBSERVE_ALL_RESERVATION_POLICY_V4:
                _fail("TEVS_IR_V4_COMMAND_OBSERVE_ALL_POLICY", "R2 OBSERVE_ALL runtime reservation policy mismatch")
            requests = []
            return_types: dict[str, str] = {}
            for observation in step["observations"]:
                contract = capabilities.require(observation["capability_id"])
                if observation["contract_hash"] != contract.contract_hash or observation["return_type"] != contract.return_type_id:
                    _fail("TEVS_IR_V4_COMMAND_OBSERVE_ALL_CONTRACT", f"R2 OBSERVE_ALL contract drift for {contract.capability_id!r}")
                values: list[Any] = []
                encoded_args: list[Any] = []
                for expr, type_id in zip(observation["arguments"], contract.parameter_type_ids, strict=True):
                    value, steps = _eval_pure(expr, type_id, table, bindings)
                    evaluation_steps += steps
                    values.append(value)
                    encoded_args.append(encode_v4_value(type_id, value, table, context=f"R2 observation {contract.capability_id} argument"))
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
            locals_[step["name"]] = value
            local_types[step["name"]] = step["type"]
            evaluation_steps += steps + 1
        elif op == "SET_STATE":
            value, steps = _eval_pure(step["value"], step["type"], table, bindings)
            working[step["state"]] = value
            evaluation_steps += steps + 1
        elif op == "ASSERT":
            value, steps = _eval_pure(step["condition"], "Bool", table, bindings)
            evaluation_steps += steps + 1
            if value is not True:
                _fail("TEVS_IR_V4_COMMAND_ASSERT", "R2 assertion failed; no effect batch is authorized")
        elif op == "REQUEST_EFFECT":
            contract = commands.require(step["command_id"])
            encoded_args: list[Any] = []
            for expr, type_id in zip(step["arguments"], contract.parameter_type_ids, strict=True):
                value, steps = _eval_pure(expr, type_id, table, bindings)
                evaluation_steps += steps
                encoded_args.append(encode_v4_value(type_id, value, table, context=f"R2 command {contract.command_id} argument"))
            pending_commands.append((contract, tuple(encoded_args)))
            evaluation_steps += 1
        else:
            raise AssertionError(f"validated R2 op {op!r}")
        if evaluation_steps > action.static_step_upper_bound:
            _fail("TEVS_IR_V4_COMMAND_RUNTIME_BUDGET", "R2 runtime steps exceeded static action bound")
    host.require_exact_consumption()
    if len(pending_commands) != action.command_request_upper_bound:
        raise AssertionError("linear R2 action must emit exactly its static REQUEST_EFFECT count")
    if not pending_commands:
        _fail("TEVS_IR_V4_COMMAND_BATCH_EMPTY", "R2 planning unexpectedly produced an empty command batch")
    final_wire = _state_wire(states, working, table)
    final_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1", "states": final_wire})
    transcript = tuple(host.transcript)
    transcript_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_EFFECT_CAPABILITY_TRANSCRIPT_V1", "calls": transcript})
    plan_context_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PLAN_CONTEXT_R2_V2",
        "action_hash": action.action_hash,
        "state_schema_hash": states.schema_hash,
        "capability_table_hash": capabilities.table_hash,
        "command_table_hash": commands.table_hash,
        "scenario_hash": scenario.scenario_hash,
        "initial_state_hash": initial_hash,
        "arguments_hash": arguments_hash,
        "capability_transcript_hash": transcript_hash,
        "proposed_final_state_hash": final_hash,
    }
    plan_context_hash = _hash(plan_context_payload)
    intents: list[EffectCommandIntentV4] = []
    for intent_index, (contract, encoded_args) in enumerate(pending_commands):
        idempotency_payload = {
            "schema": "TEV_SCRIPT_IR_V4_EFFECT_IDEMPOTENCY_KEY_R2_V1",
            "plan_context_hash": plan_context_hash,
            "intent_index": intent_index,
            "command_id": contract.command_id,
            "contract_hash": contract.contract_hash,
            "arguments": list(encoded_args),
        }
        idempotency_key = _hash(idempotency_payload)
        intent_payload = {
            "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_INTENT_R2_V1",
            "plan_context_hash": plan_context_hash,
            "intent_index": intent_index,
            "command_id": contract.command_id,
            "contract_hash": contract.contract_hash,
            "arguments": list(encoded_args),
            "idempotency_key": idempotency_key,
        }
        intents.append(EffectCommandIntentV4(
            intent_index, contract.command_id, contract.contract_hash, tuple(encoded_args),
            plan_context_hash, idempotency_key, _hash(intent_payload),
        ))
    batch_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_BATCH_R2_V1",
        "plan_context_hash": plan_context_hash,
        "command_table_hash": commands.table_hash,
        "intents": [_intent_wire(intent) for intent in intents],
    }
    batch = EffectCommandBatchV4(plan_context_hash, commands.table_hash, tuple(intents), _hash(batch_payload))
    planning_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PLANNING_RECEIPT_R2_V1",
        "action_hash": action.action_hash,
        "state_schema_hash": states.schema_hash,
        "capability_table_hash": capabilities.table_hash,
        "command_table_hash": commands.table_hash,
        "scenario_hash": scenario.scenario_hash,
        "initial_state_hash": initial_hash,
        "arguments_hash": arguments_hash,
        "plan_context_hash": plan_context_hash,
        "capability_transcript_hash": transcript_hash,
        "proposed_final_state": final_wire,
        "proposed_final_state_hash": final_hash,
        "command_batch_hash": batch.batch_hash,
        "evaluation_steps": evaluation_steps,
        "observation_calls": len(transcript),
    }
    return PlannedEffectTransitionV4(
        planning_payload["schema"],
        action.action_hash,
        states.schema_hash,
        capabilities.table_hash,
        commands.table_hash,
        scenario.scenario_hash,
        initial_hash,
        arguments_hash,
        plan_context_hash,
        transcript,
        transcript_hash,
        tuple(final_wire),
        final_hash,
        batch,
        evaluation_steps,
        len(transcript),
        _hash(planning_payload),
    )


def build_effect_provider_descriptor_v4(
    *,
    provider_id: str,
    provider_version: str,
    provider_implementation_hash: str,
    supported_contract_hashes: Sequence[str],
    commit_semantics: str = "atomic_batch_v1",
) -> EffectProviderDescriptorV4:
    provider_id = _command_id(provider_id, "provider_id")
    if not isinstance(provider_version, str) or not provider_version:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER", "provider_version must be non-empty")
    implementation_hash = _sha(provider_implementation_hash, "provider_implementation_hash")
    contracts = tuple(sorted({_sha(value, "supported_contract_hash") for value in supported_contract_hashes}))
    if not 1 <= len(contracts) <= MAX_EFFECT_PROVIDER_CONTRACTS_V4:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER", "provider must support a bounded non-empty contract set")
    if commit_semantics != "atomic_batch_v1":
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_ATOMICITY", "R2 admits atomic_batch_v1 providers only")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PROVIDER_DESCRIPTOR_R2_V1",
        "provider_id": provider_id,
        "provider_version": provider_version,
        "provider_implementation_hash": implementation_hash,
        "supported_contract_hashes": list(contracts),
        "commit_semantics": commit_semantics,
    }
    return EffectProviderDescriptorV4(
        provider_id,
        provider_version,
        implementation_hash,
        contracts,
        commit_semantics,
        _hash(payload),
    )


def build_effect_authority_grant_v4(
    descriptor: EffectProviderDescriptorV4,
    batch: EffectCommandBatchV4,
    *,
    allowed_contract_hashes: Sequence[str],
    authority_scope_hash: str,
) -> EffectAuthorityGrantV4:
    allowed = tuple(sorted({_sha(value, "allowed_contract_hash") for value in allowed_contract_hashes}))
    if not allowed:
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority grant must allow at least one contract")
    supported = set(descriptor.supported_contract_hashes)
    if not set(allowed).issubset(supported):
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority grant cannot exceed provider supported contracts")
    required = {intent.contract_hash for intent in batch.intents}
    if not required.issubset(set(allowed)):
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority grant does not cover the exact command batch")
    scope_hash = _sha(authority_scope_hash, "authority_scope_hash")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_AUTHORITY_GRANT_R2_V1",
        "provider_descriptor_hash": descriptor.descriptor_hash,
        "batch_hash": batch.batch_hash,
        "allowed_contract_hashes": list(allowed),
        "authority_scope_hash": scope_hash,
    }
    return EffectAuthorityGrantV4(
        descriptor.descriptor_hash,
        batch.batch_hash,
        allowed,
        scope_hash,
        _hash(payload),
    )


def build_provider_batch_observation_v4(
    *,
    batch_hash: str,
    provider_descriptor_hash: str,
    authority_grant_hash: str,
    status: str,
    intent_receipts: Sequence[tuple[str, str]],
    provider_batch_receipt_hash: str,
) -> ProviderBatchObservationV4:
    batch_hash = _sha(batch_hash, "batch_hash")
    provider_hash = _sha(provider_descriptor_hash, "provider_descriptor_hash")
    grant_hash = _sha(authority_grant_hash, "authority_grant_hash")
    if status not in {"PASS", "FAIL"}:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_STATUS", "provider status must be PASS or FAIL")
    receipts = tuple(
        ProviderIntentReceiptV4(_sha(intent_hash, "intent_hash"), _sha(effect_hash, "provider_effect_receipt_hash"))
        for intent_hash, effect_hash in intent_receipts
    )
    if status == "FAIL" and receipts:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_ATOMICITY", "atomic failed batch cannot report committed intent receipts")
    provider_batch_hash = _sha(provider_batch_receipt_hash, "provider_batch_receipt_hash")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PROVIDER_BATCH_OBSERVATION_R2_V1",
        "batch_hash": batch_hash,
        "provider_descriptor_hash": provider_hash,
        "authority_grant_hash": grant_hash,
        "status": status,
        "intent_receipts": [_provider_intent_wire(item) for item in receipts],
        "provider_batch_receipt_hash": provider_batch_hash,
    }
    return ProviderBatchObservationV4(
        batch_hash,
        provider_hash,
        grant_hash,
        status,
        receipts,
        provider_batch_hash,
        _hash(payload),
    )


def commit_effect_command_batch_v4(
    batch: EffectCommandBatchV4,
    provider: AtomicEffectProviderV4,
    authority: EffectAuthorityGrantV4,
    ledger: EffectCommitLedgerV4,
) -> EffectCommandBatchCommitReceiptV4:
    _validate_batch(batch)
    _validate_authority(authority)
    descriptor = provider.descriptor
    _validate_descriptor(descriptor)
    if descriptor.commit_semantics != "atomic_batch_v1":
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_ATOMICITY", "provider does not promise atomic_batch_v1")
    if authority.provider_descriptor_hash != descriptor.descriptor_hash:
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority grant is bound to a different provider")
    if authority.batch_hash != batch.batch_hash:
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority grant is bound to a different batch")
    required_contracts = {intent.contract_hash for intent in batch.intents}
    if not required_contracts.issubset(set(descriptor.supported_contract_hashes)):
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_SUPPORT", "provider does not support every command contract in the batch")
    if not required_contracts.issubset(set(authority.allowed_contract_hashes)):
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority grant does not allow every command contract in the batch")

    existing = ledger.lookup(batch.batch_hash)
    if existing is not None:
        if existing.provider_descriptor_hash != descriptor.descriptor_hash or existing.authority_grant_hash != authority.grant_hash:
            _fail("TEVS_IR_V4_COMMAND_IDEMPOTENCY_AUTHORITY", "committed batch replay uses a different provider or authority grant")
        return existing

    observation = provider.commit_batch(batch, authority)
    _validate_provider_observation(observation, batch, descriptor, authority)
    receipt_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_BATCH_COMMIT_RECEIPT_R2_V1",
        "batch_hash": batch.batch_hash,
        "plan_context_hash": batch.plan_context_hash,
        "command_table_hash": batch.command_table_hash,
        "provider_descriptor_hash": descriptor.descriptor_hash,
        "authority_grant_hash": authority.grant_hash,
        "status": observation.status,
        "intent_receipts": [_provider_intent_wire(item) for item in observation.intent_receipts],
        "provider_batch_receipt_hash": observation.provider_batch_receipt_hash,
        "provider_observation_hash": observation.observation_hash,
    }
    receipt = EffectCommandBatchCommitReceiptV4(
        receipt_payload["schema"],
        batch.batch_hash,
        batch.plan_context_hash,
        batch.command_table_hash,
        descriptor.descriptor_hash,
        authority.grant_hash,
        observation.status,
        observation.intent_receipts,
        observation.provider_batch_receipt_hash,
        observation.observation_hash,
        _hash(receipt_payload),
    )
    if receipt.status == "PASS":
        ledger.record(receipt)
    return receipt


def finalize_effect_transition_v4(
    planned: PlannedEffectTransitionV4,
    commit: EffectCommandBatchCommitReceiptV4,
) -> FinalizedEffectTransitionReceiptV4:
    _validate_batch(planned.command_batch)
    _validate_commit_receipt(commit)
    if commit.status != "PASS":
        _fail("TEVS_IR_V4_COMMAND_FINALIZE_STATUS", "proposed state cannot finalize without a PASS command commit")
    if commit.batch_hash != planned.command_batch.batch_hash:
        _fail("TEVS_IR_V4_COMMAND_FINALIZE_BATCH", "commit receipt belongs to a different command batch")
    if commit.plan_context_hash != planned.plan_context_hash:
        _fail("TEVS_IR_V4_COMMAND_FINALIZE_CONTEXT", "commit receipt belongs to a different planning context")
    if commit.command_table_hash != planned.command_table_hash:
        _fail("TEVS_IR_V4_COMMAND_FINALIZE_TABLE", "commit receipt uses a different command table")
    expected_intents = tuple(intent.intent_hash for intent in planned.command_batch.intents)
    observed_intents = tuple(item.intent_hash for item in commit.intent_receipts)
    if observed_intents != expected_intents:
        _fail("TEVS_IR_V4_COMMAND_FINALIZE_INTENTS", "commit receipt does not cover the exact ordered intent set")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_FINALIZED_TRANSITION_R2_V1",
        "planning_receipt_hash": planned.planning_receipt_hash,
        "commit_receipt_hash": commit.receipt_hash,
        "batch_hash": planned.command_batch.batch_hash,
        "provider_descriptor_hash": commit.provider_descriptor_hash,
        "authority_grant_hash": commit.authority_grant_hash,
        "final_state": list(planned.proposed_final_state),
        "final_state_hash": planned.proposed_final_state_hash,
    }
    return FinalizedEffectTransitionReceiptV4(
        payload["schema"],
        planned.planning_receipt_hash,
        commit.receipt_hash,
        planned.command_batch.batch_hash,
        commit.provider_descriptor_hash,
        commit.authority_grant_hash,
        planned.proposed_final_state,
        planned.proposed_final_state_hash,
        _hash(payload),
    )




def validate_effect_command_batch_v4(batch: EffectCommandBatchV4) -> None:
    _validate_batch(batch)


def validate_effect_authority_grant_v4(authority: EffectAuthorityGrantV4) -> None:
    _validate_authority(authority)


def validate_effect_command_commit_receipt_v4(receipt: EffectCommandBatchCommitReceiptV4) -> None:
    _validate_commit_receipt(receipt)


def validate_planned_effect_transition_v4(planned: PlannedEffectTransitionV4) -> None:
    if not isinstance(planned, PlannedEffectTransitionV4):
        _fail("TEVS_IR_V4_COMMAND_PLAN", "planned transition must be PlannedEffectTransitionV4")
    for value, path in (
        (planned.action_hash, "plan.action_hash"),
        (planned.state_schema_hash, "plan.state_schema_hash"),
        (planned.capability_table_hash, "plan.capability_table_hash"),
        (planned.command_table_hash, "plan.command_table_hash"),
        (planned.scenario_hash, "plan.scenario_hash"),
        (planned.initial_state_hash, "plan.initial_state_hash"),
        (planned.arguments_hash, "plan.arguments_hash"),
        (planned.plan_context_hash, "plan.plan_context_hash"),
        (planned.capability_transcript_hash, "plan.capability_transcript_hash"),
        (planned.proposed_final_state_hash, "plan.proposed_final_state_hash"),
    ):
        _sha(value, path)
    if planned.command_batch.plan_context_hash != planned.plan_context_hash:
        _fail("TEVS_IR_V4_COMMAND_PLAN_CONTEXT", "planned batch context differs from plan")
    if planned.command_batch.command_table_hash != planned.command_table_hash:
        _fail("TEVS_IR_V4_COMMAND_PLAN_TABLE", "planned batch command table differs from plan")
    _validate_batch(planned.command_batch)
    transcript = tuple(planned.capability_transcript)
    transcript_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_EFFECT_CAPABILITY_TRANSCRIPT_V1", "calls": transcript})
    if transcript_hash != planned.capability_transcript_hash:
        _fail("TEVS_IR_V4_COMMAND_PLAN_TRANSCRIPT", "planned capability transcript hash mismatch")
    final_state = list(planned.proposed_final_state)
    final_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1", "states": final_state})
    if final_hash != planned.proposed_final_state_hash:
        _fail("TEVS_IR_V4_COMMAND_PLAN_STATE", "planned proposed final state hash mismatch")
    context_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PLAN_CONTEXT_R2_V2",
        "action_hash": planned.action_hash,
        "state_schema_hash": planned.state_schema_hash,
        "capability_table_hash": planned.capability_table_hash,
        "command_table_hash": planned.command_table_hash,
        "scenario_hash": planned.scenario_hash,
        "initial_state_hash": planned.initial_state_hash,
        "arguments_hash": planned.arguments_hash,
        "capability_transcript_hash": planned.capability_transcript_hash,
        "proposed_final_state_hash": planned.proposed_final_state_hash,
    }
    if planned.plan_context_hash != _hash(context_payload):
        _fail("TEVS_IR_V4_COMMAND_PLAN_CONTEXT", "planned context is not causally bound to transcript/final state")
    if planned.observation_calls != len(transcript):
        _fail("TEVS_IR_V4_COMMAND_PLAN_TRANSCRIPT", "planned observation count mismatch")
    if isinstance(planned.evaluation_steps, bool) or not isinstance(planned.evaluation_steps, int) or planned.evaluation_steps < 1:
        _fail("TEVS_IR_V4_COMMAND_PLAN_STEPS", "planned evaluation steps must be positive")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PLANNING_RECEIPT_R2_V1",
        "action_hash": planned.action_hash,
        "state_schema_hash": planned.state_schema_hash,
        "capability_table_hash": planned.capability_table_hash,
        "command_table_hash": planned.command_table_hash,
        "scenario_hash": planned.scenario_hash,
        "initial_state_hash": planned.initial_state_hash,
        "arguments_hash": planned.arguments_hash,
        "plan_context_hash": planned.plan_context_hash,
        "capability_transcript_hash": planned.capability_transcript_hash,
        "proposed_final_state": final_state,
        "proposed_final_state_hash": planned.proposed_final_state_hash,
        "command_batch_hash": planned.command_batch.batch_hash,
        "evaluation_steps": planned.evaluation_steps,
        "observation_calls": planned.observation_calls,
    }
    if planned.planning_receipt_hash != _hash(payload):
        _fail("TEVS_IR_V4_COMMAND_PLAN_HASH", "planning receipt hash mismatch")


def effect_command_batch_to_dict_v4(batch: EffectCommandBatchV4) -> dict[str, Any]:
    _validate_batch(batch)
    return {
        "schema": "TEV_SCRIPT_EFFECT_COMMAND_BATCH_ARTIFACT_R2_V1",
        "plan_context_hash": batch.plan_context_hash,
        "command_table_hash": batch.command_table_hash,
        "intents": [_intent_wire(intent) for intent in batch.intents],
        "batch_hash": batch.batch_hash,
    }


def load_effect_command_batch_v4(raw: Mapping[str, Any]) -> EffectCommandBatchV4:
    item = _object(raw, "batch_artifact")
    _exact(item, {"schema", "plan_context_hash", "command_table_hash", "intents", "batch_hash"}, "batch_artifact")
    if item["schema"] != "TEV_SCRIPT_EFFECT_COMMAND_BATCH_ARTIFACT_R2_V1":
        _fail("TEVS_IR_V4_COMMAND_ARTIFACT_SCHEMA", "unsupported command batch artifact schema")
    plan_context_hash = _sha(item["plan_context_hash"], "batch_artifact.plan_context_hash")
    command_table_hash = _sha(item["command_table_hash"], "batch_artifact.command_table_hash")
    raw_intents = item["intents"]
    if not isinstance(raw_intents, list) or not raw_intents:
        _fail("TEVS_IR_V4_COMMAND_BATCH_EMPTY", "batch artifact intents must be non-empty")
    intents: list[EffectCommandIntentV4] = []
    for index, raw_intent in enumerate(raw_intents):
        intent = _object(raw_intent, f"batch_artifact.intents[{index}]")
        _exact(intent, {"intent_index", "command_id", "contract_hash", "arguments", "plan_context_hash", "idempotency_key", "intent_hash"}, f"batch_artifact.intents[{index}]")
        intent_index = intent["intent_index"]
        if isinstance(intent_index, bool) or not isinstance(intent_index, int):
            _fail("TEVS_IR_V4_COMMAND_INTENT_ORDER", "intent_index must be integer")
        arguments = intent["arguments"]
        if not isinstance(arguments, list):
            _fail("TEVS_IR_V4_COMMAND_SHAPE", "intent arguments must be an array")
        intents.append(EffectCommandIntentV4(
            intent_index,
            _command_id(intent["command_id"], "intent.command_id"),
            _sha(intent["contract_hash"], "intent.contract_hash"),
            tuple(arguments),
            _sha(intent["plan_context_hash"], "intent.plan_context_hash"),
            _sha(intent["idempotency_key"], "intent.idempotency_key"),
            _sha(intent["intent_hash"], "intent.intent_hash"),
        ))
    batch = EffectCommandBatchV4(plan_context_hash, command_table_hash, tuple(intents), _sha(item["batch_hash"], "batch_artifact.batch_hash"))
    _validate_batch(batch)
    return batch


def planned_effect_transition_to_dict_v4(planned: PlannedEffectTransitionV4) -> dict[str, Any]:
    validate_planned_effect_transition_v4(planned)
    return {
        "schema": "TEV_SCRIPT_EFFECT_PLAN_ARTIFACT_R2_V1",
        "action_hash": planned.action_hash,
        "state_schema_hash": planned.state_schema_hash,
        "capability_table_hash": planned.capability_table_hash,
        "command_table_hash": planned.command_table_hash,
        "scenario_hash": planned.scenario_hash,
        "initial_state_hash": planned.initial_state_hash,
        "arguments_hash": planned.arguments_hash,
        "plan_context_hash": planned.plan_context_hash,
        "capability_transcript": list(planned.capability_transcript),
        "capability_transcript_hash": planned.capability_transcript_hash,
        "proposed_final_state": list(planned.proposed_final_state),
        "proposed_final_state_hash": planned.proposed_final_state_hash,
        "command_batch": effect_command_batch_to_dict_v4(planned.command_batch),
        "evaluation_steps": planned.evaluation_steps,
        "observation_calls": planned.observation_calls,
        "planning_receipt_hash": planned.planning_receipt_hash,
        "artifact_hash": _hash({
            "schema": "TEV_SCRIPT_EFFECT_PLAN_ARTIFACT_R2_CONTENT_V1",
            "planning_receipt_hash": planned.planning_receipt_hash,
            "command_batch_hash": planned.command_batch.batch_hash,
            "proposed_final_state_hash": planned.proposed_final_state_hash,
        }),
    }


def load_planned_effect_transition_v4(raw: Mapping[str, Any]) -> PlannedEffectTransitionV4:
    item = _object(raw, "plan_artifact")
    expected = {
        "schema", "action_hash", "state_schema_hash", "capability_table_hash", "command_table_hash",
        "scenario_hash", "initial_state_hash", "arguments_hash", "plan_context_hash", "capability_transcript",
        "capability_transcript_hash", "proposed_final_state", "proposed_final_state_hash", "command_batch",
        "evaluation_steps", "observation_calls", "planning_receipt_hash", "artifact_hash",
    }
    _exact(item, expected, "plan_artifact")
    if item["schema"] != "TEV_SCRIPT_EFFECT_PLAN_ARTIFACT_R2_V1":
        _fail("TEVS_IR_V4_COMMAND_ARTIFACT_SCHEMA", "unsupported effect plan artifact schema")
    transcript = item["capability_transcript"]
    final_state = item["proposed_final_state"]
    if not isinstance(transcript, list) or not isinstance(final_state, list):
        _fail("TEVS_IR_V4_COMMAND_SHAPE", "plan transcript/state must be arrays")
    steps = item["evaluation_steps"]
    observations = item["observation_calls"]
    if isinstance(steps, bool) or not isinstance(steps, int) or isinstance(observations, bool) or not isinstance(observations, int):
        _fail("TEVS_IR_V4_COMMAND_SHAPE", "plan counters must be integers")
    batch = load_effect_command_batch_v4(_object(item["command_batch"], "plan_artifact.command_batch"))
    planned = PlannedEffectTransitionV4(
        "TEV_SCRIPT_IR_V4_EFFECT_PLANNING_RECEIPT_R2_V1",
        _sha(item["action_hash"], "plan.action_hash"),
        _sha(item["state_schema_hash"], "plan.state_schema_hash"),
        _sha(item["capability_table_hash"], "plan.capability_table_hash"),
        _sha(item["command_table_hash"], "plan.command_table_hash"),
        _sha(item["scenario_hash"], "plan.scenario_hash"),
        _sha(item["initial_state_hash"], "plan.initial_state_hash"),
        _sha(item["arguments_hash"], "plan.arguments_hash"),
        _sha(item["plan_context_hash"], "plan.plan_context_hash"),
        tuple(_object(call, "plan.capability_transcript.call") for call in transcript),
        _sha(item["capability_transcript_hash"], "plan.capability_transcript_hash"),
        tuple(_object(slot, "plan.proposed_final_state.slot") for slot in final_state),
        _sha(item["proposed_final_state_hash"], "plan.proposed_final_state_hash"),
        batch,
        steps,
        observations,
        _sha(item["planning_receipt_hash"], "plan.planning_receipt_hash"),
    )
    validate_planned_effect_transition_v4(planned)
    expected_artifact_hash = _hash({
        "schema": "TEV_SCRIPT_EFFECT_PLAN_ARTIFACT_R2_CONTENT_V1",
        "planning_receipt_hash": planned.planning_receipt_hash,
        "command_batch_hash": planned.command_batch.batch_hash,
        "proposed_final_state_hash": planned.proposed_final_state_hash,
    })
    if _sha(item["artifact_hash"], "plan.artifact_hash") != expected_artifact_hash:
        _fail("TEVS_IR_V4_COMMAND_ARTIFACT_HASH", "effect plan artifact hash mismatch")
    return planned


def effect_provider_descriptor_to_dict_v4(descriptor: EffectProviderDescriptorV4) -> dict[str, Any]:
    _validate_descriptor(descriptor)
    return {
        "schema": "TEV_SCRIPT_EFFECT_PROVIDER_DESCRIPTOR_ARTIFACT_R2_V1",
        "provider_id": descriptor.provider_id,
        "provider_version": descriptor.provider_version,
        "provider_implementation_hash": descriptor.provider_implementation_hash,
        "supported_contract_hashes": list(descriptor.supported_contract_hashes),
        "commit_semantics": descriptor.commit_semantics,
        "descriptor_hash": descriptor.descriptor_hash,
    }


def load_effect_provider_descriptor_v4(raw: Mapping[str, Any]) -> EffectProviderDescriptorV4:
    item = _object(raw, "provider_descriptor")
    _exact(item, {"schema", "provider_id", "provider_version", "provider_implementation_hash", "supported_contract_hashes", "commit_semantics", "descriptor_hash"}, "provider_descriptor")
    if item["schema"] != "TEV_SCRIPT_EFFECT_PROVIDER_DESCRIPTOR_ARTIFACT_R2_V1":
        _fail("TEVS_IR_V4_COMMAND_ARTIFACT_SCHEMA", "unsupported provider descriptor artifact schema")
    supported = item["supported_contract_hashes"]
    if not isinstance(supported, list):
        _fail("TEVS_IR_V4_COMMAND_SHAPE", "supported_contract_hashes must be an array")
    descriptor = EffectProviderDescriptorV4(
        _command_id(item["provider_id"], "provider.provider_id"),
        item["provider_version"] if isinstance(item["provider_version"], str) and item["provider_version"] else _raise("TEVS_IR_V4_COMMAND_PROVIDER", "provider_version must be non-empty"),
        _sha(item["provider_implementation_hash"], "provider.provider_implementation_hash"),
        tuple(_sha(value, "provider.supported_contract_hash") for value in supported),
        item["commit_semantics"],
        _sha(item["descriptor_hash"], "provider.descriptor_hash"),
    )
    _validate_descriptor(descriptor)
    return descriptor


def effect_authority_grant_to_dict_v4(authority: EffectAuthorityGrantV4) -> dict[str, Any]:
    _validate_authority(authority)
    return {
        "schema": "TEV_SCRIPT_EFFECT_AUTHORITY_GRANT_ARTIFACT_R2_V1",
        "provider_descriptor_hash": authority.provider_descriptor_hash,
        "batch_hash": authority.batch_hash,
        "allowed_contract_hashes": list(authority.allowed_contract_hashes),
        "authority_scope_hash": authority.authority_scope_hash,
        "grant_hash": authority.grant_hash,
    }


def load_effect_authority_grant_v4(raw: Mapping[str, Any]) -> EffectAuthorityGrantV4:
    item = _object(raw, "authority_grant")
    _exact(item, {"schema", "provider_descriptor_hash", "batch_hash", "allowed_contract_hashes", "authority_scope_hash", "grant_hash"}, "authority_grant")
    if item["schema"] != "TEV_SCRIPT_EFFECT_AUTHORITY_GRANT_ARTIFACT_R2_V1":
        _fail("TEVS_IR_V4_COMMAND_ARTIFACT_SCHEMA", "unsupported authority grant artifact schema")
    allowed = item["allowed_contract_hashes"]
    if not isinstance(allowed, list):
        _fail("TEVS_IR_V4_COMMAND_SHAPE", "allowed_contract_hashes must be an array")
    authority = EffectAuthorityGrantV4(
        _sha(item["provider_descriptor_hash"], "authority.provider_descriptor_hash"),
        _sha(item["batch_hash"], "authority.batch_hash"),
        tuple(_sha(value, "authority.allowed_contract_hash") for value in allowed),
        _sha(item["authority_scope_hash"], "authority.authority_scope_hash"),
        _sha(item["grant_hash"], "authority.grant_hash"),
    )
    _validate_authority(authority)
    return authority


def effect_command_commit_receipt_to_dict_v4(receipt: EffectCommandBatchCommitReceiptV4) -> dict[str, Any]:
    _validate_commit_receipt(receipt)
    return {
        "schema": "TEV_SCRIPT_EFFECT_COMMAND_COMMIT_ARTIFACT_R2_V1",
        "batch_hash": receipt.batch_hash,
        "plan_context_hash": receipt.plan_context_hash,
        "command_table_hash": receipt.command_table_hash,
        "provider_descriptor_hash": receipt.provider_descriptor_hash,
        "authority_grant_hash": receipt.authority_grant_hash,
        "status": receipt.status,
        "intent_receipts": [_provider_intent_wire(item) for item in receipt.intent_receipts],
        "provider_batch_receipt_hash": receipt.provider_batch_receipt_hash,
        "provider_observation_hash": receipt.provider_observation_hash,
        "receipt_hash": receipt.receipt_hash,
    }


def load_effect_command_commit_receipt_v4(raw: Mapping[str, Any]) -> EffectCommandBatchCommitReceiptV4:
    item = _object(raw, "commit_receipt")
    _exact(item, {"schema", "batch_hash", "plan_context_hash", "command_table_hash", "provider_descriptor_hash", "authority_grant_hash", "status", "intent_receipts", "provider_batch_receipt_hash", "provider_observation_hash", "receipt_hash"}, "commit_receipt")
    if item["schema"] != "TEV_SCRIPT_EFFECT_COMMAND_COMMIT_ARTIFACT_R2_V1":
        _fail("TEVS_IR_V4_COMMAND_ARTIFACT_SCHEMA", "unsupported command commit artifact schema")
    raw_receipts = item["intent_receipts"]
    if not isinstance(raw_receipts, list):
        _fail("TEVS_IR_V4_COMMAND_SHAPE", "commit intent_receipts must be an array")
    receipts = []
    for raw_receipt in raw_receipts:
        child = _object(raw_receipt, "commit_receipt.intent_receipt")
        _exact(child, {"intent_hash", "provider_effect_receipt_hash"}, "commit_receipt.intent_receipt")
        receipts.append(ProviderIntentReceiptV4(_sha(child["intent_hash"], "commit.intent_hash"), _sha(child["provider_effect_receipt_hash"], "commit.provider_effect_receipt_hash")))
    receipt = EffectCommandBatchCommitReceiptV4(
        "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_BATCH_COMMIT_RECEIPT_R2_V1",
        _sha(item["batch_hash"], "commit.batch_hash"),
        _sha(item["plan_context_hash"], "commit.plan_context_hash"),
        _sha(item["command_table_hash"], "commit.command_table_hash"),
        _sha(item["provider_descriptor_hash"], "commit.provider_descriptor_hash"),
        _sha(item["authority_grant_hash"], "commit.authority_grant_hash"),
        item["status"],
        tuple(receipts),
        _sha(item["provider_batch_receipt_hash"], "commit.provider_batch_receipt_hash"),
        _sha(item["provider_observation_hash"], "commit.provider_observation_hash"),
        _sha(item["receipt_hash"], "commit.receipt_hash"),
    )
    _validate_commit_receipt(receipt)
    return receipt


def finalized_effect_transition_to_dict_v4(receipt: FinalizedEffectTransitionReceiptV4) -> dict[str, Any]:
    if not isinstance(receipt, FinalizedEffectTransitionReceiptV4):
        _fail("TEVS_IR_V4_COMMAND_FINALIZE_RECEIPT", "final receipt must be FinalizedEffectTransitionReceiptV4")
    return {
        "schema": "TEV_SCRIPT_EFFECT_FINALIZATION_ARTIFACT_R2_V1",
        "planning_receipt_hash": receipt.planning_receipt_hash,
        "commit_receipt_hash": receipt.commit_receipt_hash,
        "batch_hash": receipt.batch_hash,
        "provider_descriptor_hash": receipt.provider_descriptor_hash,
        "authority_grant_hash": receipt.authority_grant_hash,
        "final_state": list(receipt.final_state),
        "final_state_hash": receipt.final_state_hash,
        "receipt_hash": receipt.receipt_hash,
    }


def _raise(code: str, message: str):
    _fail(code, message)

def _validate_batch(batch: EffectCommandBatchV4) -> None:
    if not isinstance(batch, EffectCommandBatchV4):
        _fail("TEVS_IR_V4_COMMAND_BATCH", "command batch must be EffectCommandBatchV4")
    _sha(batch.plan_context_hash, "batch.plan_context_hash")
    _sha(batch.command_table_hash, "batch.command_table_hash")
    if not batch.intents:
        _fail("TEVS_IR_V4_COMMAND_BATCH_EMPTY", "command batch cannot be empty")
    for index, intent in enumerate(batch.intents):
        if intent.intent_index != index:
            _fail("TEVS_IR_V4_COMMAND_INTENT_ORDER", "intent indices must be contiguous and ordered")
        if intent.plan_context_hash != batch.plan_context_hash:
            _fail("TEVS_IR_V4_COMMAND_INTENT_CONTEXT", "intent plan context differs from batch")
        _command_id(intent.command_id, "intent.command_id")
        _sha(intent.contract_hash, "intent.contract_hash")
        idempotency_payload = {
            "schema": "TEV_SCRIPT_IR_V4_EFFECT_IDEMPOTENCY_KEY_R2_V1",
            "plan_context_hash": intent.plan_context_hash,
            "intent_index": intent.intent_index,
            "command_id": intent.command_id,
            "contract_hash": intent.contract_hash,
            "arguments": list(intent.argument_encodings),
        }
        if intent.idempotency_key != _hash(idempotency_payload):
            _fail("TEVS_IR_V4_COMMAND_IDEMPOTENCY_HASH", "intent idempotency key mismatch")
        intent_payload = {
            "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_INTENT_R2_V1",
            "plan_context_hash": intent.plan_context_hash,
            "intent_index": intent.intent_index,
            "command_id": intent.command_id,
            "contract_hash": intent.contract_hash,
            "arguments": list(intent.argument_encodings),
            "idempotency_key": intent.idempotency_key,
        }
        if intent.intent_hash != _hash(intent_payload):
            _fail("TEVS_IR_V4_COMMAND_INTENT_HASH", "intent hash mismatch")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_BATCH_R2_V1",
        "plan_context_hash": batch.plan_context_hash,
        "command_table_hash": batch.command_table_hash,
        "intents": [_intent_wire(intent) for intent in batch.intents],
    }
    if batch.batch_hash != _hash(payload):
        _fail("TEVS_IR_V4_COMMAND_BATCH_HASH", "command batch hash mismatch")


def _validate_authority(authority: EffectAuthorityGrantV4) -> None:
    if not isinstance(authority, EffectAuthorityGrantV4):
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority must be EffectAuthorityGrantV4")
    _sha(authority.provider_descriptor_hash, "authority.provider_descriptor_hash")
    _sha(authority.batch_hash, "authority.batch_hash")
    scope_hash = _sha(authority.authority_scope_hash, "authority.authority_scope_hash")
    allowed = tuple(authority.allowed_contract_hashes)
    if not allowed or allowed != tuple(sorted(set(allowed))):
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY", "authority allowed contract hashes must be non-empty sorted unique")
    for contract_hash in allowed:
        _sha(contract_hash, "authority.allowed_contract_hash")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_AUTHORITY_GRANT_R2_V1",
        "provider_descriptor_hash": authority.provider_descriptor_hash,
        "batch_hash": authority.batch_hash,
        "allowed_contract_hashes": list(allowed),
        "authority_scope_hash": scope_hash,
    }
    if authority.grant_hash != _hash(payload):
        _fail("TEVS_IR_V4_COMMAND_AUTHORITY_HASH", "authority grant hash mismatch")


def _validate_commit_receipt(receipt: EffectCommandBatchCommitReceiptV4) -> None:
    if not isinstance(receipt, EffectCommandBatchCommitReceiptV4):
        _fail("TEVS_IR_V4_COMMAND_COMMIT_RECEIPT", "commit receipt must be EffectCommandBatchCommitReceiptV4")
    if receipt.status not in {"PASS", "FAIL"}:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_STATUS", "commit receipt status must be PASS or FAIL")
    for value, path in (
        (receipt.batch_hash, "commit.batch_hash"),
        (receipt.plan_context_hash, "commit.plan_context_hash"),
        (receipt.command_table_hash, "commit.command_table_hash"),
        (receipt.provider_descriptor_hash, "commit.provider_descriptor_hash"),
        (receipt.authority_grant_hash, "commit.authority_grant_hash"),
        (receipt.provider_batch_receipt_hash, "commit.provider_batch_receipt_hash"),
        (receipt.provider_observation_hash, "commit.provider_observation_hash"),
    ):
        _sha(value, path)
    if receipt.status == "FAIL" and receipt.intent_receipts:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_ATOMICITY", "failed atomic commit receipt cannot contain committed intents")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_COMMAND_BATCH_COMMIT_RECEIPT_R2_V1",
        "batch_hash": receipt.batch_hash,
        "plan_context_hash": receipt.plan_context_hash,
        "command_table_hash": receipt.command_table_hash,
        "provider_descriptor_hash": receipt.provider_descriptor_hash,
        "authority_grant_hash": receipt.authority_grant_hash,
        "status": receipt.status,
        "intent_receipts": [_provider_intent_wire(item) for item in receipt.intent_receipts],
        "provider_batch_receipt_hash": receipt.provider_batch_receipt_hash,
        "provider_observation_hash": receipt.provider_observation_hash,
    }
    if receipt.receipt_hash != _hash(payload):
        _fail("TEVS_IR_V4_COMMAND_COMMIT_RECEIPT_HASH", "commit receipt hash mismatch")

def _validate_provider_observation(
    observation: ProviderBatchObservationV4,
    batch: EffectCommandBatchV4,
    descriptor: EffectProviderDescriptorV4,
    authority: EffectAuthorityGrantV4,
) -> None:
    if not isinstance(observation, ProviderBatchObservationV4):
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_OBSERVATION", "provider must return ProviderBatchObservationV4")
    expected_payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PROVIDER_BATCH_OBSERVATION_R2_V1",
        "batch_hash": observation.batch_hash,
        "provider_descriptor_hash": observation.provider_descriptor_hash,
        "authority_grant_hash": observation.authority_grant_hash,
        "status": observation.status,
        "intent_receipts": [_provider_intent_wire(item) for item in observation.intent_receipts],
        "provider_batch_receipt_hash": observation.provider_batch_receipt_hash,
    }
    if observation.observation_hash != _hash(expected_payload):
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_OBSERVATION_HASH", "provider observation hash mismatch")
    if observation.batch_hash != batch.batch_hash:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_BATCH", "provider observed a different batch")
    if observation.provider_descriptor_hash != descriptor.descriptor_hash:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_DESCRIPTOR", "provider observation descriptor hash mismatch")
    if observation.authority_grant_hash != authority.grant_hash:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_AUTHORITY", "provider observation authority hash mismatch")
    if observation.status == "PASS":
        expected_intents = tuple(intent.intent_hash for intent in batch.intents)
        observed_intents = tuple(item.intent_hash for item in observation.intent_receipts)
        if observed_intents != expected_intents:
            _fail("TEVS_IR_V4_COMMAND_PROVIDER_INTENTS", "provider PASS observation must cover exact ordered intent set")
        if len(observation.intent_receipts) != len(batch.intents):
            _fail("TEVS_IR_V4_COMMAND_PROVIDER_INTENTS", "provider PASS observation intent count mismatch")
    elif observation.status == "FAIL":
        if observation.intent_receipts:
            _fail("TEVS_IR_V4_COMMAND_PROVIDER_ATOMICITY", "atomic FAIL observation cannot include committed intents")
    else:
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_STATUS", f"unsupported provider status {observation.status!r}")


def _validate_descriptor(descriptor: EffectProviderDescriptorV4) -> None:
    if not isinstance(descriptor, EffectProviderDescriptorV4):
        _fail("TEVS_IR_V4_COMMAND_PROVIDER", "provider descriptor must be EffectProviderDescriptorV4")
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_EFFECT_PROVIDER_DESCRIPTOR_R2_V1",
        "provider_id": descriptor.provider_id,
        "provider_version": descriptor.provider_version,
        "provider_implementation_hash": descriptor.provider_implementation_hash,
        "supported_contract_hashes": list(descriptor.supported_contract_hashes),
        "commit_semantics": descriptor.commit_semantics,
    }
    if descriptor.descriptor_hash != _hash(payload):
        _fail("TEVS_IR_V4_COMMAND_PROVIDER_DESCRIPTOR_HASH", "provider descriptor hash mismatch")


def _intent_wire(intent: EffectCommandIntentV4) -> dict[str, Any]:
    return {
        "intent_index": intent.intent_index,
        "command_id": intent.command_id,
        "contract_hash": intent.contract_hash,
        "arguments": list(intent.argument_encodings),
        "plan_context_hash": intent.plan_context_hash,
        "idempotency_key": intent.idempotency_key,
        "intent_hash": intent.intent_hash,
    }


def _provider_intent_wire(item: ProviderIntentReceiptV4) -> dict[str, str]:
    return {"intent_hash": item.intent_hash, "provider_effect_receipt_hash": item.provider_effect_receipt_hash}


def _storable_type(table: TypeTableV4, value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("TEVS_IR_V4_COMMAND_TYPE", f"{path} must be a type id")
    descriptor = table.require(value, context=path)
    if descriptor.kind == "unit":
        _fail("TEVS_IR_V4_COMMAND_TYPE", f"Unit is not storable at {path}")
    return value


def _local_name(value: Any, path: str) -> str:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None or value.startswith("__tev_"):
        _fail("TEVS_IR_V4_COMMAND_NAME", f"{path} must be a non-reserved local name")
    return value


def _command_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or _COMMAND_ID.fullmatch(value) is None:
        _fail("TEVS_IR_V4_COMMAND_ID", f"{path} is not a stable dotted id")
    return value


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail("TEVS_IR_V4_COMMAND_HASH", f"{path} must be lowercase sha256 hex")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TEVS_IR_V4_COMMAND_SHAPE", f"{path} must be an object")
    return dict(value)


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        _fail("TEVS_IR_V4_COMMAND_SHAPE", f"{path} field set mismatch: {sorted(set(value) ^ expected)}")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
