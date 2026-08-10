from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True, slots=True)
class SemanticArtifactV0:
    artifact_id: str
    artifact_hash: str
    stratum: int

    def __post_init__(self) -> None:
        if self.stratum < 0:
            raise ValueError("stratum")

@dataclass(frozen=True, slots=True)
class ChangeProposalV0:
    subject: SemanticArtifactV0
    candidate_hash: str
    verifier: SemanticArtifactV0
    touched_artifacts: tuple[str, ...] = ()

def verify_stratified_change(proposal: ChangeProposalV0, evidence_methods: Iterable[str]) -> tuple[str, tuple[str, ...]]:
    reasons = []
    if proposal.verifier.stratum <= proposal.subject.stratum:
        reasons.append("verification_authority_not_above_subject")
    if proposal.verifier.artifact_id in proposal.touched_artifacts:
        reasons.append("candidate_changes_its_verifier")
    methods = set(evidence_methods)
    if not methods.intersection({"proved", "attested", "exhaustive"}):
        reasons.append("strong_evidence_missing")
    return ("PASS" if not reasons else "REJECT", tuple(reasons))

__all__ = ["SemanticArtifactV0", "ChangeProposalV0", "verify_stratified_change"]
