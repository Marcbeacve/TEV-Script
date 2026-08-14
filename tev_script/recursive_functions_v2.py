from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .generic_functions_v2 import (
    _TYPE_FIELDS,
    _canonical_type_ref,
    _canonicalize_body_types,
    _collect_instantiated_type_ids,
    _const_type_refs,
    _dependency_hash,
    _hash,
    _instantiate_body_types,
    _mentions_parameters,
)
from .generic_types_v2 import GenericRegistryV2
from .ir_v4_pure import (
    MAX_PURE_EVAL_STEPS_V4,
    PureBindingV4,
    TypedValueV4,
    canonical_expression_v4,
    evaluate_pure_v4,
    hash_type_table_v4,
    validate_pure_v4,
)
from .ir_v4_values import decode_v4_value, encode_v4_value
from .source_types_v2 import ResolvedTypeV2, TypeRefV2, parse_type_ref_v2, resolve_type_ref_v2

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OWNER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
MAX_RECURSION_DEPTH_V2 = 256
MAX_RECURSIVE_TEMPLATES_V2 = 4096
MAX_RECURSIVE_INSTANTIATIONS_V2 = 16384
_RESERVED_PREFIX = "__tev_"
_SELF_RESULT = "__tev_self_result"


@dataclass(frozen=True, slots=True)
class RecursiveParameterTemplateV2:
    name: str
    type_ref: TypeRefV2


@dataclass(frozen=True, slots=True)
class RecursivePureFunctionTemplateV2:
    owner_id: str
    name: str
    type_parameters: tuple[str, ...]
    parameters: tuple[RecursiveParameterTemplateV2, ...]
    return_type: TypeRefV2
    body: dict[str, Any]
    measure_parameter: str
    max_depth: int
    maximum_steps: int
    template_hash: str

    @property
    def qualified_name(self) -> str:
        return f"{self.owner_id}.{self.name}"


@dataclass(frozen=True, slots=True)
class RecursivePureFunctionInstantiationV2:
    template_hash: str
    instantiation_hash: str
    callable_id: str
    argument_type_ids: tuple[str, ...]
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    return_type_id: str
    body: dict[str, Any]
    measure_parameter: str
    measure_index: int
    max_depth: int
    local_static_step_upper_bound: int
    recursive_static_step_upper_bound: int
    maximum_steps: int
    dependency_roots: tuple[str, ...]
    dependency_hash: str


@dataclass(frozen=True, slots=True)
class RecursivePureCallReceiptV2:
    schema: str
    callable_id: str
    template_hash: str
    instantiation_hash: str
    recursion_contract_hash: str
    dependency_hash: str
    type_table_hash: str
    arguments_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    evaluation_steps: int
    recursion_calls: int
    maximum_observed_depth: int
    max_depth: int
    receipt_hash: str


@dataclass(slots=True)
class _RuntimeStats:
    steps: int = 0
    recursion_calls: int = 0
    maximum_depth: int = 0


class RecursivePureFunctionRegistryV2:
    """Single-self-call recursive pure functions with a decreasing Int measure.

    R1 intentionally excludes mutual recursion, multiple self-call sites, self
    recursion inside loops, and recursion in conditions/arguments. Every actual
    SELF_CALL must present a non-negative measure strictly smaller than the
    caller's measure, and a hard max_depth is part of callable identity.
    """

    def __init__(
        self,
        types: GenericRegistryV2,
        *,
        max_templates: int = MAX_RECURSIVE_TEMPLATES_V2,
        max_instantiations: int = MAX_RECURSIVE_INSTANTIATIONS_V2,
    ) -> None:
        if not 1 <= max_templates <= MAX_RECURSIVE_TEMPLATES_V2:
            _fail("TEVS_V2_RECURSION_BUDGET", "invalid recursive template budget")
        if not 1 <= max_instantiations <= MAX_RECURSIVE_INSTANTIATIONS_V2:
            _fail("TEVS_V2_RECURSION_BUDGET", "invalid recursive instantiation budget")
        self.types = types
        self.max_templates = max_templates
        self.max_instantiations = max_instantiations
        self._templates_by_qualified: dict[str, RecursivePureFunctionTemplateV2] = {}
        self._templates_by_local: dict[str, RecursivePureFunctionTemplateV2] = {}
        self._instantiations: dict[tuple[str, tuple[str, ...], str], RecursivePureFunctionInstantiationV2] = {}

    def register(
        self,
        owner_id: str,
        name: str,
        type_parameters: Sequence[str],
        parameters: Sequence[tuple[str, str]],
        return_type: str,
        body: Mapping[str, Any],
        *,
        measure_parameter: str,
        max_depth: int,
        maximum_steps: int = 1_000_000,
    ) -> RecursivePureFunctionTemplateV2:
        if len(self._templates_by_qualified) >= self.max_templates:
            _fail("TEVS_V2_RECURSION_BUDGET", "recursive template budget exhausted")
        if not isinstance(owner_id, str) or _OWNER.fullmatch(owner_id) is None:
            _fail("TEVS_V2_RECURSION_NAME", f"invalid owner {owner_id!r}")
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            _fail("TEVS_V2_RECURSION_NAME", f"invalid function name {name!r}")
        type_params = tuple(type_parameters)
        if len(type_params) > 16 or len(set(type_params)) != len(type_params) or any(_NAME.fullmatch(item) is None for item in type_params):
            _fail("TEVS_V2_RECURSION_TYPES", "recursive function allows 0..16 unique type parameters")
        if not 1 <= len(parameters) <= 64:
            _fail("TEVS_V2_RECURSION_PARAMETERS", "recursive function requires 1..64 value parameters")
        if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 1 <= max_depth <= MAX_RECURSION_DEPTH_V2:
            _fail("TEVS_V2_RECURSION_DEPTH", f"max_depth must be 1..{MAX_RECURSION_DEPTH_V2}")
        if isinstance(maximum_steps, bool) or not isinstance(maximum_steps, int) or not 1 <= maximum_steps <= MAX_PURE_EVAL_STEPS_V4:
            _fail("TEVS_V2_RECURSION_BUDGET", f"maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
        qualified = f"{owner_id}.{name}"
        if qualified in self._templates_by_qualified or name in self._templates_by_local:
            _fail("TEVS_V2_RECURSION_DUPLICATE", f"recursive function {qualified!r} or local alias {name!r} exists")

        generic_arities = self.types.generic_arities()
        parsed_parameters: list[RecursiveParameterTemplateV2] = []
        seen: set[str] = set()
        for parameter_name, type_text in parameters:
            if (
                not isinstance(parameter_name, str)
                or _NAME.fullmatch(parameter_name) is None
                or parameter_name.startswith(_RESERVED_PREFIX)
                or parameter_name in seen
            ):
                _fail("TEVS_V2_RECURSION_PARAMETERS", f"invalid/duplicate/reserved parameter {parameter_name!r}")
            seen.add(parameter_name)
            parsed_parameters.append(
                RecursiveParameterTemplateV2(parameter_name, parse_type_ref_v2(type_text, generic_arities))
            )
        if measure_parameter not in seen:
            _fail("TEVS_V2_RECURSION_MEASURE", f"measure parameter {measure_parameter!r} is not a function parameter")
        parsed_return = parse_type_ref_v2(return_type, generic_arities)
        canonical_body = canonical_expression_v4(body)
        analysis = _analyze_self_calls(canonical_body)
        if analysis["count"] != 1:
            _fail("TEVS_V2_RECURSION_CALL_SITE", f"R1 requires exactly one static SELF_CALL site, got {analysis['count']}")
        if analysis["inside_loop"]:
            _fail("TEVS_V2_RECURSION_LOOP", "SELF_CALL inside FOR_FOLD/WHILE_FOLD is forbidden in R1")
        if analysis["inside_condition"]:
            _fail("TEVS_V2_RECURSION_CONDITION", "SELF_CALL inside IF/WHILE condition is forbidden in R1")
        if analysis["nested_argument"]:
            _fail("TEVS_V2_RECURSION_ARGUMENT", "SELF_CALL arguments cannot themselves contain SELF_CALL")
        for const_type in _const_type_refs(canonical_body, generic_arities):
            if _mentions_parameters(const_type, set(type_params)):
                _fail(
                    "TEVS_V2_RECURSION_CONST_GENERIC",
                    "generic-dependent CONST is forbidden; use typed IR constructors",
                )

        positions = {parameter: index for index, parameter in enumerate(type_params)}
        measure_index = [item.name for item in parsed_parameters].index(measure_parameter)
        canonical = {
            "schema": "TEV_SCRIPT_V2_RECURSIVE_PURE_FUNCTION_TEMPLATE_V1",
            "owner_id": owner_id,
            "name": name,
            "type_parameter_count": len(type_params),
            "parameters": [
                {"name": item.name, "type": _canonical_type_ref(item.type_ref, positions)}
                for item in parsed_parameters
            ],
            "return_type": _canonical_type_ref(parsed_return, positions),
            "body": _canonicalize_body_types(canonical_body, positions, generic_arities),
            "recursion_contract": {
                "kind": "decreases_int",
                "measure_parameter_index": measure_index,
                "max_depth": max_depth,
                "single_static_self_call": True,
                "self_call_in_loops": False,
                "self_call_in_conditions": False,
            },
            "maximum_steps": maximum_steps,
        }
        template = RecursivePureFunctionTemplateV2(
            owner_id,
            name,
            type_params,
            tuple(parsed_parameters),
            parsed_return,
            canonical_body,
            measure_parameter,
            max_depth,
            maximum_steps,
            _hash(canonical),
        )
        self._templates_by_qualified[qualified] = template
        self._templates_by_local[name] = template
        return template

    def instantiate(
        self,
        template_or_name: RecursivePureFunctionTemplateV2 | str,
        arguments: Sequence[ResolvedTypeV2 | str] = (),
    ) -> RecursivePureFunctionInstantiationV2:
        template = self._template(template_or_name)
        resolved_args: list[ResolvedTypeV2] = []
        for raw in arguments:
            resolved = raw if isinstance(raw, ResolvedTypeV2) else self.types.resolve_source_type(raw) if isinstance(raw, str) else None
            if resolved is None:
                _fail("TEVS_V2_RECURSION_TYPES", "type argument must be resolved type or source type text")
            self.types.materialize_resolved_type(resolved)
            resolved_args.append(resolved)
        args = tuple(resolved_args)
        if len(args) != len(template.type_parameters):
            _fail("TEVS_V2_RECURSION_ARITY", f"{template.qualified_name} expects {len(template.type_parameters)} type arguments, got {len(args)}")
        substitutions = dict(zip(template.type_parameters, args, strict=True))
        parameter_types = tuple(self._resolve_template_type(item.type_ref, substitutions) for item in template.parameters)
        return_type = self._resolve_template_type(template.return_type, substitutions)
        for resolved in (*parameter_types, return_type):
            self.types.materialize_resolved_type(resolved)
        measure_index = [item.name for item in template.parameters].index(template.measure_parameter)
        if parameter_types[measure_index].type_id != "Int":
            _fail(
                "TEVS_V2_RECURSION_MEASURE",
                f"decreases_int measure parameter must instantiate to Int, got {parameter_types[measure_index].type_id}",
            )

        body = _instantiate_body_types(
            template.body,
            lambda type_text: self._resolve_type_text(type_text, substitutions),
        )
        self_call = _single_self_call(body)
        if len(self_call["arguments"]) != len(parameter_types):
            _fail(
                "TEVS_V2_RECURSION_ARITY",
                f"SELF_CALL expects {len(parameter_types)} arguments, got {len(self_call['arguments'])}",
            )
        parameter_environment = {
            parameter.name: resolved.type_id
            for parameter, resolved in zip(template.parameters, parameter_types, strict=True)
        }
        argument_validations = []
        for index, (argument_expr, expected) in enumerate(zip(self_call["arguments"], parameter_types, strict=True)):
            validation = validate_pure_v4(argument_expr, self.types.table, parameter_environment)
            if validation.result_type != expected.type_id:
                _fail(
                    "TEVS_V2_RECURSION_TYPE",
                    f"SELF_CALL argument {index} expected {expected.type_id}, got {validation.result_type}",
                )
            argument_validations.append(validation)

        placeholder_body = _replace_self_call_with_placeholder(body, return_type.type_id)
        validation_environment = dict(parameter_environment)
        validation_environment[_SELF_RESULT] = return_type.type_id
        local_validation = validate_pure_v4(placeholder_body, self.types.table, validation_environment)
        if local_validation.result_type != return_type.type_id:
            _fail(
                "TEVS_V2_RECURSION_RETURN",
                f"recursive body returns {local_validation.result_type}, declared {return_type.type_id}",
            )
        argument_bound = sum(item.static_step_upper_bound for item in argument_validations)
        frame_bound = 4 * (local_validation.static_step_upper_bound + argument_bound + 4)
        recursive_bound = frame_bound * (template.max_depth + 1)
        if recursive_bound > MAX_PURE_EVAL_STEPS_V4:
            _fail(
                "TEVS_V2_RECURSION_STATIC_BUDGET",
                f"recursive static upper bound {recursive_bound} exceeds global {MAX_PURE_EVAL_STEPS_V4}",
            )
        if recursive_bound > template.maximum_steps:
            _fail(
                "TEVS_V2_RECURSION_STATIC_BUDGET",
                f"recursive static upper bound {recursive_bound} exceeds function maximum_steps {template.maximum_steps}",
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
            _fail("TEVS_V2_RECURSION_BUDGET", "recursive instantiation budget exhausted")

        payload = {
            "schema": "TEV_SCRIPT_V2_RECURSIVE_PURE_FUNCTION_INSTANTIATION_V1",
            "template_hash": template.template_hash,
            "argument_type_ids": [item.type_id for item in args],
            "parameter_type_ids": [item.type_id for item in parameter_types],
            "return_type_id": return_type.type_id,
            "dependency_hash": dependency_hash,
            "recursion_contract": {
                "kind": "decreases_int",
                "measure_parameter_index": measure_index,
                "max_depth": template.max_depth,
            },
            "local_static_step_upper_bound": local_validation.static_step_upper_bound,
            "recursive_static_step_upper_bound": recursive_bound,
            "maximum_steps": template.maximum_steps,
        }
        instantiation_hash = _hash(payload)
        result = RecursivePureFunctionInstantiationV2(
            template.template_hash,
            instantiation_hash,
            f"{template.owner_id}.{template.name}__rec_{instantiation_hash}",
            tuple(item.type_id for item in args),
            tuple(item.name for item in template.parameters),
            tuple(item.type_id for item in parameter_types),
            return_type.type_id,
            body,
            template.measure_parameter,
            measure_index,
            template.max_depth,
            local_validation.static_step_upper_bound,
            recursive_bound,
            template.maximum_steps,
            dependency_roots,
            dependency_hash,
        )
        self._instantiations[cache_key] = result
        return result

    def call(
        self,
        instantiation: RecursivePureFunctionInstantiationV2,
        arguments: Sequence[Any],
    ) -> RecursivePureCallReceiptV2:
        if not isinstance(instantiation, RecursivePureFunctionInstantiationV2):
            _fail("TEVS_V2_RECURSION_CALL", "call requires a recursive pure instantiation")
        if len(arguments) != len(instantiation.parameter_names):
            _fail("TEVS_V2_RECURSION_CALL", f"expected {len(instantiation.parameter_names)} arguments, got {len(arguments)}")
        current_dependency_hash = _dependency_hash(self.types.table, instantiation.dependency_roots)
        if current_dependency_hash != instantiation.dependency_hash:
            _fail("TEVS_V2_RECURSION_STALE", "recursive function type dependency closure changed")

        normalized = []
        argument_wire = []
        for name, type_id, raw in zip(
            instantiation.parameter_names,
            instantiation.parameter_type_ids,
            arguments,
            strict=True,
        ):
            encoded = encode_v4_value(type_id, raw, self.types.table, context=f"recursive argument {name}")
            value = decode_v4_value(type_id, encoded, self.types.table, context=f"recursive argument {name}")
            normalized.append(value)
            argument_wire.append({"name": name, "type": type_id, "value": encoded})
        initial_measure = normalized[instantiation.measure_index]
        _require_measure(initial_measure, context="initial recursion measure")
        arguments_hash = _hash(
            {
                "schema": "TEV_SCRIPT_V2_RECURSIVE_ARGUMENTS_V1",
                "arguments": argument_wire,
            }
        )
        stats = _RuntimeStats()
        result = self._invoke(instantiation, tuple(normalized), depth=0, parent_measure=None, stats=stats)
        if stats.steps > instantiation.maximum_steps:
            _fail("TEVS_V2_RECURSION_BUDGET", "runtime recursive step budget exceeded")
        encoded = encode_v4_value(instantiation.return_type_id, result.value, self.types.table, context="recursive result")
        result_hash = _hash({"type": instantiation.return_type_id, "value": encoded})
        recursion_contract = {
            "kind": "decreases_int",
            "measure_parameter_index": instantiation.measure_index,
            "max_depth": instantiation.max_depth,
            "single_static_self_call": True,
        }
        recursion_contract_hash = _hash(recursion_contract)
        payload = {
            "schema": "TEV_SCRIPT_V2_RECURSIVE_PURE_CALL_RECEIPT_V1",
            "callable_id": instantiation.callable_id,
            "template_hash": instantiation.template_hash,
            "instantiation_hash": instantiation.instantiation_hash,
            "recursion_contract_hash": recursion_contract_hash,
            "dependency_hash": instantiation.dependency_hash,
            "type_table_hash": hash_type_table_v4(self.types.table),
            "arguments_hash": arguments_hash,
            "result_type": instantiation.return_type_id,
            "result_encoded": encoded,
            "result_hash": result_hash,
            "evaluation_steps": stats.steps,
            "recursion_calls": stats.recursion_calls,
            "maximum_observed_depth": stats.maximum_depth,
            "max_depth": instantiation.max_depth,
        }
        return RecursivePureCallReceiptV2(
            payload["schema"],
            instantiation.callable_id,
            instantiation.template_hash,
            instantiation.instantiation_hash,
            recursion_contract_hash,
            instantiation.dependency_hash,
            payload["type_table_hash"],
            arguments_hash,
            instantiation.return_type_id,
            encoded,
            result_hash,
            stats.steps,
            stats.recursion_calls,
            stats.maximum_depth,
            instantiation.max_depth,
            _hash(payload),
        )

    def call_recursive(
        self,
        name: str,
        type_arguments: Sequence[ResolvedTypeV2 | str],
        arguments: Sequence[Any],
    ) -> RecursivePureCallReceiptV2:
        return self.call(self.instantiate(name, type_arguments), arguments)

    def _invoke(
        self,
        instantiation: RecursivePureFunctionInstantiationV2,
        arguments: tuple[Any, ...],
        *,
        depth: int,
        parent_measure: int | None,
        stats: _RuntimeStats,
    ) -> TypedValueV4:
        stats.maximum_depth = max(stats.maximum_depth, depth)
        measure = arguments[instantiation.measure_index]
        _require_measure(measure, context="recursive frame measure")
        if parent_measure is not None and not measure < parent_measure:
            _fail(
                "TEVS_V2_RECURSION_MEASURE_NOT_DECREASING",
                f"SELF_CALL measure must satisfy 0 <= next < current; got next={measure}, current={parent_measure}",
            )
        environment = {
            name: TypedValueV4(type_id, value)
            for name, type_id, value in zip(
                instantiation.parameter_names,
                instantiation.parameter_type_ids,
                arguments,
                strict=True,
            )
        }
        result = self._evaluate_recursive_node(
            instantiation.body,
            instantiation,
            environment,
            current_measure=measure,
            depth=depth,
            stats=stats,
        )
        if result.type_id != instantiation.return_type_id:
            _fail("TEVS_V2_RECURSION_RETURN", "runtime recursive result type diverged from instantiation")
        return result

    def _evaluate_recursive_node(
        self,
        node: Mapping[str, Any],
        instantiation: RecursivePureFunctionInstantiationV2,
        environment: Mapping[str, TypedValueV4],
        *,
        current_measure: int,
        depth: int,
        stats: _RuntimeStats,
    ) -> TypedValueV4:
        if not _contains_self_call(node):
            return self._pure_eval(node, environment, instantiation, stats)
        op = str(node.get("op"))
        if op == "SELF_CALL":
            if depth >= instantiation.max_depth:
                _fail(
                    "TEVS_V2_RECURSION_DEPTH_EXHAUSTED",
                    f"SELF_CALL would exceed max_depth={instantiation.max_depth}",
                )
            raw_arguments = node["arguments"]
            next_values = []
            for index, (argument_expr, expected_type) in enumerate(
                zip(raw_arguments, instantiation.parameter_type_ids, strict=True)
            ):
                if _contains_self_call(argument_expr):
                    _fail("TEVS_V2_RECURSION_ARGUMENT", "nested SELF_CALL in recursive arguments is forbidden")
                value = self._pure_eval(argument_expr, environment, instantiation, stats)
                if value.type_id != expected_type:
                    _fail(
                        "TEVS_V2_RECURSION_TYPE",
                        f"SELF_CALL argument {index} expected {expected_type}, got {value.type_id}",
                    )
                next_values.append(value.value)
            next_measure = next_values[instantiation.measure_index]
            _require_measure(next_measure, context="SELF_CALL measure")
            if not next_measure < current_measure:
                _fail(
                    "TEVS_V2_RECURSION_MEASURE_NOT_DECREASING",
                    f"SELF_CALL measure must satisfy 0 <= next < current; got next={next_measure}, current={current_measure}",
                )
            stats.steps += 1
            stats.recursion_calls += 1
            self._check_runtime_budget(instantiation, stats)
            return self._invoke(
                instantiation,
                tuple(next_values),
                depth=depth + 1,
                parent_measure=current_measure,
                stats=stats,
            )
        if op == "IF":
            if _contains_self_call(node["condition"]):
                _fail("TEVS_V2_RECURSION_CONDITION", "SELF_CALL in IF condition is forbidden")
            condition = self._pure_eval(node["condition"], environment, instantiation, stats)
            if condition.type_id != "Bool":
                _fail("TEVS_V2_RECURSION_TYPE", "recursive IF condition must be Bool")
            branch = node["then"] if condition.value else node["else"]
            return self._evaluate_recursive_node(
                branch,
                instantiation,
                environment,
                current_measure=current_measure,
                depth=depth,
                stats=stats,
            )
        if op == "LET":
            value = self._evaluate_recursive_node(
                node["value"],
                instantiation,
                environment,
                current_measure=current_measure,
                depth=depth,
                stats=stats,
            )
            declared = str(node["type"])
            if value.type_id != declared:
                _fail("TEVS_V2_RECURSION_TYPE", f"recursive LET expected {declared}, got {value.type_id}")
            nested = dict(environment)
            nested[str(node["name"])] = value
            result = self._evaluate_recursive_node(
                node["body"],
                instantiation,
                nested,
                current_measure=current_measure,
                depth=depth,
                stats=stats,
            )
            if result.type_id != str(node["result_type"]):
                _fail("TEVS_V2_RECURSION_TYPE", "recursive LET body result type mismatch")
            return result
        if op in {"FOR_FOLD", "WHILE_FOLD"}:
            _fail("TEVS_V2_RECURSION_LOOP", "SELF_CALL inside loop is forbidden in R1")

        materialized = self._materialize_self_calls(
            node,
            instantiation,
            environment,
            current_measure=current_measure,
            depth=depth,
            stats=stats,
        )
        return self._pure_eval(materialized, environment, instantiation, stats)

    def _materialize_self_calls(
        self,
        value: Any,
        instantiation: RecursivePureFunctionInstantiationV2,
        environment: Mapping[str, TypedValueV4],
        *,
        current_measure: int,
        depth: int,
        stats: _RuntimeStats,
    ) -> Any:
        if isinstance(value, Mapping) and value.get("op") == "SELF_CALL":
            result = self._evaluate_recursive_node(
                value,
                instantiation,
                environment,
                current_measure=current_measure,
                depth=depth,
                stats=stats,
            )
            return _const_node(result, self.types.table)
        if isinstance(value, Mapping) and value.get("op") in {"IF", "LET"} and _contains_self_call(value):
            result = self._evaluate_recursive_node(
                value,
                instantiation,
                environment,
                current_measure=current_measure,
                depth=depth,
                stats=stats,
            )
            return _const_node(result, self.types.table)
        if isinstance(value, Mapping):
            return {
                key: self._materialize_self_calls(
                    child,
                    instantiation,
                    environment,
                    current_measure=current_measure,
                    depth=depth,
                    stats=stats,
                )
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [
                self._materialize_self_calls(
                    child,
                    instantiation,
                    environment,
                    current_measure=current_measure,
                    depth=depth,
                    stats=stats,
                )
                for child in value
            ]
        return value

    def _pure_eval(
        self,
        node: Mapping[str, Any],
        environment: Mapping[str, TypedValueV4],
        instantiation: RecursivePureFunctionInstantiationV2,
        stats: _RuntimeStats,
    ) -> TypedValueV4:
        if _contains_self_call(node):
            _fail("TEVS_V2_RECURSION_INTERNAL", "unresolved SELF_CALL reached pure evaluator")
        bindings = [
            PureBindingV4(name, value.type_id, value.value)
            for name, value in sorted(environment.items(), key=lambda item: item[0])
        ]
        validation = validate_pure_v4(
            node,
            self.types.table,
            {name: value.type_id for name, value in environment.items()},
        )
        receipt = evaluate_pure_v4(
            node,
            self.types.table,
            bindings,
            maximum_steps=max(validation.static_step_upper_bound, 1),
        )
        stats.steps += receipt.evaluation_steps
        self._check_runtime_budget(instantiation, stats)
        return TypedValueV4(
            receipt.result_type,
            decode_v4_value(
                receipt.result_type,
                receipt.result_encoded,
                self.types.table,
                context="recursive pure fragment",
            ),
        )

    @staticmethod
    def _check_runtime_budget(
        instantiation: RecursivePureFunctionInstantiationV2,
        stats: _RuntimeStats,
    ) -> None:
        if stats.steps > instantiation.maximum_steps:
            _fail(
                "TEVS_V2_RECURSION_BUDGET",
                f"runtime recursive steps {stats.steps} exceed maximum_steps {instantiation.maximum_steps}",
            )

    def _resolve_type_text(
        self,
        text: str,
        substitutions: Mapping[str, ResolvedTypeV2],
    ) -> ResolvedTypeV2:
        ref = parse_type_ref_v2(text, self.types.generic_arities())
        return self._resolve_template_type(ref, substitutions)

    def _resolve_template_type(
        self,
        ref: TypeRefV2,
        substitutions: Mapping[str, ResolvedTypeV2],
    ) -> ResolvedTypeV2:
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

    def _template(
        self,
        template_or_name: RecursivePureFunctionTemplateV2 | str,
    ) -> RecursivePureFunctionTemplateV2:
        if isinstance(template_or_name, RecursivePureFunctionTemplateV2):
            registered = self._templates_by_qualified.get(template_or_name.qualified_name)
            if registered != template_or_name:
                _fail("TEVS_V2_RECURSION_TEMPLATE", "recursive template is not registered here")
            return template_or_name
        if not isinstance(template_or_name, str):
            _fail("TEVS_V2_RECURSION_TEMPLATE", "recursive template reference must be template or name")
        result = self._templates_by_qualified.get(template_or_name) or self._templates_by_local.get(template_or_name)
        if result is None:
            _fail("TEVS_V2_RECURSION_TEMPLATE", f"unknown recursive function {template_or_name!r}")
        return result


def _analyze_self_calls(body: Mapping[str, Any]) -> dict[str, Any]:
    result = {"count": 0, "inside_loop": False, "inside_condition": False, "nested_argument": False}

    def visit(value: Any, *, in_loop: bool = False, in_condition: bool = False, in_self_argument: bool = False) -> None:
        if isinstance(value, Mapping):
            op = value.get("op")
            if op == "SELF_CALL":
                result["count"] += 1
                result["inside_loop"] = result["inside_loop"] or in_loop
                result["inside_condition"] = result["inside_condition"] or in_condition
                result["nested_argument"] = result["nested_argument"] or in_self_argument
                for argument in value.get("arguments", []):
                    visit(argument, in_loop=in_loop, in_condition=False, in_self_argument=True)
                return
            if op in {"FOR_FOLD", "WHILE_FOLD"}:
                for child in value.values():
                    visit(child, in_loop=True, in_condition=False, in_self_argument=in_self_argument)
                return
            if op == "IF":
                visit(value.get("condition"), in_loop=in_loop, in_condition=True, in_self_argument=in_self_argument)
                visit(value.get("then"), in_loop=in_loop, in_condition=False, in_self_argument=in_self_argument)
                visit(value.get("else"), in_loop=in_loop, in_condition=False, in_self_argument=in_self_argument)
                return
            for child in value.values():
                visit(child, in_loop=in_loop, in_condition=in_condition, in_self_argument=in_self_argument)
        elif isinstance(value, list):
            for child in value:
                visit(child, in_loop=in_loop, in_condition=in_condition, in_self_argument=in_self_argument)

    visit(body)
    return result


def _single_self_call(body: Mapping[str, Any]) -> dict[str, Any]:
    found: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("op") == "SELF_CALL":
                found.append(dict(value))
                return
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(body)
    if len(found) != 1:
        _fail("TEVS_V2_RECURSION_CALL_SITE", f"expected exactly one SELF_CALL, found {len(found)}")
    return found[0]


def _replace_self_call_with_placeholder(body: Mapping[str, Any], return_type: str) -> dict[str, Any]:
    def visit(value: Any) -> Any:
        if isinstance(value, Mapping):
            if value.get("op") == "SELF_CALL":
                return {"op": "PARAM", "name": _SELF_RESULT, "type": return_type}
            return {key: visit(child) for key, child in value.items()}
        if isinstance(value, list):
            return [visit(child) for child in value]
        return value

    result = visit(body)
    assert isinstance(result, dict)
    return canonical_expression_v4(result)


def _contains_self_call(value: Any) -> bool:
    if isinstance(value, Mapping):
        return value.get("op") == "SELF_CALL" or any(_contains_self_call(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_self_call(child) for child in value)
    return False


def _const_node(value: TypedValueV4, table) -> dict[str, Any]:
    return {
        "op": "CONST",
        "type": value.type_id,
        "value": encode_v4_value(value.type_id, value.value, table, context="recursive materialization"),
    }


def _require_measure(value: Any, *, context: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_V2_RECURSION_MEASURE", f"{context} must be a non-negative Int, got {value!r}")


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
