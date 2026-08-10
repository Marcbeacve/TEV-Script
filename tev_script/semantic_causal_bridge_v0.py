from __future__ import annotations

from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .causal_model_v1 import (
    CapabilityLawCatalogV1,
    CommitResultV1,
    PreparedReactionV1,
    PreparabilityResultV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from .semantic_kernel_v0 import FactV0, SemanticFieldV0
from .semantic_residual_v0 import (
    ResidualObstructionV0,
    residual_from_obstructions,
)

CAUSAL_SEMANTIC_BRIDGE_PROFILE_V0 = "TEV_SCRIPT_CAUSAL_SEMANTIC_BRIDGE_V0"
CAUSAL_ARTIFACT_DECLS_V0 = (
    ("tev.causal.artifact", 4),
    ("tev.causal.binding", 3),
)
_COMMIT_STATUS_KINDS = {
    "ABORTED": "operational.application_aborted",
    "EXTERNAL_PARTIAL": "operational.partial_commit",
    "LAW_VIOLATION": "operational.law_violation",
}


def _artifact_field(
    *,
    kind: str,
    schema: str,
    identity_hash: str,
    payload: Mapping[str, Any],
    bindings: Iterable[tuple[str, str, Any]] = (),
) -> SemanticFieldV0:
    body = dict(payload)
    if body.get("schema") != schema:
        raise ValueError("causal artifact schema mismatch")
    if len(identity_hash) != 64 or any(ch not in "0123456789abcdef" for ch in identity_hash):
        raise ValueError("causal artifact identity hash")
    payload_json = canonical_json(body)
    facts = [
        FactV0(
            "tev.causal.artifact",
            (CAUSAL_SEMANTIC_BRIDGE_PROFILE_V0, kind, identity_hash, payload_json),
        )
    ]
    for role, key, value in sorted(
        ((str(role), str(key), value) for role, key, value in bindings),
        key=lambda row: (row[0], row[1], canonical_json(row[2])),
    ):
        facts.append(FactV0("tev.causal.binding", (role, key, canonical_json(value))))
    return SemanticFieldV0.build(CAUSAL_ARTIFACT_DECLS_V0, facts)


def reaction_contract_field(contract: ReactionContractV1) -> SemanticFieldV0:
    payload = contract.to_object()
    return _artifact_field(
        kind="reaction_contract",
        schema=str(payload["schema"]),
        identity_hash=contract.contract_hash,
        payload=payload,
        bindings=(
            ("identity", "contract_id", contract.contract_id),
            ("reaction", "entity_id", contract.entity_id),
            ("reaction", "trigger_event", contract.trigger_event),
        ),
    )


def capability_law_catalog_field(catalog: CapabilityLawCatalogV1) -> SemanticFieldV0:
    payload = catalog.to_object()
    return _artifact_field(
        kind="capability_law_catalog",
        schema=str(payload["schema"]),
        identity_hash=catalog.catalog_hash,
        payload=payload,
        bindings=(
            ("identity", "deployment_id", catalog.deployment_id),
            ("authority", "complete", catalog.complete),
        ),
    )


def reaction_footprint_field(footprint: ReactionFootprintV1) -> SemanticFieldV0:
    payload = footprint.to_object()
    return _artifact_field(
        kind="reaction_footprint",
        schema=str(payload["schema"]),
        identity_hash=footprint.footprint_hash,
        payload=payload,
        bindings=(
            ("program", "program_semantic_hash", footprint.program_semantic_hash),
            ("program", "source_semantic_hash", footprint.source_semantic_hash),
            ("reaction", "entity_id", footprint.entity_id),
            ("reaction", "trigger_event", footprint.trigger_event),
        ),
    )


def refinement_receipt_field(receipt: RefinementReceiptV1) -> SemanticFieldV0:
    payload = receipt.to_object()
    return _artifact_field(
        kind="refinement_receipt",
        schema=str(payload["schema"]),
        identity_hash=receipt.receipt_hash,
        payload=payload,
        bindings=(
            ("contract", "contract_hash", receipt.contract_hash),
            ("program", "program_semantic_hash", receipt.candidate_program_semantic_hash),
            ("footprint", "footprint_hash", receipt.footprint_hash),
            ("law", "law_catalog_hash", receipt.law_catalog_hash),
            ("verdict", "status", receipt.status),
        ),
    )


def prepared_reaction_field(prepared: PreparedReactionV1) -> SemanticFieldV0:
    payload = prepared.to_object()
    return _artifact_field(
        kind="prepared_reaction",
        schema=str(payload["schema"]),
        identity_hash=prepared.prepared_reaction_hash,
        payload=payload,
        bindings=(
            ("program", "program_semantic_hash", prepared.program_semantic_hash),
            ("program", "source_semantic_hash", prepared.source_semantic_hash),
            ("contract", "contract_hash", prepared.contract_hash),
            ("law", "law_catalog_hash", prepared.law_catalog_hash),
            ("refinement", "refinement_receipt_hash", prepared.refinement_receipt_hash),
            ("footprint", "footprint_hash", prepared.footprint_hash),
            ("reaction", "entity_id", prepared.entity_id),
            ("reaction", "trigger_event", prepared.trigger_event),
            ("state", "before_checkpoint_hash", prepared.before_checkpoint_hash),
            ("state", "after_checkpoint_hash", prepared.after_checkpoint_hash),
            ("atomicity", "level", prepared.atomicity),
        ),
    )


def _commit_result_object(result: CommitResultV1) -> dict[str, Any]:
    return {
        "schema": "TEV_SCRIPT_CAUSAL_COMMIT_RESULT_V1",
        "status": str(result.status),
        "prepared_reaction_hash": str(result.prepared_reaction_hash),
        "state_committed": bool(result.state_committed),
        "external_partial": bool(result.external_partial),
        "committed_effects": int(result.committed_effects),
        "emitted_events": [dict(item) for item in result.emitted_events],
        "detail": str(result.detail),
    }


def commit_result_field(result: CommitResultV1) -> SemanticFieldV0:
    payload = _commit_result_object(result)
    identity_hash = canonical_hash(payload)
    return _artifact_field(
        kind="commit_result",
        schema=str(payload["schema"]),
        identity_hash=identity_hash,
        payload=payload,
        bindings=(
            ("prepared", "prepared_reaction_hash", result.prepared_reaction_hash),
            ("verdict", "status", result.status),
            ("state", "state_committed", result.state_committed),
            ("external", "external_partial", result.external_partial),
            ("external", "committed_effects", result.committed_effects),
        ),
    )


def _preparability_object(result: PreparabilityResultV1) -> dict[str, Any]:
    return {
        "schema": "TEV_SCRIPT_CAUSAL_PREPARABILITY_RESULT_V1",
        "preparable": bool(result.preparable),
        "atomicity": str(result.atomicity),
        "reasons": list(result.reasons),
        "hazards": [list(item) for item in result.hazards],
    }


def preparability_result_field(result: PreparabilityResultV1) -> SemanticFieldV0:
    payload = _preparability_object(result)
    return _artifact_field(
        kind="preparability_result",
        schema=str(payload["schema"]),
        identity_hash=canonical_hash(payload),
        payload=payload,
        bindings=(
            ("verdict", "preparable", result.preparable),
            ("atomicity", "level", result.atomicity),
        ),
    )


def causal_semantic_snapshot(*fields: SemanticFieldV0) -> SemanticFieldV0:
    if not fields:
        return SemanticFieldV0.build(CAUSAL_ARTIFACT_DECLS_V0, ())
    result = fields[0]
    for field in fields[1:]:
        result = result.merge(field)
    return result


def residual_from_preparability_result_v1(
    result: PreparabilityResultV1,
    *,
    footprint: ReactionFootprintV1 | None = None,
    laws: CapabilityLawCatalogV1 | None = None,
    judgment_id: str = "causal_preparability",
) -> SemanticFieldV0:
    if result.preparable and (result.reasons or result.hazards):
        raise ValueError("preparable result cannot carry reasons or hazards")
    dependencies = tuple(
        value
        for value in (
            None if footprint is None else footprint.footprint_hash,
            None if laws is None else laws.catalog_hash,
        )
        if value is not None
    )
    obstructions: list[ResidualObstructionV0] = []
    if not result.preparable:
        for reason in sorted(set(str(item) for item in result.reasons)):
            obstructions.append(
                ResidualObstructionV0(
                    "causal.preparability_reason",
                    reason,
                    "absent",
                    "present",
                    {"atomicity": result.atomicity},
                    dependency_refs=dependencies,
                )
            )
        for effect_id, observation_id in sorted(set(result.hazards)):
            obstructions.append(
                ResidualObstructionV0(
                    "causal.staging_hazard",
                    f"{effect_id}->{observation_id}",
                    "non_interfering",
                    "may_interfere",
                    {
                        "effect_capability": effect_id,
                        "observation_capability": observation_id,
                        "atomicity": result.atomicity,
                    },
                    dependency_refs=dependencies,
                )
            )
        if not obstructions:
            obstructions.append(
                ResidualObstructionV0(
                    "causal.not_preparable",
                    "reaction",
                    "preparable",
                    "not_preparable",
                    {"atomicity": result.atomicity},
                    dependency_refs=dependencies,
                )
            )
    source_field = preparability_result_field(result)
    return residual_from_obstructions(
        domain="causal",
        judgment_id=judgment_id,
        judgment={
            "kind": "reaction_preparable",
            "required": True,
            "footprint_hash": None if footprint is None else footprint.footprint_hash,
            "law_catalog_hash": None if laws is None else laws.catalog_hash,
        },
        source={
            "kind": "causal_preparability_result",
            "field_hash": source_field.field_hash,
            "result": _preparability_object(result),
        },
        obstructions=obstructions,
    )


def residual_from_refinement_receipt_v1(
    receipt: RefinementReceiptV1,
    *,
    judgment_id: str = "causal_refinement",
) -> SemanticFieldV0:
    if receipt.status == "PASS" and (receipt.failures or receipt.pending_obligations):
        raise ValueError("PASS refinement receipt carries unresolved evidence")
    if receipt.status == "PROOF_REQUIRED" and receipt.failures:
        raise ValueError("PROOF_REQUIRED refinement receipt cannot carry failures")
    dependencies = (
        receipt.receipt_hash,
        receipt.contract_hash,
        receipt.candidate_program_semantic_hash,
        receipt.footprint_hash,
        receipt.law_catalog_hash,
    )
    obstructions: list[ResidualObstructionV0] = []
    if receipt.status == "REJECT":
        failures = tuple(dict(item) for item in receipt.failures)
        if not failures:
            failures = ({"kind": "unspecified_rejection"},)
        for index, failure in enumerate(failures):
            obstructions.append(
                ResidualObstructionV0(
                    "refinement.failure",
                    f"{failure.get('kind', 'failure')}:{index}",
                    "satisfied",
                    "violated",
                    failure,
                    evidence_hash=receipt.receipt_hash,
                    dependency_refs=dependencies,
                )
            )
    elif receipt.status == "PROOF_REQUIRED":
        obligations = tuple(receipt.pending_obligations)
        if not obligations:
            obstructions.append(
                ResidualObstructionV0(
                    "proof.required",
                    "refinement",
                    "discharged",
                    "pending",
                    evidence_hash=receipt.receipt_hash,
                    dependency_refs=dependencies,
                )
            )
        else:
            for obligation in obligations:
                obstructions.append(
                    ResidualObstructionV0(
                        "proof.required",
                        obligation,
                        "discharged",
                        "pending",
                        evidence_hash=receipt.receipt_hash,
                        dependency_refs=dependencies,
                    )
                )
    elif receipt.status != "PASS":
        raise ValueError("unsupported refinement status")
    source_field = refinement_receipt_field(receipt)
    return residual_from_obstructions(
        domain="refinement",
        judgment_id=judgment_id,
        judgment={
            "kind": "reaction_refines_contract",
            "contract_hash": receipt.contract_hash,
            "footprint_hash": receipt.footprint_hash,
            "law_catalog_hash": receipt.law_catalog_hash,
        },
        source={
            "kind": "causal_refinement_receipt",
            "field_hash": source_field.field_hash,
            "receipt_hash": receipt.receipt_hash,
            "status": receipt.status,
        },
        obstructions=obstructions,
    )


def residual_from_commit_result_v1(
    result: CommitResultV1,
    *,
    judgment_id: str = "causal_commit",
) -> SemanticFieldV0:
    status = str(result.status)
    if status == "COMMITTED":
        if not result.state_committed or result.external_partial:
            raise ValueError("COMMITTED result has inconsistent commit flags")
        obstructions: tuple[ResidualObstructionV0, ...] = ()
    else:
        if status not in _COMMIT_STATUS_KINDS:
            raise ValueError("unsupported causal commit status")
        if result.state_committed:
            raise ValueError("non-COMMITTED result cannot claim state committed")
        if status in {"EXTERNAL_PARTIAL", "LAW_VIOLATION"} and not result.external_partial:
            raise ValueError("partial/law-violation result must expose external partiality")
        if status == "ABORTED" and result.external_partial:
            raise ValueError("ABORTED result cannot claim external partiality")
        obstructions = (
            ResidualObstructionV0(
                _COMMIT_STATUS_KINDS[status],
                result.prepared_reaction_hash,
                {"status": "COMMITTED", "state_committed": True, "external_partial": False},
                {
                    "status": status,
                    "state_committed": result.state_committed,
                    "external_partial": result.external_partial,
                },
                {
                    "committed_effects": result.committed_effects,
                    "detail": result.detail,
                },
                dependency_refs=(result.prepared_reaction_hash,),
            ),
        )
    source_field = commit_result_field(result)
    return residual_from_obstructions(
        domain="operational",
        judgment_id=judgment_id,
        judgment={
            "kind": "causal_commit_success",
            "prepared_reaction_hash": result.prepared_reaction_hash,
            "required_status": "COMMITTED",
        },
        source={
            "kind": "causal_commit_result",
            "field_hash": source_field.field_hash,
            "result": _commit_result_object(result),
        },
        obstructions=obstructions,
    )


__all__ = [
    "CAUSAL_SEMANTIC_BRIDGE_PROFILE_V0",
    "CAUSAL_ARTIFACT_DECLS_V0",
    "reaction_contract_field",
    "capability_law_catalog_field",
    "reaction_footprint_field",
    "refinement_receipt_field",
    "prepared_reaction_field",
    "commit_result_field",
    "preparability_result_field",
    "causal_semantic_snapshot",
    "residual_from_preparability_result_v1",
    "residual_from_refinement_receipt_v1",
    "residual_from_commit_result_v1",
]
