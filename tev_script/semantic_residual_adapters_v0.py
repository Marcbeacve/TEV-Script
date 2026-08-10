from __future__ import annotations

from typing import Any, Iterable, Mapping

from .semantic_kernel_v0 import META_RELATION, SemanticFieldV0, field_delta
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

_SUCCESS_OUTCOME_STATUSES = frozenset({"COMPLETED", "PREPARED", "COMMITTED"})
_FAILURE_OUTCOME_KINDS = {
    "REJECTED": "application_rejected",
    "FAILED": "application_failed",
    "PARTIAL": "partial_commit",
    "UNKNOWN_COMMIT": "unknown_commit",
    "LAW_VIOLATION": "law_violation",
}

def _object_source(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"kind": kind, **dict(payload)}

def residual_from_application_outcome(
    outcome: SemanticFieldV0,
    *,
    judgment_id: str = "application_closure",
) -> SemanticFieldV0:
    roots = outcome.facts_for("tev.outcome")
    if len(roots) != 1:
        raise ValueError("invalid outcome field")
    status, mode, before_hash, after_hash, rule_hash, context_hash, law_hash, handler_id = roots[0].arguments
    status = str(status); mode = str(mode)
    if status not in _SUCCESS_OUTCOME_STATUSES and status not in _FAILURE_OUTCOME_KINDS:
        raise ValueError("unsupported outcome status")
    reasons = tuple(str(f.arguments[0]) for f in outcome.facts_for("tev.outcome.reason"))
    obstructions = () if status in _SUCCESS_OUTCOME_STATUSES else (
        ResidualObstructionV0(
            _FAILURE_OUTCOME_KINDS[status],
            str(rule_hash),
            {"terminal": "success"},
            {"status": status, "mode": mode},
            {
                "reasons": list(reasons),
                "before_field_hash": str(before_hash),
                "after_field_hash": str(after_hash),
                "context_hash": str(context_hash),
                "law_hash": str(law_hash),
                "handler_id": str(handler_id),
            },
        ),
    )
    return residual_from_obstructions(
        domain="operational",
        judgment_id=judgment_id,
        judgment={"kind": "application_terminal_success", "mode": mode, "rule_hash": str(rule_hash)},
        source=_object_source("application_outcome", {"outcome_field_hash": outcome.field_hash}),
        obstructions=obstructions,
    )

def residual_from_inference_judgment(
    judgment: Any,
    *,
    judgment_id: str = "inference_closure",
) -> SemanticFieldV0:
    status = str(getattr(judgment, "status"))
    reason = str(getattr(judgment, "reason", ""))
    countermodel = tuple(tuple(row) for row in getattr(judgment, "countermodel", ()))
    source = {"kind": "inference_judgment", "status": status, "reason": reason, "countermodel": [list(row) for row in countermodel]}
    if status == "PASS":
        obstructions = ()
    elif status == "PROOF_REQUIRED":
        obstructions = (ResidualObstructionV0("proof_required", reason or "inference", "discharged", "pending", {"reason": reason}),)
    elif status == "REJECT":
        obstructions = (ResidualObstructionV0("countermodel", reason or "inference", "conclusion_supported", [list(row) for row in countermodel], {"reason": reason}),)
    else:
        raise ValueError("unsupported inference status")
    return residual_from_obstructions(
        domain="epistemic",
        judgment_id=judgment_id,
        judgment={"kind": "inference_acceptance"},
        source=source,
        obstructions=obstructions,
    )

def residual_from_proof_boundary(
    witness: Any,
    trust_policy: Any,
    expected_scope_hash: str,
    *,
    judgment_id: str = "proof_boundary",
) -> SemanticFieldV0:
    accepted = bool(trust_policy.accepts(witness, expected_scope_hash))
    source = {
        "kind": "proof_boundary",
        "proof_hash": str(witness.proof_hash),
        "verifier_hash": str(witness.verifier_hash),
        "scope_hash": str(witness.scope_hash),
        "method": str(witness.method),
        "status": str(witness.status),
        "policy_hash": str(trust_policy.policy_hash),
    }
    obstructions: list[ResidualObstructionV0] = []
    if not accepted:
        if str(witness.scope_hash) != str(expected_scope_hash):
            obstructions.append(ResidualObstructionV0("scope_mismatch", "proof.scope", str(expected_scope_hash), str(witness.scope_hash)))
        if str(witness.status) != "active":
            obstructions.append(ResidualObstructionV0("proof_inactive", "proof.status", "active", str(witness.status)))
        if str(witness.method) not in {"proved", "attested", "exhaustive"}:
            obstructions.append(ResidualObstructionV0("proof_method_weak", "proof.method", ["proved", "attested", "exhaustive"], str(witness.method)))
        if str(witness.verifier_hash) not in tuple(str(v) for v in trust_policy.trusted_verifier_hashes):
            obstructions.append(ResidualObstructionV0("untrusted_verifier", "proof.verifier", "trusted", str(witness.verifier_hash)))
        if not obstructions:
            obstructions.append(ResidualObstructionV0("proof_required", "proof.boundary", "accepted", "rejected"))
    return residual_from_obstructions(
        domain="proof",
        judgment_id=judgment_id,
        judgment={"kind": "trusted_proof", "scope_hash": str(expected_scope_hash)},
        source=source,
        obstructions=obstructions,
    )

def residual_from_divergence(
    observed: SemanticFieldV0,
    expected: SemanticFieldV0,
    *,
    domain: str,
    judgment_id: str,
    relation_scope: Iterable[str] | None = None,
) -> SemanticFieldV0:
    scope = None if relation_scope is None else frozenset(str(x) for x in relation_scope)
    missing, unexpected = field_delta(observed, expected)
    obstructions: list[ResidualObstructionV0] = []
    for fact in missing:
        if fact.relation == META_RELATION or (scope is not None and fact.relation not in scope):
            continue
        obstructions.append(ResidualObstructionV0("missing_fact", fact.relation, list(fact.arguments), None, {"expected_fact_hash": fact.fact_hash}))
    for fact in unexpected:
        if fact.relation == META_RELATION or (scope is not None and fact.relation not in scope):
            continue
        obstructions.append(ResidualObstructionV0("unexpected_fact", fact.relation, None, list(fact.arguments), {"observed_fact_hash": fact.fact_hash}))
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={"kind": "field_equality", "expected_field_hash": expected.field_hash, "relation_scope": None if scope is None else sorted(scope)},
        source={"kind": "semantic_field", "field_hash": observed.field_hash},
        obstructions=obstructions,
    )

def residual_from_obligations(
    *,
    domain: str,
    judgment_id: str,
    kind: str,
    obligations: Iterable[str],
    source: Any,
) -> SemanticFieldV0:
    rows = tuple(sorted(set(str(x) for x in obligations)))
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={"kind": "obligations_discharged", "obligation_kind": kind, "obligations": list(rows)},
        source=source,
        obstructions=(ResidualObstructionV0(kind, item, "discharged", "pending") for item in rows),
    )

def residual_from_missing_authority(capabilities: Iterable[str], *, judgment_id: str = "authority_closure", source: Any = None) -> SemanticFieldV0:
    return residual_from_obligations(domain="authority", judgment_id=judgment_id, kind="missing_authority", obligations=capabilities, source={"kind": "authority_check", "source": source})

def residual_from_missing_knowledge(propositions: Iterable[str], *, judgment_id: str = "knowledge_closure", source: Any = None) -> SemanticFieldV0:
    return residual_from_obligations(domain="epistemic", judgment_id=judgment_id, kind="missing_knowledge", obligations=propositions, source={"kind": "knowledge_check", "source": source})

def residual_from_causal_hazards(hazards: Iterable[str], *, judgment_id: str = "causal_preparability", source: Any = None) -> SemanticFieldV0:
    return residual_from_obligations(domain="causal", judgment_id=judgment_id, kind="causal_hazard", obligations=hazards, source={"kind": "causal_analysis", "source": source})

def residual_from_refinement_failures(failures: Iterable[str], *, judgment_id: str = "refinement_closure", source: Any = None) -> SemanticFieldV0:
    return residual_from_obligations(domain="refinement", judgment_id=judgment_id, kind="refinement_failure", obligations=failures, source={"kind": "refinement_check", "source": source})

__all__ = [
    "residual_from_application_outcome", "residual_from_inference_judgment",
    "residual_from_proof_boundary", "residual_from_divergence", "residual_from_obligations",
    "residual_from_missing_authority", "residual_from_missing_knowledge",
    "residual_from_causal_hazards", "residual_from_refinement_failures",
]
