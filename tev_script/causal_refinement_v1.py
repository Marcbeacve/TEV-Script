from __future__ import annotations

from typing import Any, Mapping

from .canonical import canonical_json
from .causal_analysis_v1 import reaction_resources
from .causal_model_v1 import (
    CapabilityLawCatalogV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)

_ATOMICITY_RANK = {
    "interleaved": 0,
    "state_atomic_external_partial_possible": 1,
    "state_atomic": 1,
    "transactional": 2,
    "durable_transactional": 3,
}
_REQUIRED_RANK = {"any": 0, "state_atomic": 1, "transactional": 2, "durable_transactional": 3}


def _extra(kind: str, values, allowed) -> dict[str, object] | None:
    extra = sorted(set(values) - set(allowed))
    return None if not extra else {"kind": kind, "extra": extra}


def _checkpoint_state(
    checkpoint: Mapping[str, Any], entity_id: str, state_name: str
) -> Mapping[str, Any] | None:
    for raw_entity in checkpoint.get("entities", []):
        if raw_entity.get("entity_id") == entity_id:
            value = raw_entity.get("state", {}).get(state_name)
            return value if isinstance(value, Mapping) else None
    return None


def verify_structural_refinement(
    contract: ReactionContractV1,
    footprint: ReactionFootprintV1,
    catalog: CapabilityLawCatalogV1,
) -> RefinementReceiptV1:
    failures: list[dict[str, object]] = []
    if footprint.entity_id != contract.entity_id:
        failures.append({"kind": "entity_id", "expected": contract.entity_id, "observed": footprint.entity_id})
    if footprint.trigger_event != contract.trigger_event:
        failures.append({"kind": "trigger_event", "expected": contract.trigger_event, "observed": footprint.trigger_event})
    for kind, values, allowed in (
        ("state_reads", footprint.state_reads, contract.allowed_state_reads),
        ("state_writes", footprint.state_writes, contract.allowed_state_writes),
        ("observations", footprint.observations, contract.allowed_observations),
        ("effects", footprint.effects, contract.allowed_effects),
        ("emitted_events", footprint.emitted_events, contract.allowed_emitted_events),
        ("resources", reaction_resources(footprint, catalog), contract.allowed_resources),
    ):
        failure = _extra(kind, values, allowed)
        if failure is not None:
            failures.append(failure)
    if footprint.reachable_handler_count > contract.maximum_reachable_events:
        failures.append({
            "kind": "reachable_events_budget",
            "observed": footprint.reachable_handler_count,
            "maximum": contract.maximum_reachable_events,
        })
    if footprint.instruction_ceiling > contract.maximum_instruction_ceiling:
        failures.append({
            "kind": "instruction_ceiling_budget",
            "observed": footprint.instruction_ceiling,
            "maximum": contract.maximum_instruction_ceiling,
        })
    pending = tuple(item.obligation_id for item in contract.proof_obligations)
    status = "REJECT" if failures else ("PROOF_REQUIRED" if pending else "PASS")
    return RefinementReceiptV1(
        contract_hash=contract.contract_hash,
        candidate_program_semantic_hash=footprint.program_semantic_hash,
        footprint_hash=footprint.footprint_hash,
        law_catalog_hash=catalog.catalog_hash,
        status=status,
        failures=tuple(failures),
        pending_obligations=pending,
    )


def verify_prepared_refinement(
    contract: ReactionContractV1,
    footprint: ReactionFootprintV1,
    catalog: CapabilityLawCatalogV1,
    before_checkpoint: Mapping[str, Any],
    after_checkpoint: Mapping[str, Any],
    atomicity: str,
) -> RefinementReceiptV1:
    structural = verify_structural_refinement(contract, footprint, catalog)
    failures = [dict(item) for item in structural.failures]
    if atomicity not in _ATOMICITY_RANK:
        failures.append({"kind": "atomicity_unknown", "observed": atomicity})
    elif _ATOMICITY_RANK[atomicity] < _REQUIRED_RANK[contract.required_atomicity]:
        failures.append({
            "kind": "atomicity",
            "required": contract.required_atomicity,
            "observed": atomicity,
        })
    if contract.protocol is not None:
        before = _checkpoint_state(before_checkpoint, contract.entity_id, contract.protocol.state_name)
        after = _checkpoint_state(after_checkpoint, contract.entity_id, contract.protocol.state_name)
        if before is None or after is None:
            failures.append({"kind": "protocol_state_missing", "state_name": contract.protocol.state_name})
        else:
            matched = any(
                edge.event_id == contract.trigger_event
                and canonical_json(dict(edge.before)) == canonical_json(dict(before))
                and canonical_json(dict(edge.after)) == canonical_json(dict(after))
                for edge in contract.protocol.edges
            )
            if not matched:
                failures.append({
                    "kind": "protocol_edge_absent",
                    "state_name": contract.protocol.state_name,
                    "event_id": contract.trigger_event,
                    "before": dict(before),
                    "after": dict(after),
                })
    pending = tuple(item.obligation_id for item in contract.proof_obligations)
    status = "REJECT" if failures else ("PROOF_REQUIRED" if pending else "PASS")
    return RefinementReceiptV1(
        contract_hash=contract.contract_hash,
        candidate_program_semantic_hash=footprint.program_semantic_hash,
        footprint_hash=footprint.footprint_hash,
        law_catalog_hash=catalog.catalog_hash,
        status=status,
        failures=tuple(failures),
        pending_obligations=pending,
    )


def contract_from_footprint(
    contract_id: str,
    footprint: ReactionFootprintV1,
    catalog: CapabilityLawCatalogV1,
    *,
    required_atomicity: str = "any",
) -> ReactionContractV1:
    return ReactionContractV1(
        contract_id=contract_id,
        entity_id=footprint.entity_id,
        trigger_event=footprint.trigger_event,
        allowed_state_reads=footprint.state_reads,
        allowed_state_writes=footprint.state_writes,
        allowed_observations=footprint.observations,
        allowed_effects=footprint.effects,
        allowed_emitted_events=footprint.emitted_events,
        allowed_resources=reaction_resources(footprint, catalog),
        maximum_reachable_events=footprint.reachable_handler_count,
        maximum_instruction_ceiling=footprint.instruction_ceiling,
        required_atomicity=required_atomicity,
    )


__all__ = [
    "verify_structural_refinement",
    "verify_prepared_refinement",
    "contract_from_footprint",
]
