from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

_LABELS = {"Public": 0, "Internal": 1, "Confidential": 2, "Secret": 3}

@dataclass(frozen=True, slots=True)
class AuthorityGrantV0:
    subject: str
    operation: str
    resource: str
    scope: str
    max_label: str = "Public"
    delegatable: bool = False
    consumable: bool = False

    def __post_init__(self) -> None:
        if self.max_label not in _LABELS:
            raise ValueError("security label")

def label_allows_flow(source: str, target: str) -> bool:
    if source not in _LABELS or target not in _LABELS:
        raise ValueError("security label")
    return _LABELS[source] <= _LABELS[target]

def can_observe(grants: Iterable[AuthorityGrantV0], subject: str, resource: str, label: str) -> bool:
    return any(
        g.subject == subject and g.operation == "observe" and g.resource == resource
        and _LABELS[g.max_label] >= _LABELS[label]
        for g in grants
    )

def can_disclose(
    grants: Iterable[AuthorityGrantV0],
    subject: str,
    resource: str,
    source_label: str,
    target_label: str,
) -> bool:
    direct = any(
        g.subject == subject and g.operation == "disclose" and g.resource == resource
        and _LABELS[g.max_label] >= _LABELS[source_label]
        for g in grants
    )
    if not direct:
        return False
    if label_allows_flow(source_label, target_label):
        return True
    return any(
        g.subject == subject and g.operation == "declassify" and g.resource == resource
        and _LABELS[g.max_label] >= _LABELS[source_label]
        for g in grants
    )

def _within(parent: str, child: str) -> bool:
    p = PurePosixPath(parent)
    c = PurePosixPath(child)
    try:
        c.relative_to(p)
        return True
    except ValueError:
        return False

def attenuate(grant: AuthorityGrantV0, *, subject: str, scope: str, max_label: str | None = None) -> AuthorityGrantV0:
    if not grant.delegatable:
        raise ValueError("grant not delegatable")
    if not _within(grant.scope, scope):
        raise ValueError("scope amplification")
    label = grant.max_label if max_label is None else max_label
    if _LABELS[label] > _LABELS[grant.max_label]:
        raise ValueError("label amplification")
    return AuthorityGrantV0(
        subject=subject, operation=grant.operation, resource=grant.resource,
        scope=scope, max_label=label, delegatable=False, consumable=grant.consumable,
    )

__all__ = ["AuthorityGrantV0", "label_allows_flow", "can_observe", "can_disclose", "attenuate"]
