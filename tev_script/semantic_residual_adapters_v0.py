from __future__ import annotations

from typing import Any, Iterable, Mapping

from .semantic_kernel_v0 import META_RELATION, SemanticFieldV0, field_delta
from .semantic_residual_v0 import (
    DEFAULT_RESIDUAL_CONTEXT_HASH,
    DEFAULT_RESIDUAL_LAW_HASH,
    ResidualObstructionV0,
    residual_from_obstructions,
)

_MODE_SUCCESS = {
    "evaluate": frozenset({"COMPLETED"}),
    "project": frozenset({"COMPLETED"}),
    "prepare": frozenset({"PREPARED"}),
    "replay": frozenset({"PREPARED"}),
    "commit": frozenset({"COMMITTED"}),
}
_FAILURE_OUTCOME_KINDS = {
    "REJECTED": "operational.application_rejected",
    "FAILED": "operational.application_failed",
    "PARTIAL": "operational.partial_commit",
    "UNKNOWN_COMMIT": "operational.unknown_commit",
    "LAW_VIOLATION": "operational.law_violation",
    "ABSTAINED": "operational.abstained",
    "DEFERRED": "operational.deferred",
    "SUSPENDED": "operational.suspended",
    "BUDGET_EXCEEDED": "resource.budget_exceeded",
    "CAPABILITY_UNAVAILABLE": "authority.capability_unavailable",
}


def _object_source(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"kind": kind, **dict(payload)}


def residual_from_application_outcome(
    outcome: SemanticFieldV0,
    *,
    judgment_id: str = "application_closure",
    acceptable_statuses: Iterable[str] | None = None,
) -> SemanticFieldV0:
    roots = outcome.facts_for("tev.outcome")
    if len(roots) != 1:
        raise ValueError("invalid outcome field")
    status, mode, before_hash, after_hash, rule_hash, context_hash, law_hash, handler_id = roots[0].arguments
    status = str(status)
    mode = str(mode)
    accepted = (
        frozenset(str(value) for value in acceptable_statuses)
        if acceptable_statuses is not None
        else _MODE_SUCCESS.get(mode, frozenset())
    )
    if not accepted:
        raise ValueError("no accepted outcome status for mode")
    reasons = tuple(sorted(str(f.arguments[0]) for f in outcome.facts_for("tev.outcome.reason")))
    obstructions: tuple[ResidualObstructionV0, ...]
    if status in accepted:
        obstructions = ()
    else:
        code = _FAILURE_OUTCOME_KINDS.get(status, "operational.status_unaccepted")
        obstructions = (
            ResidualObstructionV0(
                code,
                str(rule_hash),
                {"acceptable_statuses": sorted(accepted)},
                {"status": status, "mode": mode},
                {
                    "reasons": list(reasons),
                    "before_field_hash": str(before_hash),
                    "after_field_hash": str(after_hash),
                    "handler_id": str(handler_id),
                },
                dependency_refs=(outcome.field_hash, str(rule_hash)),
            ),
        )
    return residual_from_obstructions(
        domain="operational",
        judgment_id=judgment_id,
        judgment={
            "kind": "application_regime_success",
            "mode": mode,
            "rule_hash": str(rule_hash),
            "acceptable_statuses": sorted(accepted),
        },
        source=_object_source("application_outcome", {"outcome_field_hash": outcome.field_hash}),
        obstructions=obstructions,
        context_hash=str(context_hash),
        law_hash=str(law_hash),
    )


def residual_from_inference_judgment(
    judgment: Any,
    *,
    judgment_id: str = "inference_closure",
) -> SemanticFieldV0:
    status = str(getattr(judgment, "status"))
    reason = str(getattr(judgment, "reason", ""))
    countermodel = tuple(tuple(row) for row in getattr(judgment, "countermodel", ()))
    source = {
        "kind": "inference_judgment",
        "status": status,
        "reason": reason,
        "countermodel": [list(row) for row in countermodel],
    }
    if status == "PASS":
        obstructions = ()
    elif status == "PROOF_REQUIRED":
        obstructions = (
            ResidualObstructionV0(
                "proof.required",
                reason or "inference",
                "discharged",
                "pending",
                {"reason": reason},
            ),
        )
    elif status == "REJECT":
        obstructions = (
            ResidualObstructionV0(
                "epistemic.countermodel",
                reason or "inference",
                "conclusion_supported",
                [list(row) for row in countermodel],
                {"reason": reason},
            ),
        )
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
    deps = (str(witness.proof_hash), str(witness.verifier_hash), str(trust_policy.policy_hash))
    if not accepted:
        if str(witness.scope_hash) != str(expected_scope_hash):
            obstructions.append(
                ResidualObstructionV0(
                    "proof.scope_mismatch", "proof.scope", str(expected_scope_hash), str(witness.scope_hash),
                    dependency_refs=deps,
                )
            )
        if str(witness.status) != "active":
            obstructions.append(
                ResidualObstructionV0(
                    "proof.inactive", "proof.status", "active", str(witness.status), dependency_refs=deps,
                )
            )
        if str(witness.method) not in {"proved", "attested", "exhaustive"}:
            obstructions.append(
                ResidualObstructionV0(
                    "proof.method_weak", "proof.method",
                    ["proved", "attested", "exhaustive"], str(witness.method), dependency_refs=deps,
                )
            )
        if str(witness.verifier_hash) not in tuple(str(v) for v in trust_policy.trusted_verifier_hashes):
            obstructions.append(
                ResidualObstructionV0(
                    "proof.untrusted_verifier", "proof.verifier", "trusted", str(witness.verifier_hash),
                    dependency_refs=deps,
                )
            )
        if not obstructions:
            obstructions.append(
                ResidualObstructionV0(
                    "proof.required", "proof.boundary", "accepted", "rejected", dependency_refs=deps,
                )
            )
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
    context_hash: str = DEFAULT_RESIDUAL_CONTEXT_HASH,
    law_hash: str = DEFAULT_RESIDUAL_LAW_HASH,
) -> SemanticFieldV0:
    scope = None if relation_scope is None else frozenset(str(x) for x in relation_scope)
    missing, unexpected = field_delta(observed, expected)
    obstructions: list[ResidualObstructionV0] = []
    deps = (observed.field_hash, expected.field_hash)
    for fact in missing:
        if fact.relation == META_RELATION or (scope is not None and fact.relation not in scope):
            continue
        obstructions.append(
            ResidualObstructionV0(
                f"{domain}.missing_fact",
                fact.relation,
                list(fact.arguments),
                None,
                {"expected_fact_hash": fact.fact_hash},
                dependency_refs=deps,
            )
        )
    for fact in unexpected:
        if fact.relation == META_RELATION or (scope is not None and fact.relation not in scope):
            continue
        obstructions.append(
            ResidualObstructionV0(
                f"{domain}.unexpected_fact",
                fact.relation,
                None,
                list(fact.arguments),
                {"observed_fact_hash": fact.fact_hash},
                dependency_refs=deps,
            )
        )
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={
            "kind": "field_equality",
            "expected_field_hash": expected.field_hash,
            "relation_scope": None if scope is None else sorted(scope),
        },
        source={"kind": "semantic_field", "field_hash": observed.field_hash},
        obstructions=obstructions,
        context_hash=context_hash,
        law_hash=law_hash,
    )


def residual_from_obligations(
    *,
    domain: str,
    judgment_id: str,
    kind: str,
    obligations: Iterable[str],
    source: Any,
    expected: Any = "discharged",
    observed: Any = "pending",
) -> SemanticFieldV0:
    rows = tuple(sorted(set(str(x) for x in obligations)))
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={
            "kind": "obligations_discharged",
            "obligation_kind": kind,
            "obligations": list(rows),
        },
        source=source,
        obstructions=(
            ResidualObstructionV0(
                kind, item, expected, observed, dependency_refs=(item,)
            )
            for item in rows
        ),
    )


def residual_from_missing_authority(
    capabilities: Iterable[str], *, judgment_id: str = "authority_closure", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="authority", judgment_id=judgment_id, kind="authority.missing",
        obligations=capabilities, source={"kind": "authority_check", "source": source},
    )


def residual_from_missing_knowledge(
    propositions: Iterable[str], *, judgment_id: str = "knowledge_closure", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="epistemic", judgment_id=judgment_id, kind="epistemic.missing_knowledge",
        obligations=propositions, source={"kind": "knowledge_check", "source": source},
    )


def residual_from_causal_hazards(
    hazards: Iterable[str], *, judgment_id: str = "causal_preparability", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="causal", judgment_id=judgment_id, kind="causal.hazard",
        obligations=hazards, source={"kind": "causal_analysis", "source": source},
        expected="absent", observed="present",
    )


def residual_from_refinement_failures(
    failures: Iterable[str], *, judgment_id: str = "refinement_closure", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="refinement", judgment_id=judgment_id, kind="refinement.failure",
        obligations=failures, source={"kind": "refinement_check", "source": source},
    )


def residual_from_resource_deficits(
    resources: Iterable[str], *, judgment_id: str = "resource_closure", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="resource", judgment_id=judgment_id, kind="resource.deficit",
        obligations=resources, source={"kind": "resource_check", "source": source},
        expected="available", observed="insufficient",
    )


def residual_from_safety_violations(
    violations: Iterable[str], *, judgment_id: str = "safety_closure", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="safety", judgment_id=judgment_id, kind="safety.violation",
        obligations=violations, source={"kind": "safety_check", "source": source},
        expected="safe", observed="violated",
    )


def residual_from_liveness_obligations(
    obligations: Iterable[str], *, judgment_id: str = "liveness_closure", source: Any = None
) -> SemanticFieldV0:
    return residual_from_obligations(
        domain="liveness", judgment_id=judgment_id, kind="liveness.pending",
        obligations=obligations, source={"kind": "liveness_check", "source": source},
    )


__all__ = [
    "residual_from_application_outcome", "residual_from_inference_judgment",
    "residual_from_proof_boundary", "residual_from_divergence", "residual_from_obligations",
    "residual_from_missing_authority", "residual_from_missing_knowledge",
    "residual_from_causal_hazards", "residual_from_refinement_failures",
    "residual_from_resource_deficits", "residual_from_safety_violations",
    "residual_from_liveness_obligations",
]
