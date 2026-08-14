from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Callable, Mapping, Sequence, Any

from .diagnostics import TevScriptError
from .ir_v4_values import TypeTableV4, build_type_table_v4
from .source_types_v2 import ResolvedTypeV2, TypeRefV2, parse_type_ref_v2, resolve_type_ref_v2

MAX_GENERIC_PARAMETERS_V2 = 16
MAX_GENERIC_INSTANTIATIONS_V2 = 4096
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_QUALIFIED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


@dataclass(frozen=True, slots=True)
class GenericFieldTemplateV2:
    name: str
    type_ref: TypeRefV2


@dataclass(frozen=True, slots=True)
class GenericRecordTemplateV2:
    owner_id: str
    name: str
    parameters: tuple[str, ...]
    fields: tuple[GenericFieldTemplateV2, ...]
    template_hash: str

    @property
    def qualified_name(self) -> str:
        return f"{self.owner_id}.{self.name}"


@dataclass(frozen=True, slots=True)
class GenericInstantiationV2:
    template_hash: str
    instantiation_hash: str
    source_type_id: str
    runtime_type_id: str
    argument_type_ids: tuple[str, ...]
    emitted_descriptors: tuple[dict[str, Any], ...]


class GenericRegistryV2:
    """Bounded monomorphizing registry for V2 user-defined record generics.

    Runtime identity is content-addressed by template hash + exact runtime type
    arguments. No reflection, erasure, host object identity, or dynamic type
    creation occurs during program execution; monomorphization is a compile step.
    """

    def __init__(
        self,
        base_program: Mapping[str, Any],
        *,
        nominal_resolver: Callable[[str], str] | None = None,
        max_instantiations: int = MAX_GENERIC_INSTANTIATIONS_V2,
    ) -> None:
        boundary = base_program.get("boundary")
        raw_types = base_program.get("types")
        if not isinstance(boundary, Mapping) or not isinstance(raw_types, list):
            _fail("TEVS_V2_GENERIC_BASE", "base program requires boundary and types")
        if not 1 <= max_instantiations <= MAX_GENERIC_INSTANTIATIONS_V2:
            _fail("TEVS_V2_GENERIC_BUDGET", f"max_instantiations must be 1..{MAX_GENERIC_INSTANTIATIONS_V2}")
        self._boundary = dict(boundary)
        self._wire_types: dict[str, dict[str, Any]] = {}
        for raw in raw_types:
            if not isinstance(raw, dict) or not isinstance(raw.get("type_id"), str):
                _fail("TEVS_V2_GENERIC_BASE", "base type descriptor is malformed")
            type_id = str(raw["type_id"])
            if type_id in self._wire_types:
                _fail("TEVS_V2_GENERIC_BASE", f"duplicate base type {type_id!r}")
            self._wire_types[type_id] = dict(raw)
        self._external_nominal_resolver = nominal_resolver
        self._max_instantiations = max_instantiations
        self._templates_by_qualified: dict[str, GenericRecordTemplateV2] = {}
        self._templates_by_local: dict[str, GenericRecordTemplateV2] = {}
        self._instantiations: dict[tuple[str, tuple[str, ...]], GenericInstantiationV2] = {}
        self._active: set[tuple[str, tuple[str, ...]]] = set()
        self._runtime_templates: dict[str, GenericRecordTemplateV2] = {}
        self._table = self._rebuild_table()

    @property
    def table(self) -> TypeTableV4:
        return self._table

    @property
    def instantiation_count(self) -> int:
        return len(self._instantiations)

    def generic_arities(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for template in self._templates_by_qualified.values():
            result[template.qualified_name] = len(template.parameters)
            result[template.name] = len(template.parameters)
        return result

    def register_record(
        self,
        owner_id: str,
        name: str,
        parameters: Sequence[str],
        fields: Sequence[tuple[str, str]],
    ) -> GenericRecordTemplateV2:
        if _QUALIFIED.fullmatch(owner_id) is None:
            _fail("TEVS_V2_GENERIC_NAME", f"invalid generic owner {owner_id!r}")
        if _LOCAL.fullmatch(name) is None:
            _fail("TEVS_V2_GENERIC_NAME", f"invalid generic name {name!r}")
        params = tuple(parameters)
        if not 1 <= len(params) <= MAX_GENERIC_PARAMETERS_V2:
            _fail("TEVS_V2_GENERIC_PARAMETERS", f"generic requires 1..{MAX_GENERIC_PARAMETERS_V2} type parameters")
        if len(set(params)) != len(params) or any(_LOCAL.fullmatch(item) is None for item in params):
            _fail("TEVS_V2_GENERIC_PARAMETERS", "generic type parameters must be unique local names")
        if not 1 <= len(fields) <= 256:
            _fail("TEVS_V2_GENERIC_FIELDS", "generic record requires 1..256 fields")
        qualified = f"{owner_id}.{name}"
        if qualified in self._templates_by_qualified or name in self._templates_by_local:
            _fail("TEVS_V2_GENERIC_DUPLICATE", f"generic template {qualified!r} or local alias {name!r} already exists")
        arities = self.generic_arities()
        arities[name] = len(params)
        arities[qualified] = len(params)
        parsed_fields: list[GenericFieldTemplateV2] = []
        seen_fields: set[str] = set()
        for field_name, type_text in fields:
            if _LOCAL.fullmatch(field_name) is None or field_name in seen_fields:
                _fail("TEVS_V2_GENERIC_FIELDS", f"invalid or duplicate field {field_name!r}")
            seen_fields.add(field_name)
            parsed_fields.append(GenericFieldTemplateV2(field_name, parse_type_ref_v2(type_text, arities)))
        parsed_fields.sort(key=lambda item: item.name)
        parameter_positions = {parameter: index for index, parameter in enumerate(params)}
        canonical = {
            "schema": "TEV_SCRIPT_V2_GENERIC_RECORD_TEMPLATE_V1",
            "owner_id": owner_id,
            "name": name,
            "parameter_count": len(params),
            "fields": [
                {"name": item.name, "type": _canonical_type_ref(item.type_ref, parameter_positions)}
                for item in parsed_fields
            ],
        }
        template_hash = _hash(canonical)
        template = GenericRecordTemplateV2(owner_id, name, params, tuple(parsed_fields), template_hash)
        self._templates_by_qualified[qualified] = template
        self._templates_by_local[name] = template
        return template

    def resolve_source_type(self, text: str) -> ResolvedTypeV2:
        ref = parse_type_ref_v2(text, self.generic_arities())
        return resolve_type_ref_v2(ref, self._resolve_nominal, self._resolve_generic)

    def materialize_source_type(self, text: str) -> ResolvedTypeV2:
        ref = parse_type_ref_v2(text, self.generic_arities())

        def close(item: TypeRefV2) -> ResolvedTypeV2:
            for child in item.arguments:
                close(child)
            resolved = resolve_type_ref_v2(item, self._resolve_nominal, self._resolve_generic)
            self.materialize_resolved_type(resolved)
            return resolved

        return close(ref)

    def parse_literal(self, source_type: str, literal_text: str):
        from .source_collection_literals_v2 import parse_contextual_literal_v2

        resolved = self.resolve_source_type(source_type)
        return parse_contextual_literal_v2(
            literal_text,
            resolved.type_id,
            self._table,
            constructor_names=self.constructor_names(),
        )

    def instantiate(
        self,
        template_or_name: GenericRecordTemplateV2 | str,
        arguments: Sequence[ResolvedTypeV2 | str],
    ) -> GenericInstantiationV2:
        template = self._template(template_or_name)
        normalized: list[ResolvedTypeV2] = []
        for argument in arguments:
            if isinstance(argument, ResolvedTypeV2):
                resolved = argument
            elif isinstance(argument, str):
                resolved = self.resolve_source_type(argument)
            else:
                _fail("TEVS_V2_GENERIC_ARGUMENT", "generic argument must be a resolved type or source type text")
            self._table.require(resolved.type_id, context="generic argument")
            normalized.append(resolved)
        args = tuple(normalized)
        if len(args) != len(template.parameters):
            _fail("TEVS_V2_GENERIC_ARITY", f"{template.qualified_name} expects {len(template.parameters)} type arguments, got {len(args)}")
        key = (template.template_hash, tuple(item.type_id for item in args))
        cached = self._instantiations.get(key)
        if cached is not None:
            return cached
        if key in self._active:
            _fail("TEVS_V2_GENERIC_RECURSION", f"recursive generic instantiation detected for {template.qualified_name}")
        if len(self._instantiations) >= self._max_instantiations:
            _fail("TEVS_V2_GENERIC_BUDGET", f"generic instantiation budget {self._max_instantiations} exhausted")
        self._active.add(key)
        before = set(self._wire_types)
        try:
            parameter_map = dict(zip(template.parameters, args, strict=True))

            def nominal(name: str) -> str:
                argument = parameter_map.get(name)
                if argument is not None:
                    return argument.type_id
                return self._resolve_nominal(name)

            resolved_fields: list[tuple[str, ResolvedTypeV2]] = []
            for field in template.fields:
                resolved = resolve_type_ref_v2(field.type_ref, nominal, self._resolve_generic)
                self._ensure_descriptor(resolved)
                resolved_fields.append((field.name, resolved))

            instantiation_payload = {
                "schema": "TEV_SCRIPT_V2_GENERIC_INSTANTIATION_V1",
                "template_hash": template.template_hash,
                "arguments": [item.type_id for item in args],
            }
            instantiation_hash = _hash(instantiation_payload)
            runtime_type_id = f"{template.owner_id}.{template.name}__g_{instantiation_hash}"
            source_type_id = f"{template.qualified_name}<{','.join(item.type_id for item in args)}>"
            descriptor = {
                "type_id": runtime_type_id,
                "kind": "record",
                "fields": [
                    {"name": name, "type": resolved.type_id}
                    for name, resolved in sorted(resolved_fields, key=lambda item: item[0])
                ],
            }
            existing = self._wire_types.get(runtime_type_id)
            if existing is not None and existing != descriptor:
                _fail("TEVS_V2_GENERIC_COLLISION", f"monomorphized runtime id collision at {runtime_type_id!r}")
            self._wire_types[runtime_type_id] = descriptor
            self._table = self._rebuild_table()
            emitted = tuple(
                dict(self._wire_types[type_id])
                for type_id in sorted(set(self._wire_types) - before)
            )
            result = GenericInstantiationV2(
                template.template_hash,
                instantiation_hash,
                source_type_id,
                runtime_type_id,
                tuple(item.type_id for item in args),
                emitted,
            )
            self._instantiations[key] = result
            self._runtime_templates[runtime_type_id] = template
            return result
        except Exception:
            # Roll back descriptors added by a failed instantiation so a rejected
            # candidate cannot poison later name resolution.
            for type_id in list(set(self._wire_types) - before):
                self._wire_types.pop(type_id, None)
            self._table = self._rebuild_table()
            raise
        finally:
            self._active.discard(key)

    def materialize_resolved_type(self, resolved: ResolvedTypeV2) -> None:
        self._ensure_descriptor(resolved)
        self._table = self._rebuild_table()

    def constructor_names(self) -> dict[str, tuple[str, ...]]:
        return {
            runtime_type_id: (template.name, template.qualified_name)
            for runtime_type_id, template in sorted(self._runtime_templates.items())
        }

    def type_descriptors(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(self._wire_types[type_id]) for type_id in sorted(self._wire_types))

    def _template(self, template_or_name: GenericRecordTemplateV2 | str) -> GenericRecordTemplateV2:
        if isinstance(template_or_name, GenericRecordTemplateV2):
            registered = self._templates_by_qualified.get(template_or_name.qualified_name)
            if registered != template_or_name:
                _fail("TEVS_V2_GENERIC_TEMPLATE", "generic template is not registered in this registry")
            return template_or_name
        if not isinstance(template_or_name, str):
            _fail("TEVS_V2_GENERIC_TEMPLATE", "generic template reference must be template or name")
        result = self._templates_by_qualified.get(template_or_name) or self._templates_by_local.get(template_or_name)
        if result is None:
            _fail("TEVS_V2_GENERIC_TEMPLATE", f"unknown generic template {template_or_name!r}")
        return result

    def _resolve_generic(self, name: str, args: tuple[ResolvedTypeV2, ...]) -> str:
        return self.instantiate(name, args).runtime_type_id

    def _resolve_nominal(self, name: str) -> str:
        if name in self._wire_types:
            return name
        matches = sorted(type_id for type_id in self._wire_types if type_id.endswith("." + name))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            _fail("TEVS_V2_GENERIC_NOMINAL", f"ambiguous nominal type {name!r}: {matches}")
        if self._external_nominal_resolver is not None:
            resolved = self._external_nominal_resolver(name)
            if isinstance(resolved, str) and resolved in self._wire_types:
                return resolved
        _fail("TEVS_V2_GENERIC_NOMINAL", f"unknown nominal type {name!r}")

    def _ensure_descriptor(self, resolved: ResolvedTypeV2) -> None:
        if resolved.type_id in self._wire_types:
            return
        for child in resolved.arguments:
            self._ensure_descriptor(child)
        if resolved.kind == "option":
            descriptor = {"type_id": resolved.type_id, "kind": "option", "argument": resolved.arguments[0].type_id}
        elif resolved.kind == "result":
            descriptor = {
                "type_id": resolved.type_id,
                "kind": "result",
                "ok_type": resolved.arguments[0].type_id,
                "err_type": resolved.arguments[1].type_id,
            }
        elif resolved.kind in {"list", "set"}:
            capacity = resolved.collection_capacity
            assert capacity is not None
            descriptor = {
                "type_id": resolved.type_id,
                "kind": resolved.kind,
                "element_type": resolved.arguments[0].type_id,
                "capacity": capacity,
                "order_policy": "sequence" if resolved.kind == "list" else "canonical_value_bytes",
            }
        elif resolved.kind == "array":
            length = resolved.array_length
            assert length is not None
            descriptor = {
                "type_id": resolved.type_id,
                "kind": "array",
                "element_type": resolved.arguments[0].type_id,
                "length": length,
                "order_policy": "sequence",
            }
        elif resolved.kind == "map":
            capacity = resolved.collection_capacity
            assert capacity is not None
            descriptor = {
                "type_id": resolved.type_id,
                "kind": "map",
                "key_type": resolved.arguments[0].type_id,
                "value_type": resolved.arguments[1].type_id,
                "capacity": capacity,
                "order_policy": "canonical_key_bytes",
            }
        else:
            _fail("TEVS_V2_GENERIC_DESCRIPTOR", f"runtime descriptor for {resolved.type_id!r} is unavailable")
        self._wire_types[resolved.type_id] = descriptor

    def _rebuild_table(self) -> TypeTableV4:
        return build_type_table_v4({
            "boundary": dict(self._boundary),
            "types": [dict(self._wire_types[type_id]) for type_id in sorted(self._wire_types)],
        })


def _canonical_type_ref(ref: TypeRefV2, parameter_positions: Mapping[str, int]) -> dict[str, Any]:
    if ref.kind == "named" and ref.name in parameter_positions:
        return {"kind": "parameter", "index": parameter_positions[ref.name]}
    return {
        "kind": ref.kind,
        "name": ref.name,
        "arguments": [_canonical_type_ref(item, parameter_positions) for item in ref.arguments],
        "const_arguments": list(ref.const_arguments),
    }


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
