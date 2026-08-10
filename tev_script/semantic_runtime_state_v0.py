from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

RUNTIME_STATE_OBSERVATION_SCHEMA_V0 = "TEV_SCRIPT_RUNTIME_STATE_OBSERVATION_V0"
RUNTIME_STATE_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_RUNTIME_STATE_CLAIM_V0"
RUNTIME_STATE_POLICY_SCHEMA_V0 = "TEV_SCRIPT_RUNTIME_STATE_POLICY_V0"
RUNTIME_STATE_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_RUNTIME_STATE_EVALUATION_V0"
_AVAILABILITY = frozenset({"AVAILABLE", "DEGRADED", "UNAVAILABLE", "UNKNOWN"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class RuntimeStateSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise RuntimeStateSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RuntimeStateSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class RuntimeStateObservationV0:
    machine_instance_hash: str
    observation_epoch_hash: str
    availability_status: str
    runtime_state_hash: str
    assumption_hashes: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()
    observation_source_hash: str = ""
    detail: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_instance_hash", _hash64(self.machine_instance_hash, "machine_instance_hash"))
        object.__setattr__(self, "observation_epoch_hash", _hash64(self.observation_epoch_hash, "observation_epoch_hash"))
        if self.availability_status not in _AVAILABILITY:
            raise RuntimeStateSemanticsError("unsupported availability_status")
        object.__setattr__(self, "runtime_state_hash", _hash64(self.runtime_state_hash, "runtime_state_hash"))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "runtime state assumption hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "runtime state evidence hash"))
        object.__setattr__(self, "observation_source_hash", _optional_hash(self.observation_source_hash, "observation_source_hash"))
        detail = {} if self.detail is None else dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def claim_object(self) -> dict[str, object]:
        return {
            "schema": RUNTIME_STATE_CLAIM_SCHEMA_V0,
            "machine_instance_hash": self.machine_instance_hash,
            "observation_epoch_hash": self.observation_epoch_hash,
            "availability_status": self.availability_status,
            "runtime_state_hash": self.runtime_state_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def runtime_state_claim_hash(self) -> str:
        return canonical_hash(self.claim_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RUNTIME_STATE_OBSERVATION_SCHEMA_V0,
            "runtime_state_claim_hash": self.runtime_state_claim_hash,
            **{key: value for key, value in self.claim_object().items() if key != "schema"},
            "evidence_hashes": list(self.evidence_hashes),
            "observation_source_hash": self.observation_source_hash,
            "detail": dict(self.detail or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.runtime_state.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RuntimeStatePolicyV0:
    evidence_policy_hash: str
    accepted_availability_statuses: tuple[str, ...] = ("AVAILABLE",)
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        statuses = tuple(sorted(set(str(item) for item in self.accepted_availability_statuses)))
        if not statuses or any(item not in _AVAILABILITY for item in statuses):
            raise RuntimeStateSemanticsError("accepted_availability_statuses")
        if "UNKNOWN" in statuses:
            raise RuntimeStateSemanticsError("UNKNOWN cannot be an admitted runtime availability status")
        object.__setattr__(self, "accepted_availability_statuses", statuses)
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "runtime accepted assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RUNTIME_STATE_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "accepted_availability_statuses": list(self.accepted_availability_statuses),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class RuntimeStateIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "runtime state issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RuntimeStateSemanticsError("runtime state issue severity")
        subject = str(self.subject)
        if not subject:
            raise RuntimeStateSemanticsError("runtime state issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class RuntimeStateEvaluationV0:
    runtime_state_claim_hash: str
    runtime_state_record_hash: str
    policy_hash: str
    evidence_evaluation_hash: str
    issues: tuple[RuntimeStateIssueV0, ...]

    def __post_init__(self) -> None:
        for name in ("runtime_state_claim_hash", "runtime_state_record_hash", "policy_hash", "evidence_evaluation_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RUNTIME_STATE_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "runtime_state_claim_hash": self.runtime_state_claim_hash,
            "runtime_state_record_hash": self.runtime_state_record_hash,
            "policy_hash": self.policy_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_runtime_state(
    observation: RuntimeStateObservationV0,
    *,
    policy: RuntimeStatePolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> RuntimeStateEvaluationV0:
    issues: list[RuntimeStateIssueV0] = []

    if policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(RuntimeStateIssueV0("runtime.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"expected": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(RuntimeStateIssueV0("runtime.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))

    if observation.availability_status == "UNKNOWN":
        issues.append(RuntimeStateIssueV0("runtime.availability_unknown", "PROOF_REQUIRED", observation.runtime_state_claim_hash, {}))
    elif observation.availability_status not in policy.accepted_availability_statuses:
        issues.append(RuntimeStateIssueV0("runtime.availability_not_accepted", "REJECT", observation.availability_status, {"accepted": list(policy.accepted_availability_statuses)}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(observation.assumption_hashes) - accepted_assumptions):
        issues.append(RuntimeStateIssueV0("runtime.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in observation.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(RuntimeStateIssueV0("runtime.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evaluation = evaluate_evidence(observation.runtime_state_claim_hash, evidence_policy, evidence_items)
    for item in evaluation.issues:
        issues.append(
            RuntimeStateIssueV0(
                "runtime." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in evaluation.accepted_evidence_hashes:
        if accepted_hash not in observation.evidence_hashes:
            issues.append(RuntimeStateIssueV0("runtime.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(RuntimeStateIssueV0("runtime.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return RuntimeStateEvaluationV0(
        observation.runtime_state_claim_hash,
        observation.record_hash,
        policy.policy_hash,
        evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_runtime_state(evaluation: RuntimeStateEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_runtime_state",
        judgment_id="runtime_state_admission",
        judgment={
            "kind": "runtime_state_admissible",
            "runtime_state_claim_hash": evaluation.runtime_state_claim_hash,
            "status": evaluation.status,
        },
        source={"kind": "runtime_state_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(evaluation.runtime_state_claim_hash, evaluation.runtime_state_record_hash),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "RUNTIME_STATE_OBSERVATION_SCHEMA_V0",
    "RUNTIME_STATE_CLAIM_SCHEMA_V0",
    "RUNTIME_STATE_POLICY_SCHEMA_V0",
    "RUNTIME_STATE_EVALUATION_SCHEMA_V0",
    "RuntimeStateSemanticsError",
    "RuntimeStateObservationV0",
    "RuntimeStatePolicyV0",
    "RuntimeStateIssueV0",
    "RuntimeStateEvaluationV0",
    "evaluate_runtime_state",
    "residual_from_runtime_state",
]
