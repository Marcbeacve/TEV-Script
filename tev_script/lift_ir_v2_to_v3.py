from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .contracts import MAX_EVENT_CHAIN
from .contracts_v1 import MAX_TYPE_NESTING
from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .ir_validation import validate_program_ir

_BASE_TYPE_TABLE = [
    {"type_id":"Bool","kind":"primitive"},
    {"type_id":"Int","kind":"primitive"},
    {"type_id":"Rat","kind":"primitive"},
    {"type_id":"Text","kind":"primitive"},
    {"type_id":"Unit","kind":"unit"},
    {"type_id":"Vec2","kind":"primitive"},
    {"type_id":"Vec3","kind":"primitive"},
]
_BASE_TYPE_TABLE.sort(key=lambda item: item["type_id"])


@dataclass(frozen=True, slots=True)
class LiftedIrV3Bundle:
    ir: dict[str, object]
    canonical_json: str
    source_ir_v2_semantic_hash: str


def lift_ir_v2_to_v3(ir_v2: Mapping[str, Any]) -> LiftedIrV3Bundle:
    source = deepcopy(dict(ir_v2))
    validate_program_ir(source)
    if source.get("schema") != "TEV_SCRIPT_PROGRAM_IR_V2" or source.get("language_version") != "0.2.0":
        raise TevScriptError(
            "TEVS_IR_V3_LIFT_SOURCE",
            "V2 lift requires TEV_SCRIPT_PROGRAM_IR_V2 / 0.2.0",
        )
    source_hash = str(source["semantic_hash"])

    entities = [_lift_entity(entity) for entity in source["entities"]]
    entities.sort(key=lambda item: str(item["entity_id"]))
    semantic: dict[str, object] = {
        "schema":"TEV_SCRIPT_PROGRAM_IR_V3",
        "language_version":"1.0.0",
        "lowering_profile":"TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1",
        "source_schema":"TEV_SCRIPT_PROGRAM_IR_V2",
        "source_semantic_hash":source_hash,
        "program_id":str(source["program_id"]),
        "types":deepcopy(_BASE_TYPE_TABLE),
        "entities":entities,
        "boundary":{
            "dynamic_code":False,
            "reflection":False,
            "unbounded_loops":False,
            "implicit_physical_effects":False,
            "runtime_source_compilation":False,
            "automatic_authority_escalation":False,
            "host_object_references":False,
            "maximum_event_chain":int(source["boundary"]["maximum_event_chain"]),
            "maximum_value_nesting":MAX_TYPE_NESTING,
        },
    }
    target = dict(semantic)
    target["semantic_hash"] = canonical_hash(semantic)
    debug = {
        "source_schema":"TEV_SCRIPT_PROGRAM_IR_V2",
        "source_semantic_hash":source_hash,
        "source_debug_hash":str(source["debug_hash"]),
        "source_debug":deepcopy(source["debug"]),
    }
    target["debug"] = debug
    target["debug_hash"] = canonical_hash(debug)
    validate_program_ir_v3(target, expected_source_semantic_hash=source_hash)
    return LiftedIrV3Bundle(target, canonical_json(target), source_hash)


def _lift_entity(raw: Mapping[str, Any]) -> dict[str, object]:
    states = [deepcopy(dict(item)) for item in raw["states"]]
    states.sort(key=lambda item: str(item["name"]))

    handlers: list[dict[str, object]] = []
    for raw_handler in raw["handlers"]:
        handler = deepcopy(dict(raw_handler))
        # Parameter order is event-ABI semantic. Local declaration order is not.
        handler["locals"] = sorted(
            [deepcopy(dict(item)) for item in handler["locals"]],
            key=lambda item: str(item["name"]),
        )
        handlers.append(handler)
    handlers.sort(key=lambda item: str(item["event_id"]))

    capabilities = [deepcopy(dict(item)) for item in raw["capabilities"]]
    capabilities.sort(key=lambda item: str(item["capability_id"]))
    emitted_events = [deepcopy(dict(item)) for item in raw["emitted_events"]]
    emitted_events.sort(key=lambda item: str(item["event_id"]))
    return {
        "entity_id":str(raw["entity_id"]),
        "states":states,
        "handlers":handlers,
        "capabilities":capabilities,
        "emitted_events":emitted_events,
    }
