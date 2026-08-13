from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .ir_v3_conformance import run_ir_v3_conformance
from .ir_v3_values import build_type_table_v3, encode_v3_value
from .lift_ir_v2_to_v3 import lift_ir_v2_to_v3
from .runtime_checkpoint_v2 import RuntimeCheckpointV2
from .values import decode_typed_value

IR_V3_SCENARIO_SCHEMA_V1 = "TEV_SCRIPT_IR_V3_SCENARIO_V1"
IR_V3_RECEIPT_SCHEMA_V1 = "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1"


def _issue(kind: str, severity: str, subject: Any, **detail: Any) -> dict[str, object]:
    return {
        "kind": kind,
        "severity": severity,
        "subject": str(subject),
        "detail": detail,
    }


def _contracts(ir: Mapping[str, Any], entity_id: str) -> dict[str, dict[str, Any]]:
    for raw_entity in ir["entities"]:
        if raw_entity["entity_id"] == entity_id:
            return {
                str(item["capability_id"]): dict(item)
                for item in raw_entity["capabilities"]
            }
    return {}


def _v2_raw_to_v3(
    type_id: str,
    raw: Any,
    type_table: Any,
    *,
    context: str,
) -> Any:
    value = decode_typed_value(type_id, raw)
    return encode_v3_value(type_id, value, type_table, context=context)


def _checkpoint_from_legacy_baseline(
    v3_ir: Mapping[str, Any],
    baseline_state: Any,
    type_table: Any,
) -> tuple[RuntimeCheckpointV2 | None, list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    if not isinstance(baseline_state, list):
        return None, [_issue("replacement.variable_baseline_shape_invalid", "REJECT", "baseline_state")]

    observed: dict[str, Mapping[str, Any]] = {}
    for index, raw_row in enumerate(baseline_state):
        if not isinstance(raw_row, Mapping) or set(raw_row) != {"entity_id", "state"}:
            issues.append(_issue("replacement.variable_baseline_entity_shape_invalid", "REJECT", index))
            continue
        entity_id = str(raw_row["entity_id"])
        if entity_id in observed:
            issues.append(_issue("replacement.variable_baseline_entity_duplicate", "REJECT", entity_id))
            continue
        if not isinstance(raw_row["state"], Mapping):
            issues.append(_issue("replacement.variable_baseline_state_shape_invalid", "REJECT", entity_id))
            continue
        observed[entity_id] = raw_row

    expected_entities = {
        str(raw_entity["entity_id"]): raw_entity
        for raw_entity in v3_ir["entities"]
    }
    if set(observed) != set(expected_entities):
        issues.append(
            _issue(
                "replacement.variable_baseline_entity_set_mismatch",
                "REJECT",
                canonical_hash(baseline_state),
                expected=sorted(expected_entities),
                observed=sorted(observed),
            )
        )
    if issues:
        return None, issues

    checkpoint_entities: list[tuple[str, tuple[tuple[str, str, Any], ...]]] = []
    for entity_id in sorted(expected_entities):
        definition = expected_entities[entity_id]
        expected_states = {
            str(item["name"]): str(item["type"])
            for item in definition["states"]
        }
        raw_state = observed[entity_id]["state"]
        assert isinstance(raw_state, Mapping)
        if set(raw_state) != set(expected_states):
            issues.append(
                _issue(
                    "replacement.variable_baseline_state_set_mismatch",
                    "REJECT",
                    entity_id,
                    expected=sorted(expected_states),
                    observed=sorted(raw_state),
                )
            )
            continue

        states: list[tuple[str, str, Any]] = []
        for state_name in sorted(expected_states):
            typed = raw_state[state_name]
            if not isinstance(typed, Mapping) or set(typed) != {"type", "value"}:
                issues.append(
                    _issue(
                        "replacement.variable_baseline_typed_value_shape_invalid",
                        "REJECT",
                        f"{entity_id}.{state_name}",
                    )
                )
                continue
            expected_type = expected_states[state_name]
            observed_type = str(typed["type"])
            if observed_type != expected_type:
                issues.append(
                    _issue(
                        "replacement.variable_baseline_type_mismatch",
                        "REJECT",
                        f"{entity_id}.{state_name}",
                        expected=expected_type,
                        observed=observed_type,
                    )
                )
                continue
            try:
                converted = _v2_raw_to_v3(
                    expected_type,
                    typed["value"],
                    type_table,
                    context=f"R10 baseline {entity_id}.{state_name}",
                )
            except Exception as error:
                issues.append(
                    _issue(
                        "replacement.variable_baseline_value_invalid",
                        "REJECT",
                        f"{entity_id}.{state_name}",
                        error_type=type(error).__name__,
                    )
                )
                continue
            states.append((state_name, expected_type, converted))
        checkpoint_entities.append((entity_id, tuple(states)))

    if issues:
        return None, issues

    checkpoint = RuntimeCheckpointV2(
        program_id=str(v3_ir["program_id"]),
        ir_schema=str(v3_ir["schema"]),
        semantic_hash=str(v3_ir["semantic_hash"]),
        source_schema=str(v3_ir["source_schema"]),
        source_semantic_hash=str(v3_ir["source_semantic_hash"]),
        entities=tuple(checkpoint_entities),
    )
    return checkpoint, []


def _prepare_variable_projection(
    ir: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> tuple[
    dict[str, object] | None,
    list[dict[str, object]],
    RuntimeCheckpointV2 | None,
    list[dict[str, object]],
]:
    """Build an IR V3 scripted-call scenario and exact baseline checkpoint.

    The V2 semantic hash is preserved by the V2->V3 lift as
    source_semantic_hash. Variable observations therefore reuse the canonical
    IR V3 scripted-call semantics, while the candidate baseline is restored
    through RuntimeCheckpointV2 before replay.
    """
    issues: list[dict[str, object]] = []
    try:
        lifted = lift_ir_v2_to_v3(ir)
    except Exception as error:
        issues.append(
            _issue(
                "replacement.ir_v3_lift_rejected",
                "REJECT",
                bundle.get("program_semantic_hash", ""),
                error_type=type(error).__name__,
                error=str(error),
            )
        )
        return None, [], None, issues

    v3_ir = lifted.ir
    if v3_ir.get("source_semantic_hash") != ir.get("semantic_hash"):
        issues.append(
            _issue(
                "replacement.ir_v3_source_binding_mismatch",
                "REJECT",
                v3_ir.get("source_semantic_hash", ""),
                expected=ir.get("semantic_hash", ""),
            )
        )
        return None, [], None, issues

    try:
        type_table = build_type_table_v3(v3_ir)
    except Exception as error:
        issues.append(
            _issue(
                "replacement.ir_v3_type_table_rejected",
                "REJECT",
                v3_ir.get("semantic_hash", ""),
                error_type=type(error).__name__,
                error=str(error),
            )
        )
        return None, [], None, issues

    checkpoint, checkpoint_issues = _checkpoint_from_legacy_baseline(
        v3_ir,
        bundle.get("baseline_state"),
        type_table,
    )
    issues.extend(checkpoint_issues)
    if checkpoint is None or issues:
        return None, [], checkpoint, issues

    invocations = bundle.get("invocations")
    if not isinstance(invocations, list) or not invocations:
        issues.append(_issue("replacement.variable_invocations_invalid", "REJECT", bundle.get("bundle_hash", "")))
        return None, [], checkpoint, issues
    entity_ids = {
        str(item.get("entity_id", ""))
        for item in invocations
        if isinstance(item, dict)
    }
    if len(entity_ids) != 1:
        issues.append(
            _issue(
                "replacement.variable_multi_entity_projection_required",
                "PROOF_REQUIRED",
                bundle.get("bundle_hash", ""),
                entities=sorted(entity_ids),
            )
        )
        return None, [], checkpoint, issues
    entity_id = next(iter(entity_ids))
    contracts = _contracts(ir, entity_id)
    bindings = bundle.get("capability_bindings")
    if not isinstance(bindings, dict):
        issues.append(_issue("replacement.variable_capability_bindings_invalid", "REJECT", bundle.get("bundle_hash", "")))
        return None, [], checkpoint, issues

    calls_by_capability: dict[str, list[dict[str, object]]] = {
        capability_id: [] for capability_id in sorted(bindings)
    }
    expected_transcript: list[dict[str, object]] = []
    raw_trace = bundle.get("observed_capability_trace")
    if not isinstance(raw_trace, list):
        issues.append(_issue("replacement.variable_trace_invalid", "REJECT", bundle.get("bundle_hash", "")))
        return None, [], checkpoint, issues

    for index, raw_call in enumerate(raw_trace):
        if not isinstance(raw_call, dict) or set(raw_call) != {"capability_id", "arguments", "result"}:
            issues.append(_issue("replacement.variable_trace_call_shape_invalid", "REJECT", index))
            continue
        capability_id = str(raw_call["capability_id"])
        contract = contracts.get(capability_id)
        config = bindings.get(capability_id)
        if contract is None:
            issues.append(_issue("replacement.variable_trace_capability_undeclared", "REJECT", capability_id))
            continue
        if not isinstance(config, dict):
            issues.append(_issue("replacement.variable_trace_capability_unbound", "REJECT", capability_id))
            continue

        parameters = tuple(str(item) for item in contract["parameters"])
        return_type = str(contract["return_type"])
        kind = str(contract["kind"])
        raw_arguments = raw_call["arguments"]
        if not isinstance(raw_arguments, list) or len(raw_arguments) != len(parameters):
            issues.append(
                _issue(
                    "replacement.variable_trace_argument_arity",
                    "REJECT",
                    capability_id,
                    expected=len(parameters),
                    observed=None if not isinstance(raw_arguments, list) else len(raw_arguments),
                )
            )
            continue

        typed_arguments: list[dict[str, object]] = []
        conversion_failed = False
        for argument_index, (type_id, raw_value) in enumerate(zip(parameters, raw_arguments, strict=True)):
            try:
                converted = _v2_raw_to_v3(
                    type_id,
                    raw_value,
                    type_table,
                    context=f"R10 capability {capability_id} argument {argument_index}",
                )
            except Exception as error:
                issues.append(
                    _issue(
                        "replacement.variable_trace_argument_invalid",
                        "REJECT",
                        capability_id,
                        index=argument_index,
                        error_type=type(error).__name__,
                    )
                )
                conversion_failed = True
                break
            typed_arguments.append({"type": type_id, "value": converted})
        if conversion_failed:
            continue

        mode = config.get("mode")
        if mode == "variable":
            if set(config) != {"mode"} or kind != "observation" or return_type == "Unit":
                issues.append(
                    _issue(
                        "replacement.variable_binding_invalid",
                        "REJECT",
                        capability_id,
                        capability_kind=kind,
                        return_type=return_type,
                    )
                )
                continue
        elif mode == "constant":
            if set(config) != {"mode", "value_type", "value"}:
                issues.append(_issue("replacement.constant_binding_shape_invalid", "REJECT", capability_id))
                continue
            if config.get("value_type") != return_type:
                issues.append(
                    _issue(
                        "replacement.capability_return_type_mismatch",
                        "REJECT",
                        capability_id,
                        expected=return_type,
                        observed=config.get("value_type"),
                    )
                )
                continue
        elif mode == "trace":
            if set(config) != {"mode"} or kind != "effect" or return_type != "Unit":
                issues.append(_issue("replacement.trace_binding_not_unit_effect", "REJECT", capability_id))
                continue
        else:
            issues.append(_issue("replacement.capability_mode_unknown", "REJECT", capability_id, mode=mode))
            continue

        call: dict[str, object] = {"arguments": typed_arguments}
        transcript: dict[str, object] = {
            "index": index,
            "capability_id": capability_id,
            "arguments": typed_arguments,
        }
        if return_type == "Unit":
            if raw_call["result"] is not None:
                issues.append(_issue("replacement.variable_trace_unit_result", "REJECT", capability_id))
                continue
        else:
            if raw_call["result"] is None:
                issues.append(_issue("replacement.variable_trace_return_missing", "REJECT", capability_id))
                continue
            try:
                converted_return = _v2_raw_to_v3(
                    return_type,
                    raw_call["result"],
                    type_table,
                    context=f"R10 capability {capability_id} return",
                )
            except Exception as error:
                issues.append(
                    _issue(
                        "replacement.variable_trace_return_invalid",
                        "REJECT",
                        capability_id,
                        error_type=type(error).__name__,
                    )
                )
                continue
            typed_return = {"type": return_type, "value": converted_return}
            call["return"] = typed_return
            transcript["return"] = typed_return
            if mode == "constant":
                try:
                    expected_constant = _v2_raw_to_v3(
                        return_type,
                        config["value"],
                        type_table,
                        context=f"R10 constant {capability_id}",
                    )
                except Exception as error:
                    issues.append(
                        _issue(
                            "replacement.constant_binding_value_invalid",
                            "REJECT",
                            capability_id,
                            error_type=type(error).__name__,
                        )
                    )
                    continue
                if canonical_json(expected_constant) != canonical_json(converted_return):
                    issues.append(
                        _issue(
                            "replacement.constant_observation_changed",
                            "REJECT",
                            capability_id,
                            trace_index=index,
                        )
                    )
                    continue

        calls_by_capability.setdefault(capability_id, []).append(call)
        expected_transcript.append(transcript)

    if issues:
        return None, expected_transcript, checkpoint, issues

    steps: list[dict[str, object]] = []
    for index, raw_invocation in enumerate(invocations):
        if not isinstance(raw_invocation, dict) or set(raw_invocation) != {"entity_id", "event_id", "arguments"}:
            issues.append(_issue("replacement.variable_invocation_shape_invalid", "REJECT", index))
            continue
        raw_arguments = raw_invocation["arguments"]
        if not isinstance(raw_arguments, list):
            issues.append(_issue("replacement.variable_invocation_arguments_invalid", "REJECT", index))
            continue
        typed_arguments: list[dict[str, object]] = []
        for argument_index, raw_argument in enumerate(raw_arguments):
            if not isinstance(raw_argument, dict) or set(raw_argument) != {"type", "value"}:
                issues.append(_issue("replacement.variable_invocation_argument_shape_invalid", "REJECT", f"{index}:{argument_index}"))
                continue
            type_id = str(raw_argument["type"])
            try:
                converted = _v2_raw_to_v3(
                    type_id,
                    raw_argument["value"],
                    type_table,
                    context=f"R10 invocation {index} argument {argument_index}",
                )
            except Exception as error:
                issues.append(
                    _issue(
                        "replacement.variable_invocation_argument_invalid",
                        "REJECT",
                        f"{index}:{argument_index}",
                        error_type=type(error).__name__,
                    )
                )
                continue
            typed_arguments.append({"type": type_id, "value": converted})
        steps.append(
            {
                "entity_id": str(raw_invocation["entity_id"]),
                "event_id": str(raw_invocation["event_id"]),
                "arguments": typed_arguments,
            }
        )

    if issues:
        return None, expected_transcript, checkpoint, issues

    scenario = {
        "schema": IR_V3_SCENARIO_SCHEMA_V1,
        "scenario_id": str(bundle["scenario_id"]),
        "program_semantic_hash": str(v3_ir["semantic_hash"]),
        "source_semantic_hash": str(v3_ir["source_semantic_hash"]),
        "capabilities": [
            {
                "capability_id": capability_id,
                "calls": deepcopy(calls_by_capability.get(capability_id, [])),
            }
            for capability_id in sorted(calls_by_capability)
        ],
        "steps": steps,
    }
    return scenario, expected_transcript, checkpoint, []


def project_variable_adaptive_replacement_v1(
    ir: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> tuple[dict[str, object] | None, tuple[dict[str, object], ...]]:
    scenario, _expected, _checkpoint, issues = _prepare_variable_projection(ir, bundle)
    return scenario, tuple(issues)


def evaluate_variable_adaptive_replacement_v1(
    ir: Mapping[str, Any],
    bundle: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> tuple[str, tuple[dict[str, object], ...]]:
    projected, expected_transcript, checkpoint, preparation_issues = _prepare_variable_projection(ir, bundle)
    issues = list(preparation_issues)
    if projected is None or checkpoint is None:
        return "", tuple(issues)
    if canonical_json(projected) != canonical_json(dict(scenario)):
        issues.append(
            _issue(
                "replacement.ir_v3_projection_identity_mismatch",
                "REJECT",
                canonical_hash(dict(scenario)),
                expected=canonical_hash(projected),
            )
        )
        return "", tuple(issues)

    try:
        lifted = lift_ir_v2_to_v3(ir)
        result = run_ir_v3_conformance(
            lifted.ir,
            projected,
            initial_checkpoint=checkpoint,
        )
    except Exception as error:
        issues.append(
            _issue(
                "replacement.conformance_runner_rejected",
                "REJECT",
                canonical_hash(projected),
                runner="IR_V3",
                error_type=type(error).__name__,
                error=str(error),
            )
        )
        return "", tuple(issues)

    receipt = result.receipt
    runner_receipt_hash = result.receipt_hash
    if receipt.get("schema") != IR_V3_RECEIPT_SCHEMA_V1:
        issues.append(_issue("replacement.ir_v3_receipt_schema_mismatch", "REJECT", receipt.get("schema", "")))
    if receipt.get("source_semantic_hash") != ir.get("semantic_hash"):
        issues.append(
            _issue(
                "replacement.ir_v3_receipt_source_mismatch",
                "REJECT",
                receipt.get("source_semantic_hash", ""),
                expected=ir.get("semantic_hash", ""),
            )
        )
    if receipt.get("initial_state_hash") != bundle.get("baseline_state_hash"):
        issues.append(
            _issue(
                "replacement.ir_v3_baseline_binding_mismatch",
                "REJECT",
                bundle.get("baseline_state_hash", ""),
                observed=receipt.get("initial_state_hash"),
                checkpoint_hash=checkpoint.checkpoint_hash,
            )
        )
    if canonical_json(receipt.get("final_state")) != canonical_json(bundle.get("observed_final_states")):
        issues.append(
            _issue(
                "replacement.observable_divergence",
                "REJECT",
                "observed_final_states",
                runner_receipt_hash=runner_receipt_hash,
            )
        )

    emitted_events: list[dict[str, object]] = []
    for step in receipt.get("steps", []):
        for event in step.get("emitted", []):
            emitted_events.append(
                {
                    "entity_id": event["entity_id"],
                    "event_id": event["event_id"],
                    "arguments": [item["value"] for item in event["arguments"]],
                }
            )
    if canonical_json(emitted_events) != canonical_json(bundle.get("observed_emitted_events")):
        issues.append(
            _issue(
                "replacement.observable_divergence",
                "REJECT",
                "observed_emitted_events",
                runner_receipt_hash=runner_receipt_hash,
            )
        )
    if canonical_json(receipt.get("capability_calls")) != canonical_json(expected_transcript):
        issues.append(
            _issue(
                "replacement.observable_divergence",
                "REJECT",
                "observed_capability_trace",
                runner_receipt_hash=runner_receipt_hash,
            )
        )

    return runner_receipt_hash, tuple(issues)


__all__ = [
    "IR_V3_SCENARIO_SCHEMA_V1",
    "IR_V3_RECEIPT_SCHEMA_V1",
    "project_variable_adaptive_replacement_v1",
    "evaluate_variable_adaptive_replacement_v1",
]
