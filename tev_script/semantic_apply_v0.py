from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Any, Callable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import FactV0, SemanticFieldV0, META_RELATION
from .semantic_effects_v0 import EffectAtomV0, commitment_vector

RULE_DECLS = (
    ("tev.rule", 2),
    ("tev.rule.op", 3),
    ("tev.rule.effect", 2),
)
OUTCOME_DECLS = (
    ("tev.outcome", 8),
    ("tev.outcome.parent", 1),
    ("tev.outcome.reason", 1),
    ("tev.outcome.after_decl", 2),
    ("tev.outcome.after_fact", 2),
    ("tev.outcome.expected_decl", 2),
    ("tev.outcome.expected_fact", 2),
    ("tev.outcome.effect", 2),
    ("tev.outcome.observation", 3),
    ("tev.outcome.commitment", 3),
)
_MODES = frozenset({"evaluate", "project", "prepare", "replay"})
_COMMIT_RESULTS = frozenset({"COMMITTED", "REJECTED", "FAILED", "PARTIAL", "UNKNOWN_COMMIT", "LAW_VIOLATION"})
DEFAULT_CONTEXT_HASH = canonical_hash({"schema": "TEV_SCRIPT_SEMANTIC_CONTEXT_V0", "center": "none"})
DEFAULT_LAW_HASH = canonical_hash({"schema": "TEV_SCRIPT_SEMANTIC_LAW_CONTEXT_V0", "laws": []})

@dataclass(frozen=True, slots=True)
class RuleOpV0:
    opcode: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.opcode not in {"put", "remove", "require", "observe", "effect"}:
            raise ValueError("unsupported semantic rule opcode")
        canonical_json(dict(self.payload))

    def to_object(self) -> dict[str, Any]:
        return {"opcode": self.opcode, "payload": dict(self.payload)}

def rule_field(rule_id: str, operations: tuple[RuleOpV0, ...], effects: tuple[EffectAtomV0, ...] = ()) -> SemanticFieldV0:
    definition_hash = canonical_hash({
        "rule_id": rule_id,
        "operations": [o.to_object() for o in operations],
        "effects": [e.to_object() for e in effects],
    })
    facts = [FactV0("tev.rule", (rule_id, definition_hash))]
    for i, op in enumerate(operations):
        facts.append(FactV0("tev.rule.op", (i, op.opcode, canonical_json(dict(op.payload)))))
    for i, effect in enumerate(effects):
        facts.append(FactV0("tev.rule.effect", (i, canonical_json(effect.to_object()))))
    return SemanticFieldV0.build(RULE_DECLS, facts)

def parse_rule(field: SemanticFieldV0) -> tuple[str, str, tuple[RuleOpV0, ...], tuple[EffectAtomV0, ...]]:
    roots = field.facts_for("tev.rule")
    if len(roots) != 1:
        raise ValueError("exactly one tev.rule required")
    rule_id, definition_hash = map(str, roots[0].arguments)
    ops = []
    for fact in sorted(field.facts_for("tev.rule.op"), key=lambda f: int(f.arguments[0])):
        _, opcode, payload = fact.arguments
        ops.append(RuleOpV0(str(opcode), json.loads(str(payload))))
    effects = []
    for fact in sorted(field.facts_for("tev.rule.effect"), key=lambda f: int(f.arguments[0])):
        obj = json.loads(str(fact.arguments[1]))
        effects.append(EffectAtomV0(
            domain=str(obj["domain"]), resource=str(obj["resource"]), mode=str(obj["mode"]),
            payload=tuple(obj.get("payload", [])), temporal=str(obj.get("temporal", "unknown")),
            amount=obj.get("amount"), stage=str(obj.get("stage", "untouched")),
            recoverability=str(obj.get("recoverability", "unknown")),
            durability=str(obj.get("durability", "unknown")), exposure=str(obj.get("exposure", "none")),
        ))
    observed = canonical_hash({
        "rule_id": rule_id,
        "operations": [o.to_object() for o in ops],
        "effects": [e.to_object() for e in effects],
    })
    if observed != definition_hash:
        raise ValueError("rule definition hash mismatch")
    return rule_id, definition_hash, tuple(ops), tuple(effects)

def _field_encoding(field: SemanticFieldV0, prefix: str) -> tuple[list[FactV0], list[FactV0]]:
    decls = [FactV0(f"tev.outcome.{prefix}_decl", (n, a)) for n, a in field.declarations]
    facts = [
        FactV0(f"tev.outcome.{prefix}_fact", (f.relation, canonical_json(list(f.arguments))))
        for f in field.facts if f.relation != META_RELATION
    ]
    return decls, facts

def _decode_field(outcome: SemanticFieldV0, prefix: str) -> SemanticFieldV0:
    decls = [(str(f.arguments[0]), int(f.arguments[1])) for f in outcome.facts_for(f"tev.outcome.{prefix}_decl")]
    facts = [
        FactV0(str(f.arguments[0]), tuple(json.loads(str(f.arguments[1]))))
        for f in outcome.facts_for(f"tev.outcome.{prefix}_fact")
    ]
    return SemanticFieldV0.build(decls, facts)

def outcome_after_field(outcome: SemanticFieldV0) -> SemanticFieldV0:
    return _decode_field(outcome, "after")

def outcome_expected_field(outcome: SemanticFieldV0) -> SemanticFieldV0:
    return _decode_field(outcome, "expected")

def _outcome(
    status: str,
    mode: str,
    before: SemanticFieldV0,
    after: SemanticFieldV0,
    rule_hash: str,
    reasons: tuple[str, ...],
    effects: tuple[EffectAtomV0, ...],
    observations: tuple[tuple[str, Any], ...],
    expected_after: SemanticFieldV0 | None = None,
    context_hash: str = DEFAULT_CONTEXT_HASH,
    law_hash: str = DEFAULT_LAW_HASH,
    handler_id: str = "reference.evaluate",
    parent_hash: str | None = None,
) -> SemanticFieldV0:
    expected = after if expected_after is None else expected_after
    decls, after_facts = _field_encoding(after, "after")
    expected_decls, expected_facts = _field_encoding(expected, "expected")
    facts: list[FactV0] = [
        FactV0("tev.outcome", (status, mode, before.field_hash, after.field_hash, rule_hash, context_hash, law_hash, handler_id)),
        *decls, *after_facts, *expected_decls, *expected_facts,
    ]
    if parent_hash is not None:
        facts.append(FactV0("tev.outcome.parent", (parent_hash,)))
    facts += [FactV0("tev.outcome.reason", (r,)) for r in reasons]
    facts += [FactV0("tev.outcome.effect", (i, canonical_json(e.to_object()))) for i, e in enumerate(effects)]
    facts += [FactV0("tev.outcome.observation", (i, cap, value)) for i, (cap, value) in enumerate(observations)]
    for domain, vals in commitment_vector(effects).items():
        facts.append(FactV0("tev.outcome.commitment", (domain, canonical_json(list(vals)), len(vals))))
    return SemanticFieldV0.build(OUTCOME_DECLS, facts)

def apply_rule(
    field: SemanticFieldV0,
    rule: SemanticFieldV0,
    *,
    mode: str = "evaluate",
    observation_provider: Callable[[str, tuple[Any, ...]], Any] | None = None,
    replay_transcript: Mapping[str, Any] | None = None,
    context_hash: str = DEFAULT_CONTEXT_HASH,
    law_hash: str = DEFAULT_LAW_HASH,
    handler_id: str | None = None,
) -> SemanticFieldV0:
    if mode not in _MODES:
        raise ValueError("invalid apply mode")
    handler = handler_id or f"reference.{mode}"
    for name, value in (("context_hash", context_hash), ("law_hash", law_hash)):
        if len(str(value)) != 64 or any(c not in "0123456789abcdef" for c in str(value)):
            raise ValueError(name)
    _, rule_hash, ops, declared_effects = parse_rule(rule)
    current = field
    observations: list[tuple[str, Any]] = []
    intents: list[EffectAtomV0] = list(declared_effects)
    reasons: list[str] = []
    for op in ops:
        p = dict(op.payload)
        if op.opcode == "require":
            rel = str(p["relation"])
            args = tuple(p.get("arguments", []))
            if not current.has(rel, args):
                reasons.append(f"require_failed:{rel}")
                return _outcome("REJECTED", mode, field, current, rule_hash, tuple(reasons), tuple(intents), tuple(observations), context_hash=context_hash, law_hash=law_hash, handler_id=handler)
        elif op.opcode == "put":
            current = current.with_fact(FactV0(str(p["relation"]), tuple(p.get("arguments", []))))
        elif op.opcode == "remove":
            current = current.without(str(p["relation"]), tuple(p.get("arguments", [])) if "arguments" in p else None)
        elif op.opcode == "observe":
            cap = str(p["capability"])
            args = tuple(p.get("arguments", []))
            if mode == "project":
                if observation_provider is None:
                    return _outcome("REJECTED", mode, field, current, rule_hash, ("model_operation_unavailable:" + cap,), tuple(intents), tuple(observations), context_hash=context_hash, law_hash=law_hash, handler_id=handler)
                value = observation_provider(cap, args)
            elif mode == "replay":
                if replay_transcript is None or cap not in replay_transcript:
                    return _outcome("REJECTED", mode, field, current, rule_hash, ("replay_observation_missing:" + cap,), tuple(intents), tuple(observations), context_hash=context_hash, law_hash=law_hash, handler_id=handler)
                value = replay_transcript[cap]
            else:
                if observation_provider is None:
                    return _outcome("REJECTED", mode, field, current, rule_hash, ("observation_provider_missing:" + cap,), tuple(intents), tuple(observations), context_hash=context_hash, law_hash=law_hash, handler_id=handler)
                value = observation_provider(cap, args)
            observations.append((cap, value))
            target = p.get("target_relation")
            if target:
                current = current.with_fact(FactV0(str(target), tuple(p.get("target_prefix", [])) + (value,)))
        elif op.opcode == "effect":
            # Effects are intents during evaluate/project/prepare/replay. Physical realization is commit_prepared().
            idx = int(p["effect_index"])
            if idx < 0 or idx >= len(declared_effects):
                raise ValueError("effect index out of range")
    return _outcome("PREPARED" if mode in {"prepare", "replay"} else "COMPLETED", mode, field, current, rule_hash, tuple(reasons), tuple(intents), tuple(observations), context_hash=context_hash, law_hash=law_hash, handler_id=handler)

def commit_prepared(
    prepared: SemanticFieldV0,
    *,
    current: SemanticFieldV0,
    effect_provider: Callable[[EffectAtomV0], str],
) -> SemanticFieldV0:
    roots = prepared.facts_for("tev.outcome")
    if len(roots) != 1:
        raise ValueError("invalid outcome field")
    status, mode, before_hash, _, rule_hash, context_hash, law_hash, _prepared_handler = roots[0].arguments
    if str(status) != "PREPARED" or str(mode) not in {"prepare", "replay"}:
        raise ValueError("commit requires prepared outcome")
    if current.field_hash != str(before_hash):
        return _outcome("REJECTED", "commit", current, current, str(rule_hash), ("stale_before_field",), (), (), context_hash=str(context_hash), law_hash=str(law_hash), handler_id="reference.commit", parent_hash=prepared.field_hash)
    after = outcome_after_field(prepared)
    effects = []
    for fact in sorted(prepared.facts_for("tev.outcome.effect"), key=lambda f: int(f.arguments[0])):
        obj = json.loads(str(fact.arguments[1]))
        effects.append(EffectAtomV0(
            domain=str(obj["domain"]), resource=str(obj["resource"]), mode=str(obj["mode"]),
            payload=tuple(obj.get("payload", [])), temporal=str(obj.get("temporal", "unknown")),
            amount=obj.get("amount"), stage=str(obj.get("stage", "untouched")),
            recoverability=str(obj.get("recoverability", "unknown")),
            durability=str(obj.get("durability", "unknown")), exposure=str(obj.get("exposure", "none")),
        ))
    reasons: list[str] = []
    final_status = "COMMITTED"
    for effect in effects:
        result = str(effect_provider(effect))
        if result not in _COMMIT_RESULTS:
            raise ValueError("invalid effect commit result")
        if result != "COMMITTED":
            final_status = result
            reasons.append(f"effect_commit:{effect.domain}:{effect.resource}:{result}")
            break
    committed_after = after if final_status == "COMMITTED" else current
    return _outcome(final_status, "commit", current, committed_after, str(rule_hash), tuple(reasons), tuple(effects), (), expected_after=after, context_hash=str(context_hash), law_hash=str(law_hash), handler_id="reference.commit", parent_hash=prepared.field_hash)

__all__ = [
    "DEFAULT_CONTEXT_HASH", "DEFAULT_LAW_HASH", "RuleOpV0", "rule_field", "parse_rule", "apply_rule", "commit_prepared", "outcome_after_field", "outcome_expected_field",
]
