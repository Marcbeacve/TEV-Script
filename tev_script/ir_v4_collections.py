from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .diagnostics import TevScriptError
from .ir_v4_values import (
    ArrayValueV4,
    ListValueV4,
    MapValueV4,
    SetValueV4,
    TypeTableV4,
    encode_v4_value,
)


@dataclass(frozen=True, slots=True)
class MapLookupV4:
    found: bool
    value: Any = None


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _same_value(type_id: str, left: Any, right: Any, table: TypeTableV4) -> bool:
    return encode_v4_value(type_id, left, table) == encode_v4_value(type_id, right, table)


def list_push(value: ListValueV4, item: Any, table: TypeTableV4) -> ListValueV4:
    descriptor = table.require(value.type_id, context="list_push")
    if descriptor.kind != "list":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"list_push requires list type, got {value.type_id!r}")
    assert descriptor.element_type is not None and descriptor.capacity is not None
    encode_v4_value(descriptor.element_type, item, table, context="list_push.item")
    if len(value.items) >= descriptor.capacity:
        _fail("TEVS_IR_V4_COLLECTION_OVERFLOW", f"{value.type_id} capacity {descriptor.capacity} exceeded")
    return ListValueV4(value.type_id, (*value.items, item))


def list_get(value: ListValueV4, index: int, table: TypeTableV4) -> Any:
    descriptor = table.require(value.type_id, context="list_get")
    if descriptor.kind != "list":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"list_get requires list type, got {value.type_id!r}")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(value.items):
        _fail("TEVS_IR_V4_COLLECTION_INDEX", f"index {index!r} outside [0,{len(value.items)})")
    return value.items[index]


def list_set(value: ListValueV4, index: int, item: Any, table: TypeTableV4) -> ListValueV4:
    descriptor = table.require(value.type_id, context="list_set")
    if descriptor.kind != "list":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"list_set requires list type, got {value.type_id!r}")
    assert descriptor.element_type is not None
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(value.items):
        _fail("TEVS_IR_V4_COLLECTION_INDEX", f"index {index!r} outside [0,{len(value.items)})")
    encode_v4_value(descriptor.element_type, item, table, context="list_set.item")
    items = list(value.items)
    items[index] = item
    return ListValueV4(value.type_id, tuple(items))


def list_items(value: ListValueV4, table: TypeTableV4) -> tuple[Any, ...]:
    descriptor = table.require(value.type_id, context="list_items")
    if descriptor.kind != "list":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"list_items requires list type, got {value.type_id!r}")
    encode_v4_value(value.type_id, value, table, context="list_items.value")
    return value.items



def array_get(value: ArrayValueV4, index: int, table: TypeTableV4) -> Any:
    descriptor = table.require(value.type_id, context="array_get")
    if descriptor.kind != "array":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"array_get requires array type, got {value.type_id!r}")
    assert descriptor.length is not None
    encode_v4_value(value.type_id, value, table, context="array_get.value")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < descriptor.length:
        _fail("TEVS_IR_V4_COLLECTION_INDEX", f"index {index!r} outside [0,{descriptor.length})")
    return value.items[index]


def array_set(value: ArrayValueV4, index: int, item: Any, table: TypeTableV4) -> ArrayValueV4:
    descriptor = table.require(value.type_id, context="array_set")
    if descriptor.kind != "array":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"array_set requires array type, got {value.type_id!r}")
    assert descriptor.element_type is not None and descriptor.length is not None
    encode_v4_value(value.type_id, value, table, context="array_set.value")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < descriptor.length:
        _fail("TEVS_IR_V4_COLLECTION_INDEX", f"index {index!r} outside [0,{descriptor.length})")
    encode_v4_value(descriptor.element_type, item, table, context="array_set.item")
    items = list(value.items); items[index] = item
    result = ArrayValueV4(value.type_id, tuple(items))
    encode_v4_value(value.type_id, result, table, context="array_set.result")
    return result


def array_items(value: ArrayValueV4, table: TypeTableV4) -> tuple[Any, ...]:
    descriptor = table.require(value.type_id, context="array_items")
    if descriptor.kind != "array":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"array_items requires array type, got {value.type_id!r}")
    encode_v4_value(value.type_id, value, table, context="array_items.value")
    return value.items

def set_add(value: SetValueV4, item: Any, table: TypeTableV4) -> SetValueV4:
    descriptor = table.require(value.type_id, context="set_add")
    if descriptor.kind != "set":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"set_add requires set type, got {value.type_id!r}")
    assert descriptor.element_type is not None and descriptor.capacity is not None
    encoded_item = encode_v4_value(descriptor.element_type, item, table, context="set_add.item")
    for existing in value.items:
        if encode_v4_value(descriptor.element_type, existing, table) == encoded_item:
            return value
    if len(value.items) >= descriptor.capacity:
        _fail("TEVS_IR_V4_COLLECTION_OVERFLOW", f"{value.type_id} capacity {descriptor.capacity} exceeded")
    candidate = SetValueV4(value.type_id, (*value.items, item))
    # Canonical encoder is authority for uniqueness and deterministic ordering.
    encode_v4_value(value.type_id, candidate, table, context="set_add.result")
    return candidate


def set_contains(value: SetValueV4, item: Any, table: TypeTableV4) -> bool:
    descriptor = table.require(value.type_id, context="set_contains")
    if descriptor.kind != "set":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"set_contains requires set type, got {value.type_id!r}")
    assert descriptor.element_type is not None
    encoded_item = encode_v4_value(descriptor.element_type, item, table, context="set_contains.item")
    return any(encode_v4_value(descriptor.element_type, existing, table) == encoded_item for existing in value.items)


def set_items(value: SetValueV4, table: TypeTableV4) -> tuple[Any, ...]:
    descriptor = table.require(value.type_id, context="set_items")
    if descriptor.kind != "set":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"set_items requires set type, got {value.type_id!r}")
    encoded = encode_v4_value(value.type_id, value, table, context="set_items.value")
    canonical_items = encoded["$set"]["items"]
    # Resolve canonical wire order back onto semantic values without relying on
    # host comparison/order semantics.
    assert descriptor.element_type is not None
    by_wire = {
        _wire_key(encode_v4_value(descriptor.element_type, item, table)): item
        for item in value.items
    }
    return tuple(by_wire[_wire_key(item)] for item in canonical_items)


def map_put(value: MapValueV4, key: Any, item: Any, table: TypeTableV4) -> MapValueV4:
    descriptor = table.require(value.type_id, context="map_put")
    if descriptor.kind != "map":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"map_put requires map type, got {value.type_id!r}")
    assert descriptor.key_type is not None and descriptor.value_type is not None and descriptor.capacity is not None
    encoded_key = encode_v4_value(descriptor.key_type, key, table, context="map_put.key")
    encode_v4_value(descriptor.value_type, item, table, context="map_put.value")
    entries = list(value.entries)
    for index, (old_key, _) in enumerate(entries):
        if encode_v4_value(descriptor.key_type, old_key, table) == encoded_key:
            entries[index] = (key, item)
            return MapValueV4(value.type_id, tuple(entries))
    if len(entries) >= descriptor.capacity:
        _fail("TEVS_IR_V4_COLLECTION_OVERFLOW", f"{value.type_id} capacity {descriptor.capacity} exceeded")
    entries.append((key, item))
    candidate = MapValueV4(value.type_id, tuple(entries))
    encode_v4_value(value.type_id, candidate, table, context="map_put.result")
    return candidate


def map_lookup(value: MapValueV4, key: Any, table: TypeTableV4) -> MapLookupV4:
    descriptor = table.require(value.type_id, context="map_lookup")
    if descriptor.kind != "map":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"map_lookup requires map type, got {value.type_id!r}")
    assert descriptor.key_type is not None
    encoded_key = encode_v4_value(descriptor.key_type, key, table, context="map_lookup.key")
    for old_key, item in value.entries:
        if encode_v4_value(descriptor.key_type, old_key, table) == encoded_key:
            return MapLookupV4(True, item)
    return MapLookupV4(False)


def map_entries(value: MapValueV4, table: TypeTableV4) -> tuple[tuple[Any, Any], ...]:
    descriptor = table.require(value.type_id, context="map_entries")
    if descriptor.kind != "map":
        _fail("TEVS_IR_V4_COLLECTION_KIND", f"map_entries requires map type, got {value.type_id!r}")
    assert descriptor.key_type is not None
    encode_v4_value(value.type_id, value, table, context="map_entries.value")
    return tuple(sorted(value.entries, key=lambda pair: _wire_key(encode_v4_value(descriptor.key_type, pair[0], table))))


def collection_length(value: ArrayValueV4 | ListValueV4 | SetValueV4 | MapValueV4, table: TypeTableV4) -> int:
    descriptor = table.require(value.type_id, context="collection_length")
    if descriptor.kind == "map" and isinstance(value, MapValueV4):
        return len(value.entries)
    if descriptor.kind == "array" and isinstance(value, ArrayValueV4):
        encode_v4_value(value.type_id, value, table, context="collection_length.array")
        assert descriptor.length is not None
        return descriptor.length
    if descriptor.kind in {"list", "set"} and isinstance(value, (ListValueV4, SetValueV4)):
        return len(value.items)
    _fail("TEVS_IR_V4_COLLECTION_KIND", f"value/type mismatch for collection_length: {value.type_id!r}")


def _wire_key(value: Any) -> bytes:
    import json
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
