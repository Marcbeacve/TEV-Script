from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .canonical import canonical_json
from .causal_analysis_v1 import find_reaction_footprint, prove_preparability
from .causal_model_v1 import (
    CapabilityLawCatalogV1,
    CommitResultV1,
    PreparedReactionV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from .causal_refinement_v1 import verify_prepared_refinement, verify_structural_refinement
from .diagnostics import TevScriptError
from .ir_v3_values import decode_v3_value, encode_v3_value
from .runtime_checkpoint_v2 import RuntimeCheckpointV2
from .runtime_v3 import EmittedEventV3, ScriptRuntimeV3, _coerce_runtime_v3


@dataclass(frozen=True, slots=True)
class PreparedReactionBundleV1:
    footprint: ReactionFootprintV1
    refinement: RefinementReceiptV1
    prepared: PreparedReactionV1
    prepared_hash: str


def _capability_contracts(ir: Mapping[str, Any]) -> dict[str, tuple[tuple[str, ...], str, str]]:
    result: dict[str, tuple[tuple[str, ...], str, str]] = {}
    for entity in ir["entities"]:
        for raw in entity["capabilities"]:
            value = (
                tuple(str(item) for item in raw["parameters"]),
                str(raw["return_type"]),
                str(raw["kind"]),
            )
            capability_id = str(raw["capability_id"])
            previous = result.get(capability_id)
            if previous is not None and previous != value:
                raise TevScriptError(
                    "TEVS_CAUSAL_CAPABILITY_CONTRACT",
                    f"conflicting runtime capability contract for {capability_id!r}",
                )
            result[capability_id] = value
    return result


def _typed_arguments(
    runtime: ScriptRuntimeV3,
    entity_id: str,
    event_id: str,
    arguments: tuple[Any, ...],
) -> tuple[dict[str, Any], ...]:
    entity = runtime.entities.get(entity_id)
    if entity is None:
        raise TevScriptError("TEVS_CAUSAL_ENTITY_UNKNOWN", f"unknown entity {entity_id!r}")
    handler = entity.handlers.get(event_id)
    if handler is None:
        raise TevScriptError("TEVS_CAUSAL_TRIGGER_HANDLER", f"reaction trigger {event_id!r} has no handler")
    parameters = handler["parameters"]
    if len(parameters) != len(arguments):
        raise TevScriptError("TEVS_CAUSAL_TRIGGER_ARITY", f"reaction trigger expects {len(parameters)} arguments")
    result: list[dict[str, Any]] = []
    for index, (parameter, value) in enumerate(zip(parameters, arguments, strict=True)):
        type_id = str(parameter["type"])
        coerced = _coerce_runtime_v3(
            type_id,
            value,
            runtime.type_table,
            context=f"causal trigger {entity_id}.{event_id}[{index}]",
        )
        result.append({
            "type": type_id,
            "value": encode_v3_value(
                type_id,
                coerced,
                runtime.type_table,
                context=f"causal trigger {index}",
            ),
        })
    return tuple(result)


def _event_witness(runtime: ScriptRuntimeV3, event: EmittedEventV3) -> dict[str, Any]:
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
                    context=f"causal emitted {event.event_id}[{index}]",
                ),
            }
            for index, (type_id, value) in enumerate(
                zip(event.argument_types, event.arguments, strict=True)
            )
        ],
    }


def prepare_reaction(
    runtime: ScriptRuntimeV3,
    entity_id: str,
    event_id: str,
    *arguments: Any,
    contract: ReactionContractV1,
    laws: CapabilityLawCatalogV1,
) -> PreparedReactionBundleV1:
    footprint = find_reaction_footprint(runtime.ir, entity_id, event_id)
    structural = verify_structural_refinement(contract, footprint, laws)
    if structural.status == "REJECT":
        raise TevScriptError("TEVS_CAUSAL_REFINEMENT_REJECT", canonical_json(structural.to_object()))
    if structural.status == "PROOF_REQUIRED":
        raise TevScriptError("TEVS_CAUSAL_PROOF_REQUIRED", canonical_json(structural.to_object()))

    preparability = prove_preparability(runtime.ir, footprint, laws)
    if not preparability.preparable:
        raise TevScriptError(
            "TEVS_CAUSAL_NOT_PREPARABLE",
            canonical_json({
                "reasons": list(preparability.reasons),
                "hazards": [list(item) for item in preparability.hazards],
            }),
        )

    before = RuntimeCheckpointV2.capture(runtime)
    before_object = before.to_object()
    contracts = _capability_contracts(runtime.ir)
    observations: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []
    bindings: dict[str, Any] = {}

    for capability_id, (parameter_types, return_type, kind) in contracts.items():
        if kind == "observation":
            original = runtime.capabilities.get(capability_id)
            if capability_id in footprint.observations and original is None:
                raise TevScriptError(
                    "TEVS_CAUSAL_CAPABILITY_MISSING",
                    f"missing observation binding {capability_id!r}",
                )
            if original is None:
                continue

            def observation_provider(
                *values: Any,
                _id=capability_id,
                _params=parameter_types,
                _return=return_type,
                _original=original,
            ):
                encoded_args = [
                    {
                        "type": type_id,
                        "value": encode_v3_value(
                            type_id,
                            value,
                            runtime.type_table,
                            context=f"causal observation {_id} arg {index}",
                        ),
                    }
                    for index, (type_id, value) in enumerate(zip(_params, values, strict=True))
                ]
                raw = _original(*values)
                entry: dict[str, Any] = {
                    "index": len(observations),
                    "capability_id": _id,
                    "arguments": encoded_args,
                }
                if _return != "Unit":
                    coerced = _coerce_runtime_v3(
                        _return,
                        raw,
                        runtime.type_table,
                        context=f"causal observation {_id} return",
                    )
                    entry["return"] = {
                        "type": _return,
                        "value": encode_v3_value(
                            _return,
                            coerced,
                            runtime.type_table,
                            context=f"causal observation {_id} return",
                        ),
                    }
                    observations.append(entry)
                    return coerced
                observations.append(entry)
                return None

            bindings[capability_id] = observation_provider
        else:
            def effect_intent_provider(
                *values: Any,
                _id=capability_id,
                _params=parameter_types,
            ):
                intents.append({
                    "index": len(intents),
                    "capability_id": _id,
                    "arguments": [
                        {
                            "type": type_id,
                            "value": encode_v3_value(
                                type_id,
                                value,
                                runtime.type_table,
                                context=f"causal effect intent {_id} arg {index}",
                            ),
                        }
                        for index, (type_id, value) in enumerate(zip(_params, values, strict=True))
                    ],
                })
                return None

            bindings[capability_id] = effect_intent_provider

    shadow = before.restore_exact(runtime.ir, bindings)
    typed_arguments = _typed_arguments(shadow, entity_id, event_id, tuple(arguments))
    emitted = shadow.invoke(entity_id, event_id, *arguments)
    after = RuntimeCheckpointV2.capture(shadow)
    after_object = after.to_object()

    final_refinement = verify_prepared_refinement(
        contract,
        footprint,
        laws,
        before_object,
        after_object,
        preparability.atomicity,
    )
    if final_refinement.status == "REJECT":
        raise TevScriptError("TEVS_CAUSAL_REFINEMENT_REJECT", canonical_json(final_refinement.to_object()))
    if final_refinement.status == "PROOF_REQUIRED":
        raise TevScriptError("TEVS_CAUSAL_PROOF_REQUIRED", canonical_json(final_refinement.to_object()))

    prepared = PreparedReactionV1(
        program_semantic_hash=str(runtime.ir["semantic_hash"]),
        source_semantic_hash=str(runtime.ir["source_semantic_hash"]),
        contract_hash=contract.contract_hash,
        law_catalog_hash=laws.catalog_hash,
        refinement_receipt_hash=final_refinement.receipt_hash,
        footprint_hash=footprint.footprint_hash,
        entity_id=entity_id,
        trigger_event=event_id,
        arguments=typed_arguments,
        before_checkpoint=before_object,
        before_checkpoint_hash=before.checkpoint_hash,
        after_checkpoint=after_object,
        after_checkpoint_hash=after.checkpoint_hash,
        observations=tuple(observations),
        effect_intents=tuple(intents),
        emitted_events=tuple(_event_witness(shadow, event) for event in emitted),
        atomicity=preparability.atomicity,
        preparation_evidence=(
            "canonical_checkpoint_shadow",
            "effects_staged_as_intents",
            "deployment_laws_bound",
            "refinement_pass",
        ),
    )
    return PreparedReactionBundleV1(
        footprint, final_refinement, prepared, prepared.prepared_reaction_hash
    )


def _decode_intent_arguments(
    runtime: ScriptRuntimeV3, intent: Mapping[str, Any]
) -> tuple[Any, ...]:
    values: list[Any] = []
    for index, typed in enumerate(intent["arguments"]):
        type_id = str(typed["type"])
        values.append(
            decode_v3_value(
                type_id,
                typed["value"],
                runtime.type_table,
                context=f"causal commit {intent['capability_id']} arg {index}",
            )
        )
    return tuple(values)


def _publish_after_checkpoint(runtime: ScriptRuntimeV3, prepared: PreparedReactionV1) -> None:
    checkpoint = RuntimeCheckpointV2.parse(canonical_json(dict(prepared.after_checkpoint)))
    restored = checkpoint.restore_exact(runtime.ir, runtime.capabilities)
    for entity_id, source in restored.entities.items():
        runtime.entities[entity_id].state = dict(source.state)
    for witness in prepared.emitted_events:
        arguments = tuple(
            decode_v3_value(
                str(typed["type"]),
                typed["value"],
                runtime.type_table,
                context=f"causal committed event {witness['event_id']}[{index}]",
            )
            for index, typed in enumerate(witness["arguments"])
        )
        runtime.emitted.append(
            EmittedEventV3(
                str(witness["entity_id"]),
                str(witness["event_id"]),
                tuple(str(typed["type"]) for typed in witness["arguments"]),
                arguments,
            )
        )


def commit_prepared_reaction(
    runtime: ScriptRuntimeV3,
    bundle: PreparedReactionBundleV1,
    *,
    contract: ReactionContractV1,
    laws: CapabilityLawCatalogV1,
    effect_bindings: Mapping[str, Any] | None = None,
) -> CommitResultV1:
    prepared = bundle.prepared
    if prepared.prepared_reaction_hash != bundle.prepared_hash:
        raise TevScriptError("TEVS_CAUSAL_PREPARED_TAMPER", "prepared reaction changed after preparation")
    if prepared.footprint_hash != bundle.footprint.footprint_hash:
        raise TevScriptError("TEVS_CAUSAL_FOOTPRINT_STALE", "prepared reaction footprint binding changed")
    if (
        bundle.refinement.contract_hash != prepared.contract_hash
        or bundle.refinement.footprint_hash != prepared.footprint_hash
        or bundle.refinement.law_catalog_hash != prepared.law_catalog_hash
        or bundle.refinement.candidate_program_semantic_hash != prepared.program_semantic_hash
    ):
        raise TevScriptError("TEVS_CAUSAL_REFINEMENT_STALE", "refinement receipt bindings changed")
    if prepared.contract_hash != contract.contract_hash:
        raise TevScriptError("TEVS_CAUSAL_STALE_CONTRACT", "prepared reaction contract hash changed")
    if prepared.law_catalog_hash != laws.catalog_hash:
        raise TevScriptError("TEVS_CAUSAL_STALE_LAWS", "prepared reaction deployment law hash changed")
    if prepared.refinement_receipt_hash != bundle.refinement.receipt_hash or bundle.refinement.status != "PASS":
        raise TevScriptError(
            "TEVS_CAUSAL_REFINEMENT_REQUIRED",
            "prepared reaction is not bound to a PASS refinement receipt",
        )
    if prepared.program_semantic_hash != str(runtime.ir["semantic_hash"]):
        raise TevScriptError("TEVS_CAUSAL_STALE_PROGRAM", "prepared reaction program hash changed")
    current = RuntimeCheckpointV2.capture(runtime)
    if current.checkpoint_hash != prepared.before_checkpoint_hash:
        raise TevScriptError("TEVS_CAUSAL_STALE_STATE", "runtime state changed after preparation")

    providers = dict(runtime.capabilities)
    providers.update(dict(effect_bindings or {}))
    committed = 0

    if prepared.atomicity in {"transactional", "durable_transactional"}:
        tokens: list[tuple[str, Any, Any]] = []
        try:
            for intent in prepared.effect_intents:
                capability_id = str(intent["capability_id"])
                law = laws.law(capability_id)
                provider = providers.get(capability_id)
                if law is None or law.effect_protocol != "prepare_commit_abort":
                    raise TevScriptError(
                        "TEVS_CAUSAL_TRANSACTION_LAW",
                        f"{capability_id!r} lacks prepare_commit_abort law",
                    )
                if provider is None or not all(
                    callable(getattr(provider, name, None))
                    for name in ("prepare", "commit", "abort")
                ):
                    raise TevScriptError(
                        "TEVS_CAUSAL_TRANSACTION_PROVIDER",
                        f"{capability_id!r} lacks prepare/commit/abort provider",
                    )
                token = provider.prepare(*_decode_intent_arguments(runtime, intent))
                tokens.append((capability_id, provider, token))
        except Exception as error:
            for _capability_id, provider, token in reversed(tokens):
                try:
                    provider.abort(token)
                except Exception:
                    pass
            return CommitResultV1(
                "ABORTED",
                prepared.prepared_reaction_hash,
                False,
                False,
                0,
                prepared.emitted_events,
                f"prepare:{type(error).__name__}:{error}",
            )

        for index, (capability_id, provider, token) in enumerate(tokens):
            try:
                provider.commit(token)
                committed += 1
            except Exception as error:
                for _id, pending_provider, pending_token in reversed(tokens[index + 1:]):
                    try:
                        pending_provider.abort(pending_token)
                    except Exception:
                        pass
                law = laws.law(capability_id)
                status = (
                    "LAW_VIOLATION"
                    if law is not None and law.commit_total_after_prepare
                    else "EXTERNAL_PARTIAL"
                )
                return CommitResultV1(
                    status,
                    prepared.prepared_reaction_hash,
                    False,
                    True,
                    committed,
                    prepared.emitted_events,
                    f"commit:{type(error).__name__}:{error}",
                )
    else:
        for intent in prepared.effect_intents:
            capability_id = str(intent["capability_id"])
            provider = providers.get(capability_id)
            if provider is None or not callable(provider):
                return CommitResultV1(
                    "EXTERNAL_PARTIAL",
                    prepared.prepared_reaction_hash,
                    False,
                    True,
                    committed,
                    prepared.emitted_events,
                    f"missing effect provider {capability_id}",
                )
            try:
                provider(*_decode_intent_arguments(runtime, intent))
                committed += 1
            except Exception as error:
                return CommitResultV1(
                    "EXTERNAL_PARTIAL",
                    prepared.prepared_reaction_hash,
                    False,
                    True,
                    committed,
                    prepared.emitted_events,
                    f"effect:{type(error).__name__}:{error}",
                )

    _publish_after_checkpoint(runtime, prepared)
    return CommitResultV1(
        "COMMITTED",
        prepared.prepared_reaction_hash,
        True,
        False,
        committed,
        prepared.emitted_events,
        "",
    )


__all__ = [
    "PreparedReactionBundleV1",
    "prepare_reaction",
    "commit_prepared_reaction",
]
