from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import re
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .values import decode_typed_value, encode_typed_value

_PRIMITIVES = frozenset({"Bool", "Int", "Rat", "Text", "Vec2", "Vec3"})
_BASE_TYPES = frozenset({*_PRIMITIVES, "Unit"})
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NOMINAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_MISSING = object()


@dataclass(frozen=True, slots=True)
class TypeDescriptorV3:
    type_id: str
    kind: str
    fields: tuple[tuple[str, str], ...] = ()
    variants: tuple[str, ...] = ()
    argument: str | None = None
    ok_type: str | None = None
    err_type: str | None = None

    def field_type(self, name: str) -> str | None:
        for field_name, type_id in self.fields:
            if field_name == name:
                return type_id
        return None


@dataclass(frozen=True, slots=True)
class RecordValueV3:
    type_id: str
    fields: tuple[tuple[str, Any], ...]

    def field(self, name: str) -> Any:
        for field_name, value in self.fields:
            if field_name == name:
                return value
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class VariantValueV3:
    type_id: str
    variant: str
    payload: Any = _MISSING

    @property
    def has_payload(self) -> bool:
        return self.payload is not _MISSING


@dataclass(frozen=True, slots=True)
class TypeTableV3:
    descriptors: tuple[TypeDescriptorV3, ...]
    maximum_value_nesting: int
    _by_id: Mapping[str, TypeDescriptorV3] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_id", {item.type_id: item for item in self.descriptors})

    def get(self, type_id: str) -> TypeDescriptorV3 | None:
        return self._by_id.get(type_id)

    def require(self, type_id: str, *, context: str = "type") -> TypeDescriptorV3:
        result = self.get(type_id)
        if result is None:
            raise TevScriptError(
                "TEVS_IR_V3_TYPE_UNKNOWN",
                f"{context} references unknown V3 type {type_id!r}",
            )
        return result

    def is_storable(self, type_id: str) -> bool:
        descriptor = self.get(type_id)
        return descriptor is not None and descriptor.kind != "unit"

    def variant_payload_type(self, type_id: str, variant: str) -> str | None:
        descriptor = self.require(type_id)
        if descriptor.kind == "enum":
            if variant not in descriptor.variants:
                raise TevScriptError(
                    "TEVS_IR_V3_VARIANT_UNKNOWN",
                    f"enum {type_id!r} has no variant {variant!r}",
                )
            return None
        if descriptor.kind == "option":
            if variant == "None":
                return None
            if variant == "Some":
                assert descriptor.argument is not None
                return descriptor.argument
        if descriptor.kind == "result":
            if variant == "Ok":
                assert descriptor.ok_type is not None
                return descriptor.ok_type
            if variant == "Err":
                assert descriptor.err_type is not None
                return descriptor.err_type
        raise TevScriptError(
            "TEVS_IR_V3_VARIANT_UNKNOWN",
            f"type {type_id!r} does not define variant {variant!r}",
        )


def build_type_table_v3(ir: Mapping[str, Any]) -> TypeTableV3:
    raw_boundary = _object(ir.get("boundary"), "$.boundary")
    maximum_value_nesting = _integer(
        raw_boundary.get("maximum_value_nesting"),
        "$.boundary.maximum_value_nesting",
        1,
        128,
    )
    raw_types = _array(ir.get("types"), "$.types")
    if not 7 <= len(raw_types) <= 16_384:
        _fail("$.types", "type table must contain between 7 and 16384 descriptors")

    descriptors: list[TypeDescriptorV3] = []
    seen: set[str] = set()
    observed_order: list[str] = []
    for index, raw in enumerate(raw_types):
        path = f"$.types[{index}]"
        item = _object(raw, path)
        type_id = _string(item.get("type_id"), path + ".type_id")
        if type_id in seen:
            _fail(path + ".type_id", f"duplicate type id {type_id!r}")
        seen.add(type_id)
        observed_order.append(type_id)
        kind = _string(item.get("kind"), path + ".kind")

        if kind == "primitive":
            if set(item) != {"type_id", "kind"} or type_id not in _PRIMITIVES:
                _fail(path, "invalid primitive descriptor")
            descriptor = TypeDescriptorV3(type_id, kind)
        elif kind == "unit":
            if set(item) != {"type_id", "kind"} or type_id != "Unit":
                _fail(path, "invalid Unit descriptor")
            descriptor = TypeDescriptorV3(type_id, kind)
        elif kind == "record":
            if set(item) != {"type_id", "kind", "fields"}:
                _fail(path, "record descriptor field set mismatch")
            if _NOMINAL.fullmatch(type_id) is None:
                _fail(path + ".type_id", "record type id must be nominal and qualified")
            raw_fields = _array(item["fields"], path + ".fields")
            if not 1 <= len(raw_fields) <= 256:
                _fail(path + ".fields", "record requires 1..256 fields")
            fields: list[tuple[str, str]] = []
            field_names: set[str] = set()
            for field_index, raw_field in enumerate(raw_fields):
                field_path = f"{path}.fields[{field_index}]"
                field = _object(raw_field, field_path)
                if set(field) != {"name", "type"}:
                    _fail(field_path, "record field must contain name and type")
                name = _local_name(field["name"], field_path + ".name")
                field_type = _string(field["type"], field_path + ".type")
                if name in field_names:
                    _fail(field_path + ".name", f"duplicate record field {name!r}")
                field_names.add(name)
                fields.append((name, field_type))
            if [name for name, _ in fields] != sorted(field_names):
                _fail(path + ".fields", "record fields must be sorted lexically by name")
            descriptor = TypeDescriptorV3(type_id, kind, fields=tuple(fields))
        elif kind == "enum":
            if set(item) != {"type_id", "kind", "variants"}:
                _fail(path, "enum descriptor field set mismatch")
            if _NOMINAL.fullmatch(type_id) is None:
                _fail(path + ".type_id", "enum type id must be nominal and qualified")
            variants = tuple(
                _local_name(value, f"{path}.variants[{position}]")
                for position, value in enumerate(_array(item["variants"], path + ".variants"))
            )
            if not 1 <= len(variants) <= 256:
                _fail(path + ".variants", "enum requires 1..256 variants")
            if len(set(variants)) != len(variants):
                _fail(path + ".variants", "enum variants must be unique")
            if list(variants) != sorted(variants):
                _fail(path + ".variants", "enum variants must be sorted lexically")
            descriptor = TypeDescriptorV3(type_id, kind, variants=variants)
        elif kind == "option":
            if set(item) != {"type_id", "kind", "argument"}:
                _fail(path, "Option descriptor field set mismatch")
            argument = _string(item["argument"], path + ".argument")
            if type_id != f"Option<{argument}>":
                _fail(path + ".type_id", "Option type id does not match argument")
            descriptor = TypeDescriptorV3(type_id, kind, argument=argument)
        elif kind == "result":
            if set(item) != {"type_id", "kind", "ok_type", "err_type"}:
                _fail(path, "Result descriptor field set mismatch")
            ok_type = _string(item["ok_type"], path + ".ok_type")
            err_type = _string(item["err_type"], path + ".err_type")
            if type_id != f"Result<{ok_type},{err_type}>":
                _fail(path + ".type_id", "Result type id does not match arguments")
            descriptor = TypeDescriptorV3(type_id, kind, ok_type=ok_type, err_type=err_type)
        else:
            _fail(path + ".kind", f"unsupported V3 type kind {kind!r}")
        descriptors.append(descriptor)

    if observed_order != sorted(observed_order):
        _fail("$.types", "type table must be sorted lexically by type_id")
    missing_base = sorted(_BASE_TYPES - seen)
    if missing_base:
        _fail("$.types", f"missing portable base descriptors {missing_base}")

    table = TypeTableV3(tuple(descriptors), maximum_value_nesting)
    _validate_descriptor_references(table)
    _validate_type_nesting(table)
    _validate_record_acyclic(table)
    return table


def decode_v3_value(
    type_id: str,
    raw: Any,
    table: TypeTableV3,
    *,
    context: str = "value",
    depth: int = 1,
) -> Any:
    if depth > table.maximum_value_nesting:
        raise TevScriptError(
            "TEVS_IR_V3_VALUE_NESTING",
            f"{context}: value nesting exceeds {table.maximum_value_nesting}",
        )
    descriptor = table.require(type_id, context=context)
    if descriptor.kind == "unit":
        raise TevScriptError("TEVS_IR_V3_UNIT_VALUE", f"{context}: Unit is not a runtime value")
    if descriptor.kind == "primitive":
        try:
            return decode_typed_value(type_id, raw)
        except (TevScriptError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise TevScriptError(
                "TEVS_IR_V3_VALUE_INVALID",
                f"{context}: invalid {type_id} value: {exc}",
            ) from exc

    if descriptor.kind == "record":
        outer = _object(raw, context)
        if set(outer) != {"$record"}:
            _value_fail(context, type_id, "expected $record")
        payload = _object(outer["$record"], context + ".$record")
        if set(payload) != {"type", "fields"} or payload["type"] != type_id:
            _value_fail(context, type_id, "record encoded type mismatch")
        raw_fields = _array(payload["fields"], context + ".$record.fields")
        expected_names = [name for name, _ in descriptor.fields]
        observed_names: list[str] = []
        decoded: list[tuple[str, Any]] = []
        if len(raw_fields) != len(descriptor.fields):
            _value_fail(context, type_id, "record field count mismatch")
        for index, ((expected_name, field_type), raw_field) in enumerate(zip(descriptor.fields, raw_fields, strict=True)):
            field_path = f"{context}.$record.fields[{index}]"
            field = _object(raw_field, field_path)
            if set(field) != {"name", "value"}:
                _value_fail(field_path, field_type, "record field shape mismatch")
            name = field["name"]
            observed_names.append(str(name))
            if name != expected_name:
                _value_fail(field_path, field_type, f"expected canonical field {expected_name!r}, got {name!r}")
            decoded.append(
                (
                    expected_name,
                    decode_v3_value(
                        field_type,
                        field["value"],
                        table,
                        context=field_path + ".value",
                        depth=depth + 1,
                    ),
                )
            )
        if observed_names != expected_names:
            _value_fail(context, type_id, "record field order mismatch")
        return RecordValueV3(type_id, tuple(decoded))

    if descriptor.kind == "enum":
        outer = _object(raw, context)
        if set(outer) != {"$enum"}:
            _value_fail(context, type_id, "expected $enum")
        payload = _object(outer["$enum"], context + ".$enum")
        if set(payload) != {"type", "variant"} or payload["type"] != type_id:
            _value_fail(context, type_id, "enum encoded type mismatch")
        variant = _local_name(payload["variant"], context + ".$enum.variant")
        if variant not in descriptor.variants:
            _value_fail(context, type_id, f"unknown enum variant {variant!r}")
        return VariantValueV3(type_id, variant)

    if descriptor.kind == "option":
        outer = _object(raw, context)
        if set(outer) != {"$option"}:
            _value_fail(context, type_id, "expected $option")
        payload = _object(outer["$option"], context + ".$option")
        if payload.get("type") != type_id:
            _value_fail(context, type_id, "Option encoded type mismatch")
        variant = payload.get("variant")
        if variant == "None":
            if set(payload) != {"type", "variant"}:
                _value_fail(context, type_id, "None must not carry a payload")
            return VariantValueV3(type_id, "None")
        if variant == "Some":
            if set(payload) != {"type", "variant", "value"}:
                _value_fail(context, type_id, "Some requires exactly one payload")
            assert descriptor.argument is not None
            return VariantValueV3(
                type_id,
                "Some",
                decode_v3_value(
                    descriptor.argument,
                    payload["value"],
                    table,
                    context=context + ".$option.value",
                    depth=depth + 1,
                ),
            )
        _value_fail(context, type_id, f"unknown Option variant {variant!r}")

    if descriptor.kind == "result":
        outer = _object(raw, context)
        if set(outer) != {"$result"}:
            _value_fail(context, type_id, "expected $result")
        payload = _object(outer["$result"], context + ".$result")
        if payload.get("type") != type_id:
            _value_fail(context, type_id, "Result encoded type mismatch")
        variant = payload.get("variant")
        payload_type = descriptor.ok_type if variant == "Ok" else descriptor.err_type if variant == "Err" else None
        if payload_type is None:
            _value_fail(context, type_id, f"unknown Result variant {variant!r}")
        if set(payload) != {"type", "variant", "value"}:
            _value_fail(context, type_id, f"{variant} requires exactly one payload")
        return VariantValueV3(
            type_id,
            str(variant),
            decode_v3_value(
                payload_type,
                payload["value"],
                table,
                context=context + ".$result.value",
                depth=depth + 1,
            ),
        )
    raise AssertionError(descriptor.kind)


def encode_v3_value(
    type_id: str,
    value: Any,
    table: TypeTableV3,
    *,
    context: str = "value",
    depth: int = 1,
) -> Any:
    if depth > table.maximum_value_nesting:
        raise TevScriptError(
            "TEVS_IR_V3_VALUE_NESTING",
            f"{context}: value nesting exceeds {table.maximum_value_nesting}",
        )
    descriptor = table.require(type_id, context=context)
    if descriptor.kind == "unit":
        raise TevScriptError("TEVS_IR_V3_UNIT_VALUE", f"{context}: Unit is not encodable")
    if descriptor.kind == "primitive":
        return encode_typed_value(type_id, value)
    if descriptor.kind == "record":
        if not isinstance(value, RecordValueV3) or value.type_id != type_id:
            _value_fail(context, type_id, "expected exact RecordValueV3")
        actual = dict(value.fields)
        if set(actual) != {name for name, _ in descriptor.fields}:
            _value_fail(context, type_id, "record field set mismatch")
        return {
            "$record": {
                "type": type_id,
                "fields": [
                    {
                        "name": name,
                        "value": encode_v3_value(
                            field_type,
                            actual[name],
                            table,
                            context=f"{context}.{name}",
                            depth=depth + 1,
                        ),
                    }
                    for name, field_type in descriptor.fields
                ],
            }
        }
    if not isinstance(value, VariantValueV3) or value.type_id != type_id:
        _value_fail(context, type_id, "expected exact VariantValueV3")
    payload_type = table.variant_payload_type(type_id, value.variant)
    if descriptor.kind == "enum":
        if value.has_payload:
            _value_fail(context, type_id, "enum variant cannot carry payload")
        return {"$enum": {"type": type_id, "variant": value.variant}}
    key = "$option" if descriptor.kind == "option" else "$result"
    result: dict[str, Any] = {"type": type_id, "variant": value.variant}
    if payload_type is None:
        if value.has_payload:
            _value_fail(context, type_id, f"{value.variant} cannot carry payload")
    else:
        if not value.has_payload:
            _value_fail(context, type_id, f"{value.variant} requires payload")
        result["value"] = encode_v3_value(
            payload_type,
            value.payload,
            table,
            context=context + ".value",
            depth=depth + 1,
        )
    return {key: result}


def v3_values_equal(type_id: str, left: Any, right: Any, table: TypeTableV3) -> bool:
    descriptor = table.require(type_id)
    if descriptor.kind == "primitive":
        return left == right
    if descriptor.kind == "record":
        if not isinstance(left, RecordValueV3) or not isinstance(right, RecordValueV3):
            return False
        return left.type_id == right.type_id == type_id and left.fields == right.fields
    if descriptor.kind in {"enum", "option", "result"}:
        if not isinstance(left, VariantValueV3) or not isinstance(right, VariantValueV3):
            return False
        return (
            left.type_id == right.type_id == type_id
            and left.variant == right.variant
            and left.has_payload == right.has_payload
            and (not left.has_payload or left.payload == right.payload)
        )
    return False


def _validate_descriptor_references(table: TypeTableV3) -> None:
    for descriptor in table.descriptors:
        referenced: list[str] = []
        if descriptor.kind == "record":
            referenced.extend(type_id for _name, type_id in descriptor.fields)
        elif descriptor.kind == "option":
            assert descriptor.argument is not None
            referenced.append(descriptor.argument)
        elif descriptor.kind == "result":
            assert descriptor.ok_type is not None and descriptor.err_type is not None
            referenced.extend((descriptor.ok_type, descriptor.err_type))
        for type_id in referenced:
            child = table.require(type_id, context=f"descriptor {descriptor.type_id}")
            if child.kind == "unit":
                _fail("$.types", f"Unit is not storable inside {descriptor.type_id!r}")


def _validate_type_nesting(table: TypeTableV3) -> None:
    memo: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(type_id: str) -> int:
        if type_id in memo:
            return memo[type_id]
        if type_id in visiting:
            _fail("$.types", f"constructed type dependency cycle at {type_id!r}")
        visiting.add(type_id)
        descriptor = table.require(type_id)
        if descriptor.kind == "option":
            assert descriptor.argument is not None
            result = 1 + depth(descriptor.argument)
        elif descriptor.kind == "result":
            assert descriptor.ok_type is not None and descriptor.err_type is not None
            result = 1 + max(depth(descriptor.ok_type), depth(descriptor.err_type))
        else:
            result = 1
        visiting.remove(type_id)
        memo[type_id] = result
        return result

    for type_id in sorted(table._by_id):
        observed = depth(type_id)
        if observed > 128:
            _fail("$.types", f"type nesting exceeds 128 at {type_id!r}: got {observed}")


def _validate_record_acyclic(table: TypeTableV3) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    for descriptor in table.descriptors:
        if descriptor.kind != "record":
            continue
        dependencies: set[str] = set()
        stack = [type_id for _name, type_id in descriptor.fields]
        seen_types: set[str] = set()
        while stack:
            type_id = stack.pop()
            if type_id in seen_types:
                continue
            seen_types.add(type_id)
            child = table.require(type_id)
            if child.kind == "record":
                dependencies.add(type_id)
                continue
            if child.kind == "option" and child.argument is not None:
                stack.append(child.argument)
            elif child.kind == "result":
                assert child.ok_type is not None and child.err_type is not None
                stack.extend((child.ok_type, child.err_type))
        graph[descriptor.type_id] = tuple(sorted(dependencies))

    state: dict[str, int] = {}
    for start in sorted(graph):
        if state.get(start, 0) == 2:
            continue
        frames: list[list[Any]] = [[start, 0]]
        path: list[str] = []
        while frames:
            node = str(frames[-1][0])
            index = int(frames[-1][1])
            if state.get(node, 0) == 0:
                state[node] = 1
                path.append(node)
            deps = graph[node]
            if index < len(deps):
                child = deps[index]
                frames[-1][1] = index + 1
                mark = state.get(child, 0)
                if mark == 0:
                    frames.append([child, 0])
                    continue
                if mark == 1:
                    start_index = path.index(child) if child in path else 0
                    cycle = [*path[start_index:], child]
                    _fail("$.types", "recursive record dependency: " + " -> ".join(cycle))
                continue
            frames.pop()
            popped = path.pop()
            assert popped == node
            state[node] = 2


def _fail(path: str, message: str) -> None:
    raise TevScriptError("TEVS_IR_V3_CONTRACT", f"{path}: {message}")


def _value_fail(path: str, type_id: str, message: str) -> None:
    raise TevScriptError(
        "TEVS_IR_V3_VALUE_INVALID",
        f"{path}: {message} for expected type {type_id!r}",
    )


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(path, "expected object with string keys")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "expected array")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail(path, "expected string")
    return value


def _local_name(value: Any, path: str) -> str:
    result = _string(value, path)
    if _LOCAL.fullmatch(result) is None:
        _fail(path, f"expected local identifier, got {result!r}")
    return result


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail(path, f"expected integer in [{minimum}, {maximum}]")
    return value
