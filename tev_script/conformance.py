from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash
from .runtime import ScriptRuntime
from .values import decode_typed_value, encode_typed_value


def _capability_signatures(ir: Mapping[str, Any], entity_id: str) -> dict[str, dict[str, Any]]:
    for entity in ir["entities"]:
        if entity["entity_id"] == entity_id:
            return {item["capability_id"]: item for item in entity["capabilities"]}
    raise KeyError(entity_id)


def _decode_argument(raw: Mapping[str, Any]) -> Any:
    return decode_typed_value(str(raw["type"]), raw["value"])


def _state_witness(runtime: ScriptRuntime, ir: Mapping[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for raw_entity in ir["entities"]:
        runtime_entity = runtime.entities[raw_entity["entity_id"]]
        states.append(
            {
                "entity_id": raw_entity["entity_id"],
                "state": {
                    name: {
                        "type": runtime_entity.state_types[name],
                        "value": encode_typed_value(
                            runtime_entity.state_types[name], value
                        ),
                    }
                    for name, value in sorted(runtime_entity.state.items())
                },
            }
        )
    return states


def _restore_state_witness(
    runtime: ScriptRuntime,
    ir: Mapping[str, Any],
    initial_state: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(initial_state, (list, tuple)):
        raise ValueError("initial_state must be an array")

    rows: dict[str, Mapping[str, Any]] = {}
    for index, raw_row in enumerate(initial_state):
        if not isinstance(raw_row, Mapping) or set(raw_row) != {"entity_id", "state"}:
            raise ValueError(f"initial_state[{index}] has invalid shape")
        entity_id = str(raw_row["entity_id"])
        if entity_id in rows:
            raise ValueError(f"initial_state duplicates entity {entity_id}")
        if not isinstance(raw_row["state"], Mapping):
            raise ValueError(f"initial_state[{index}].state must be an object")
        rows[entity_id] = raw_row

    expected_entities = [str(item["entity_id"]) for item in ir["entities"]]
    if set(rows) != set(expected_entities):
        raise ValueError(
            "initial_state entity set mismatch: "
            f"expected={sorted(expected_entities)} observed={sorted(rows)}"
        )

    for entity_id in expected_entities:
        runtime_entity = runtime.entities[entity_id]
        raw_state = rows[entity_id]["state"]
        expected_states = set(runtime_entity.state)
        observed_states = set(raw_state)
        if observed_states != expected_states:
            raise ValueError(
                f"initial_state state set mismatch for {entity_id}: "
                f"expected={sorted(expected_states)} observed={sorted(observed_states)}"
            )

        restored: dict[str, Any] = {}
        for state_name in sorted(expected_states):
            raw_value = raw_state[state_name]
            if not isinstance(raw_value, Mapping) or set(raw_value) != {"type", "value"}:
                raise ValueError(
                    f"initial_state {entity_id}.{state_name} has invalid typed-value shape"
                )
            expected_type = runtime_entity.state_types[state_name]
            observed_type = str(raw_value["type"])
            if observed_type != expected_type:
                raise ValueError(
                    f"initial_state type mismatch for {entity_id}.{state_name}: "
                    f"expected={expected_type} observed={observed_type}"
                )
            restored[state_name] = decode_typed_value(expected_type, raw_value["value"])

        runtime_entity.state.clear()
        runtime_entity.state.update(restored)

    return _state_witness(runtime, ir)


def run_conformance(
    ir: Mapping[str, Any],
    scenario: Mapping[str, Any],
    *,
    initial_state: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    entity_id = str(scenario["entity_id"])
    signatures = _capability_signatures(ir, entity_id)
    capability_config = dict(scenario.get("capabilities", {}))
    trace: list[dict[str, Any]] = []
    capabilities: dict[str, Any] = {}

    for capability_id, signature in signatures.items():
        config = capability_config.get(capability_id)
        if config is None:
            raise ValueError(f"scenario lacks capability {capability_id}")

        def make_capability(
            current_id: str,
            current_signature: Mapping[str, Any],
            current_config: Mapping[str, Any],
        ):
            def capability(*arguments: Any) -> Any:
                mode = current_config["mode"]
                if mode == "constant":
                    result = decode_typed_value(
                        str(current_config["value_type"]),
                        current_config["value"],
                    )
                elif mode == "trace":
                    result = None
                else:
                    raise ValueError(f"unsupported capability mode {mode}")
                trace.append(
                    {
                        "capability_id": current_id,
                        "arguments": [
                            encode_typed_value(type_name, arguments[index])
                            for index, type_name in enumerate(
                                current_signature["parameters"]
                            )
                        ],
                        "result": None
                        if current_signature["return_type"] == "Unit"
                        else encode_typed_value(
                            current_signature["return_type"], result
                        ),
                    }
                )
                return result

            return capability

        capabilities[capability_id] = make_capability(
            capability_id, signature, config
        )

    runtime = ScriptRuntime(ir, capabilities)
    restored_initial_state: list[dict[str, Any]] | None = None
    if initial_state is not None:
        restored_initial_state = _restore_state_witness(runtime, ir, initial_state)

    for invocation in scenario["invocations"]:
        runtime.invoke(
            invocation["entity_id"],
            invocation["event_id"],
            *[_decode_argument(item) for item in invocation["arguments"]],
        )

    final_states = _state_witness(runtime, ir)

    event_types: dict[tuple[str, str], tuple[str, ...]] = {}
    for raw_entity in ir["entities"]:
        for event in raw_entity["emitted_events"]:
            event_types[(raw_entity["entity_id"], event["event_id"])] = tuple(
                event["parameters"]
            )

    emitted_events = []
    for event in runtime.emitted:
        types = event_types.get((event.entity_id, event.event_id), ())
        emitted_events.append(
            {
                "entity_id": event.entity_id,
                "event_id": event.event_id,
                "arguments": [
                    encode_typed_value(types[index], value)
                    for index, value in enumerate(event.arguments)
                ],
            }
        )

    if restored_initial_state is None:
        semantic = {
            "schema": "TEV_SCRIPT_CONFORMANCE_RECEIPT_V1",
            "scenario_id": scenario["scenario_id"],
            "program_hash": ir["semantic_hash"],
            "final_states": final_states,
            "emitted_events": emitted_events,
            "capability_trace": trace,
        }
    else:
        semantic = {
            "schema": "TEV_SCRIPT_CONFORMANCE_RECEIPT_V2",
            "scenario_id": scenario["scenario_id"],
            "scenario_hash": canonical_hash(dict(scenario)),
            "program_hash": ir["semantic_hash"],
            "initial_state_hash": canonical_hash(restored_initial_state),
            "final_states": final_states,
            "emitted_events": emitted_events,
            "capability_trace": trace,
        }
    return {**semantic, "receipt_hash": canonical_hash(semantic)}
