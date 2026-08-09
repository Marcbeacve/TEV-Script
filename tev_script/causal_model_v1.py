from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json

CAPABILITY_LAW_CATALOG_SCHEMA_V1 = "TEV_SCRIPT_CAPABILITY_LAW_CATALOG_V1"
REACTION_CONTRACT_SCHEMA_V1 = "TEV_SCRIPT_REACTION_CONTRACT_V1"
PREPARED_REACTION_SCHEMA_V1 = "TEV_SCRIPT_PREPARED_REACTION_V1"
REFINEMENT_RECEIPT_SCHEMA_V1 = "TEV_SCRIPT_REFINEMENT_RECEIPT_V1"

_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ACCESS_MODES = frozenset({"read", "write", "consume", "reserve"})
_RESOURCE_KINDS = frozenset({"external", "authority", "logical"})
_CAPABILITY_KINDS = frozenset({"observation", "effect"})
_OBSERVATION_SEMANTICS = frozenset({"none", "snapshot", "stable", "sequence_sensitive", "unknown"})
_EFFECT_PROTOCOLS = frozenset({"none", "immediate", "prepare_commit_abort"})
_ATOMICITY = frozenset({
    "interleaved",
    "state_atomic",
    "state_atomic_external_partial_possible",
    "transactional",
    "durable_transactional",
})
_REQUIRED_ATOMICITY = frozenset({"any", "state_atomic", "transactional", "durable_transactional"})


class CausalModelError(ValueError):
    pass


def _stable(value: str, field: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise CausalModelError(f"{field} must be a stable id")
    return text


def _sha(value: str, field: str) -> str:
    text = str(value).lower()
    if _SHA.fullmatch(text) is None:
        raise CausalModelError(f"{field} must be a lowercase sha256")
    return text


def _canonical_ids(values: Iterable[str], field: str) -> tuple[str, ...]:
    return tuple(sorted({_stable(value, field) for value in values}))


def _canonical_json_values(values: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    normalized = [dict(value) for value in values]
    normalized.sort(key=canonical_json)
    return tuple(normalized)


@dataclass(frozen=True, slots=True, order=True)
class ResourceAccessV1:
    resource_id: str
    mode: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", _stable(self.resource_id, "resource_id"))
        if self.mode not in _ACCESS_MODES:
            raise CausalModelError(f"unsupported resource access mode {self.mode!r}")

    def to_object(self) -> dict[str, object]:
        return {"resource_id": self.resource_id, "mode": self.mode}


@dataclass(frozen=True, slots=True)
class ResourceLawV1:
    resource_id: str
    kind: str = "external"
    aliases: tuple[str, ...] = ()
    capacity: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", _stable(self.resource_id, "resource_id"))
        if self.kind not in _RESOURCE_KINDS:
            raise CausalModelError(f"unsupported resource kind {self.kind!r}")
        object.__setattr__(self, "aliases", _canonical_ids(self.aliases, "resource alias"))
        if self.capacity is not None and (
            not isinstance(self.capacity, int)
            or isinstance(self.capacity, bool)
            or self.capacity <= 0
        ):
            raise CausalModelError("resource capacity must be a positive integer or null")

    def to_object(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "aliases": list(self.aliases),
            "capacity": self.capacity,
        }


@dataclass(frozen=True, slots=True)
class CapabilityLawV1:
    capability_id: str
    kind: str
    accesses: tuple[ResourceAccessV1, ...] = ()
    observation_semantics: str = "none"
    effect_protocol: str = "none"
    commutes_with: tuple[str, ...] = ()
    commit_total_after_prepare: bool = False
    durable_recovery: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", _stable(self.capability_id, "capability_id"))
        if self.kind not in _CAPABILITY_KINDS:
            raise CausalModelError(f"unsupported capability kind {self.kind!r}")
        object.__setattr__(
            self,
            "accesses",
            tuple(sorted(set(self.accesses), key=lambda item: (item.resource_id, item.mode))),
        )
        object.__setattr__(self, "commutes_with", _canonical_ids(self.commutes_with, "commutes_with"))
        if self.observation_semantics not in _OBSERVATION_SEMANTICS:
            raise CausalModelError(f"unsupported observation semantics {self.observation_semantics!r}")
        if self.effect_protocol not in _EFFECT_PROTOCOLS:
            raise CausalModelError(f"unsupported effect protocol {self.effect_protocol!r}")
        if self.kind == "observation":
            if self.observation_semantics == "none":
                raise CausalModelError("observation capability requires an observation semantics law")
            if self.effect_protocol != "none" or self.commit_total_after_prepare or self.durable_recovery:
                raise CausalModelError("observation capability cannot claim effect transaction laws")
        else:
            if self.observation_semantics != "none":
                raise CausalModelError("effect capability cannot claim observation semantics")
            if self.effect_protocol == "none":
                raise CausalModelError("effect capability requires an effect protocol")
            if (self.commit_total_after_prepare or self.durable_recovery) and self.effect_protocol != "prepare_commit_abort":
                raise CausalModelError("transaction guarantees require prepare_commit_abort")
            if self.durable_recovery and not self.commit_total_after_prepare:
                raise CausalModelError("durable recovery requires commit_total_after_prepare")

    def to_object(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "kind": self.kind,
            "accesses": [item.to_object() for item in self.accesses],
            "observation_semantics": self.observation_semantics,
            "effect_protocol": self.effect_protocol,
            "commutes_with": list(self.commutes_with),
            "commit_total_after_prepare": self.commit_total_after_prepare,
            "durable_recovery": self.durable_recovery,
        }


@dataclass(frozen=True, slots=True)
class CapabilityLawCatalogV1:
    deployment_id: str
    complete: bool
    resources: tuple[ResourceLawV1, ...] = ()
    capabilities: tuple[CapabilityLawV1, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "deployment_id", _stable(self.deployment_id, "deployment_id"))
        if not isinstance(self.complete, bool):
            raise CausalModelError("complete must be bool")
        resources = tuple(sorted(self.resources, key=lambda item: item.resource_id))
        capabilities = tuple(sorted(self.capabilities, key=lambda item: item.capability_id))
        if len({item.resource_id for item in resources}) != len(resources):
            raise CausalModelError("duplicate resource law")
        if len({item.capability_id for item in capabilities}) != len(capabilities):
            raise CausalModelError("duplicate capability law")
        alias_owner: dict[str, str] = {}
        for resource in resources:
            for name in (resource.resource_id, *resource.aliases):
                previous = alias_owner.get(name)
                if previous is not None and previous != resource.resource_id:
                    raise CausalModelError(f"resource alias {name!r} belongs to multiple resources")
                alias_owner[name] = resource.resource_id
        if self.complete:
            known = set(alias_owner)
            for capability in capabilities:
                for access in capability.accesses:
                    if access.resource_id not in known:
                        raise CausalModelError(
                            f"complete catalog references undeclared resource {access.resource_id!r}"
                        )
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "capabilities", capabilities)

    def law(self, capability_id: str) -> CapabilityLawV1 | None:
        for law in self.capabilities:
            if law.capability_id == capability_id:
                return law
        return None

    def resource_law(self, resource_id: str) -> ResourceLawV1 | None:
        canonical = self.canonical_resource(resource_id)
        if canonical is None:
            return None
        for resource in self.resources:
            if resource.resource_id == canonical:
                return resource
        return None

    def canonical_resource(self, resource_id: str) -> str | None:
        for resource in self.resources:
            if resource_id == resource.resource_id or resource_id in resource.aliases:
                return resource.resource_id
        return None

    def alias_relation(self, left: str, right: str) -> str:
        if left == right:
            return "same"
        l = self.canonical_resource(left)
        r = self.canonical_resource(right)
        if l is not None and r is not None:
            return "same" if l == r else "disjoint"
        return "disjoint" if self.complete else "unknown"

    def _body(self) -> dict[str, object]:
        return {
            "schema": CAPABILITY_LAW_CATALOG_SCHEMA_V1,
            "deployment_id": self.deployment_id,
            "complete": self.complete,
            "resources": [item.to_object() for item in self.resources],
            "capabilities": [item.to_object() for item in self.capabilities],
        }

    @property
    def catalog_hash(self) -> str:
        return canonical_hash(self._body())

    def to_object(self) -> dict[str, object]:
        return {**self._body(), "catalog_hash": self.catalog_hash}

    @property
    def canonical_json(self) -> str:
        return canonical_json(self.to_object())


@dataclass(frozen=True, slots=True, order=True)
class CapabilityOccurrenceV1:
    event_id: str
    instruction_index: int
    capability_id: str
    kind: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _stable(self.event_id, "event_id"))
        object.__setattr__(self, "capability_id", _stable(self.capability_id, "capability_id"))
        if (
            not isinstance(self.instruction_index, int)
            or isinstance(self.instruction_index, bool)
            or self.instruction_index < 0
        ):
            raise CausalModelError("instruction_index must be a non-negative integer")
        if self.kind not in _CAPABILITY_KINDS:
            raise CausalModelError("capability occurrence kind invalid")

    def to_object(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "instruction_index": self.instruction_index,
            "capability_id": self.capability_id,
            "kind": self.kind,
        }


@dataclass(frozen=True, slots=True)
class ReactionFootprintV1:
    program_semantic_hash: str
    source_semantic_hash: str
    entity_id: str
    trigger_event: str
    reachable_events: tuple[str, ...]
    state_reads: tuple[str, ...]
    state_writes: tuple[str, ...]
    observations: tuple[str, ...]
    effects: tuple[str, ...]
    emitted_events: tuple[str, ...]
    capability_occurrences: tuple[CapabilityOccurrenceV1, ...]
    reachable_handler_count: int
    maximum_event_chain: int
    instruction_ceiling: int
    cyclic_event_graph: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "program_semantic_hash", _sha(self.program_semantic_hash, "program_semantic_hash"))
        object.__setattr__(self, "source_semantic_hash", _sha(self.source_semantic_hash, "source_semantic_hash"))
        object.__setattr__(self, "entity_id", _stable(self.entity_id, "entity_id"))
        object.__setattr__(self, "trigger_event", _stable(self.trigger_event, "trigger_event"))
        for name in (
            "reachable_events", "state_reads", "state_writes", "observations",
            "effects", "emitted_events",
        ):
            object.__setattr__(self, name, _canonical_ids(getattr(self, name), name))
        object.__setattr__(self, "capability_occurrences", tuple(sorted(set(self.capability_occurrences))))
        if self.reachable_handler_count != len(self.reachable_events):
            raise CausalModelError("reachable_handler_count must match reachable_events")
        if self.maximum_event_chain <= 0 or self.instruction_ceiling <= 0:
            raise CausalModelError("reaction budgets must be positive")

    def _body(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_REACTION_FOOTPRINT_V1",
            "program_semantic_hash": self.program_semantic_hash,
            "source_semantic_hash": self.source_semantic_hash,
            "entity_id": self.entity_id,
            "trigger_event": self.trigger_event,
            "reachable_events": list(self.reachable_events),
            "state_reads": list(self.state_reads),
            "state_writes": list(self.state_writes),
            "observations": list(self.observations),
            "effects": list(self.effects),
            "emitted_events": list(self.emitted_events),
            "capability_occurrences": [item.to_object() for item in self.capability_occurrences],
            "reachable_handler_count": self.reachable_handler_count,
            "maximum_event_chain": self.maximum_event_chain,
            "instruction_ceiling": self.instruction_ceiling,
            "cyclic_event_graph": self.cyclic_event_graph,
        }

    @property
    def footprint_hash(self) -> str:
        return canonical_hash(self._body())

    def to_object(self) -> dict[str, object]:
        return {**self._body(), "footprint_hash": self.footprint_hash}


@dataclass(frozen=True, slots=True)
class ProtocolEdgeV1:
    event_id: str
    before: Mapping[str, Any]
    after: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _stable(self.event_id, "event_id"))
        for field, value in (("before", self.before), ("after", self.after)):
            witness = dict(value)
            if set(witness) != {"type", "value"} or not isinstance(witness.get("type"), str) or not witness["type"]:
                raise CausalModelError(f"protocol {field} must be one canonical typed state witness")
            canonical_json(witness)

    def to_object(self) -> dict[str, object]:
        return {"event_id": self.event_id, "before": dict(self.before), "after": dict(self.after)}


@dataclass(frozen=True, slots=True)
class ProtocolViewV1:
    state_name: str
    edges: tuple[ProtocolEdgeV1, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_name", _stable(self.state_name, "state_name"))
        edges = tuple(sorted(self.edges, key=lambda item: canonical_json(item.to_object())))
        if len({canonical_json(item.to_object()) for item in edges}) != len(edges):
            raise CausalModelError("duplicate protocol edge")
        object.__setattr__(self, "edges", edges)

    def to_object(self) -> dict[str, object]:
        return {"state_name": self.state_name, "edges": [item.to_object() for item in self.edges]}


@dataclass(frozen=True, slots=True)
class ProofObligationRefV1:
    obligation_id: str
    domain: str
    statement_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "obligation_id", _stable(self.obligation_id, "obligation_id"))
        object.__setattr__(self, "domain", _stable(self.domain, "domain"))
        object.__setattr__(self, "statement_hash", _sha(self.statement_hash, "statement_hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "obligation_id": self.obligation_id,
            "domain": self.domain,
            "statement_hash": self.statement_hash,
        }


@dataclass(frozen=True, slots=True)
class ReactionContractV1:
    contract_id: str
    entity_id: str
    trigger_event: str
    allowed_state_reads: tuple[str, ...] = ()
    allowed_state_writes: tuple[str, ...] = ()
    allowed_observations: tuple[str, ...] = ()
    allowed_effects: tuple[str, ...] = ()
    allowed_emitted_events: tuple[str, ...] = ()
    allowed_resources: tuple[str, ...] = ()
    maximum_reachable_events: int = 1
    maximum_instruction_ceiling: int = 8192
    required_atomicity: str = "any"
    protocol: ProtocolViewV1 | None = None
    proof_obligations: tuple[ProofObligationRefV1, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "contract_id", _stable(self.contract_id, "contract_id"))
        object.__setattr__(self, "entity_id", _stable(self.entity_id, "entity_id"))
        object.__setattr__(self, "trigger_event", _stable(self.trigger_event, "trigger_event"))
        for name in (
            "allowed_state_reads", "allowed_state_writes", "allowed_observations",
            "allowed_effects", "allowed_emitted_events", "allowed_resources",
        ):
            object.__setattr__(self, name, _canonical_ids(getattr(self, name), name))
        if (
            not isinstance(self.maximum_reachable_events, int)
            or isinstance(self.maximum_reachable_events, bool)
            or self.maximum_reachable_events <= 0
        ):
            raise CausalModelError("maximum_reachable_events must be positive")
        if (
            not isinstance(self.maximum_instruction_ceiling, int)
            or isinstance(self.maximum_instruction_ceiling, bool)
            or self.maximum_instruction_ceiling <= 0
        ):
            raise CausalModelError("maximum_instruction_ceiling must be positive")
        if self.required_atomicity not in _REQUIRED_ATOMICITY:
            raise CausalModelError("required_atomicity invalid")
        obligations = tuple(sorted(self.proof_obligations, key=lambda item: item.obligation_id))
        if len({item.obligation_id for item in obligations}) != len(obligations):
            raise CausalModelError("duplicate proof obligation id")
        object.__setattr__(self, "proof_obligations", obligations)

    def _body(self) -> dict[str, object]:
        return {
            "schema": REACTION_CONTRACT_SCHEMA_V1,
            "contract_id": self.contract_id,
            "entity_id": self.entity_id,
            "trigger_event": self.trigger_event,
            "allowed": {
                "state_reads": list(self.allowed_state_reads),
                "state_writes": list(self.allowed_state_writes),
                "observations": list(self.allowed_observations),
                "effects": list(self.allowed_effects),
                "emitted_events": list(self.allowed_emitted_events),
                "resources": list(self.allowed_resources),
            },
            "budgets": {
                "maximum_reachable_events": self.maximum_reachable_events,
                "maximum_instruction_ceiling": self.maximum_instruction_ceiling,
            },
            "required_atomicity": self.required_atomicity,
            "protocol": None if self.protocol is None else self.protocol.to_object(),
            "proof_obligations": [item.to_object() for item in self.proof_obligations],
        }

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self._body())

    def to_object(self) -> dict[str, object]:
        return {**self._body(), "contract_hash": self.contract_hash}

    @property
    def canonical_json(self) -> str:
        return canonical_json(self.to_object())


@dataclass(frozen=True, slots=True)
class RefinementReceiptV1:
    contract_hash: str
    candidate_program_semantic_hash: str
    footprint_hash: str
    law_catalog_hash: str
    status: str
    failures: tuple[Mapping[str, Any], ...] = ()
    pending_obligations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("contract_hash", "candidate_program_semantic_hash", "footprint_hash", "law_catalog_hash"):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if self.status not in {"PASS", "REJECT", "PROOF_REQUIRED"}:
            raise CausalModelError("refinement status invalid")
        object.__setattr__(self, "failures", _canonical_json_values(self.failures))
        object.__setattr__(self, "pending_obligations", _canonical_ids(self.pending_obligations, "pending obligation"))

    def _body(self) -> dict[str, object]:
        return {
            "schema": REFINEMENT_RECEIPT_SCHEMA_V1,
            "contract_hash": self.contract_hash,
            "candidate_program_semantic_hash": self.candidate_program_semantic_hash,
            "footprint_hash": self.footprint_hash,
            "law_catalog_hash": self.law_catalog_hash,
            "status": self.status,
            "failures": [dict(item) for item in self.failures],
            "pending_obligations": list(self.pending_obligations),
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self._body())

    def to_object(self) -> dict[str, object]:
        return {**self._body(), "receipt_hash": self.receipt_hash}


@dataclass(frozen=True, slots=True)
class PreparedReactionV1:
    program_semantic_hash: str
    source_semantic_hash: str
    contract_hash: str
    law_catalog_hash: str
    refinement_receipt_hash: str
    footprint_hash: str
    entity_id: str
    trigger_event: str
    arguments: tuple[Mapping[str, Any], ...]
    before_checkpoint: Mapping[str, Any]
    before_checkpoint_hash: str
    after_checkpoint: Mapping[str, Any]
    after_checkpoint_hash: str
    observations: tuple[Mapping[str, Any], ...]
    effect_intents: tuple[Mapping[str, Any], ...]
    emitted_events: tuple[Mapping[str, Any], ...]
    atomicity: str
    preparation_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "program_semantic_hash", "source_semantic_hash", "contract_hash",
            "law_catalog_hash", "refinement_receipt_hash", "footprint_hash",
            "before_checkpoint_hash", "after_checkpoint_hash",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        object.__setattr__(self, "entity_id", _stable(self.entity_id, "entity_id"))
        object.__setattr__(self, "trigger_event", _stable(self.trigger_event, "trigger_event"))
        if self.atomicity not in _ATOMICITY:
            raise CausalModelError("prepared reaction atomicity invalid")
        before_object = dict(self.before_checkpoint)
        after_object = dict(self.after_checkpoint)
        canonical_json(before_object)
        canonical_json(after_object)
        if canonical_hash(before_object) != self.before_checkpoint_hash:
            raise CausalModelError("before checkpoint hash mismatch")
        if canonical_hash(after_object) != self.after_checkpoint_hash:
            raise CausalModelError("after checkpoint hash mismatch")
        for name in ("arguments", "observations", "effect_intents", "emitted_events"):
            values = tuple(dict(item) for item in getattr(self, name))
            for item in values:
                canonical_json(item)
            object.__setattr__(self, name, values)
        object.__setattr__(
            self,
            "preparation_evidence",
            tuple(sorted(set(str(item) for item in self.preparation_evidence))),
        )

    def _body(self) -> dict[str, object]:
        return {
            "schema": PREPARED_REACTION_SCHEMA_V1,
            "program_semantic_hash": self.program_semantic_hash,
            "source_semantic_hash": self.source_semantic_hash,
            "contract_hash": self.contract_hash,
            "law_catalog_hash": self.law_catalog_hash,
            "refinement_receipt_hash": self.refinement_receipt_hash,
            "footprint_hash": self.footprint_hash,
            "entity_id": self.entity_id,
            "trigger_event": self.trigger_event,
            "arguments": [dict(item) for item in self.arguments],
            "before_checkpoint": dict(self.before_checkpoint),
            "before_checkpoint_hash": self.before_checkpoint_hash,
            "after_checkpoint": dict(self.after_checkpoint),
            "after_checkpoint_hash": self.after_checkpoint_hash,
            "observations": [dict(item) for item in self.observations],
            "effect_intents": [dict(item) for item in self.effect_intents],
            "emitted_events": [dict(item) for item in self.emitted_events],
            "atomicity": self.atomicity,
            "preparation_evidence": list(self.preparation_evidence),
        }

    @property
    def prepared_reaction_hash(self) -> str:
        return canonical_hash(self._body())

    def to_object(self) -> dict[str, object]:
        return {**self._body(), "prepared_reaction_hash": self.prepared_reaction_hash}

    @property
    def canonical_json(self) -> str:
        return canonical_json(self.to_object())


@dataclass(frozen=True, slots=True)
class IndependenceResultV1:
    independent: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparabilityResultV1:
    preparable: bool
    atomicity: str
    reasons: tuple[str, ...]
    hazards: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CommitResultV1:
    status: str
    prepared_reaction_hash: str
    state_committed: bool
    external_partial: bool
    committed_effects: int
    emitted_events: tuple[Mapping[str, Any], ...]
    detail: str = ""


__all__ = [
    "CAPABILITY_LAW_CATALOG_SCHEMA_V1",
    "REACTION_CONTRACT_SCHEMA_V1",
    "PREPARED_REACTION_SCHEMA_V1",
    "REFINEMENT_RECEIPT_SCHEMA_V1",
    "CausalModelError",
    "ResourceAccessV1",
    "ResourceLawV1",
    "CapabilityLawV1",
    "CapabilityLawCatalogV1",
    "CapabilityOccurrenceV1",
    "ReactionFootprintV1",
    "ProtocolEdgeV1",
    "ProtocolViewV1",
    "ProofObligationRefV1",
    "ReactionContractV1",
    "RefinementReceiptV1",
    "PreparedReactionV1",
    "IndependenceResultV1",
    "PreparabilityResultV1",
    "CommitResultV1",
]
