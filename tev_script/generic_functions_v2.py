from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .generic_types_v2 import GenericRegistryV2
from .ir_v4_pure import (
    MAX_PURE_EVAL_STEPS_V4,
    PureBindingV4,
    PureValidationV4,
    canonical_expression_v4,
    evaluate_pure_v4,
    validate_pure_v4,
)
from .ir_v4_values import TypeDescriptorV4, TypeTableV4
from .source_types_v2 import (
    ResolvedTypeV2,
    TypeRefV2,
    parse_type_ref_v2,
    resolve_type_ref_v2,
    validate_static_type_ref_v2,
)

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OWNER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
MAX_GENERIC_FUNCTION_PARAMETERS_V2 = 64
MAX_GENERIC_FUNCTION_TEMPLATES_V2 = 4096
MAX_GENERIC_FUNCTION_INSTANTIATIONS_V2 = 16384
_TYPE_FIELDS = frozenset({
    "type", "operand_type", "result_type", "left_type", "right_type",
    "record_type", "collection_type", "accumulator_type", "subject_type",
})


@dataclass(frozen=True, slots=True)
class GenericFunctionParameterTemplateV2:
    name: str
    type_ref: TypeRefV2


@dataclass(frozen=True, slots=True)
class GenericPureFunctionTemplateV2:
    owner_id: str
    name: str
    type_parameters: tuple[str, ...]
    parameters: tuple[GenericFunctionParameterTemplateV2, ...]
    return_type: TypeRefV2
    body: dict[str, Any]
    maximum_steps: int
    template_hash: str

    @property
    def qualified_name(self) -> str:
        return f"{self.owner_id}.{self.name}"


@dataclass(frozen=True, slots=True)
class GenericPureFunctionInstantiationV2:
    template_hash: str
    instantiation_hash: str
    callable_id: str
    argument_type_ids: tuple[str, ...]
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    return_type_id: str
    body: dict[str, Any]
    body_expression_hash: str
    dependency_roots: tuple[str, ...]
    dependency_hash: str
    static_step_upper_bound: int
    maximum_steps: int


@dataclass(frozen=True, slots=True)
class GenericPureFunctionCallReceiptV2:
    schema: str
    callable_id: str
    template_hash: str
    instantiation_hash: str
    dependency_hash: str
    type_table_hash: str
    arguments_hash: str
    evaluation_receipt_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    evaluation_steps: int
    static_step_upper_bound: int
    bounded_loop_iterations: int
    receipt_hash: str


class GenericPureFunctionRegistryV2:
    def __init__(
        self,
        types: GenericRegistryV2,
        *,
        max_templates: int = MAX_GENERIC_FUNCTION_TEMPLATES_V2,
        max_instantiations: int = MAX_GENERIC_FUNCTION_INSTANTIATIONS_V2,
    ) -> None:
        if not 1 <= max_templates <= MAX_GENERIC_FUNCTION_TEMPLATES_V2:
            _fail("TEVS_V2_GENERIC_FUNCTION_BUDGET", "invalid template budget")
        if not 1 <= max_instantiations <= MAX_GENERIC_FUNCTION_INSTANTIATIONS_V2:
            _fail("TEVS_V2_GENERIC_FUNCTION_BUDGET", "invalid instantiation budget")
        self.types = types
        self.max_templates = max_templates
        self.max_instantiations = max_instantiations
        self._templates_by_qualified: dict[str, GenericPureFunctionTemplateV2] = {}
        self._templates_by_local: dict[str, GenericPureFunctionTemplateV2] = {}
        self._instantiations: dict[tuple[str, tuple[str, ...], str], GenericPureFunctionInstantiationV2] = {}

    def register(
        self,
        owner_id: str,
        name: str,
        type_parameters: Sequence[str],
        parameters: Sequence[tuple[str, str]],
        return_type: str,
        body: Mapping[str, Any],
        *,
        maximum_steps: int = 100_000,
    ) -> GenericPureFunctionTemplateV2:
        if len(self._templates_by_qualified) >= self.max_templates:
            _fail("TEVS_V2_GENERIC_FUNCTION_BUDGET", "generic function template budget exhausted")
        if not isinstance(owner_id, str) or _OWNER.fullmatch(owner_id) is None:
            _fail("TEVS_V2_GENERIC_FUNCTION_NAME", f"invalid owner {owner_id!r}")
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            _fail("TEVS_V2_GENERIC_FUNCTION_NAME", f"invalid function name {name!r}")
        type_params = tuple(type_parameters)
        if not 0 <= len(type_params) <= 16 or len(set(type_params)) != len(type_params) or any(_NAME.fullmatch(item) is None for item in type_params):
            _fail("TEVS_V2_GENERIC_FUNCTION_TYPES", "pure function allows 0..16 unique type parameters")
        if not 0 <= len(parameters) <= MAX_GENERIC_FUNCTION_PARAMETERS_V2:
            _fail("TEVS_V2_GENERIC_FUNCTION_PARAMETERS", f"pure function allows 0..{MAX_GENERIC_FUNCTION_PARAMETERS_V2} value parameters")
        if isinstance(maximum_steps, bool) or not isinstance(maximum_steps, int) or not 1 <= maximum_steps <= MAX_PURE_EVAL_STEPS_V4:
            _fail("TEVS_V2_GENERIC_FUNCTION_BUDGET", f"maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
        qualified = f"{owner_id}.{name}"
        if qualified in self._templates_by_qualified or name in self._templates_by_local:
            _fail("TEVS_V2_GENERIC_FUNCTION_DUPLICATE", f"function {qualified!r} or local alias {name!r} already exists")

        generic_arities = self.types.generic_arities()
        parsed_parameters: list[GenericFunctionParameterTemplateV2] = []
        seen_names: set[str] = set()
        for parameter_name, type_text in parameters:
            if not isinstance(parameter_name, str) or _NAME.fullmatch(parameter_name) is None or parameter_name in seen_names:
                _fail("TEVS_V2_GENERIC_FUNCTION_PARAMETERS", f"invalid or duplicate parameter {parameter_name!r}")
            seen_names.add(parameter_name)
            parsed_type = parse_type_ref_v2(type_text, generic_arities)
            validate_static_type_ref_v2(
                parsed_type,
                type_parameters=type_params,
                nominal_resolver=lambda item: self.types.resolve_source_type(item).type_id,
                user_generic_arities=generic_arities,
            )
            parsed_parameters.append(GenericFunctionParameterTemplateV2(parameter_name, parsed_type))
        parsed_return = parse_type_ref_v2(return_type, generic_arities)
        validate_static_type_ref_v2(
            parsed_return,
            type_parameters=type_params,
            nominal_resolver=lambda item: self.types.resolve_source_type(item).type_id,
            user_generic_arities=generic_arities,
        )
        canonical_body = canonical_expression_v4(body)
        for const_type in _const_type_refs(canonical_body, generic_arities):
            if _mentions_parameters(const_type, set(type_params)):
                _fail(
                    "TEVS_V2_GENERIC_FUNCTION_CONST_GENERIC",
                    "generic-dependent CONST is forbidden; construct the value with typed IR V4 nodes instead",
                )

        positions = {parameter: index for index, parameter in enumerate(type_params)}
        canonical = {
            "schema": "TEV_SCRIPT_V2_GENERIC_PURE_FUNCTION_TEMPLATE_V1",
            "owner_id": owner_id,
            "name": name,
            "type_parameter_count": len(type_params),
            "parameters": [
                {"name": parameter.name, "type": _canonical_type_ref(parameter.type_ref, positions)}
                for parameter in parsed_parameters
            ],
            "return_type": _canonical_type_ref(parsed_return, positions),
            "body": _canonicalize_body_types(canonical_body, positions, generic_arities),
            "maximum_steps": maximum_steps,
        }
        template = GenericPureFunctionTemplateV2(
            owner_id,
            name,
            type_params,
            tuple(parsed_parameters),
            parsed_return,
            canonical_body,
            maximum_steps,
            _hash(canonical),
        )
        self._templates_by_qualified[qualified] = template
        self._templates_by_local[name] = template
        return template

    def instantiate(
        self,
        template_or_name: GenericPureFunctionTemplateV2 | str,
        arguments: Sequence[ResolvedTypeV2 | str],
    ) -> GenericPureFunctionInstantiationV2:
        template = self._template(template_or_name)
        resolved_args: list[ResolvedTypeV2] = []
        for raw in arguments:
            resolved = raw if isinstance(raw, ResolvedTypeV2) else self.types.resolve_source_type(raw) if isinstance(raw, str) else None
            if resolved is None:
                _fail("TEVS_V2_GENERIC_FUNCTION_TYPES", "type argument must be resolved type or source type text")
            self.types.materialize_resolved_type(resolved)
            resolved_args.append(resolved)
        args = tuple(resolved_args)
        if len(args) != len(template.type_parameters):
            _fail("TEVS_V2_GENERIC_FUNCTION_ARITY", f"{template.qualified_name} expects {len(template.type_parameters)} type arguments, got {len(args)}")
        substitutions = dict(zip(template.type_parameters, args, strict=True))

        parameter_types = tuple(self._resolve_template_type(item.type_ref, substitutions) for item in template.parameters)
        return_type = self._resolve_template_type(template.return_type, substitutions)
        for resolved in (*parameter_types, return_type):
            self.types.materialize_resolved_type(resolved)

        body = _instantiate_body_types(
            template.body,
            lambda type_text: self._resolve_type_text(type_text, substitutions),
        )
        validation = validate_pure_v4(
            body,
            self.types.table,
            {parameter.name: resolved.type_id for parameter, resolved in zip(template.parameters, parameter_types, strict=True)},
        )
        if validation.result_type != return_type.type_id:
            _fail(
                "TEVS_V2_GENERIC_FUNCTION_RETURN",
                f"function body returns {validation.result_type}, declared {return_type.type_id}",
            )
        if validation.static_step_upper_bound > template.maximum_steps:
            _fail(
                "TEVS_V2_GENERIC_FUNCTION_BUDGET",
                f"static step upper bound {validation.static_step_upper_bound} exceeds function budget {template.maximum_steps}",
            )

        roots = set(item.type_id for item in parameter_types)
        roots.add(return_type.type_id)
        roots.update(_collect_instantiated_type_ids(body))
        dependency_roots = tuple(sorted(roots))
        dependency_hash = _dependency_hash(self.types.table, dependency_roots)
        cache_key = (template.template_hash, tuple(item.type_id for item in args), dependency_hash)
        cached = self._instantiations.get(cache_key)
        if cached is not None:
            return cached
        if len(self._instantiations) >= self.max_instantiations:
            _fail("TEVS_V2_GENERIC_FUNCTION_BUDGET", "generic function instantiation budget exhausted")

        instantiation_payload = {
            "schema": "TEV_SCRIPT_V2_GENERIC_PURE_FUNCTION_INSTANTIATION_V1",
            "template_hash": template.template_hash,
            "argument_type_ids": [item.type_id for item in args],
            "parameter_type_ids": [item.type_id for item in parameter_types],
            "return_type_id": return_type.type_id,
            "body_expression_hash": validation.expression_hash,
            "dependency_hash": dependency_hash,
            "static_step_upper_bound": validation.static_step_upper_bound,
            "maximum_steps": template.maximum_steps,
        }
        instantiation_hash = _hash(instantiation_payload)
        result = GenericPureFunctionInstantiationV2(
            template.template_hash,
            instantiation_hash,
            f"{template.owner_id}.{template.name}__g_{instantiation_hash}",
            tuple(item.type_id for item in args),
            tuple(item.name for item in template.parameters),
            tuple(item.type_id for item in parameter_types),
            return_type.type_id,
            body,
            validation.expression_hash,
            dependency_roots,
            dependency_hash,
            validation.static_step_upper_bound,
            template.maximum_steps,
        )
        self._instantiations[cache_key] = result
        return result

    def call(
        self,
        instantiation: GenericPureFunctionInstantiationV2,
        arguments: Sequence[Any],
    ) -> GenericPureFunctionCallReceiptV2:
        if not isinstance(instantiation, GenericPureFunctionInstantiationV2):
            _fail("TEVS_V2_GENERIC_FUNCTION_CALL", "call requires a generic pure function instantiation")
        if len(arguments) != len(instantiation.parameter_names):
            _fail("TEVS_V2_GENERIC_FUNCTION_CALL", f"expected {len(instantiation.parameter_names)} arguments, got {len(arguments)}")
        current_dependency_hash = _dependency_hash(self.types.table, instantiation.dependency_roots)
        if current_dependency_hash != instantiation.dependency_hash:
            _fail("TEVS_V2_GENERIC_FUNCTION_STALE", "function type dependency closure changed after instantiation")
        bindings = [
            PureBindingV4(name, type_id, value)
            for name, type_id, value in zip(
                instantiation.parameter_names,
                instantiation.parameter_type_ids,
                arguments,
                strict=True,
            )
        ]
        evaluation = evaluate_pure_v4(
            instantiation.body,
            self.types.table,
            bindings,
            maximum_steps=instantiation.maximum_steps,
        )
        if evaluation.result_type != instantiation.return_type_id:
            _fail("TEVS_V2_GENERIC_FUNCTION_RETURN", "runtime result type diverged from validated instantiation")
        payload = {
            "schema": "TEV_SCRIPT_V2_GENERIC_PURE_FUNCTION_CALL_RECEIPT_V1",
            "callable_id": instantiation.callable_id,
            "template_hash": instantiation.template_hash,
            "instantiation_hash": instantiation.instantiation_hash,
            "dependency_hash": instantiation.dependency_hash,
            "type_table_hash": evaluation.type_table_hash,
            "arguments_hash": evaluation.environment_hash,
            "evaluation_receipt_hash": evaluation.receipt_hash,
            "result_type": evaluation.result_type,
            "result_encoded": evaluation.result_encoded,
            "result_hash": evaluation.result_hash,
            "evaluation_steps": evaluation.evaluation_steps,
            "static_step_upper_bound": evaluation.static_step_upper_bound,
            "bounded_loop_iterations": evaluation.bounded_loop_iterations,
        }
        return GenericPureFunctionCallReceiptV2(
            payload["schema"],
            instantiation.callable_id,
            instantiation.template_hash,
            instantiation.instantiation_hash,
            instantiation.dependency_hash,
            evaluation.type_table_hash,
            evaluation.environment_hash,
            evaluation.receipt_hash,
            evaluation.result_type,
            evaluation.result_encoded,
            evaluation.result_hash,
            evaluation.evaluation_steps,
            evaluation.static_step_upper_bound,
            evaluation.bounded_loop_iterations,
            _hash(payload),
        )

    def call_generic(
        self,
        name: str,
        type_arguments: Sequence[ResolvedTypeV2 | str],
        arguments: Sequence[Any],
    ) -> GenericPureFunctionCallReceiptV2:
        return self.call(self.instantiate(name, type_arguments), arguments)

    def _template(self, template_or_name: GenericPureFunctionTemplateV2 | str) -> GenericPureFunctionTemplateV2:
        if isinstance(template_or_name, GenericPureFunctionTemplateV2):
            registered = self._templates_by_qualified.get(template_or_name.qualified_name)
            if registered != template_or_name:
                _fail("TEVS_V2_GENERIC_FUNCTION_TEMPLATE", "function template is not registered here")
            return template_or_name
        if not isinstance(template_or_name, str):
            _fail("TEVS_V2_GENERIC_FUNCTION_TEMPLATE", "function template reference must be template or name")
        result = self._templates_by_qualified.get(template_or_name) or self._templates_by_local.get(template_or_name)
        if result is None:
            _fail("TEVS_V2_GENERIC_FUNCTION_TEMPLATE", f"unknown generic function {template_or_name!r}")
        return result

    def _resolve_type_text(self, text: str, substitutions: Mapping[str, ResolvedTypeV2]) -> ResolvedTypeV2:
        ref = parse_type_ref_v2(text, self.types.generic_arities())
        return self._resolve_template_type(ref, substitutions)

    def _resolve_template_type(self, ref: TypeRefV2, substitutions: Mapping[str, ResolvedTypeV2]) -> ResolvedTypeV2:
        def nominal(name: str) -> str:
            substitution = substitutions.get(name)
            if substitution is not None:
                return substitution.type_id
            return self.types.resolve_source_type(name).type_id

        def generic(name: str, args: tuple[ResolvedTypeV2, ...]) -> str:
            return self.types.instantiate(name, args).runtime_type_id

        resolved = resolve_type_ref_v2(ref, nominal, generic)
        self.types.materialize_resolved_type(resolved)
        return resolved


def _const_type_refs(body: Mapping[str, Any], arities: Mapping[str, int]) -> tuple[TypeRefV2, ...]:
    result: list[TypeRefV2] = []
    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            if node.get("op") == "CONST" and isinstance(node.get("type"), str):
                result.append(parse_type_ref_v2(str(node["type"]), arities))
            for value in node.values(): visit(value)
        elif isinstance(node, list):
            for value in node: visit(value)
    visit(body)
    return tuple(result)


def _mentions_parameters(ref: TypeRefV2, parameters: set[str]) -> bool:
    return (ref.kind == "named" and ref.name in parameters) or any(_mentions_parameters(item, parameters) for item in ref.arguments)


def _canonical_type_ref(ref: TypeRefV2, positions: Mapping[str, int]) -> Any:
    if ref.kind == "named" and ref.name in positions:
        return {"kind": "parameter", "index": positions[ref.name]}
    return {
        "kind": ref.kind,
        "name": ref.name,
        "arguments": [_canonical_type_ref(item, positions) for item in ref.arguments],
        "const_arguments": list(ref.const_arguments),
    }


def _canonicalize_body_types(body: Mapping[str, Any], positions: Mapping[str, int], arities: Mapping[str, int]) -> Any:
    def visit(value: Any, key: str | None = None) -> Any:
        if key in _TYPE_FIELDS and isinstance(value, str):
            return _canonical_type_ref(parse_type_ref_v2(value, arities), positions)
        if isinstance(value, Mapping):
            return {k: visit(v, k) for k, v in sorted(value.items(), key=lambda item: item[0])}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value
    return visit(body)


def _instantiate_body_types(body: Mapping[str, Any], resolver) -> dict[str, Any]:
    def visit(value: Any, key: str | None = None) -> Any:
        if key in _TYPE_FIELDS and isinstance(value, str):
            return resolver(value).type_id
        if isinstance(value, Mapping):
            return {k: visit(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value
    result = visit(body)
    assert isinstance(result, dict)
    return canonical_expression_v4(result)


def _collect_instantiated_type_ids(body: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    def visit(value: Any, key: str | None = None) -> None:
        if key in _TYPE_FIELDS and isinstance(value, str):
            result.add(value)
        if isinstance(value, Mapping):
            for k, v in value.items(): visit(v, k)
        elif isinstance(value, list):
            for item in value: visit(item)
    visit(body)
    return result


def _dependency_hash(table: TypeTableV4, roots: Sequence[str]) -> str:
    closure: set[str] = set()
    stack = list(roots)
    while stack:
        type_id = stack.pop()
        if type_id in closure:
            continue
        descriptor = table.require(type_id, context="generic function dependency")
        closure.add(type_id)
        stack.extend(_descriptor_children(descriptor))
    payload = {
        "schema": "TEV_SCRIPT_V2_GENERIC_FUNCTION_TYPE_DEPENDENCY_V1",
        "types": [_descriptor_wire(table.require(type_id)) for type_id in sorted(closure)],
    }
    return _hash(payload)


def _descriptor_children(descriptor: TypeDescriptorV4) -> tuple[str, ...]:
    if descriptor.kind == "record": return tuple(type_id for _name, type_id in descriptor.fields)
    if descriptor.kind == "option": return (descriptor.argument,) if descriptor.argument is not None else ()
    if descriptor.kind == "result": return tuple(item for item in (descriptor.ok_type, descriptor.err_type) if item is not None)
    if descriptor.kind in {"list", "array", "set"}: return (descriptor.element_type,) if descriptor.element_type is not None else ()
    if descriptor.kind == "map": return tuple(item for item in (descriptor.key_type, descriptor.value_type) if item is not None)
    return ()


def _descriptor_wire(item: TypeDescriptorV4) -> dict[str, Any]:
    result: dict[str, Any] = {"type_id": item.type_id, "kind": item.kind}
    if item.kind == "record": result["fields"] = [{"name": name, "type": type_id} for name, type_id in item.fields]
    elif item.kind == "enum": result["variants"] = list(item.variants)
    elif item.kind == "option": result["argument"] = item.argument
    elif item.kind == "result": result.update({"ok_type": item.ok_type, "err_type": item.err_type})
    elif item.kind in {"list", "set"}: result.update({"element_type": item.element_type, "capacity": item.capacity, "order_policy": item.order_policy})
    elif item.kind == "array": result.update({"element_type": item.element_type, "length": item.length, "order_policy": item.order_policy})
    elif item.kind == "map": result.update({"key_type": item.key_type, "value_type": item.value_type, "capacity": item.capacity, "order_policy": item.order_policy})
    return result


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
