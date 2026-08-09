from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_values import decode_v3_value, encode_v3_value
from .runtime_v3 import EmittedEventV3, ScriptRuntimeV3

_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class IrV3ConformanceReceiptBundle:
    receipt: dict[str, object]
    canonical_json: str
    receipt_hash: str


@dataclass(slots=True)
class _CapabilityScript:
    capability_id: str
    parameters: tuple[str, ...]
    return_type: str
    calls: list[dict[str, object]]
    cursor: int = 0


class _ScenarioHost:
    def __init__(
        self,
        runtime: ScriptRuntimeV3,
        scenario_scripts: list[dict[str, object]],
    ) -> None:
        self.runtime = runtime
        self.contracts = _global_capability_contracts(runtime.ir)
        self.scripts: dict[str, _CapabilityScript] = {}
        self.transcript: list[dict[str, object]] = []
        previous_id: str | None = None
        for index, raw in enumerate(scenario_scripts):
            path = f"$.capabilities[{index}]"
            item = _object(raw, path)
            _exact_keys(item, path, {"capability_id", "calls"})
            capability_id = _stable(item["capability_id"], path + ".capability_id")
            if capability_id in self.scripts:
                _fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_DUPLICATE", path, f"duplicate capability script {capability_id!r}")
            if previous_id is not None and capability_id <= previous_id:
                _fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_ORDER", path, "capability scripts must be strictly sorted by id")
            previous_id = capability_id
            contract = self.contracts.get(capability_id)
            if contract is None:
                _fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_UNKNOWN", path, f"scenario scripts undeclared capability {capability_id!r}")
            parameters, return_type, _kind = contract
            calls = _array(item["calls"], path + ".calls", 0, 4096)
            for call_index, call in enumerate(calls):
                _validate_scripted_call(
                    _object(call, f"{path}.calls[{call_index}]"),
                    parameters,
                    return_type,
                    runtime,
                    f"{path}.calls[{call_index}]",
                )
            self.scripts[capability_id] = _CapabilityScript(
                capability_id,
                parameters,
                return_type,
                calls,
            )

    def bindings(self) -> dict[str, Any]:
        return {
            capability_id: self._provider(script)
            for capability_id, script in self.scripts.items()
        }

    def _provider(self, script: _CapabilityScript):
        def provider(*arguments: Any) -> Any:
            if script.cursor >= len(script.calls):
                _fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_OVERFLOW",
                    script.capability_id,
                    "runtime invoked capability more times than scripted",
                )
            expected = script.calls[script.cursor]
            call_index = len(self.transcript)
            encoded_arguments = [
                {
                    "type": type_id,
                    "value": encode_v3_value(
                        type_id,
                        value,
                        self.runtime.type_table,
                        context=f"capability {script.capability_id} argument {index}",
                    ),
                }
                for index, (type_id, value) in enumerate(
                    zip(script.parameters, arguments, strict=True)
                )
            ]
            if canonical_json(encoded_arguments) != canonical_json(expected["arguments"]):
                _fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARGUMENTS",
                    script.capability_id,
                    f"call {script.cursor} arguments differ from scripted canonical values",
                )
            transcript_entry: dict[str, object] = {
                "index": call_index,
                "capability_id": script.capability_id,
                "arguments": encoded_arguments,
            }
            script.cursor += 1
            if script.return_type == "Unit":
                if "return" in expected:
                    _fail(
                        "TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN",
                        script.capability_id,
                        "Unit scripted call must not contain return",
                    )
                self.transcript.append(transcript_entry)
                return None

            raw_return = expected.get("return")
            if raw_return is None:
                _fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN",
                    script.capability_id,
                    "non-Unit scripted call requires return",
                )
            typed_return = _object(raw_return, f"capability {script.capability_id}.return")
            transcript_entry["return"] = typed_return
            self.transcript.append(transcript_entry)
            return decode_v3_value(
                script.return_type,
                typed_return["value"],
                self.runtime.type_table,
                context=f"capability {script.capability_id} scripted return",
            )

        return provider

    def verify_consumed(self) -> None:
        pending = {
            capability_id: len(script.calls) - script.cursor
            for capability_id, script in self.scripts.items()
            if script.cursor != len(script.calls)
        }
        if pending:
            _fail(
                "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_UNDERFLOW",
                "$.capabilities",
                f"scripted capability calls not consumed exactly: {pending}",
            )


def run_ir_v3_conformance(
    ir: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> IrV3ConformanceReceiptBundle:
    program = dict(ir)
    validate_program_ir_v3(program)
    scenario_obj = _validate_scenario(dict(scenario), program)
    scenario_hash = canonical_hash(scenario_obj)

    bootstrap = ScriptRuntimeV3(
        program,
        expected_source_semantic_hash=str(scenario_obj["source_semantic_hash"]),
    )
    host = _ScenarioHost(
        bootstrap,
        _array(scenario_obj["capabilities"], "$.capabilities", 0, 8192),
    )
    # Recreate the runtime with the fully validated scripted capability bindings.
    runtime = ScriptRuntimeV3(
        program,
        host.bindings(),
        expected_source_semantic_hash=str(scenario_obj["source_semantic_hash"]),
    )
    host.runtime = runtime

    initial_state = _state_witness(runtime)
    initial_state_hash = canonical_hash(initial_state)
    step_receipts: list[dict[str, object]] = []
    steps = _array(scenario_obj["steps"], "$.steps", 0, 1024)
    for index, raw_step in enumerate(steps):
        step = _object(raw_step, f"$.steps[{index}]")
        entity_id = str(step["entity_id"])
        event_id = str(step["event_id"])
        arguments = _decode_invocation_arguments(
            runtime,
            entity_id,
            event_id,
            _array(step["arguments"], f"$.steps[{index}].arguments", 0, 64),
        )
        emitted = runtime.invoke(entity_id, event_id, *arguments)
        state = _state_witness(runtime)
        step_receipts.append(
            {
                "index": index,
                "entity_id": entity_id,
                "event_id": event_id,
                "emitted": [_event_witness(event, runtime) for event in emitted],
                "state_hash": canonical_hash(state),
            }
        )

    host.verify_consumed()
    final_state = _state_witness(runtime)
    final_state_hash = canonical_hash(final_state)
    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1",
        "scenario_id": str(scenario_obj["scenario_id"]),
        "scenario_hash": scenario_hash,
        "program_semantic_hash": str(program["semantic_hash"]),
        "source_semantic_hash": str(program["source_semantic_hash"]),
        "initial_state_hash": initial_state_hash,
        "steps": step_receipts,
        "capability_calls": host.transcript,
        "final_state": final_state,
        "final_state_hash": final_state_hash,
    }
    receipt_hash = canonical_hash(body)
    receipt = dict(body)
    receipt["receipt_hash"] = receipt_hash
    return IrV3ConformanceReceiptBundle(
        receipt,
        canonical_json(receipt),
        receipt_hash,
    )


def _state_witness(runtime: ScriptRuntimeV3) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for entity_id in sorted(runtime.entities):
        entity = runtime.entities[entity_id]
        state = {
            state_name: {
                "type": entity.state_types[state_name],
                "value": encode_v3_value(
                    entity.state_types[state_name],
                    entity.state[state_name],
                    runtime.type_table,
                    context=f"state witness {entity_id}.{state_name}",
                ),
            }
            for state_name in sorted(entity.state)
        }
        result.append({"entity_id": entity_id, "state": state})
    return result


def _event_witness(event: EmittedEventV3, runtime: ScriptRuntimeV3) -> dict[str, object]:
    return {
        "entity_id": event.entity_id,
        "event_id": event.event_id,
        "arguments": [
            {
                "type": type_id,
                "value": encode_v3_value(
                    type_id,
                    value,
                    runtime.type_table,
                    context=f"event witness {event.event_id}[{index}]",
                ),
            }
            for index, (type_id, value) in enumerate(
                zip(event.argument_types, event.arguments, strict=True)
            )
        ],
    }


def _decode_invocation_arguments(
    runtime: ScriptRuntimeV3,
    entity_id: str,
    event_id: str,
    arguments: list[dict[str, object]],
) -> tuple[Any, ...]:
    entity = runtime.entities.get(entity_id)
    if entity is None:
        _fail("TEVS_IR_V3_CONFORMANCE_ENTITY", entity_id, "unknown scenario entity")
    handler = entity.handlers.get(event_id)
    if handler is not None:
        expected = tuple(str(item["type"]) for item in handler["parameters"])
    else:
        expected = entity.emitted_event_types.get(event_id)
        if expected is None:
            if arguments:
                _fail(
                    "TEVS_IR_V3_CONFORMANCE_EVENT_SIGNATURE",
                    event_id,
                    "unhandled scenario event with arguments has no portable signature",
                )
            expected = ()
    if len(expected) != len(arguments):
        _fail(
            "TEVS_IR_V3_CONFORMANCE_EVENT_ARITY",
            event_id,
            f"expected {len(expected)} arguments, got {len(arguments)}",
        )
    decoded: list[Any] = []
    for index, (expected_type, raw_argument) in enumerate(zip(expected, arguments, strict=True)):
        typed = _object(raw_argument, f"scenario argument {index}")
        _exact_keys(typed, f"scenario argument {index}", {"type", "value"})
        if typed["type"] != expected_type:
            _fail(
                "TEVS_IR_V3_CONFORMANCE_EVENT_TYPE",
                event_id,
                f"argument {index} expected {expected_type}, got {typed['type']!r}",
            )
        decoded.append(
            decode_v3_value(
                expected_type,
                typed["value"],
                runtime.type_table,
                context=f"scenario {entity_id}.{event_id}[{index}]",
            )
        )
    return tuple(decoded)


def _validate_scenario(
    scenario: dict[str, object],
    program: dict[str, object],
) -> dict[str, object]:
    _exact_keys(
        scenario,
        "$",
        {
            "schema", "scenario_id", "program_semantic_hash",
            "source_semantic_hash", "capabilities", "steps",
        },
    )
    if scenario["schema"] != "TEV_SCRIPT_IR_V3_SCENARIO_V1":
        _fail("TEVS_IR_V3_CONFORMANCE_SCENARIO_SCHEMA", "$.schema", "unexpected scenario schema")
    scenario_id = _stable(scenario["scenario_id"], "$.scenario_id")
    del scenario_id
    program_hash = _sha(scenario["program_semantic_hash"], "$.program_semantic_hash")
    source_hash = _sha(scenario["source_semantic_hash"], "$.source_semantic_hash")
    if program_hash != program["semantic_hash"]:
        _fail("TEVS_IR_V3_CONFORMANCE_PROGRAM_HASH", "$.program_semantic_hash", "scenario targets a different IR V3 semantic hash")
    if source_hash != program["source_semantic_hash"]:
        _fail("TEVS_IR_V3_CONFORMANCE_SOURCE_HASH", "$.source_semantic_hash", "scenario targets a different source semantic hash")
    _array(scenario["capabilities"], "$.capabilities", 0, 8192)
    steps = _array(scenario["steps"], "$.steps", 0, 1024)
    for index, raw in enumerate(steps):
        step = _object(raw, f"$.steps[{index}]")
        _exact_keys(step, f"$.steps[{index}]", {"entity_id", "event_id", "arguments"})
        _local(step["entity_id"], f"$.steps[{index}].entity_id")
        _local(step["event_id"], f"$.steps[{index}].event_id")
        _array(step["arguments"], f"$.steps[{index}].arguments", 0, 64)
    return scenario


def _global_capability_contracts(
    ir: Mapping[str, Any],
) -> dict[str, tuple[tuple[str, ...], str, str]]:
    result: dict[str, tuple[tuple[str, ...], str, str]] = {}
    for entity in ir["entities"]:
        for capability in entity["capabilities"]:
            capability_id = str(capability["capability_id"])
            contract = (
                tuple(str(item) for item in capability["parameters"]),
                str(capability["return_type"]),
                str(capability["kind"]),
            )
            previous = result.get(capability_id)
            if previous is not None and previous != contract:
                _fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CONFLICT",
                    capability_id,
                    "program contains conflicting capability contracts",
                )
            result[capability_id] = contract
    return result


def _validate_scripted_call(
    call: dict[str, object],
    parameters: tuple[str, ...],
    return_type: str,
    runtime: ScriptRuntimeV3,
    path: str,
) -> None:
    allowed = {"arguments"} if return_type == "Unit" else {"arguments", "return"}
    _exact_keys(call, path, allowed)
    arguments = _array(call["arguments"], path + ".arguments", 0, 64)
    if len(arguments) != len(parameters):
        _fail(
            "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARITY",
            path,
            f"expected {len(parameters)} arguments, got {len(arguments)}",
        )
    for index, (type_id, raw) in enumerate(zip(parameters, arguments, strict=True)):
        typed = _object(raw, f"{path}.arguments[{index}]")
        _exact_keys(typed, f"{path}.arguments[{index}]", {"type", "value"})
        if typed["type"] != type_id:
            _fail(
                "TEVS_IR_V3_CONFORMANCE_CAPABILITY_TYPE",
                path,
                f"argument {index} expected {type_id}, got {typed['type']!r}",
            )
        decode_v3_value(
            type_id,
            typed["value"],
            runtime.type_table,
            context=f"{path}.arguments[{index}]",
        )
    if return_type != "Unit":
        raw_return = _object(call["return"], path + ".return")
        _exact_keys(raw_return, path + ".return", {"type", "value"})
        if raw_return["type"] != return_type:
            _fail(
                "TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN_TYPE",
                path,
                f"expected return {return_type}, got {raw_return['type']!r}",
            )
        decode_v3_value(
            return_type,
            raw_return["value"],
            runtime.type_table,
            context=path + ".return",
        )


def _fail(code: str, path: str, message: str) -> None:
    raise TevScriptError(code, f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, "expected object")
    return value


def _array(value: Any, path: str, minimum: int, maximum: int) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, f"expected array length in [{minimum}, {maximum}]")
    return value


def _exact_keys(value: Mapping[str, Any], path: str, expected: set[str]) -> None:
    observed = set(value)
    if observed != expected:
        _fail(
            "TEVS_IR_V3_CONFORMANCE_SHAPE",
            path,
            f"field set mismatch; missing={sorted(expected-observed)}, extra={sorted(observed-expected)}",
        )


def _stable(value: Any, path: str) -> str:
    if not isinstance(value, str) or _STABLE.fullmatch(value) is None:
        _fail("TEVS_IR_V3_CONFORMANCE_IDENTIFIER", path, f"invalid stable id {value!r}")
    return value


def _local(value: Any, path: str) -> str:
    if not isinstance(value, str) or _LOCAL.fullmatch(value) is None:
        _fail("TEVS_IR_V3_CONFORMANCE_IDENTIFIER", path, f"invalid local id {value!r}")
    return value


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        _fail("TEVS_IR_V3_CONFORMANCE_HASH", path, "expected lowercase SHA-256")
    return value
