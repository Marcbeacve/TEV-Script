from __future__ import annotations
from typing import Any, Mapping

from .canonical import canonical_hash
from .semantic_kernel_v0 import FactV0, SemanticFieldV0
from .semantic_apply_v0 import RuleOpV0, rule_field
from .semantic_effects_v0 import EffectAtomV0
from .ir_v3_validation import validate_program_ir_v3

PROGRAM_DECLS = (
    ("tev.program", 5),
    ("tev.entity", 1),
    ("tev.state_decl", 4),
    ("tev.capability", 5),
    ("tev.handler", 3),
    ("tev.instruction", 4),
)

def project_ir_v3_program(ir: Mapping[str, Any]) -> SemanticFieldV0:
    obj = dict(ir)
    validate_program_ir_v3(obj)
    facts = [FactV0("tev.program", (
        str(obj["program_id"]), str(obj["schema"]), str(obj["language_version"]),
        str(obj["semantic_hash"]), str(obj["source_semantic_hash"]),
    ))]
    for entity in obj["entities"]:
        eid = str(entity["entity_id"])
        facts.append(FactV0("tev.entity", (eid,)))
        for state in entity["states"]:
            facts.append(FactV0("tev.state_decl", (eid, str(state["name"]), str(state["type"]), state["initial"])))
        for cap in entity["capabilities"]:
            facts.append(FactV0("tev.capability", (
                eid, str(cap["capability_id"]), str(cap["kind"]), str(cap["return_type"]), list(cap["parameters"])
            )))
        for handler in entity["handlers"]:
            event = str(handler["event_id"])
            facts.append(FactV0("tev.handler", (eid, event, int(handler["instruction_budget"]))))
            for i, ins in enumerate(handler["instructions"]):
                facts.append(FactV0("tev.instruction", (eid, event, i, dict(ins))))
    return SemanticFieldV0.build(PROGRAM_DECLS, facts)

def derive_handler_rule(ir: Mapping[str, Any], entity_id: str, event_id: str) -> SemanticFieldV0:
    obj = dict(ir)
    validate_program_ir_v3(obj)
    entity = next(e for e in obj["entities"] if str(e["entity_id"]) == entity_id)
    handler = next(h for h in entity["handlers"] if str(h["event_id"]) == event_id)
    effects = []
    ops = []
    for ins in handler["instructions"]:
        op = str(ins["op"])
        if op == "LOAD_STATE":
            effects.append(EffectAtomV0("state", f"{entity_id}:{ins['name']}", "read", temporal="snapshot"))
        elif op == "STORE_STATE":
            effects.append(EffectAtomV0("state", f"{entity_id}:{ins['name']}", "write"))
        elif op == "CALL_CAPABILITY":
            cap = str(ins["capability_id"])
            kind = str(ins["kind"])
            if kind == "observation":
                effects.append(EffectAtomV0("knowledge", cap, "read", temporal="unknown", exposure="acquired"))
                effects.append(EffectAtomV0("external", cap, "read", temporal="unknown"))
            else:
                effects.append(EffectAtomV0("external", cap, "write"))
                effects.append(EffectAtomV0("authority", cap, "consume"))
        elif op == "EMIT_EVENT":
            effects.append(EffectAtomV0("event", f"{entity_id}:{ins['event_id']}", "write"))
    return rule_field(
        f"{entity_id}.{event_id}",
        tuple(ops),
        tuple(effects),
    )

def model_projection_metadata(model_hash: str, assumptions: tuple[str, ...], result_hash: str) -> SemanticFieldV0:
    return SemanticFieldV0.build(
        (("tev.projected", 3), ("tev.assumption", 1)),
        (FactV0("tev.projected", (model_hash, canonical_hash(list(assumptions)), result_hash)),)
        + tuple(FactV0("tev.assumption", (a,)) for a in assumptions),
    )

def necessary_cause_focal(actual_effect: bool, counterfactual_effect_without_intervention: bool) -> bool:
    return actual_effect and not counterfactual_effect_without_intervention

__all__ = [
    "project_ir_v3_program", "derive_handler_rule", "model_projection_metadata",
    "necessary_cause_focal",
]
