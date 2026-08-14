from __future__ import annotations

from dataclasses import dataclass
import json
from fractions import Fraction
from typing import Any

from .diagnostics import TevScriptError
from .values import encode_typed_value

MAX_COLLECTION_CAPACITY_V2 = 4096


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _capacity(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_COLLECTION_CAPACITY_V2:
        _fail("TEVS_V2_COLLECTION_CAPACITY", f"collection capacity must be 1..{MAX_COLLECTION_CAPACITY_V2}")
    return value


def _type_name(value: str, role: str) -> str:
    if not isinstance(value, str) or not value or any(ch.isspace() for ch in value):
        _fail("TEVS_V2_COLLECTION_TYPE", f"{role} type must be a non-empty canonical type id without whitespace")
    return value


def _canonical_bytes(type_id: str, value: Any) -> bytes:
    try:
        encoded = encode_typed_value(type_id, value)
        return json.dumps(encoded, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TevScriptError, TypeError, ValueError, ZeroDivisionError) as exc:
        _fail("TEVS_V2_COLLECTION_VALUE_NOT_CANONICAL", f"{type_id} value is not canonically encodable: {exc}")


@dataclass(frozen=True, slots=True)
class MapLookupV2:
    found: bool
    value: Any = None

    @classmethod
    def missing(cls) -> "MapLookupV2":
        return cls(False)

    @classmethod
    def present(cls, value: Any) -> "MapLookupV2":
        return cls(True, value)


@dataclass(frozen=True, slots=True)
class CollectionTypeV2:
    kind: str
    capacity: int
    element_type: str | None = None
    key_type: str | None = None
    value_type: str | None = None
    order_policy: str = "sequence"

    def __post_init__(self) -> None:
        _capacity(self.capacity)
        if self.kind in {"list", "set"}:
            if self.element_type is None or self.key_type is not None or self.value_type is not None:
                _fail("TEVS_V2_COLLECTION_DESCRIPTOR", f"{self.kind} requires exactly element_type")
            _type_name(self.element_type, "element")
            expected = "sequence" if self.kind == "list" else "canonical_value_bytes"
        elif self.kind == "map":
            if self.element_type is not None or self.key_type is None or self.value_type is None:
                _fail("TEVS_V2_COLLECTION_DESCRIPTOR", "map requires exactly key_type and value_type")
            _type_name(self.key_type, "key")
            _type_name(self.value_type, "value")
            expected = "canonical_key_bytes"
        else:
            _fail("TEVS_V2_COLLECTION_KIND", f"unsupported collection kind {self.kind!r}")
        if self.order_policy != expected:
            _fail("TEVS_V2_COLLECTION_ORDER_POLICY", f"{self.kind} requires order policy {expected}")

    @property
    def type_id(self) -> str:
        if self.kind == "list":
            return f"List<{self.element_type},{self.capacity}>"
        if self.kind == "set":
            return f"Set<{self.element_type},{self.capacity}>"
        return f"Map<{self.key_type},{self.value_type},{self.capacity}>"


@dataclass(frozen=True, slots=True)
class ListValueV2:
    type: CollectionTypeV2
    items: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if self.type.kind != "list":
            _fail("TEVS_V2_COLLECTION_KIND_MISMATCH", "ListValueV2 requires list descriptor")
        if len(self.items) > self.type.capacity:
            _fail("TEVS_V2_COLLECTION_OVERFLOW", f"{self.type.type_id} capacity exceeded")
        for value in self.items:
            _canonical_bytes(self.type.element_type, value)

    def append(self, value: Any) -> "ListValueV2":
        if len(self.items) >= self.type.capacity:
            _fail("TEVS_V2_COLLECTION_OVERFLOW", f"{self.type.type_id} capacity exceeded")
        _canonical_bytes(self.type.element_type, value)
        return ListValueV2(self.type, self.items + (value,))

    def set(self, index: int, value: Any) -> "ListValueV2":
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.items):
            _fail("TEVS_V2_COLLECTION_INDEX", "list index out of bounds")
        _canonical_bytes(self.type.element_type, value)
        items = list(self.items)
        items[index] = value
        return ListValueV2(self.type, tuple(items))

    def get(self, index: int) -> Any:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(self.items):
            _fail("TEVS_V2_COLLECTION_INDEX", "list index out of bounds")
        return self.items[index]

    def canonical(self) -> dict[str, Any]:
        return {"$list": {"type": self.type.type_id, "items": list(self.items)}}


@dataclass(frozen=True, slots=True)
class SetValueV2:
    type: CollectionTypeV2
    items: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if self.type.kind != "set":
            _fail("TEVS_V2_COLLECTION_KIND_MISMATCH", "SetValueV2 requires set descriptor")
        unique: dict[bytes, Any] = {}
        for value in self.items:
            key = _canonical_bytes(self.type.element_type, value)
            if key in unique:
                _fail("TEVS_V2_COLLECTION_DUPLICATE", "set contains duplicate canonical value")
            unique[key] = value
        if len(unique) > self.type.capacity:
            _fail("TEVS_V2_COLLECTION_OVERFLOW", f"{self.type.type_id} capacity exceeded")
        object.__setattr__(self, "items", tuple(unique[key] for key in sorted(unique)))

    def add(self, value: Any) -> "SetValueV2":
        key = _canonical_bytes(self.type.element_type, value)
        if any(_canonical_bytes(self.type.element_type, item) == key for item in self.items):
            return self
        if len(self.items) >= self.type.capacity:
            _fail("TEVS_V2_COLLECTION_OVERFLOW", f"{self.type.type_id} capacity exceeded")
        return SetValueV2(self.type, self.items + (value,))

    def contains(self, value: Any) -> bool:
        key = _canonical_bytes(self.type.element_type, value)
        return any(_canonical_bytes(self.type.element_type, item) == key for item in self.items)

    def canonical(self) -> dict[str, Any]:
        return {"$set": {"type": self.type.type_id, "items": list(self.items)}}


@dataclass(frozen=True, slots=True)
class MapValueV2:
    type: CollectionTypeV2
    entries: tuple[tuple[Any, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.type.kind != "map":
            _fail("TEVS_V2_COLLECTION_KIND_MISMATCH", "MapValueV2 requires map descriptor")
        assert self.type.key_type is not None and self.type.value_type is not None
        unique: dict[bytes, tuple[Any, Any]] = {}
        for key, value in self.entries:
            encoded = _canonical_bytes(self.type.key_type, key)
            _canonical_bytes(self.type.value_type, value)
            if encoded in unique:
                _fail("TEVS_V2_COLLECTION_DUPLICATE_KEY", "map contains duplicate canonical key")
            unique[encoded] = (key, value)
        if len(unique) > self.type.capacity:
            _fail("TEVS_V2_COLLECTION_OVERFLOW", f"{self.type.type_id} capacity exceeded")
        object.__setattr__(self, "entries", tuple(unique[key] for key in sorted(unique)))

    def put(self, key: Any, value: Any) -> "MapValueV2":
        assert self.type.key_type is not None and self.type.value_type is not None
        encoded = _canonical_bytes(self.type.key_type, key)
        _canonical_bytes(self.type.value_type, value)
        current = list(self.entries)
        for index, (old_key, _) in enumerate(current):
            if _canonical_bytes(self.type.key_type, old_key) == encoded:
                current[index] = (key, value)
                return MapValueV2(self.type, tuple(current))
        if len(current) >= self.type.capacity:
            _fail("TEVS_V2_COLLECTION_OVERFLOW", f"{self.type.type_id} capacity exceeded")
        current.append((key, value))
        return MapValueV2(self.type, tuple(current))

    def lookup(self, key: Any) -> MapLookupV2:
        assert self.type.key_type is not None
        encoded = _canonical_bytes(self.type.key_type, key)
        for old_key, value in self.entries:
            if _canonical_bytes(self.type.key_type, old_key) == encoded:
                return MapLookupV2.present(value)
        return MapLookupV2.missing()

    def contains_key(self, key: Any) -> bool:
        return self.lookup(key).found

    def canonical(self) -> dict[str, Any]:
        return {"$map": {"type": self.type.type_id, "entries": [{"key": key, "value": value} for key, value in self.entries]}}
