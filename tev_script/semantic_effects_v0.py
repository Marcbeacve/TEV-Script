from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json

_RESOURCE_MODES = frozenset({"read", "write", "consume", "reserve", "release"})
_TEMPORAL = frozenset({"snapshot", "stable", "sequence_sensitive", "unknown"})
_RECOVER = frozenset({"reversible", "compensable", "irreversible", "unknown"})
_STAGE = frozenset({"untouched", "reserved", "applied", "confirmed", "unknown"})
_DURABILITY = frozenset({"volatile", "durable", "unknown"})
_EXPOSURE = frozenset({"none", "acquired", "disclosed"})

@dataclass(frozen=True, slots=True)
class EffectAtomV0:
    domain: str
    resource: str
    mode: str
    payload: tuple[Any, ...] = ()
    temporal: str = "unknown"
    amount: int | None = None
    stage: str = "untouched"
    recoverability: str = "unknown"
    durability: str = "unknown"
    exposure: str = "none"

    def __post_init__(self) -> None:
        if self.mode not in _RESOURCE_MODES:
            raise ValueError("invalid effect mode")
        if self.temporal not in _TEMPORAL:
            raise ValueError("invalid temporal semantics")
        if self.stage not in _STAGE or self.recoverability not in _RECOVER:
            raise ValueError("invalid commitment profile")
        if self.durability not in _DURABILITY or self.exposure not in _EXPOSURE:
            raise ValueError("invalid commitment profile")
        if self.amount is not None and (not isinstance(self.amount, int) or isinstance(self.amount, bool) or self.amount < 0):
            raise ValueError("amount must be nonnegative int")
        canonical_json(list(self.payload))

    @property
    def resource_key(self) -> str:
        return canonical_hash({"domain": self.domain, "resource": self.resource, "payload": list(self.payload)})

    def to_object(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "resource": self.resource,
            "mode": self.mode,
            "payload": list(self.payload),
            "temporal": self.temporal,
            "amount": self.amount,
            "stage": self.stage,
            "recoverability": self.recoverability,
            "durability": self.durability,
            "exposure": self.exposure,
        }

@dataclass(frozen=True, slots=True)
class DomainLawV0:
    domain: str
    complete: bool = False
    snapshot_reads_commute: bool = False
    stable_reads_commute: bool = False
    explicit_commuting_modes: tuple[tuple[str, str], ...] = ()

    def commute_modes(self, left: EffectAtomV0, right: EffectAtomV0) -> bool:
        if left.resource_key != right.resource_key:
            return bool(self.complete)
        pair = (left.mode, right.mode)
        if pair in self.explicit_commuting_modes or pair[::-1] in self.explicit_commuting_modes:
            return True
        if left.mode == right.mode == "read":
            if left.temporal == right.temporal == "snapshot":
                return self.snapshot_reads_commute
            if left.temporal == right.temporal == "stable":
                return self.stable_reads_commute
        return False

def effects_commute(
    left: Iterable[EffectAtomV0],
    right: Iterable[EffectAtomV0],
    laws: Mapping[str, DomainLawV0],
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    for a in left:
        for b in right:
            if a.domain != b.domain:
                continue
            law = laws.get(a.domain)
            if law is None:
                reasons.append(f"missing_domain_law:{a.domain}")
                continue
            if not law.commute_modes(a, b):
                reasons.append(f"noncommuting:{a.domain}:{a.resource_key}")
    return (not reasons, tuple(sorted(set(reasons))))

def combine_costs(effects: Iterable[EffectAtomV0]) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for atom in effects:
        if atom.amount is None:
            continue
        key = (atom.domain, atom.resource)
        out[key] = out.get(key, 0) + atom.amount
    return out

def commitment_vector(effects: Iterable[EffectAtomV0]) -> dict[str, tuple[tuple[str, str, str, str], ...]]:
    out: dict[str, list[tuple[str, str, str, str]]] = {}
    for atom in effects:
        out.setdefault(atom.domain, []).append(
            (atom.resource_key, atom.stage, atom.recoverability, atom.durability + ":" + atom.exposure)
        )
    return {k: tuple(sorted(v)) for k, v in sorted(out.items())}

def derived_roles(effects: Iterable[EffectAtomV0]) -> tuple[str, ...]:
    vals = tuple(effects)
    roles: set[str] = set()
    if any(e.domain == "knowledge" and e.mode in {"read", "consume"} for e in vals):
        roles.add("observation")
    if any(e.mode in {"write", "consume", "reserve", "release"} for e in vals):
        roles.add("action")
    if not vals:
        roles.add("pure")
    return tuple(sorted(roles))

__all__ = [
    "EffectAtomV0", "DomainLawV0", "effects_commute", "combine_costs",
    "commitment_vector", "derived_roles",
]
