from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .values import decode_typed_value, encode_typed_value

_PRIMITIVES = frozenset({"Bool", "Int", "Rat", "Text", "Vec2", "Vec3"})
_BASE_TYPES = frozenset((*_PRIMITIVES, "Unit"))
_NOMINAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_COLLECTION_CAPACITY_V4 = 4096
_MISSING = object()


@dataclass(frozen=True, slots=True)
class TypeDescriptorV4:
    type_id: str
    kind: str
    fields: tuple[tuple[str, str], ...] = ()
    variants: tuple[str, ...] = ()
    argument: str | None = None
    ok_type: str | None = None
    err_type: str | None = None
    element_type: str | None = None
    key_type: str | None = None
    value_type: str | None = None
    capacity: int | None = None
    length: int | None = None
    order_policy: str | None = None


@dataclass(frozen=True, slots=True)
class RecordValueV4:
    type_id: str
    fields: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class VariantValueV4:
    type_id: str
    variant: str
    payload: Any = _MISSING

    @property
    def has_payload(self) -> bool:
        return self.payload is not _MISSING


@dataclass(frozen=True, slots=True)
class ListValueV4:
    type_id: str
    items: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class ArrayValueV4:
    type_id: str
    items: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class SetValueV4:
    type_id: str
    items: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class MapValueV4:
    type_id: str
    entries: tuple[tuple[Any, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class TypeTableV4:
    descriptors: tuple[TypeDescriptorV4, ...]
    maximum_value_nesting: int
    _by_id: Mapping[str, TypeDescriptorV4] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_id", {item.type_id: item for item in self.descriptors})

    def get(self, type_id: str) -> TypeDescriptorV4 | None:
        return self._by_id.get(type_id)

    def require(self, type_id: str, *, context: str = "type") -> TypeDescriptorV4:
        result = self.get(type_id)
        if result is None:
            raise TevScriptError("TEVS_IR_V4_TYPE_UNKNOWN", f"{context} references unknown V4 type {type_id!r}")
        return result


def build_type_table_v4(program: Mapping[str, Any]) -> TypeTableV4:
    boundary = _object(program.get("boundary"), "$.boundary")
    maximum = _integer(boundary.get("maximum_value_nesting"), "$.boundary.maximum_value_nesting", 1, 128)
    raw_types = _array(program.get("types"), "$.types")
    if not 7 <= len(raw_types) <= 16384:
        _fail("$.types", "type table requires 7..16384 descriptors")
    descriptors: list[TypeDescriptorV4] = []
    seen: set[str] = set()
    order: list[str] = []
    for index, raw in enumerate(raw_types):
        path = f"$.types[{index}]"
        item = _object(raw, path)
        type_id = _string(item.get("type_id"), path + ".type_id")
        kind = _string(item.get("kind"), path + ".kind")
        if type_id in seen:
            _fail(path + ".type_id", f"duplicate type id {type_id!r}")
        seen.add(type_id); order.append(type_id)
        if kind == "primitive":
            if set(item) != {"type_id", "kind"} or type_id not in _PRIMITIVES:
                _fail(path, "invalid primitive descriptor")
            d = TypeDescriptorV4(type_id, kind)
        elif kind == "unit":
            if set(item) != {"type_id", "kind"} or type_id != "Unit":
                _fail(path, "invalid Unit descriptor")
            d = TypeDescriptorV4(type_id, kind)
        elif kind == "record":
            if set(item) != {"type_id", "kind", "fields"} or _NOMINAL.fullmatch(type_id) is None:
                _fail(path, "invalid record descriptor")
            raw_fields = _array(item["fields"], path + ".fields")
            if not 1 <= len(raw_fields) <= 256:
                _fail(path + ".fields", "record requires 1..256 fields")
            fields: list[tuple[str, str]] = []
            names: set[str] = set()
            for fi, rf in enumerate(raw_fields):
                fp = f"{path}.fields[{fi}]"; f = _object(rf, fp)
                if set(f) != {"name", "type"}: _fail(fp, "record field shape mismatch")
                name = _local_name(f["name"], fp + ".name"); child = _string(f["type"], fp + ".type")
                if name in names: _fail(fp + ".name", f"duplicate record field {name!r}")
                names.add(name); fields.append((name, child))
            if [name for name, _ in fields] != sorted(names):
                _fail(path + ".fields", "record fields must be sorted lexically")
            d = TypeDescriptorV4(type_id, kind, fields=tuple(fields))
        elif kind == "enum":
            if set(item) != {"type_id", "kind", "variants"} or _NOMINAL.fullmatch(type_id) is None:
                _fail(path, "invalid enum descriptor")
            variants = tuple(_local_name(v, f"{path}.variants[{i}]") for i, v in enumerate(_array(item["variants"], path + ".variants")))
            if not 1 <= len(variants) <= 256 or len(set(variants)) != len(variants) or list(variants) != sorted(variants):
                _fail(path + ".variants", "enum variants must be 1..256 unique sorted names")
            d = TypeDescriptorV4(type_id, kind, variants=variants)
        elif kind == "option":
            if set(item) != {"type_id", "kind", "argument"}: _fail(path, "Option descriptor field set mismatch")
            argument = _string(item["argument"], path + ".argument")
            if type_id != f"Option<{argument}>": _fail(path + ".type_id", "Option type id does not match argument")
            d = TypeDescriptorV4(type_id, kind, argument=argument)
        elif kind == "result":
            if set(item) != {"type_id", "kind", "ok_type", "err_type"}: _fail(path, "Result descriptor field set mismatch")
            ok_type = _string(item["ok_type"], path + ".ok_type"); err_type = _string(item["err_type"], path + ".err_type")
            if type_id != f"Result<{ok_type},{err_type}>": _fail(path + ".type_id", "Result type id does not match arguments")
            d = TypeDescriptorV4(type_id, kind, ok_type=ok_type, err_type=err_type)
        elif kind in {"list", "set"}:
            if set(item) != {"type_id", "kind", "element_type", "capacity", "order_policy"}: _fail(path, f"{kind} descriptor field set mismatch")
            element = _string(item["element_type"], path + ".element_type")
            capacity = _integer(item["capacity"], path + ".capacity", 1, MAX_COLLECTION_CAPACITY_V4)
            policy = _string(item["order_policy"], path + ".order_policy")
            expected_policy = "sequence" if kind == "list" else "canonical_value_bytes"
            expected_id = f"{'List' if kind == 'list' else 'Set'}<{element},{capacity}>"
            if type_id != expected_id: _fail(path + ".type_id", f"{kind} type id does not match descriptor")
            if policy != expected_policy: _fail(path + ".order_policy", f"{kind} requires {expected_policy}")
            d = TypeDescriptorV4(type_id, kind, element_type=element, capacity=capacity, order_policy=policy)
        elif kind == "array":
            if set(item) != {"type_id", "kind", "element_type", "length", "order_policy"}: _fail(path, "array descriptor field set mismatch")
            element = _string(item["element_type"], path + ".element_type")
            length = _integer(item["length"], path + ".length", 1, MAX_COLLECTION_CAPACITY_V4)
            policy = _string(item["order_policy"], path + ".order_policy")
            if type_id != f"Array<{element},{length}>": _fail(path + ".type_id", "array type id does not match descriptor")
            if policy != "sequence": _fail(path + ".order_policy", "array requires sequence")
            d = TypeDescriptorV4(type_id, kind, element_type=element, length=length, order_policy=policy)
        elif kind == "map":
            if set(item) != {"type_id", "kind", "key_type", "value_type", "capacity", "order_policy"}: _fail(path, "map descriptor field set mismatch")
            key_type = _string(item["key_type"], path + ".key_type"); value_type = _string(item["value_type"], path + ".value_type")
            capacity = _integer(item["capacity"], path + ".capacity", 1, MAX_COLLECTION_CAPACITY_V4)
            policy = _string(item["order_policy"], path + ".order_policy")
            if type_id != f"Map<{key_type},{value_type},{capacity}>": _fail(path + ".type_id", "map type id does not match descriptor")
            if policy != "canonical_key_bytes": _fail(path + ".order_policy", "map requires canonical_key_bytes")
            d = TypeDescriptorV4(type_id, kind, key_type=key_type, value_type=value_type, capacity=capacity, order_policy=policy)
        else:
            _fail(path + ".kind", f"unsupported V4 type kind {kind!r}")
        descriptors.append(d)
    if order != sorted(order): _fail("$.types", "type table must be sorted lexically by type_id")
    missing = sorted(_BASE_TYPES - seen)
    if missing: _fail("$.types", f"missing portable base descriptors {missing}")
    table = TypeTableV4(tuple(descriptors), maximum)
    _validate_references_and_cycles(table)
    return table


def encode_v4_value(type_id: str, value: Any, table: TypeTableV4, *, context: str = "value", depth: int = 1) -> Any:
    if depth > table.maximum_value_nesting:
        raise TevScriptError("TEVS_IR_V4_VALUE_NESTING", f"{context}: value nesting exceeds {table.maximum_value_nesting}")
    d = table.require(type_id, context=context)
    if d.kind == "unit": _value_fail(context, type_id, "Unit is not encodable")
    if d.kind == "primitive":
        try: return encode_typed_value(type_id, value)
        except (TevScriptError, TypeError, ValueError, ZeroDivisionError) as exc: _value_fail(context, type_id, str(exc))
    if d.kind == "record":
        if not isinstance(value, RecordValueV4) or value.type_id != type_id: _value_fail(context, type_id, "expected exact RecordValueV4")
        actual = dict(value.fields)
        if set(actual) != {name for name, _ in d.fields}: _value_fail(context, type_id, "record field set mismatch")
        return {"$record":{"type":type_id,"fields":[{"name":name,"value":encode_v4_value(ft,actual[name],table,context=f"{context}.{name}",depth=depth+1)} for name,ft in d.fields]}}
    if d.kind == "enum":
        if not isinstance(value, VariantValueV4) or value.type_id != type_id or value.variant not in d.variants or value.has_payload: _value_fail(context,type_id,"invalid enum value")
        return {"$enum":{"type":type_id,"variant":value.variant}}
    if d.kind in {"option", "result"}:
        if not isinstance(value, VariantValueV4) or value.type_id != type_id: _value_fail(context,type_id,"expected exact VariantValueV4")
        if d.kind == "option":
            if value.variant == "None":
                if value.has_payload: _value_fail(context,type_id,"None cannot carry payload")
                return {"$option":{"type":type_id,"variant":"None"}}
            if value.variant != "Some" or not value.has_payload: _value_fail(context,type_id,"Some requires payload")
            assert d.argument is not None
            return {"$option":{"type":type_id,"variant":"Some","value":encode_v4_value(d.argument,value.payload,table,context=context+".value",depth=depth+1)}}
        payload_type = d.ok_type if value.variant == "Ok" else d.err_type if value.variant == "Err" else None
        if payload_type is None or not value.has_payload: _value_fail(context,type_id,"Result requires Ok/Err payload")
        return {"$result":{"type":type_id,"variant":value.variant,"value":encode_v4_value(payload_type,value.payload,table,context=context+".value",depth=depth+1)}}
    if d.kind == "list":
        if not isinstance(value, ListValueV4) or value.type_id != type_id: _value_fail(context,type_id,"expected exact ListValueV4")
        assert d.element_type is not None and d.capacity is not None
        if len(value.items) > d.capacity: _value_fail(context,type_id,"list capacity exceeded")
        items=[encode_v4_value(d.element_type,v,table,context=f"{context}[{i}]",depth=depth+1) for i,v in enumerate(value.items)]
        return {"$list":{"type":type_id,"items":items}}
    if d.kind == "array":
        if not isinstance(value, ArrayValueV4) or value.type_id != type_id: _value_fail(context,type_id,"expected exact ArrayValueV4")
        assert d.element_type is not None and d.length is not None
        if len(value.items) != d.length: _value_fail(context,type_id,f"array requires exact length {d.length}, got {len(value.items)}")
        items=[encode_v4_value(d.element_type,v,table,context=f"{context}[{i}]",depth=depth+1) for i,v in enumerate(value.items)]
        return {"$array":{"type":type_id,"items":items}}
    if d.kind == "set":
        if not isinstance(value, SetValueV4) or value.type_id != type_id: _value_fail(context,type_id,"expected exact SetValueV4")
        assert d.element_type is not None and d.capacity is not None
        if len(value.items) > d.capacity: _value_fail(context,type_id,"set capacity exceeded")
        pairs=[]
        for i,v in enumerate(value.items):
            encoded=encode_v4_value(d.element_type,v,table,context=f"{context}[{i}]",depth=depth+1); pairs.append((_canonical_bytes(encoded),encoded))
        keys=[k for k,_ in pairs]
        if len(set(keys)) != len(keys): _value_fail(context,type_id,"set contains duplicate canonical value")
        pairs.sort(key=lambda p:p[0])
        return {"$set":{"type":type_id,"items":[v for _,v in pairs]}}
    if d.kind == "map":
        if not isinstance(value, MapValueV4) or value.type_id != type_id: _value_fail(context,type_id,"expected exact MapValueV4")
        assert d.key_type is not None and d.value_type is not None and d.capacity is not None
        if len(value.entries) > d.capacity: _value_fail(context,type_id,"map capacity exceeded")
        pairs=[]
        for i,(k,v) in enumerate(value.entries):
            ek=encode_v4_value(d.key_type,k,table,context=f"{context}.key[{i}]",depth=depth+1)
            ev=encode_v4_value(d.value_type,v,table,context=f"{context}.value[{i}]",depth=depth+1)
            pairs.append((_canonical_bytes(ek),{"key":ek,"value":ev}))
        keys=[k for k,_ in pairs]
        if len(set(keys)) != len(keys): _value_fail(context,type_id,"map contains duplicate canonical key")
        pairs.sort(key=lambda p:p[0])
        return {"$map":{"type":type_id,"entries":[v for _,v in pairs]}}
    raise AssertionError(d.kind)


def decode_v4_value(type_id: str, raw: Any, table: TypeTableV4, *, context: str = "value", depth: int = 1) -> Any:
    if depth > table.maximum_value_nesting: raise TevScriptError("TEVS_IR_V4_VALUE_NESTING", f"{context}: value nesting exceeds {table.maximum_value_nesting}")
    d=table.require(type_id,context=context)
    if d.kind=="unit": _value_fail(context,type_id,"Unit is not a runtime value")
    if d.kind=="primitive":
        try: return decode_typed_value(type_id,raw)
        except (TevScriptError,TypeError,ValueError,ZeroDivisionError) as exc: _value_fail(context,type_id,str(exc))
    outer=_object(raw,context)
    if d.kind=="record":
        if set(outer)!={"$record"}: _value_fail(context,type_id,"expected $record")
        payload=_object(outer["$record"],context+".$record")
        if set(payload)!={"type","fields"} or payload["type"]!=type_id: _value_fail(context,type_id,"record encoded type mismatch")
        fields=_array(payload["fields"],context+".fields")
        if len(fields)!=len(d.fields): _value_fail(context,type_id,"record field count mismatch")
        decoded=[]
        for i,((name,ft),rf) in enumerate(zip(d.fields,fields,strict=True)):
            f=_object(rf,f"{context}.fields[{i}]")
            if set(f)!={"name","value"} or f["name"]!=name: _value_fail(context,type_id,"record field order/shape mismatch")
            decoded.append((name,decode_v4_value(ft,f["value"],table,context=f"{context}.{name}",depth=depth+1)))
        return RecordValueV4(type_id,tuple(decoded))
    if d.kind=="enum":
        if set(outer)!={"$enum"}: _value_fail(context,type_id,"expected $enum")
        p=_object(outer["$enum"],context+".$enum")
        if set(p)!={"type","variant"} or p["type"]!=type_id or p["variant"] not in d.variants: _value_fail(context,type_id,"invalid enum payload")
        return VariantValueV4(type_id,str(p["variant"]))
    if d.kind=="option":
        if set(outer)!={"$option"}: _value_fail(context,type_id,"expected $option")
        p=_object(outer["$option"],context+".$option")
        if p.get("type")!=type_id: _value_fail(context,type_id,"Option encoded type mismatch")
        if p.get("variant")=="None" and set(p)=={"type","variant"}: return VariantValueV4(type_id,"None")
        if p.get("variant")=="Some" and set(p)=={"type","variant","value"}:
            assert d.argument is not None
            return VariantValueV4(type_id,"Some",decode_v4_value(d.argument,p["value"],table,context=context+".value",depth=depth+1))
        _value_fail(context,type_id,"invalid Option payload")
    if d.kind=="result":
        if set(outer)!={"$result"}: _value_fail(context,type_id,"expected $result")
        p=_object(outer["$result"],context+".$result"); variant=p.get("variant")
        pt=d.ok_type if variant=="Ok" else d.err_type if variant=="Err" else None
        if p.get("type")!=type_id or pt is None or set(p)!={"type","variant","value"}: _value_fail(context,type_id,"invalid Result payload")
        return VariantValueV4(type_id,str(variant),decode_v4_value(pt,p["value"],table,context=context+".value",depth=depth+1))
    key="$list" if d.kind=="list" else "$array" if d.kind=="array" else "$set" if d.kind=="set" else "$map"
    if set(outer)!={key}: _value_fail(context,type_id,f"expected {key}")
    p=_object(outer[key],context+"."+key)
    if p.get("type")!=type_id: _value_fail(context,type_id,"collection encoded type mismatch")
    if d.kind in {"list","array","set"}:
        if set(p)!={"type","items"}: _value_fail(context,type_id,"collection field set mismatch")
        items=_array(p["items"],context+".items"); assert d.element_type is not None
        if d.kind=="array":
            assert d.length is not None
            if len(items)!=d.length: _value_fail(context,type_id,f"array requires exact length {d.length}, got {len(items)}")
        else:
            assert d.capacity is not None
            if len(items)>d.capacity: _value_fail(context,type_id,"collection capacity exceeded")
        if d.kind=="set":
            keys=[_canonical_bytes(v) for v in items]
            if keys!=sorted(keys) or len(set(keys))!=len(keys): _value_fail(context,type_id,"set items must be unique canonical-byte sorted")
        values=tuple(decode_v4_value(d.element_type,v,table,context=f"{context}[{i}]",depth=depth+1) for i,v in enumerate(items))
        if d.kind=="list": return ListValueV4(type_id,values)
        if d.kind=="array": return ArrayValueV4(type_id,values)
        return SetValueV4(type_id,values)
    if set(p)!={"type","entries"}: _value_fail(context,type_id,"map field set mismatch")
    entries=_array(p["entries"],context+".entries"); assert d.capacity is not None and d.key_type is not None and d.value_type is not None
    if len(entries)>d.capacity: _value_fail(context,type_id,"map capacity exceeded")
    raw_pairs=[]
    for i,re in enumerate(entries):
        e=_object(re,f"{context}.entries[{i}]")
        if set(e)!={"key","value"}: _value_fail(context,type_id,"map entry shape mismatch")
        raw_pairs.append((_canonical_bytes(e["key"]),e))
    keys=[k for k,_ in raw_pairs]
    if keys!=sorted(keys) or len(set(keys))!=len(keys): _value_fail(context,type_id,"map keys must be unique canonical-byte sorted")
    decoded=[]
    for i,(_,e) in enumerate(raw_pairs):
        decoded.append((decode_v4_value(d.key_type,e["key"],table,context=f"{context}.key[{i}]",depth=depth+1),decode_v4_value(d.value_type,e["value"],table,context=f"{context}.value[{i}]",depth=depth+1)))
    return MapValueV4(type_id,tuple(decoded))


def v4_values_equal(type_id: str, left: Any, right: Any, table: TypeTableV4) -> bool:
    try:
        return encode_v4_value(type_id,left,table)==encode_v4_value(type_id,right,table)
    except TevScriptError:
        return False


def _validate_references_and_cycles(table: TypeTableV4) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    for descriptor in table.descriptors:
        references: list[str | None] = []
        if descriptor.kind == "record":
            references.extend(type_id for _, type_id in descriptor.fields)
        elif descriptor.kind == "option":
            references.append(descriptor.argument)
        elif descriptor.kind == "result":
            references.extend((descriptor.ok_type, descriptor.err_type))
        elif descriptor.kind in {"list", "array", "set"}:
            references.append(descriptor.element_type)
        elif descriptor.kind == "map":
            references.extend((descriptor.key_type, descriptor.value_type))

        checked: list[str] = []
        for reference in references:
            assert reference is not None
            child = table.require(reference, context=f"descriptor {descriptor.type_id}")
            if child.kind == "unit":
                _fail("$.types", f"Unit is not storable inside {descriptor.type_id!r}")
            checked.append(reference)
        graph[descriptor.type_id] = tuple(checked)

    state: dict[str, int] = {}
    memo_depth: dict[str, int] = {}

    def depth(type_id: str, path: tuple[str, ...]) -> int:
        cached = memo_depth.get(type_id)
        if cached is not None:
            return cached
        mark = state.get(type_id, 0)
        if mark == 1:
            if type_id in path:
                cycle_start = path.index(type_id)
                cycle = (*path[cycle_start:], type_id)
            else:
                cycle = (*path, type_id)
            _fail("$.types", "constructed type dependency cycle: " + " -> ".join(cycle))
        state[type_id] = 1
        descriptor = table.require(type_id)
        child_depth = 0
        for child in graph[type_id]:
            child_depth = max(child_depth, depth(child, (*path, type_id)))
        observed = (
            1
            if descriptor.kind in {"primitive", "unit", "enum"}
            else 1 + child_depth
        )
        state[type_id] = 2
        memo_depth[type_id] = observed
        if observed > 128:
            _fail("$.types", f"type nesting exceeds 128 at {type_id!r}: got {observed}")
        return observed

    for type_id in sorted(graph):
        depth(type_id, ())

def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def _fail(path:str,message:str)->None: raise TevScriptError("TEVS_IR_V4_CONTRACT",f"{path}: {message}")
def _value_fail(path:str,type_id:str,message:str)->None: raise TevScriptError("TEVS_IR_V4_VALUE_INVALID",f"{path}: {message} for expected type {type_id!r}")
def _object(value:Any,path:str)->dict[str,Any]:
    if not isinstance(value,dict) or not all(isinstance(k,str) for k in value): _fail(path,"expected object with string keys")
    return value
def _array(value:Any,path:str)->list[Any]:
    if not isinstance(value,list): _fail(path,"expected array")
    return value
def _string(value:Any,path:str)->str:
    if not isinstance(value,str): _fail(path,"expected string")
    return value
def _integer(value:Any,path:str,minimum:int,maximum:int)->int:
    if isinstance(value,bool) or not isinstance(value,int) or not minimum<=value<=maximum: _fail(path,f"expected integer in [{minimum}, {maximum}]")
    return value
def _local_name(value:Any,path:str)->str:
    text=_string(value,path)
    if _LOCAL.fullmatch(text) is None: _fail(path,"expected local identifier")
    return text
