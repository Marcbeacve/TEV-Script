from __future__ import annotations
from dataclasses import dataclass

_STRONG_METHODS = frozenset({"proved", "attested", "exhaustive"})

@dataclass(frozen=True, slots=True)
class LawJustificationV0:
    claim_hash: str
    method: str
    scope: str
    source: str
    status: str = "active"

    def is_strong(self) -> bool:
        return self.status == "active" and self.method in _STRONG_METHODS

@dataclass(frozen=True, slots=True)
class CenterContextV0:
    center_id: str
    view_hash: str
    knowledge_hash: str
    authority_hash: str
    frame_hash: str
    policy_hash: str

@dataclass(frozen=True, slots=True)
class DecisionDimensionsV0:
    possible: bool | None
    authorized: bool | None
    safe: bool | None
    resources_available: bool | None
    desirable_score: int | None = None

    def admissibility(self) -> str:
        required = (self.possible, self.authorized, self.safe, self.resources_available)
        if any(v is False for v in required):
            return "REJECT"
        if any(v is None for v in required):
            return "UNKNOWN"
        return "ADMISSIBLE"

def law_claim_status(evidence: tuple[LawJustificationV0, ...]) -> str:
    if any(e.status == "falsified" for e in evidence):
        return "REJECT"
    if any(e.is_strong() for e in evidence):
        return "PASS"
    return "PROOF_REQUIRED"

__all__ = ["LawJustificationV0", "CenterContextV0", "DecisionDimensionsV0", "law_claim_status"]
