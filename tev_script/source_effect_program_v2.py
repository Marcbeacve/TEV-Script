from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .generic_types_v2 import GenericRegistryV2
from .ir_v4_effect_commands import (
    EffectActionR2V4,
    EffectCommandTableV4,
    build_effect_action_r2_v4,
    build_effect_command_table_v4,
)
from .ir_v4_effects import (
    OBSERVE_ALL_RESERVATION_POLICY_V4,
    CapabilityTableV4,
    EffectActionV4,
    EffectScenarioV4,
    StateSchemaV4,
    build_capability_table_v4,
    build_effect_action_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
    initial_state_v4,
)
from .program_ir_v4 import build_program_ir_v4_effects, run_program_ir_v4_effects
from .program_ir_v4_effect_commands import (
    build_program_ir_v4_effects_r2,
    plan_program_ir_v4_effects_r2,
)
from .source_collection_literals_v2 import parse_contextual_literal_v2
from .source_program_v2 import lower_expression_v2, tokenize_source_v2

LANGUAGE_VERSION_EFFECTS_V2 = "2.0.0"
MAX_EFFECT_SOURCE_DECLARATIONS_V2 = 4096
MAX_EFFECT_SOURCE_ACTIONS_V2 = 1024
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CAPABILITY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


@dataclass(frozen=True, slots=True)
class EffectStateSourceV2:
    name: str
    type_text: str
    initial_text: str


@dataclass(frozen=True, slots=True)
class EffectCapabilitySourceV2:
    capability_id: str
    parameter_types: tuple[str, ...]
    return_type: str


@dataclass(frozen=True, slots=True)
class EffectCommandSourceV2:
    command_id: str
    parameter_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffectStepSourceV2:
    kind: str
    data: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class EffectActionSourceV2:
    name: str
    parameters: tuple[tuple[str, str], ...]
    steps: tuple[EffectStepSourceV2, ...]


@dataclass(frozen=True, slots=True)
class EffectEntrySourceV2:
    name: str
    action_name: str
    argument_texts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffectSourceProgramV2:
    program_id: str
    language_version: str
    states: tuple[EffectStateSourceV2, ...]
    capabilities: tuple[EffectCapabilitySourceV2, ...]
    actions: tuple[EffectActionSourceV2, ...]
    entry: EffectEntrySourceV2
    commands: tuple[EffectCommandSourceV2, ...] = ()


@dataclass(frozen=True, slots=True)
class CompiledEffectEntryV2:
    name: str
    action_name: str
    action_hash: str
    arguments: tuple[Any, ...]
    argument_encodings: tuple[Any, ...]
    entry_hash: str


@dataclass(frozen=True, slots=True)
class CompiledEffectProgramV2:
    schema: str
    program_id: str
    language_version: str
    semantic_hash: str
    state_schema_hash: str
    initial_state_hash: str
    capability_table_hash: str
    action_hashes: tuple[tuple[str, str], ...]
    entry: CompiledEffectEntryV2
    types: GenericRegistryV2
    states: StateSchemaV4
    capabilities: CapabilityTableV4
    actions: tuple[tuple[str, EffectActionV4], ...]

    def action(self, name: str) -> EffectActionV4:
        for action_name, action in self.actions:
            if action_name == name:
                return action
        _fail("TEVS_V2_EFFECT_ENTRY", f"unknown compiled action {name!r}")


@dataclass(frozen=True, slots=True)
class CompiledEffectCommandProgramV2:
    schema: str
    program_id: str
    language_version: str
    semantic_hash: str
    state_schema_hash: str
    initial_state_hash: str
    capability_table_hash: str
    command_table_hash: str
    action_hashes: tuple[tuple[str, str], ...]
    entry: CompiledEffectEntryV2
    types: GenericRegistryV2
    states: StateSchemaV4
    capabilities: CapabilityTableV4
    commands: EffectCommandTableV4
    actions: tuple[tuple[str, EffectActionR2V4], ...]

    def action(self, name: str) -> EffectActionR2V4:
        for action_name, action in self.actions:
            if action_name == name:
                return action
        _fail("TEVS_V2_EFFECT_R2_ENTRY", f"unknown compiled R2 action {name!r}")


def parse_effect_program_v2(source: str) -> EffectSourceProgramV2:
    return _EffectParser(source).parse()


def compile_effect_program_v2(source: str) -> CompiledEffectProgramV2:
    program = parse_effect_program_v2(source)
    if program.language_version != LANGUAGE_VERSION_EFFECTS_V2:
        _fail("TEVS_V2_EFFECT_VERSION", f"effects compiler requires version {LANGUAGE_VERSION_EFFECTS_V2!r}")
    if program.commands or any(step.kind == "request" for action in program.actions for step in action.steps):
        _fail(
            "TEVS_V2_EFFECT_R2_REQUIRED",
            "physical command/request syntax requires compile_effect_command_program_v2; Effects R1 remains observation-only",
        )
    types = GenericRegistryV2(_base_type_program())

    state_sources = _unique_by_name(program.states, lambda item: item.name, "state")
    state_wire: list[dict[str, Any]] = []
    state_runtime_types: dict[str, str] = {}
    for declaration in sorted(state_sources.values(), key=lambda item: item.name):
        resolved = types.resolve_source_type(declaration.type_text)
        types.materialize_resolved_type(resolved)
        parsed = parse_contextual_literal_v2(
            declaration.initial_text,
            resolved.type_id,
            types.table,
            constructor_names=types.constructor_names(),
        )
        state_runtime_types[declaration.name] = resolved.type_id
        state_wire.append({"name": declaration.name, "type": resolved.type_id, "initial": parsed.encoded})
    states = build_state_schema_v4(state_wire, types.table)

    capability_sources = _unique_by_name(program.capabilities, lambda item: item.capability_id, "capability")
    capability_wire: list[dict[str, Any]] = []
    for declaration in sorted(capability_sources.values(), key=lambda item: item.capability_id):
        parameter_ids: list[str] = []
        for type_text in declaration.parameter_types:
            resolved = types.resolve_source_type(type_text); types.materialize_resolved_type(resolved); parameter_ids.append(resolved.type_id)
        result = types.resolve_source_type(declaration.return_type); types.materialize_resolved_type(result)
        capability_wire.append({
            "capability_id": declaration.capability_id,
            "parameters": parameter_ids,
            "return_type": result.type_id,
            "kind": "observation",
        })
    capabilities = build_capability_table_v4(capability_wire, types.table)

    action_sources = _unique_by_name(program.actions, lambda item: item.name, "action")
    if len(action_sources) > MAX_EFFECT_SOURCE_ACTIONS_V2:
        _fail("TEVS_V2_EFFECT_BUDGET", f"actions exceed {MAX_EFFECT_SOURCE_ACTIONS_V2}")
    compiled_actions: dict[str, EffectActionV4] = {}
    for declaration in sorted(action_sources.values(), key=lambda item: item.name):
        compiled_actions[declaration.name] = _compile_action(
            declaration, types, states, capabilities, state_runtime_types
        )

    selected = compiled_actions.get(program.entry.action_name)
    if selected is None:
        _fail("TEVS_V2_EFFECT_ENTRY", f"entry references unknown action {program.entry.action_name!r}")
    if len(program.entry.argument_texts) != len(selected.parameter_type_ids):
        _fail("TEVS_V2_EFFECT_ENTRY", f"entry expected {len(selected.parameter_type_ids)} arguments, got {len(program.entry.argument_texts)}")
    arguments: list[Any] = []
    encodings: list[Any] = []
    for source_text, type_id in zip(program.entry.argument_texts, selected.parameter_type_ids, strict=True):
        parsed = parse_contextual_literal_v2(source_text, type_id, types.table, constructor_names=types.constructor_names())
        arguments.append(parsed.value); encodings.append(parsed.encoded)
    entry_payload = {
        "schema": "TEV_SCRIPT_EFFECT_ENTRY_V2_IDENTITY_V1",
        "name": program.entry.name,
        "action_name": selected.action_id,
        "action_hash": selected.action_hash,
        "arguments": [
            {"type": type_id, "value": encoded}
            for type_id, encoded in zip(selected.parameter_type_ids, encodings, strict=True)
        ],
    }
    entry = CompiledEffectEntryV2(
        program.entry.name, selected.action_id, selected.action_hash,
        tuple(arguments), tuple(encodings), _hash(entry_payload),
    )
    action_hashes = tuple((name, action.action_hash) for name, action in sorted(compiled_actions.items()))
    identity = {
        "schema": "TEV_SCRIPT_EFFECT_SOURCE_V2_SEMANTIC_IDENTITY_V1",
        "program_id": program.program_id,
        "language_version": program.language_version,
        "state_schema_hash": states.schema_hash,
        "initial_state_hash": states.initial_state_hash,
        "capability_table_hash": capabilities.table_hash,
        "actions": [{"name": name, "action_hash": action_hash} for name, action_hash in action_hashes],
        "entry_hash": entry.entry_hash,
    }
    return CompiledEffectProgramV2(
        "TEV_SCRIPT_COMPILED_EFFECT_PROGRAM_V2_V1",
        program.program_id, program.language_version, _hash(identity),
        states.schema_hash, states.initial_state_hash, capabilities.table_hash,
        action_hashes, entry, types, states, capabilities, tuple(sorted(compiled_actions.items())),
    )



def compile_effect_command_program_v2(source: str) -> CompiledEffectCommandProgramV2:
    program = parse_effect_program_v2(source)
    if program.language_version != LANGUAGE_VERSION_EFFECTS_V2:
        _fail("TEVS_V2_EFFECT_VERSION", f"effects R2 compiler requires version {LANGUAGE_VERSION_EFFECTS_V2!r}")
    if not program.commands:
        _fail("TEVS_V2_EFFECT_R2_COMMANDS", "Effects R2 source requires at least one command declaration")
    if not any(step.kind == "request" for action in program.actions for step in action.steps):
        _fail("TEVS_V2_EFFECT_R2_REQUIRED", "Effects R2 source requires at least one request statement")

    types = GenericRegistryV2(_base_type_program())
    state_sources = _unique_by_name(program.states, lambda item: item.name, "state")
    state_wire: list[dict[str, Any]] = []
    state_runtime_types: dict[str, str] = {}
    for declaration in sorted(state_sources.values(), key=lambda item: item.name):
        resolved = types.resolve_source_type(declaration.type_text)
        types.materialize_resolved_type(resolved)
        parsed = parse_contextual_literal_v2(
            declaration.initial_text,
            resolved.type_id,
            types.table,
            constructor_names=types.constructor_names(),
        )
        state_runtime_types[declaration.name] = resolved.type_id
        state_wire.append({"name": declaration.name, "type": resolved.type_id, "initial": parsed.encoded})
    states = build_state_schema_v4(state_wire, types.table)

    capability_sources = _unique_by_name(program.capabilities, lambda item: item.capability_id, "capability")
    capability_wire: list[dict[str, Any]] = []
    for declaration in sorted(capability_sources.values(), key=lambda item: item.capability_id):
        parameter_ids: list[str] = []
        for type_text in declaration.parameter_types:
            resolved = types.resolve_source_type(type_text)
            types.materialize_resolved_type(resolved)
            parameter_ids.append(resolved.type_id)
        result = types.resolve_source_type(declaration.return_type)
        types.materialize_resolved_type(result)
        capability_wire.append({
            "capability_id": declaration.capability_id,
            "parameters": parameter_ids,
            "return_type": result.type_id,
            "kind": "observation",
        })
    capabilities = build_capability_table_v4(capability_wire, types.table)

    command_sources = _unique_by_name(program.commands, lambda item: item.command_id, "command")
    command_wire: list[dict[str, Any]] = []
    for declaration in sorted(command_sources.values(), key=lambda item: item.command_id):
        parameter_ids: list[str] = []
        for type_text in declaration.parameter_types:
            resolved = types.resolve_source_type(type_text)
            types.materialize_resolved_type(resolved)
            parameter_ids.append(resolved.type_id)
        command_wire.append({
            "command_id": declaration.command_id,
            "parameters": parameter_ids,
            "kind": "effect_command",
            "idempotency_policy": "content_addressed_v1",
        })
    commands = build_effect_command_table_v4(command_wire, types.table)

    action_sources = _unique_by_name(program.actions, lambda item: item.name, "action")
    if len(action_sources) > MAX_EFFECT_SOURCE_ACTIONS_V2:
        _fail("TEVS_V2_EFFECT_BUDGET", f"actions exceed {MAX_EFFECT_SOURCE_ACTIONS_V2}")
    compiled_actions: dict[str, EffectActionR2V4] = {}
    for declaration in sorted(action_sources.values(), key=lambda item: item.name):
        compiled_actions[declaration.name] = _compile_action_r2(
            declaration, types, states, capabilities, commands, state_runtime_types
        )

    selected = compiled_actions.get(program.entry.action_name)
    if selected is None:
        _fail("TEVS_V2_EFFECT_R2_ENTRY", f"entry references unknown R2 action {program.entry.action_name!r}")
    if len(program.entry.argument_texts) != len(selected.parameter_type_ids):
        _fail("TEVS_V2_EFFECT_R2_ENTRY", f"entry expected {len(selected.parameter_type_ids)} arguments, got {len(program.entry.argument_texts)}")
    arguments: list[Any] = []
    encodings: list[Any] = []
    for source_text, type_id in zip(program.entry.argument_texts, selected.parameter_type_ids, strict=True):
        parsed = parse_contextual_literal_v2(source_text, type_id, types.table, constructor_names=types.constructor_names())
        arguments.append(parsed.value)
        encodings.append(parsed.encoded)
    entry_payload = {
        "schema": "TEV_SCRIPT_EFFECT_COMMAND_ENTRY_V2_IDENTITY_V1",
        "name": program.entry.name,
        "action_name": selected.action_id,
        "action_hash": selected.action_hash,
        "arguments": [
            {"type": type_id, "value": encoded}
            for type_id, encoded in zip(selected.parameter_type_ids, encodings, strict=True)
        ],
    }
    entry = CompiledEffectEntryV2(
        program.entry.name,
        selected.action_id,
        selected.action_hash,
        tuple(arguments),
        tuple(encodings),
        _hash(entry_payload),
    )
    action_hashes = tuple((name, action.action_hash) for name, action in sorted(compiled_actions.items()))
    identity = {
        "schema": "TEV_SCRIPT_EFFECT_COMMAND_SOURCE_V2_SEMANTIC_IDENTITY_V1",
        "program_id": program.program_id,
        "language_version": program.language_version,
        "state_schema_hash": states.schema_hash,
        "initial_state_hash": states.initial_state_hash,
        "capability_table_hash": capabilities.table_hash,
        "command_table_hash": commands.table_hash,
        "actions": [{"name": name, "action_hash": action_hash} for name, action_hash in action_hashes],
        "entry_hash": entry.entry_hash,
    }
    return CompiledEffectCommandProgramV2(
        "TEV_SCRIPT_COMPILED_EFFECT_COMMAND_PROGRAM_V2_V1",
        program.program_id,
        program.language_version,
        _hash(identity),
        states.schema_hash,
        states.initial_state_hash,
        capabilities.table_hash,
        commands.table_hash,
        action_hashes,
        entry,
        types,
        states,
        capabilities,
        commands,
        tuple(sorted(compiled_actions.items())),
    )


def build_effect_command_program_ir_v4(
    compiled: CompiledEffectCommandProgramV2,
    scenario_raw: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(compiled, CompiledEffectCommandProgramV2):
        _fail("TEVS_V2_EFFECT_R2_BUILD", "build_effect_command_program_ir_v4 requires CompiledEffectCommandProgramV2")
    scenario = build_effect_scenario_v4(scenario_raw, compiled.types.table, compiled.capabilities)
    state = initial_state_v4(compiled.states) if current_state is None else dict(current_state)
    action = compiled.action(compiled.entry.action_name)
    return build_program_ir_v4_effects_r2(
        program_id=compiled.program_id,
        source_semantic_hash=compiled.semantic_hash,
        table=compiled.types.table,
        states=compiled.states,
        capabilities=compiled.capabilities,
        commands=compiled.commands,
        action=action,
        scenario=scenario,
        current_state=state,
        arguments=compiled.entry.arguments,
    )


def compile_and_plan_effect_command_program_v2(
    source: str,
    scenario_raw: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any] | None = None,
):
    compiled = compile_effect_command_program_v2(source)
    program_ir = build_effect_command_program_ir_v4(compiled, scenario_raw, current_state=current_state)
    return compiled, program_ir, plan_program_ir_v4_effects_r2(program_ir)

def build_effect_program_ir_v4(
    compiled: CompiledEffectProgramV2,
    scenario_raw: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(compiled, CompiledEffectProgramV2):
        _fail("TEVS_V2_EFFECT_BUILD", "build_effect_program_ir_v4 requires CompiledEffectProgramV2")
    scenario = build_effect_scenario_v4(scenario_raw, compiled.types.table, compiled.capabilities)
    state = initial_state_v4(compiled.states) if current_state is None else dict(current_state)
    action = compiled.action(compiled.entry.action_name)
    return build_program_ir_v4_effects(
        program_id=compiled.program_id,
        source_semantic_hash=compiled.semantic_hash,
        table=compiled.types.table,
        states=compiled.states,
        capabilities=compiled.capabilities,
        action=action,
        scenario=scenario,
        current_state=state,
        arguments=compiled.entry.arguments,
    )


def compile_and_run_effect_program_v2(
    source: str,
    scenario_raw: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any] | None = None,
):
    compiled = compile_effect_program_v2(source)
    program_ir = build_effect_program_ir_v4(compiled, scenario_raw, current_state=current_state)
    return compiled, program_ir, run_program_ir_v4_effects(program_ir)


def effect_scenario_skeleton_v2(compiled: CompiledEffectProgramV2) -> dict[str, Any]:
    return {
        "capability_table_hash": compiled.capabilities.table_hash,
        "capabilities": [
            {"capability_id": contract.capability_id, "contract_hash": contract.contract_hash, "calls": []}
            for contract in compiled.capabilities.contracts
        ],
    }


def _compile_action(
    declaration: EffectActionSourceV2,
    types: GenericRegistryV2,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    state_runtime_types: Mapping[str, str],
) -> EffectActionV4:
    parameter_runtime: dict[str, str] = {}
    parameter_wire: list[dict[str, str]] = []
    for name, type_text in declaration.parameters:
        if name in state_runtime_types or name in parameter_runtime:
            _fail("TEVS_V2_EFFECT_PARAMETER", f"duplicate/state-shadowing action parameter {name!r}")
        resolved = types.resolve_source_type(type_text); types.materialize_resolved_type(resolved)
        parameter_runtime[name] = resolved.type_id
        parameter_wire.append({"name": name, "type": resolved.type_id})

    local_runtime: dict[str, str] = {}
    steps: list[dict[str, Any]] = []
    for index, step in enumerate(declaration.steps):
        symbols = {**state_runtime_types, **parameter_runtime, **local_runtime}
        parameters = tuple(sorted(symbols.items()))
        if step.kind == "observe":
            bind, capability_id, argument_texts = step.data
            if bind in symbols:
                _fail("TEVS_V2_EFFECT_LOCAL", f"duplicate/shadowing local {bind!r}")
            contract = capabilities.require(capability_id)
            if len(argument_texts) != len(contract.parameter_type_ids):
                _fail("TEVS_V2_EFFECT_OBSERVE", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
            arguments = [
                _effectize(
                    lower_expression_v2(text, parameters=parameters, expected_type=expected).ir,
                    state_runtime_types, parameter_runtime, local_runtime,
                )
                for text, expected in zip(argument_texts, contract.parameter_type_ids, strict=True)
            ]
            steps.append({"op":"OBSERVE","capability_id":capability_id,"arguments":arguments,"bind":bind})
            local_runtime[bind] = contract.return_type_id
        elif step.kind == "observe_all":
            (raw_observations,) = step.data
            pending: dict[str, str] = {}
            observations: list[dict[str, Any]] = []
            for bind, capability_id, argument_texts in raw_observations:
                if bind in symbols or bind in pending:
                    _fail("TEVS_V2_EFFECT_LOCAL", f"duplicate/shadowing observe-all local {bind!r}")
                contract = capabilities.require(capability_id)
                if len(argument_texts) != len(contract.parameter_type_ids):
                    _fail("TEVS_V2_EFFECT_OBSERVE", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
                arguments = [
                    _effectize(
                        lower_expression_v2(text, parameters=parameters, expected_type=expected).ir,
                        state_runtime_types, parameter_runtime, local_runtime,
                    )
                    for text, expected in zip(argument_texts, contract.parameter_type_ids, strict=True)
                ]
                observations.append({"bind":bind,"capability_id":capability_id,"arguments":arguments})
                pending[bind] = contract.return_type_id
            steps.append({
                "op":"OBSERVE_ALL",
                "reservation_policy":OBSERVE_ALL_RESERVATION_POLICY_V4,
                "observations":observations,
            })
            local_runtime.update(pending)
        elif step.kind == "let":
            name, type_text, expression_text = step.data
            if name in symbols:
                _fail("TEVS_V2_EFFECT_LOCAL", f"duplicate/shadowing local {name!r}")
            resolved = types.resolve_source_type(type_text); types.materialize_resolved_type(resolved)
            lowered = lower_expression_v2(expression_text, parameters=parameters, expected_type=resolved.type_id)
            steps.append({"op":"LET_LOCAL","name":name,"type":resolved.type_id,"value":_effectize(lowered.ir,state_runtime_types,parameter_runtime,local_runtime)})
            local_runtime[name] = resolved.type_id
        elif step.kind == "set":
            state_name, expression_text = step.data
            expected = state_runtime_types.get(state_name)
            if expected is None:
                _fail("TEVS_V2_EFFECT_STATE", f"set references unknown state {state_name!r}")
            lowered = lower_expression_v2(expression_text, parameters=parameters, expected_type=expected)
            steps.append({"op":"SET_STATE","state":state_name,"value":_effectize(lowered.ir,state_runtime_types,parameter_runtime,local_runtime)})
        elif step.kind == "assert":
            (expression_text,) = step.data
            lowered = lower_expression_v2(expression_text, parameters=parameters, expected_type="Bool")
            steps.append({"op":"ASSERT","condition":_effectize(lowered.ir,state_runtime_types,parameter_runtime,local_runtime)})
        else:
            raise AssertionError(f"parsed effect step {step.kind!r}")
    return build_effect_action_v4(
        {"action_id":declaration.name,"parameters":parameter_wire,"steps":steps},
        types.table, states, capabilities,
    )



def _compile_action_r2(
    declaration: EffectActionSourceV2,
    types: GenericRegistryV2,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    commands: EffectCommandTableV4,
    state_runtime_types: Mapping[str, str],
) -> EffectActionR2V4:
    parameter_runtime: dict[str, str] = {}
    parameter_wire: list[dict[str, str]] = []
    for name, type_text in declaration.parameters:
        if name in state_runtime_types or name in parameter_runtime:
            _fail("TEVS_V2_EFFECT_PARAMETER", f"duplicate/state-shadowing R2 action parameter {name!r}")
        resolved = types.resolve_source_type(type_text)
        types.materialize_resolved_type(resolved)
        parameter_runtime[name] = resolved.type_id
        parameter_wire.append({"name": name, "type": resolved.type_id})

    local_runtime: dict[str, str] = {}
    steps: list[dict[str, Any]] = []
    for step in declaration.steps:
        symbols = {**state_runtime_types, **parameter_runtime, **local_runtime}
        parameters = tuple(sorted(symbols.items()))
        if step.kind == "observe":
            bind, capability_id, argument_texts = step.data
            if bind in symbols:
                _fail("TEVS_V2_EFFECT_LOCAL", f"duplicate/shadowing local {bind!r}")
            contract = capabilities.require(capability_id)
            if len(argument_texts) != len(contract.parameter_type_ids):
                _fail("TEVS_V2_EFFECT_OBSERVE", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
            arguments = [
                _effectize(
                    lower_expression_v2(text, parameters=parameters, expected_type=expected).ir,
                    state_runtime_types,
                    parameter_runtime,
                    local_runtime,
                )
                for text, expected in zip(argument_texts, contract.parameter_type_ids, strict=True)
            ]
            steps.append({"op": "OBSERVE", "capability_id": capability_id, "arguments": arguments, "bind": bind})
            local_runtime[bind] = contract.return_type_id
        elif step.kind == "observe_all":
            (raw_observations,) = step.data
            pending: dict[str, str] = {}
            observations: list[dict[str, Any]] = []
            for bind, capability_id, argument_texts in raw_observations:
                if bind in symbols or bind in pending:
                    _fail("TEVS_V2_EFFECT_LOCAL", f"duplicate/shadowing R2 observe-all local {bind!r}")
                contract = capabilities.require(capability_id)
                if len(argument_texts) != len(contract.parameter_type_ids):
                    _fail("TEVS_V2_EFFECT_OBSERVE", f"{capability_id} expects {len(contract.parameter_type_ids)} arguments")
                arguments = [
                    _effectize(
                        lower_expression_v2(text, parameters=parameters, expected_type=expected).ir,
                        state_runtime_types,
                        parameter_runtime,
                        local_runtime,
                    )
                    for text, expected in zip(argument_texts, contract.parameter_type_ids, strict=True)
                ]
                observations.append({"bind": bind, "capability_id": capability_id, "arguments": arguments})
                pending[bind] = contract.return_type_id
            steps.append({
                "op": "OBSERVE_ALL",
                "reservation_policy": OBSERVE_ALL_RESERVATION_POLICY_V4,
                "observations": observations,
            })
            local_runtime.update(pending)
        elif step.kind == "let":
            name, type_text, expression_text = step.data
            if name in symbols:
                _fail("TEVS_V2_EFFECT_LOCAL", f"duplicate/shadowing local {name!r}")
            resolved = types.resolve_source_type(type_text)
            types.materialize_resolved_type(resolved)
            lowered = lower_expression_v2(expression_text, parameters=parameters, expected_type=resolved.type_id)
            steps.append({"op": "LET_LOCAL", "name": name, "type": resolved.type_id, "value": _effectize(lowered.ir, state_runtime_types, parameter_runtime, local_runtime)})
            local_runtime[name] = resolved.type_id
        elif step.kind == "set":
            state_name, expression_text = step.data
            expected = state_runtime_types.get(state_name)
            if expected is None:
                _fail("TEVS_V2_EFFECT_STATE", f"set references unknown state {state_name!r}")
            lowered = lower_expression_v2(expression_text, parameters=parameters, expected_type=expected)
            steps.append({"op": "SET_STATE", "state": state_name, "value": _effectize(lowered.ir, state_runtime_types, parameter_runtime, local_runtime)})
        elif step.kind == "assert":
            (expression_text,) = step.data
            lowered = lower_expression_v2(expression_text, parameters=parameters, expected_type="Bool")
            steps.append({"op": "ASSERT", "condition": _effectize(lowered.ir, state_runtime_types, parameter_runtime, local_runtime)})
        elif step.kind == "request":
            command_id, argument_texts = step.data
            contract = commands.require(command_id)
            if len(argument_texts) != len(contract.parameter_type_ids):
                _fail("TEVS_V2_EFFECT_R2_REQUEST", f"{command_id} expects {len(contract.parameter_type_ids)} arguments")
            arguments = [
                _effectize(
                    lower_expression_v2(text, parameters=parameters, expected_type=expected).ir,
                    state_runtime_types,
                    parameter_runtime,
                    local_runtime,
                )
                for text, expected in zip(argument_texts, contract.parameter_type_ids, strict=True)
            ]
            steps.append({"op": "REQUEST_EFFECT", "command_id": command_id, "arguments": arguments})
        else:
            raise AssertionError(f"parsed R2 effect step {step.kind!r}")
    return build_effect_action_r2_v4(
        {"action_id": declaration.name, "parameters": parameter_wire, "steps": steps},
        types.table,
        states,
        capabilities,
        commands,
    )

def _effectize(
    value: Any,
    state_types: Mapping[str, str],
    parameter_types: Mapping[str, str],
    local_types: Mapping[str, str],
    *,
    bound: frozenset[str] = frozenset(),
) -> Any:
    if isinstance(value, Mapping):
        node = dict(value)
        op = node.get("op")
        if op == "PARAM":
            name = node.get("name")
            if isinstance(name, str) and name not in bound:
                if name in state_types: return {"op":"LOAD_STATE","name":name,"type":state_types[name]}
                if name in parameter_types: return {"op":"LOAD_PARAM","name":name,"type":parameter_types[name]}
                if name in local_types: return {"op":"LOAD_LOCAL","name":name,"type":local_types[name]}
            return node
        if op == "LET":
            rewritten = dict(node)
            rewritten["value"] = _effectize(node["value"],state_types,parameter_types,local_types,bound=bound)
            rewritten["body"] = _effectize(node["body"],state_types,parameter_types,local_types,bound=bound|frozenset({str(node["name"])}))
            return rewritten
        if op == "FOR_FOLD":
            names = {str(node["item_name"]), str(node["accumulator_name"])}
            if node.get("key_name") is not None: names.add(str(node["key_name"]))
            if node.get("value_name") is not None: names.add(str(node["value_name"]))
            rewritten = dict(node)
            for key, child in node.items():
                rewritten[key] = _effectize(child,state_types,parameter_types,local_types,bound=bound|frozenset(names)) if key == "body" else _effectize(child,state_types,parameter_types,local_types,bound=bound)
            return rewritten
        if op == "WHILE_FOLD":
            name = str(node["accumulator_name"])
            rewritten = dict(node)
            for key, child in node.items():
                rewritten[key] = _effectize(child,state_types,parameter_types,local_types,bound=bound|frozenset({name})) if key in {"condition","body"} else _effectize(child,state_types,parameter_types,local_types,bound=bound)
            return rewritten
        return {key:_effectize(child,state_types,parameter_types,local_types,bound=bound) for key, child in node.items()}
    if isinstance(value, list):
        return [_effectize(child,state_types,parameter_types,local_types,bound=bound) for child in value]
    return value


class _EffectParser:
    def __init__(self, source: str) -> None:
        if not isinstance(source, str): _fail("TEVS_V2_EFFECT_SOURCE", "source must be text")
        self.source = source
        self.tokens = list(tokenize_source_v2(source))
        self.index = 0
        self.declarations = 0

    def parse(self) -> EffectSourceProgramV2:
        self._word("script"); program_id=self._local(); self._word("version"); version=self._expect("STRING").value; self._expect("SEMI")
        states=[]; capabilities=[]; actions=[]; commands=[]; entry=None
        while not self._at("EOF"):
            self.declarations += 1
            if self.declarations > MAX_EFFECT_SOURCE_DECLARATIONS_V2: _fail("TEVS_V2_EFFECT_BUDGET", "effect source declaration budget exhausted")
            if self._is_word("state"): states.append(self._state()); continue
            if self._is_word("capability"): capabilities.append(self._capability()); continue
            if self._is_word("command"): commands.append(self._command()); continue
            if self._is_word("action"): actions.append(self._action()); continue
            if self._is_word("entry"):
                if entry is not None: _fail("TEVS_V2_EFFECT_ENTRY", "effects source requires exactly one entry")
                entry=self._entry(); continue
            _fail("TEVS_V2_EFFECT_DECL", f"unexpected top-level token {self._current().text!r}")
        if entry is None: _fail("TEVS_V2_EFFECT_ENTRY", "effects source requires exactly one entry")
        return EffectSourceProgramV2(program_id,str(version),tuple(states),tuple(capabilities),tuple(actions),entry,tuple(commands))

    def _state(self):
        self._word("state"); name=self._local(); self._expect("COLON"); type_text=self._type_until({"EQUAL"}); self._expect("EQUAL"); initial=self._raw_until({"SEMI"}); self._expect("SEMI")
        return EffectStateSourceV2(name,type_text,initial)

    def _capability(self):
        self._word("capability"); self._word("observation"); capability_id=self._capability_id(); self._expect("LPAREN")
        params=[]
        if not self._at("RPAREN"):
            while True:
                params.append(self._type_until({"COMMA","RPAREN"}))
                if not self._match("COMMA"): break
        self._expect("RPAREN"); self._expect("ARROW"); result=self._type_until({"SEMI"}); self._expect("SEMI")
        return EffectCapabilitySourceV2(capability_id,tuple(params),result)

    def _command(self):
        self._word("command"); command_id=self._capability_id(); self._expect("LPAREN")
        params=[]
        if not self._at("RPAREN"):
            while True:
                params.append(self._type_until({"COMMA","RPAREN"}))
                if not self._match("COMMA"): break
        self._expect("RPAREN"); self._expect("SEMI")
        return EffectCommandSourceV2(command_id,tuple(params))

    def _action(self):
        self._word("action"); name=self._local(); self._expect("LPAREN")
        params=[]
        if not self._at("RPAREN"):
            while True:
                p=self._local(); self._expect("COLON"); t=self._type_until({"COMMA","RPAREN"}); params.append((p,t))
                if not self._match("COMMA"): break
        self._expect("RPAREN"); self._expect("LBRACE")
        steps=[]
        while not self._at("RBRACE"):
            if self._is_word("observe"):
                self._advance()
                if self._is_word("all"):
                    self._advance(); self._expect("LBRACE")
                    observations=[]
                    while not self._at("RBRACE"):
                        bind=self._local(); self._expect("EQUAL"); cap=self._capability_id(); self._expect("LPAREN"); args=self._raw_arguments(); self._expect("RPAREN"); self._expect("SEMI")
                        observations.append((bind,cap,args))
                    self._expect("RBRACE")
                    if not observations: _fail("TEVS_V2_EFFECT_OBSERVE_ALL", "observe all requires at least one observation")
                    steps.append(EffectStepSourceV2("observe_all",(tuple(observations),)))
                else:
                    bind=self._local(); self._expect("EQUAL"); cap=self._capability_id(); self._expect("LPAREN"); args=self._raw_arguments(); self._expect("RPAREN"); self._expect("SEMI")
                    steps.append(EffectStepSourceV2("observe",(bind,cap,args)))
            elif self._is_word("let"):
                self._advance(); local=self._local(); self._expect("COLON"); t=self._type_until({"EQUAL"}); self._expect("EQUAL"); expr=self._raw_until({"SEMI"}); self._expect("SEMI")
                steps.append(EffectStepSourceV2("let",(local,t,expr)))
            elif self._is_word("set"):
                self._advance(); state=self._local(); self._expect("EQUAL"); expr=self._raw_until({"SEMI"}); self._expect("SEMI")
                steps.append(EffectStepSourceV2("set",(state,expr)))
            elif self._is_word("assert"):
                self._advance(); expr=self._raw_until({"SEMI"}); self._expect("SEMI"); steps.append(EffectStepSourceV2("assert",(expr,)))
            elif self._is_word("request"):
                self._advance(); command=self._capability_id(); self._expect("LPAREN"); args=self._raw_arguments(); self._expect("RPAREN"); self._expect("SEMI")
                steps.append(EffectStepSourceV2("request",(command,args)))
            else:
                _fail("TEVS_V2_EFFECT_STEP", f"unexpected action token {self._current().text!r}")
        self._expect("RBRACE")
        if not steps: _fail("TEVS_V2_EFFECT_ACTION", f"action {name!r} requires at least one step")
        return EffectActionSourceV2(name,tuple(params),tuple(steps))

    def _entry(self):
        self._word("entry"); name=self._local(); self._expect("EQUAL"); action=self._local(); self._expect("LPAREN"); args=self._raw_arguments(); self._expect("RPAREN"); self._expect("SEMI")
        return EffectEntrySourceV2(name,action,args)

    def _raw_arguments(self):
        result=[]
        if self._at("RPAREN"): return ()
        while True:
            result.append(self._raw_until({"COMMA","RPAREN"}))
            if not self._match("COMMA"): break
        return tuple(result)

    def _raw_until(self, stops: set[str]) -> str:
        start=self.index; paren=bracket=brace=angle=0
        while True:
            token=self._current()
            if token.kind=="EOF": _fail("TEVS_V2_EFFECT_SYNTAX", "unterminated expression")
            if paren==bracket==brace==angle==0 and token.kind in stops: break
            if token.kind=="LPAREN": paren+=1
            elif token.kind=="RPAREN":
                if paren==0 and "RPAREN" in stops: break
                paren-=1
            elif token.kind=="LBRACKET": bracket+=1
            elif token.kind=="RBRACKET": bracket-=1
            elif token.kind=="LBRACE": brace+=1
            elif token.kind=="RBRACE": brace-=1
            elif token.kind=="LT": angle+=1
            elif token.kind=="GT" and angle>0: angle-=1
            if min(paren,bracket,brace,angle)<0: _fail("TEVS_V2_EFFECT_SYNTAX", "unbalanced expression")
            self._advance()
        if self.index==start or any((paren,bracket,brace,angle)): _fail("TEVS_V2_EFFECT_SYNTAX", "empty or unbalanced expression")
        first=self.tokens[start]; last=self.tokens[self.index-1]
        return self.source[first.start:last.end].strip()

    def _type_until(self, stops: set[str]) -> str:
        start=self.index; angle=0
        while True:
            token=self._current()
            if token.kind=="EOF": _fail("TEVS_V2_EFFECT_TYPE", "unterminated type")
            if token.kind=="GE" and angle>0 and "EQUAL" in stops:
                cls=token.__class__
                self.tokens[self.index:self.index+1]=[cls("GT",">",None,token.start,token.start+1),cls("EQUAL","=",None,token.start+1,token.end)]
                token=self._current()
            if angle==0 and token.kind in stops: break
            if token.kind=="LT": angle+=1
            elif token.kind=="GT":
                if angle==0: _fail("TEVS_V2_EFFECT_TYPE", "unbalanced > in type")
                angle-=1
            self._advance()
        if self.index==start or angle!=0: _fail("TEVS_V2_EFFECT_TYPE", "empty or unbalanced type")
        return "".join(token.text for token in self.tokens[start:self.index])

    def _current(self): return self.tokens[self.index]
    def _at(self,kind): return self._current().kind==kind
    def _advance(self): token=self._current(); self.index+=1; return token
    def _match(self,kind):
        if self._at(kind): self.index+=1; return True
        return False
    def _expect(self,kind):
        token=self._current()
        if token.kind!=kind: _fail("TEVS_V2_EFFECT_SYNTAX",f"expected {kind}, got {token.kind} {token.text!r} at offset {token.start}")
        self.index+=1; return token
    def _is_word(self,word): return self._at("IDENT") and self._current().text==word
    def _word(self,word):
        token=self._expect("IDENT")
        if token.text!=word: _fail("TEVS_V2_EFFECT_SYNTAX",f"expected {word!r}, got {token.text!r}")
    def _local(self):
        value=self._expect("IDENT").text
        if _NAME.fullmatch(value) is None or value.startswith("__tev_"): _fail("TEVS_V2_EFFECT_NAME",f"invalid local name {value!r}")
        return value
    def _capability_id(self):
        value=self._expect("IDENT").text
        if _CAPABILITY.fullmatch(value) is None: _fail("TEVS_V2_EFFECT_CAPABILITY",f"invalid capability id {value!r}")
        return value


def _unique_by_name(items, key, category):
    result={}
    for item in items:
        name=key(item)
        if name in result: _fail("TEVS_V2_EFFECT_DUPLICATE",f"duplicate {category} {name!r}")
        result[name]=item
    return result


def _base_type_program():
    return {
        "boundary":{"maximum_value_nesting":128},
        "types":[
            {"type_id":"Bool","kind":"primitive"},
            {"type_id":"Int","kind":"primitive"},
            {"type_id":"Rat","kind":"primitive"},
            {"type_id":"Text","kind":"primitive"},
            {"type_id":"Unit","kind":"unit"},
            {"type_id":"Vec2","kind":"primitive"},
            {"type_id":"Vec3","kind":"primitive"},
        ],
    }


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code,message): raise TevScriptError(code,message)
