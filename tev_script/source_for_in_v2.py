from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .diagnostics import TevScriptError
from .ir_v4_collections import array_items, list_items, map_entries, set_items
from .ir_v4_values import ArrayValueV4, ListValueV4, MapValueV4, SetValueV4, TypeTableV4, encode_v4_value

_HEADER_ONE = re.compile(r"^\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$")
_HEADER_PAIR = re.compile(r"^\s*for\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s+in\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$")


@dataclass(frozen=True, slots=True)
class ForInHeaderV2:
    bindings: tuple[str, ...]
    source_name: str


@dataclass(frozen=True, slots=True)
class ForInPlanV2:
    schema: str
    collection_type: str
    binding_types: tuple[str, ...]
    maximum_iterations: int
    actual_iterations: int
    order_policy: str
    rows: tuple[tuple[Any, ...], ...]
    witness_hash: str


def parse_for_in_header_v2(text: str) -> ForInHeaderV2:
    if not isinstance(text, str):
        _fail("TEVS_V2_FOR_IN_SYNTAX", "for-in header must be text")
    pair = _HEADER_PAIR.fullmatch(text)
    if pair is not None:
        first, second, source = pair.groups()
        if first == second:
            _fail("TEVS_V2_FOR_IN_BINDING", "map for-in bindings must be distinct")
        return ForInHeaderV2((first, second), source)
    one = _HEADER_ONE.fullmatch(text)
    if one is not None:
        binding, source = one.groups()
        return ForInHeaderV2((binding,), source)
    _fail("TEVS_V2_FOR_IN_SYNTAX", "expected 'for x in xs' or 'for (k, v) in map'")


def plan_for_in_v2(
    header: ForInHeaderV2,
    value: ArrayValueV4 | ListValueV4 | SetValueV4 | MapValueV4,
    table: TypeTableV4,
) -> ForInPlanV2:
    descriptor = table.require(value.type_id, context="V2 for-in source")
    bound = descriptor.length if descriptor.kind == "array" else descriptor.capacity
    if bound is None or descriptor.order_policy is None:
        _fail("TEVS_V2_FOR_IN_TYPE", f"{value.type_id!r} is not an iterable collection type")

    if descriptor.kind == "list":
        assert descriptor.element_type is not None
        if len(header.bindings) != 1:
            _fail("TEVS_V2_FOR_IN_BINDING", "List for-in requires exactly one binding")
        raw_rows = tuple((item,) for item in list_items(value, table))
        binding_types = (descriptor.element_type,)
    elif descriptor.kind == "array":
        assert descriptor.element_type is not None and isinstance(value, ArrayValueV4)
        if len(header.bindings) != 1:
            _fail("TEVS_V2_FOR_IN_BINDING", "Array for-in requires exactly one binding")
        raw_rows = tuple((item,) for item in array_items(value, table))
        binding_types = (descriptor.element_type,)
    elif descriptor.kind == "set":
        assert descriptor.element_type is not None
        if len(header.bindings) != 1:
            _fail("TEVS_V2_FOR_IN_BINDING", "Set for-in requires exactly one binding")
        raw_rows = tuple((item,) for item in set_items(value, table))
        binding_types = (descriptor.element_type,)
    elif descriptor.kind == "map":
        assert descriptor.key_type is not None and descriptor.value_type is not None
        if len(header.bindings) != 2:
            _fail("TEVS_V2_FOR_IN_BINDING", "Map for-in requires exactly two bindings")
        raw_rows = tuple((key, item) for key, item in map_entries(value, table))
        binding_types = (descriptor.key_type, descriptor.value_type)
    else:
        _fail("TEVS_V2_FOR_IN_TYPE", f"{value.type_id!r} is not a V2 collection")

    if len(raw_rows) > bound:
        _fail("TEVS_V2_FOR_IN_BOUND", "actual iteration count exceeds static collection bound")
    if descriptor.kind == "array" and len(raw_rows) != bound:
        _fail("TEVS_V2_FOR_IN_BOUND", "array iteration count must equal its exact length")
    encoded_rows = [
        [encode_v4_value(type_id, item, table, context="V2 for-in witness") for type_id, item in zip(binding_types, row, strict=True)]
        for row in raw_rows
    ]
    witness = {
        "schema": "TEV_SCRIPT_V2_FOR_IN_PLAN_V1",
        "collection_type": value.type_id,
        "binding_types": list(binding_types),
        "maximum_iterations": bound,
        "actual_iterations": len(raw_rows),
        "order_policy": descriptor.order_policy,
        "rows": encoded_rows,
    }
    witness_hash = hashlib.sha256(
        json.dumps(witness, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ForInPlanV2(
        witness["schema"],
        value.type_id,
        binding_types,
        bound,
        len(raw_rows),
        descriptor.order_policy,
        raw_rows,
        witness_hash,
    )


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
