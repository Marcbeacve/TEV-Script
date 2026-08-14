from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import re
from typing import Any, Callable, Mapping, Sequence

from .diagnostics import TevScriptError
from .generic_functions_v2 import (
    GenericPureFunctionInstantiationV2,
    GenericPureFunctionRegistryV2,
    GenericPureFunctionTemplateV2,
)
from .generic_types_v2 import GenericRecordTemplateV2, GenericRegistryV2
from .ir_v4_pure import MAX_PURE_EVAL_STEPS_V4, MAX_PURE_TASKS_V4, PRIORITY_SELECT_POLICY_V4, TASK_CANCELLATION_POLICY_V4, TASK_JOIN_POLICY_V4
from .recursive_functions_v2 import (
    RecursivePureFunctionInstantiationV2,
    RecursivePureFunctionRegistryV2,
    RecursivePureFunctionTemplateV2,
)
from .source_collection_literals_v2 import parse_contextual_literal_v2
from .source_types_v2 import TypeRefV2, associated_type_parts_v2, parse_type_ref_v2

LANGUAGE_VERSION_V2 = "2.0.0"
MAX_SOURCE_BYTES_V2 = 1_000_000
MAX_SOURCE_DECLARATIONS_V2 = 4096
MAX_SOURCE_EXPRESSION_NESTING_V2 = 128
MAX_PURE_INLINE_DEPTH_V2 = 64
_INTERNAL_ENTRY_EXPRESSION_FUNCTION_V2 = "__tev_entry_expression_v2"

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_QUALIFIED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_NUMBER = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_RESERVED_SOURCE_CALL_NAMES = frozenset({
    "self",
    "len",
    "Some",
    "Ok",
    "Err",
    "list.push",
    "list.get",
    "array.get",
    "array.set",
    "set.add",
    "set.contains",
    "map.put",
    "map.get",
})


@dataclass(frozen=True, slots=True)
class SourceExprV2:
    kind: str
    value: Any = None
    children: tuple["SourceExprV2", ...] = ()


@dataclass(frozen=True, slots=True)
class LoweredExpressionV2:
    type_text: str
    ir: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GenericRecordSourceV2:
    name: str
    type_parameters: tuple[str, ...]
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class GenericFunctionSourceV2:
    name: str
    type_parameters: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...]
    return_type: str
    body: SourceExprV2
    constraints: tuple[tuple[str, str], ...] = ()
    associated_constraints: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProtocolMethodSourceV2:
    name: str
    parameters: tuple[tuple[str, str], ...]
    return_type: str


@dataclass(frozen=True, slots=True)
class ProtocolSourceV2:
    name: str
    methods: tuple[ProtocolMethodSourceV2, ...]
    associated_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AssociatedTypeBindingSourceV2:
    receiver_type: str
    protocols: tuple[str, ...]
    name: str
    type_text: str
    implementation_group: str


@dataclass(frozen=True, slots=True)
class MethodSourceV2:
    receiver_type: str
    name: str
    parameters: tuple[tuple[str, str], ...]
    return_type: str
    body: SourceExprV2
    protocols: tuple[str, ...] = ()
    implementation_group: str = ""


@dataclass(frozen=True, slots=True)
class GenericProtocolImplSourceV2:
    type_parameters: tuple[str, ...]
    receiver_type: str
    protocol_name: str
    methods: tuple[MethodSourceV2, ...]
    associated_types: tuple[tuple[str, str], ...] = ()
    implementation_group: str = ""
    constraints: tuple[tuple[str, str], ...] = ()
    associated_constraints: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class GenericProtocolImplTemplateV2:
    type_parameters: tuple[str, ...]
    receiver_pattern: str
    record_name: str
    protocol_name: str
    protocol_hash: str
    template_hash: str
    prerequisite_constraints: tuple[tuple[int, str], ...] = ()
    prerequisite_associated_constraints: tuple[tuple[int, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class GenericProtocolImplSpecializationV2:
    template_hash: str
    protocol_name: str
    receiver_source_type: str
    receiver_runtime_type: str
    type_argument_ids: tuple[str, ...]
    method_template_hashes: tuple[tuple[str, str], ...]
    associated_types: tuple[tuple[str, str, str], ...]
    specialization_hash: str
    witness_hash: str
    prerequisite_witnesses: tuple[tuple[int, str, str], ...] = ()
    prerequisite_associated_constraints: tuple[tuple[int, str, str], ...] = ()
    receiver_associated_projections: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProtocolWitnessV2:
    protocol_name: str
    protocol_hash: str
    receiver_source_type: str
    receiver_runtime_type: str
    method_template_hashes: tuple[tuple[str, str], ...]
    witness_hash: str
    method_constraint_specializations: tuple[tuple[str, tuple[str, ...]], ...] = ()
    associated_types: tuple[tuple[str, str, str], ...] = ()
    receiver_associated_projections: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ConstrainedFunctionSpecializationV2:
    function_name: str
    template_hash: str
    type_argument_ids: tuple[str, ...]
    constraint_bindings: tuple[tuple[str, str, str], ...]
    specialization_hash: str
    associated_type_bindings: tuple[tuple[str, str, str], ...] = ()
    associated_constraint_bindings: tuple[tuple[str, str, str], ...] = ()
    protocol_intersections: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RecursiveFunctionSourceV2:
    name: str
    type_parameters: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...]
    return_type: str
    body: SourceExprV2
    measure_parameter: str
    max_depth: int
    maximum_steps: int


@dataclass(frozen=True, slots=True)
class EntrySourceV2:
    name: str
    declared_type: str
    function_name: str
    type_arguments: tuple[str, ...]
    argument_texts: tuple[str, ...]
    expression: SourceExprV2 | None = None


@dataclass(frozen=True, slots=True)
class SourceProgramV2:
    program_id: str
    language_version: str
    records: tuple[GenericRecordSourceV2, ...]
    functions: tuple[GenericFunctionSourceV2, ...]
    recursive_functions: tuple[RecursiveFunctionSourceV2, ...]
    entry: EntrySourceV2
    methods: tuple[MethodSourceV2, ...] = ()
    protocols: tuple[ProtocolSourceV2, ...] = ()
    associated_type_bindings: tuple[AssociatedTypeBindingSourceV2, ...] = ()
    generic_protocol_impls: tuple[GenericProtocolImplSourceV2, ...] = ()


@dataclass(frozen=True, slots=True)
class CompiledEntryV2:
    name: str
    declared_source_type: str
    declared_runtime_type: str
    function_name: str
    function_kind: str
    function_template_hash: str
    instantiation: GenericPureFunctionInstantiationV2 | RecursivePureFunctionInstantiationV2
    type_argument_ids: tuple[str, ...]
    arguments: tuple[Any, ...]
    argument_encodings: tuple[Any, ...]
    entry_hash: str


@dataclass(frozen=True, slots=True)
class CompiledProgramV2:
    schema: str
    program_id: str
    language_version: str
    semantic_hash: str
    record_template_hashes: tuple[tuple[str, str], ...]
    function_template_hashes: tuple[tuple[str, str], ...]
    recursive_function_template_hashes: tuple[tuple[str, str], ...]
    type_descriptors: tuple[dict[str, Any], ...]
    entry: CompiledEntryV2
    types: GenericRegistryV2
    functions: GenericPureFunctionRegistryV2
    recursive_functions: RecursivePureFunctionRegistryV2
    protocol_hashes: tuple[tuple[str, str], ...] = ()
    protocol_witnesses: tuple[ProtocolWitnessV2, ...] = ()
    constrained_function_template_hashes: tuple[tuple[str, str], ...] = ()
    constrained_function_specializations: tuple[ConstrainedFunctionSpecializationV2, ...] = ()
    generic_protocol_impl_templates: tuple[GenericProtocolImplTemplateV2, ...] = ()
    generic_protocol_impl_specializations: tuple[GenericProtocolImplSpecializationV2, ...] = ()


@dataclass(frozen=True, slots=True)
class ProgramRunReceiptV2:
    schema: str
    program_semantic_hash: str
    entry_hash: str
    entry_name: str
    callable_id: str
    call_receipt_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    value: Any
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _Lowered:
    type_text: str
    ir: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ProtocolWitnessResolutionV2:
    witness: ProtocolWitnessV2
    method_dispatch: tuple[tuple[tuple[str, str], str], ...] = ()
    function_sources: tuple[tuple[str, GenericFunctionSourceV2], ...] = ()


@dataclass(frozen=True, slots=True)
class _ValidatedProtocolWitnessBindingV2:
    witness: ProtocolWitnessV2
    protocol_hash: str
    receiver_source_type: str
    receiver_runtime_type: str
    associated_source_types: tuple[tuple[str, str], ...]
    associated_type_ids: tuple[tuple[str, str], ...]

    def associated_source_type(self, name: str) -> str | None:
        return dict(self.associated_source_types).get(name)

    def associated_type_id(self, name: str) -> str | None:
        return dict(self.associated_type_ids).get(name)


@dataclass(frozen=True, slots=True)
class _AssociatedConstraintSpecificationV2:
    target_type_parameter: str
    associated_name: str
    required_source_type: str
    required_type_ref: TypeRefV2
    type_parameters: tuple[str, ...]
    dependent: bool

    @classmethod
    def build(
        cls,
        *,
        function_name: str,
        target_type_parameter: str,
        associated_name: str,
        required_type: str,
        type_parameters: Sequence[str],
        protocols_by_parameter: Mapping[str, tuple[str, ...]],
        protocols: Mapping[str, ProtocolSourceV2],
        generic_arities: Mapping[str, int],
        diagnostic_code: str = "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_TYPE",
    ) -> "_AssociatedConstraintSpecificationV2":
        ref = parse_type_ref_v2(required_type, generic_arities)
        parameters = tuple(type_parameters)
        parameter_set = frozenset(parameters)
        dependent = False
        stack = [ref]
        while stack:
            current = stack.pop()
            if current.kind == "associated":
                root, member = associated_type_parts_v2(current)
                if root not in parameter_set:
                    _fail(
                        diagnostic_code,
                        f"function {function_name!r} refinement {target_type_parameter}::{associated_name} "
                        f"depends on out-of-scope projection {root}::{member}",
                    )
                protocol_names = protocols_by_parameter.get(root, ())
                if not protocol_names:
                    _fail(
                        diagnostic_code,
                        f"function {function_name!r} refinement {target_type_parameter}::{associated_name} "
                        f"projects {root}::{member} without constraining {root}",
                    )
                _associated_owner_protocol_v2(
                    function_name=function_name,
                    type_parameter=root,
                    associated_name=member,
                    protocol_names=protocol_names,
                    protocols=protocols,
                    diagnostic_code=diagnostic_code,
                )
                dependent = True
            elif current.kind == "named" and current.name in parameter_set:
                dependent = True
            stack.extend(current.arguments)
        return cls(
            target_type_parameter,
            associated_name,
            _render_type(ref),
            ref,
            parameters,
            dependent,
        )

    @classmethod
    def from_validated_source(
        cls,
        *,
        target_type_parameter: str,
        associated_name: str,
        required_type: str,
        type_parameters: Sequence[str],
        generic_arities: Mapping[str, int],
    ) -> "_AssociatedConstraintSpecificationV2":
        ref = parse_type_ref_v2(required_type, generic_arities)
        parameters = tuple(type_parameters)
        parameter_set = frozenset(parameters)
        dependent = False
        stack = [ref]
        while stack:
            current = stack.pop()
            if current.kind == "associated" or (current.kind == "named" and current.name in parameter_set):
                dependent = True
            stack.extend(current.arguments)
        return cls(
            target_type_parameter,
            associated_name,
            _render_type(ref),
            ref,
            parameters,
            dependent,
        )

    def validate_static_types(
        self,
        *,
        types: GenericRegistryV2,
        diagnostic_code: str,
        message_prefix: str,
    ) -> None:
        if not self.dependent:
            try:
                resolved = types.resolve_source_type(self.required_source_type)
                types.materialize_resolved_type(resolved)
            except TevScriptError as error:
                _fail(diagnostic_code, f"{message_prefix} {self.required_source_type!r}: {error.diagnostic.message}")
            return
        parameter_set = frozenset(self.type_parameters)
        stack = [self.required_type_ref]
        while stack:
            current = stack.pop()
            if current.kind == "named" and current.name not in parameter_set:
                try:
                    resolved = types.resolve_source_type(current.name)
                    types.materialize_resolved_type(resolved)
                except TevScriptError as error:
                    _fail(diagnostic_code, f"{message_prefix} {self.required_source_type!r}: {error.diagnostic.message}")
            stack.extend(current.arguments)

    def resolve(
        self,
        *,
        type_substitutions: Mapping[str, TypeRefV2],
        associated_substitutions: Mapping[tuple[str, str], TypeRefV2],
        types: GenericRegistryV2,
        diagnostic_code: str,
        message_prefix: str,
    ) -> tuple[str, str]:
        specialized = _substitute_type(
            self.required_type_ref,
            type_substitutions,
            associated_substitutions,
        )
        parameter_set = frozenset(self.type_parameters)
        stack = [specialized]
        while stack:
            current = stack.pop()
            if current.kind == "associated" or (current.kind == "named" and current.name in parameter_set):
                _fail(
                    diagnostic_code,
                    f"{message_prefix} leaves unresolved dependent type {_render_type(specialized)!r}",
                )
            stack.extend(current.arguments)
        source_type = _render_type(specialized)
        try:
            resolved = types.resolve_source_type(source_type)
            types.materialize_resolved_type(resolved)
        except TevScriptError as error:
            _fail(diagnostic_code, f"{message_prefix} {source_type!r}: {error.diagnostic.message}")
        return source_type, resolved.type_id


class _ProtocolWitnessBindingResolverV2:
    """Validate a witness once, then expose only closed binding data.

    Lookup/materialization policy stays with the caller. This resolver owns the
    repeated security invariants: active protocol contract, concrete receiver
    identity, and canonical associated bindings.
    """

    @staticmethod
    def validate(
        *,
        witness: ProtocolWitnessV2,
        protocol_name: str,
        receiver_source_type: str,
        protocol_hashes: Mapping[str, str],
        types: GenericRegistryV2,
        diagnostic_code: str,
        contract_mismatch_message: str,
        runtime_mismatch_message: str,
    ) -> _ValidatedProtocolWitnessBindingV2:
        protocol_hash = protocol_hashes.get(protocol_name)
        if protocol_hash is None or witness.protocol_hash != protocol_hash:
            _fail(diagnostic_code, contract_mismatch_message)
        resolved = types.resolve_source_type(receiver_source_type)
        types.materialize_resolved_type(resolved)
        if witness.receiver_runtime_type != resolved.type_id:
            _fail(diagnostic_code, runtime_mismatch_message)
        associated_source_types = tuple(
            sorted((name, source_type) for name, source_type, _type_id in witness.associated_types)
        )
        associated_type_ids = tuple(
            sorted((name, type_id) for name, _source_type, type_id in witness.associated_types)
        )
        if len({name for name, _source_type in associated_source_types}) != len(associated_source_types):
            _fail(diagnostic_code, f"witness for {receiver_source_type} and {protocol_name!r} repeats an associated type")
        return _ValidatedProtocolWitnessBindingV2(
            witness,
            protocol_hash,
            receiver_source_type,
            resolved.type_id,
            associated_source_types,
            associated_type_ids,
        )



def tokenize_source_v2(source: str) -> tuple[Any, ...]:
    if not isinstance(source, str):
        _fail("TEVS_V2_PROGRAM_SOURCE", "source must be text")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES_V2:
        _fail("TEVS_V2_PROGRAM_SOURCE", f"source exceeds {MAX_SOURCE_BYTES_V2} bytes")
    return _tokenize(source)


def parse_expression_v2(source: str) -> SourceExprV2:
    parser = _ProgramParser(source)
    expression = parser._expression(0, 1)
    parser._expect("EOF")
    return expression


def lower_expression_v2(
    source_or_expression: str | SourceExprV2,
    *,
    parameters: Sequence[tuple[str, str]] = (),
    expected_type: str,
    generic_arities: Mapping[str, int] | None = None,
) -> LoweredExpressionV2:
    if not isinstance(expected_type, str) or not expected_type:
        _fail("TEVS_V2_PROGRAM_EXPRESSION", "lower_expression_v2 requires an expected type")
    expression = parse_expression_v2(source_or_expression) if isinstance(source_or_expression, str) else source_or_expression
    if not isinstance(expression, SourceExprV2):
        _fail("TEVS_V2_PROGRAM_EXPRESSION", "lower_expression_v2 requires source text or SourceExprV2")
    arities = dict(generic_arities or {})
    lowerer = _ExpressionLowererV2((), parameters, expected_type, {}, arities)
    lowered = lowerer.lower(expression, expected=expected_type)
    return LoweredExpressionV2(lowered.type_text, lowered.ir)

def parse_program_v2(source: str) -> SourceProgramV2:
    return _ProgramParser(source).parse()


def compile_program_v2(source: str) -> CompiledProgramV2:
    return compile_parsed_program_v2(parse_program_v2(source))


def compile_parsed_program_v2(program: SourceProgramV2) -> CompiledProgramV2:
    if not isinstance(program, SourceProgramV2):
        _fail("TEVS_V2_PROGRAM_COMPILE", "compile_parsed_program_v2 requires SourceProgramV2")
    if program.language_version != LANGUAGE_VERSION_V2:
        _fail(
            "TEVS_V2_PROGRAM_VERSION",
            f"V2 compiler requires version {LANGUAGE_VERSION_V2!r}, got {program.language_version!r}",
        )

    base = {
        "boundary": {"maximum_value_nesting": 128},
        "types": [
            {"type_id": "Bool", "kind": "primitive"},
            {"type_id": "Int", "kind": "primitive"},
            {"type_id": "Rat", "kind": "primitive"},
            {"type_id": "Text", "kind": "primitive"},
            {"type_id": "Unit", "kind": "unit"},
            {"type_id": "Vec2", "kind": "primitive"},
            {"type_id": "Vec3", "kind": "primitive"},
        ],
    }
    types = GenericRegistryV2(base)
    functions = GenericPureFunctionRegistryV2(types)
    recursive_functions = RecursivePureFunctionRegistryV2(types)

    entry_for_compile = program.entry
    pre_record_by_name = _index_records(program.records)
    method_functions, method_dispatch = _desugar_methods_v2(program.methods, pre_record_by_name)
    constrained_source_names = {item.name for item in program.functions if item.constraints}
    functions_for_compile = (*program.functions, *method_functions)
    if program.entry.expression is not None:
        if program.entry.function_name or program.entry.type_arguments or program.entry.argument_texts:
            _fail("TEVS_V2_PROGRAM_ENTRY", "expression entry cannot also carry callable fields")
        functions_for_compile = (*functions_for_compile, GenericFunctionSourceV2(
            _INTERNAL_ENTRY_EXPRESSION_FUNCTION_V2,
            (),
            (),
            program.entry.declared_type,
            program.entry.expression,
        ))
        entry_for_compile = EntrySourceV2(
            program.entry.name,
            program.entry.declared_type,
            _INTERNAL_ENTRY_EXPRESSION_FUNCTION_V2,
            (),
            (),
        )
    elif not program.entry.function_name:
        _fail("TEVS_V2_PROGRAM_ENTRY", "call entry requires a function name")
    elif program.entry.function_name in constrained_source_names:
        try:
            entry_arguments = tuple(parse_expression_v2(text) for text in program.entry.argument_texts)
        except TevScriptError as error:
            _fail(
                "TEVS_V2_PROGRAM_CONSTRAINT_ENTRY",
                f"constrained direct entry arguments must be valid V2 expressions: {error.diagnostic.message}",
            )
        entry_body = SourceExprV2(
            "call",
            (program.entry.function_name, program.entry.type_arguments, ()),
            entry_arguments,
        )
        functions_for_compile = (*functions_for_compile, GenericFunctionSourceV2(
            _INTERNAL_ENTRY_EXPRESSION_FUNCTION_V2,
            (),
            (),
            program.entry.declared_type,
            entry_body,
        ))
        entry_for_compile = EntrySourceV2(
            program.entry.name,
            program.entry.declared_type,
            _INTERNAL_ENTRY_EXPRESSION_FUNCTION_V2,
            (),
            (),
        )

    record_by_name = _index_records(program.records)
    protocol_by_name = _index_protocols(program.protocols)
    source_arities = {name: len(item.type_parameters) for name, item in record_by_name.items()}
    _validate_function_constraints_v2(program.functions, protocol_by_name, source_arities)
    _validate_generic_impl_constraints_v2(program.generic_protocol_impls, protocol_by_name, source_arities)
    constrained_template_hashes, constrained_template_hash_by_name = _constrained_function_template_hashes_v2(
        program.program_id,
        program.functions,
        {name: len(item.type_parameters) for name, item in record_by_name.items()},
        protocol_by_name,
    )
    function_by_name = _index_functions(functions_for_compile)
    recursive_by_name = _index_recursive_functions(program.recursive_functions)
    declared_names = [*record_by_name, *function_by_name, *recursive_by_name]
    if len(set(declared_names)) != len(declared_names):
        _fail(
            "TEVS_V2_PROGRAM_SYMBOL",
            "record, pure function, and recursive function names share one V2 declaration namespace",
        )
    reserved_collision = sorted(set(declared_names) & _RESERVED_SOURCE_CALL_NAMES)
    if reserved_collision:
        _fail(
            "TEVS_V2_PROGRAM_RESERVED_SYMBOL",
            f"declarations collide with reserved builtin/constructor calls {reserved_collision}",
        )
    _validate_pure_function_call_graph(
        functions_for_compile,
        recursive_function_names=set(recursive_by_name),
        record_names=set(record_by_name),
    )

    record_templates: dict[str, GenericRecordTemplateV2] = {}
    for name in _record_registration_order(program.records):
        declaration = record_by_name[name]
        record_templates[name] = types.register_record(
            program.program_id,
            declaration.name,
            declaration.type_parameters,
            declaration.fields,
        )

    _validate_associated_constraint_targets_v2(program.functions, types, protocol_by_name)
    _validate_generic_impl_associated_constraint_targets_v2(program.generic_protocol_impls, types, protocol_by_name)

    protocol_hashes, protocol_hash_by_name = _compile_protocol_contracts_v2(
        program.program_id,
        protocol_by_name,
        types,
    )
    _validate_method_types_v2(program.methods, types)
    generic_impl_templates, generic_impl_index = _prepare_generic_protocol_impl_templates_v2(
        program.program_id,
        program.generic_protocol_impls,
        record_by_name,
        protocol_by_name,
        protocol_hash_by_name,
        types,
        program.methods,
    )
    generic_impl_method_protocols: dict[tuple[str, str], set[str]] = {}
    for (record_name, protocol_name), candidates in generic_impl_index.items():
        for declaration, _template in candidates:
            for method in declaration.methods:
                generic_impl_method_protocols.setdefault((record_name, method.name), set()).add(protocol_name)
    generic_impl_method_index: dict[tuple[str, str], tuple[str, ...]] = {
        key: tuple(sorted(protocol_names))
        for key, protocol_names in generic_impl_method_protocols.items()
    }

    if program.generic_protocol_impls:
        generic_impl_symbolic_functions: list[GenericFunctionSourceV2] = []
        for declaration in program.generic_protocol_impls:
            for method in declaration.methods:
                generic_impl_symbolic_functions.append(GenericFunctionSourceV2(
                    _method_symbol(declaration.receiver_type, method.name),
                    declaration.type_parameters,
                    (("self", declaration.receiver_type), *method.parameters),
                    method.return_type,
                    method.body,
                ))
        _validate_pure_function_call_graph(
            (*functions_for_compile, *generic_impl_symbolic_functions),
            recursive_function_names=set(recursive_by_name),
            record_names=set(record_by_name),
        )
        _validate_generic_impl_internal_method_graph_v2(program.generic_protocol_impls)

    all_arities = types.generic_arities()
    function_templates: dict[str, GenericPureFunctionTemplateV2] = {}
    method_function_names = {item.name for item in method_functions}
    method_declaration_by_symbol = {item.name: item for item in method_functions}
    protocol_methods_index = _protocol_method_index_v2(protocol_by_name)
    constrained_specialization_map: dict[str, ConstrainedFunctionSpecializationV2] = {}
    protocol_witness_resolver: Callable[[str, str, dict[str, ConstrainedFunctionSpecializationV2], bool], _ProtocolWitnessResolutionV2 | None] | None = None
    generic_method_resolver: Callable[[str, str, dict[str, ConstrainedFunctionSpecializationV2], bool], _ProtocolWitnessResolutionV2 | None] | None = None

    def lower_pure_declaration(
        declaration: GenericFunctionSourceV2,
        *,
        witness_index: Mapping[tuple[str, str], ProtocolWitnessV2] | None = None,
        protocol_methods_for_lowerer: Mapping[str, frozenset[str]] | None = None,
        specializations: dict[str, ConstrainedFunctionSpecializationV2] | None = None,
        defer_missing_witnesses: bool = False,
        used_specializations: set[str] | None = None,
        allow_constraints: bool = False,
    ) -> dict[str, Any]:
        if declaration.constraints:
            if not allow_constraints:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_ABSTRACT",
                    f"constrained function {declaration.name!r} cannot be registered as abstract Pure IR",
                )
            _fail(
                "TEVS_V2_PROGRAM_CONSTRAINT_ABSTRACT",
                f"constrained source template {declaration.name!r} must be inlined at a concrete call site",
            )
        lowerer = _ExpressionLowererV2(
            declaration.type_parameters,
            declaration.parameters,
            declaration.return_type,
            record_by_name,
            all_arities,
            function_sources=function_by_name,
            recursive_function_names=tuple(recursive_by_name),
            method_dispatch=method_dispatch,
            protocol_witness_index=witness_index,
            protocol_hashes=protocol_hash_by_name,
            protocol_methods=protocol_methods_for_lowerer,
            constrained_template_hashes=constrained_template_hash_by_name,
            constrained_specializations=specializations,
            type_registry=(types if witness_index is not None or defer_missing_witnesses else None),
            defer_missing_witnesses=defer_missing_witnesses,
            used_constrained_specializations=used_specializations,
            protocol_witness_resolver=protocol_witness_resolver,
            generic_method_resolver=generic_method_resolver,
            inline_stack=(declaration.name,),
        )
        lowered = lowerer.lower(declaration.body, expected=declaration.return_type)
        if not _type_equal(lowered.type_text, declaration.return_type, all_arities):
            _fail(
                "TEVS_V2_PROGRAM_FUNCTION_RETURN",
                f"function {declaration.name!r} body has {lowered.type_text}, declared {declaration.return_type}",
            )
        return lowered.ir

    def register_lowered_pure_declaration(
        declaration: GenericFunctionSourceV2,
        body_ir: Mapping[str, Any],
    ) -> GenericPureFunctionTemplateV2:
        template = functions.register(
            program.program_id,
            declaration.name,
            declaration.type_parameters,
            declaration.parameters,
            declaration.return_type,
            body_ir,
        )
        function_templates[declaration.name] = template
        return template

    def register_pure_declaration(
        declaration: GenericFunctionSourceV2,
        *,
        witness_index: Mapping[tuple[str, str], ProtocolWitnessV2] | None = None,
        protocol_methods_for_lowerer: Mapping[str, frozenset[str]] | None = None,
        specializations: dict[str, ConstrainedFunctionSpecializationV2] | None = None,
    ) -> GenericPureFunctionTemplateV2:
        body_ir = lower_pure_declaration(
            declaration,
            witness_index=witness_index,
            protocol_methods_for_lowerer=protocol_methods_for_lowerer,
            specializations=specializations,
        )
        return register_lowered_pure_declaration(declaration, body_ir)

    # Build explicit witness-producing impl groups and the producer relation before
    # lowering any method. This lets unresolved dependencies distinguish missing
    # authority from a real self/mutual witness cycle.
    protocol_groups: dict[tuple[str, str, str], tuple[MethodSourceV2, ...]] = {}
    group_builders: dict[tuple[str, str, str], list[MethodSourceV2]] = {}
    for method in program.methods:
        if not method.protocols:
            continue
        receiver_type = _canon_type(method.receiver_type, all_arities)
        for protocol_name in method.protocols:
            group_builders.setdefault(
                (method.implementation_group, receiver_type, protocol_name),
                [],
            ).append(method)
    protocol_groups = {
        key: tuple(value)
        for key, value in group_builders.items()
    }
    associated_group_builders: dict[tuple[str, str, str], list[AssociatedTypeBindingSourceV2]] = {}
    for binding in program.associated_type_bindings:
        receiver_type = _canon_type(binding.receiver_type, all_arities)
        if not binding.protocols:
            _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_IMPL", "associated type binding has no protocol authority")
        for protocol_name in binding.protocols:
            associated_group_builders.setdefault(
                (binding.implementation_group, receiver_type, protocol_name),
                [],
            ).append(binding)
    associated_groups = {key: tuple(value) for key, value in associated_group_builders.items()}
    orphan_associated_groups = sorted(set(associated_groups) - set(protocol_groups))
    if orphan_associated_groups:
        group, receiver_type, protocol_name = orphan_associated_groups[0]
        _fail(
            "TEVS_V2_PROGRAM_ASSOCIATED_TYPE_IMPL",
            f"associated type bindings in {group} for {receiver_type} : {protocol_name} have no witness-producing method block",
        )
    witness_producer: dict[tuple[str, str], tuple[str, str, str]] = {}
    for group_key in sorted(protocol_groups):
        _group, receiver_type, protocol_name = group_key
        if protocol_name not in protocol_by_name:
            _fail("TEVS_V2_PROGRAM_PROTOCOL_UNKNOWN", f"impl references unknown protocol {protocol_name!r}")
        protocol = protocol_by_name[protocol_name]
        provided_names = {method.name for method in protocol_groups[group_key]}
        required_names = {method.name for method in protocol.methods}
        missing = sorted(required_names - provided_names)
        if missing:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_MISSING_METHOD",
                f"impl {receiver_type} : {protocol_name} is missing required methods {missing}",
            )
        block_associated = associated_groups.get(group_key, ())
        provided_associated_names = [item.name for item in block_associated]
        if len(set(provided_associated_names)) != len(provided_associated_names):
            _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_DUPLICATE", f"duplicate associated type binding in impl {receiver_type} : {protocol_name}")
        required_associated_names = set(protocol.associated_types)
        missing_associated = sorted(required_associated_names - set(provided_associated_names))
        if missing_associated:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_MISSING_ASSOCIATED_TYPE",
                f"impl {receiver_type} : {protocol_name} is missing associated types {missing_associated}",
            )
        extra_associated = sorted(set(provided_associated_names) - required_associated_names)
        if extra_associated:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_UNKNOWN_ASSOCIATED_TYPE",
                f"impl {receiver_type} : {protocol_name} binds undeclared associated types {extra_associated}",
            )
        conformance_key = (protocol_name, receiver_type)
        if conformance_key in witness_producer:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_IMPL",
                f"duplicate protocol implementation {protocol_name!r} for {receiver_type}",
            )
        witness_producer[conformance_key] = group_key

    closed_witnesses: list[ProtocolWitnessV2] = []
    closed_witness_index: dict[tuple[str, str], ProtocolWitnessV2] = {}
    registered_method_symbols: set[str] = set()
    method_constraint_specializations: dict[str, tuple[str, ...]] = {}
    generic_impl_specialization_map: dict[tuple[str, str], GenericProtocolImplSpecializationV2] = {}
    generic_impl_resolution_cache: dict[tuple[str, str], _ProtocolWitnessResolutionV2] = {}
    generic_impl_resolution_stack: set[tuple[str, str]] = set()
    generic_impl_applicability_stack: set[tuple[str, str]] = set()

    def resolve_generic_protocol_witness(
        protocol_name: str,
        receiver_source_type: str,
        specializations: dict[str, ConstrainedFunctionSpecializationV2],
        defer_missing_witnesses: bool,
    ) -> _ProtocolWitnessResolutionV2 | None:
        canonical_receiver = _canon_type(receiver_source_type, all_arities)
        witness_key = (protocol_name, canonical_receiver)
        cached = generic_impl_resolution_cache.get(witness_key)
        if cached is not None:
            return cached
        existing = closed_witness_index.get(witness_key)
        if existing is not None:
            return _ProtocolWitnessResolutionV2(existing)
        if witness_key in generic_impl_applicability_stack:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_CYCLE",
                f"generic impl applicability cycle at {canonical_receiver} : {protocol_name}",
            )
        receiver_ref = parse_type_ref_v2(canonical_receiver, all_arities)
        if receiver_ref.kind != "user_generic":
            return None
        candidates = generic_impl_index.get((receiver_ref.name, protocol_name), ())
        if not candidates:
            return None
        matching_candidates: list[
            tuple[
                GenericProtocolImplSourceV2,
                GenericProtocolImplTemplateV2,
                _GenericImplReceiverMatchV2,
            ]
        ] = []
        for candidate_declaration, candidate_template in candidates:
            candidate_match = _match_generic_protocol_impl_receiver_v2(
                candidate_declaration,
                candidate_template,
                canonical_receiver,
                types,
            )
            if candidate_match is not None:
                matching_candidates.append((candidate_declaration, candidate_template, candidate_match))
        if not matching_candidates:
            return None
        if len(matching_candidates) != 1:
            viable_candidates: list[
                tuple[
                    GenericProtocolImplSourceV2,
                    GenericProtocolImplTemplateV2,
                    _GenericImplReceiverMatchV2,
                ]
            ] = []
            deferred_missing: list[tuple[str, str]] = []
            generic_impl_applicability_stack.add(witness_key)
            try:
                for candidate_declaration, candidate_template, candidate_match in matching_candidates:
                    candidate_shape = _GenericImplReceiverPatternV2.from_template(
                        candidate_declaration,
                        candidate_template,
                        types=types,
                    )
                    candidate_domain = _ClosedGenericImplRefinementDomainV2.build(
                        candidate_declaration,
                        candidate_shape,
                        protocols=protocol_by_name,
                        types=types,
                    )
                    if not candidate_domain.entries:
                        viable_candidates.append((candidate_declaration, candidate_template, candidate_match))
                        continue
                    applicable = True
                    for ordinal, prerequisite_protocol_name, associated_name, required_type_id in candidate_domain.entries:
                        prerequisite_source_type = candidate_match.source_arguments[ordinal]
                        prerequisite_key = (prerequisite_protocol_name, prerequisite_source_type)
                        prerequisite_witness = closed_witness_index.get(prerequisite_key)
                        if prerequisite_witness is None:
                            prerequisite_resolution = resolve_generic_protocol_witness(
                                prerequisite_protocol_name,
                                prerequisite_source_type,
                                specializations,
                                defer_missing_witnesses,
                            )
                            if prerequisite_resolution is not None:
                                prerequisite_witness = prerequisite_resolution.witness
                        if prerequisite_witness is None:
                            deferred_missing.append(prerequisite_key)
                            applicable = False
                            break
                        prerequisite_binding = _ProtocolWitnessBindingResolverV2.validate(
                            witness=prerequisite_witness,
                            protocol_name=prerequisite_protocol_name,
                            receiver_source_type=prerequisite_source_type,
                            protocol_hashes=protocol_hash_by_name,
                            types=types,
                            diagnostic_code="TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_WITNESS",
                            contract_mismatch_message=(
                                f"prerequisite witness for {prerequisite_source_type} : {prerequisite_protocol_name} "
                                "is not bound to the active protocol contract"
                            ),
                            runtime_mismatch_message=(
                                f"prerequisite witness runtime receiver mismatch for "
                                f"{prerequisite_source_type} : {prerequisite_protocol_name}"
                            ),
                        )
                        associated_type_ids = dict(prerequisite_binding.associated_type_ids)
                        actual_type_id = associated_type_ids.get(associated_name)
                        if actual_type_id is None:
                            _fail(
                                "TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_ASSOCIATED",
                                f"prerequisite witness {prerequisite_source_type} : {prerequisite_protocol_name} "
                                f"does not bind associated type {associated_name!r}",
                            )
                        if actual_type_id != required_type_id:
                            applicable = False
                            break
                    if applicable:
                        viable_candidates.append((candidate_declaration, candidate_template, candidate_match))
            finally:
                generic_impl_applicability_stack.discard(witness_key)
            if not viable_candidates:
                if defer_missing_witnesses and deferred_missing:
                    missing_protocol, missing_receiver = sorted(set(deferred_missing))[0]
                    raise _DeferredProtocolWitnessV2(missing_protocol, missing_receiver)
                return None
            if len(viable_candidates) != 1:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                    f"receiver {canonical_receiver} has multiple applicable generic impl domains for protocol {protocol_name!r}",
                )
            matching_candidates = viable_candidates
        declaration, template, receiver_match = matching_candidates[0]
        if witness_key in generic_impl_resolution_stack:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_CYCLE",
                f"generic impl specialization cycle at {canonical_receiver} : {protocol_name}",
            )
        generic_impl_resolution_stack.add(witness_key)
        added_source_symbols: list[str] = []
        added_dispatch_keys: list[tuple[str, str]] = []
        try:
            source_type_by_parameter = dict(zip(
                declaration.type_parameters,
                receiver_match.source_arguments,
                strict=True,
            ))
            parameter_ordinals = {name: index for index, name in enumerate(declaration.type_parameters)}
            prerequisite_witness_map: dict[tuple[str, str], _ValidatedProtocolWitnessBindingV2] = {}
            prerequisite_witnesses: list[tuple[int, str, str]] = []
            for type_parameter, prerequisite_protocol_name in declaration.constraints:
                prerequisite_source_type = source_type_by_parameter[type_parameter]
                prerequisite_key = (prerequisite_protocol_name, prerequisite_source_type)
                prerequisite_witness = closed_witness_index.get(prerequisite_key)
                if prerequisite_witness is None:
                    prerequisite_resolution = resolve_generic_protocol_witness(
                        prerequisite_protocol_name,
                        prerequisite_source_type,
                        specializations,
                        defer_missing_witnesses,
                    )
                    if prerequisite_resolution is not None:
                        prerequisite_witness = prerequisite_resolution.witness
                if prerequisite_witness is None:
                    if defer_missing_witnesses:
                        raise _DeferredProtocolWitnessV2(
                            prerequisite_protocol_name,
                            prerequisite_source_type,
                        )
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_WITNESS",
                        f"generic impl {canonical_receiver} : {protocol_name} requires witness "
                        f"{prerequisite_source_type} : {prerequisite_protocol_name}",
                    )
                prerequisite_binding = _ProtocolWitnessBindingResolverV2.validate(
                    witness=prerequisite_witness,
                    protocol_name=prerequisite_protocol_name,
                    receiver_source_type=prerequisite_source_type,
                    protocol_hashes=protocol_hash_by_name,
                    types=types,
                    diagnostic_code="TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_WITNESS",
                    contract_mismatch_message=(
                        f"prerequisite witness for {prerequisite_source_type} : {prerequisite_protocol_name} "
                        "is not bound to the active protocol contract"
                    ),
                    runtime_mismatch_message=(
                        f"prerequisite witness runtime receiver mismatch for "
                        f"{prerequisite_source_type} : {prerequisite_protocol_name}"
                    ),
                )
                prerequisite_witness_map[(type_parameter, prerequisite_protocol_name)] = prerequisite_binding
                prerequisite_witnesses.append((
                    parameter_ordinals[type_parameter],
                    prerequisite_binding.protocol_hash,
                    prerequisite_binding.witness.witness_hash,
                ))
            prerequisite_witness_bindings = tuple(sorted(prerequisite_witnesses))
            prerequisite_associated_substitutions: dict[tuple[str, str], TypeRefV2] = {}
            for (type_parameter, prerequisite_protocol_name), prerequisite_binding in sorted(
                prerequisite_witness_map.items()
            ):
                for associated_name, associated_source_type in prerequisite_binding.associated_source_types:
                    key = (type_parameter, associated_name)
                    associated_ref = parse_type_ref_v2(associated_source_type, all_arities)
                    prior = prerequisite_associated_substitutions.get(key)
                    if prior is not None and prior != associated_ref:
                        _fail(
                            "TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_ASSOCIATED",
                            f"conflicting prerequisite associated projection {type_parameter}::{associated_name}",
                        )
                    prerequisite_associated_substitutions[key] = associated_ref

            receiver_associated_projection_bindings = receiver_match.validate_associated_projections(
                associated_substitutions=prerequisite_associated_substitutions,
                types=types,
                receiver_source_type=canonical_receiver,
            )

            prerequisite_associated_bindings: list[tuple[int, str, str]] = []
            for type_parameter, associated_name, required_type in declaration.associated_constraints:
                owner_protocols = [
                    prerequisite_protocol_name
                    for constrained_parameter, prerequisite_protocol_name in declaration.constraints
                    if constrained_parameter == type_parameter
                    and associated_name in protocol_by_name[prerequisite_protocol_name].associated_types
                ]
                if len(owner_protocols) != 1:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_ASSOCIATED",
                        f"generic impl prerequisite refinement {type_parameter}::{associated_name} "
                        "does not have one unique protocol owner",
                    )
                owner_protocol = owner_protocols[0]
                owner_binding = prerequisite_witness_map[(type_parameter, owner_protocol)]
                actual_type_id = owner_binding.associated_type_id(associated_name)
                if actual_type_id is None:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_ASSOCIATED",
                        f"prerequisite witness for {source_type_by_parameter[type_parameter]} : {owner_protocol} "
                        f"does not bind associated type {associated_name}",
                    )
                specification = _AssociatedConstraintSpecificationV2.from_validated_source(
                    target_type_parameter=type_parameter,
                    associated_name=associated_name,
                    required_type=required_type,
                    type_parameters=declaration.type_parameters,
                    generic_arities=all_arities,
                )
                required_source_type, required_type_id = specification.resolve(
                    type_substitutions=receiver_match.substitution_map(),
                    associated_substitutions=prerequisite_associated_substitutions,
                    types=types,
                    diagnostic_code="TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_REFINEMENT",
                    message_prefix=(
                        f"generic impl {canonical_receiver} : {protocol_name} refinement "
                        f"{type_parameter}::{associated_name} requires type"
                    ),
                )
                if actual_type_id != required_type_id:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_REFINEMENT",
                        f"generic impl {canonical_receiver} : {protocol_name} requires "
                        f"{type_parameter}::{associated_name}={required_source_type}, got type id {actual_type_id}",
                    )
                prerequisite_associated_bindings.append((
                    parameter_ordinals[type_parameter],
                    associated_name,
                    required_type_id,
                ))
            prerequisite_associated_constraint_bindings = tuple(sorted(prerequisite_associated_bindings))

            (
                concrete_methods,
                associated_bindings,
                concrete_function_sources,
                concrete_dispatch,
                type_argument_ids,
            ) = _specialize_generic_protocol_impl_source_v2(
                declaration,
                template,
                canonical_receiver,
                types,
                prerequisite_associated_substitutions,
            )
            source_symbols = {item.name for item in concrete_function_sources}
            for function_source in concrete_function_sources:
                if function_source.name in function_by_name or function_source.name in function_templates:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                        f"generic impl specialization collides with function symbol {function_source.name!r}",
                    )
            for dispatch_key, symbol in concrete_dispatch.items():
                if dispatch_key in method_dispatch:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                        f"generic impl specialization collides with method dispatch {dispatch_key}",
                    )
                if symbol not in source_symbols:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                        f"generic impl dispatch {dispatch_key} has no matching source symbol",
                    )
            for function_source in concrete_function_sources:
                function_by_name[function_source.name] = function_source
                added_source_symbols.append(function_source.name)
            for dispatch_key, symbol in concrete_dispatch.items():
                method_dispatch[dispatch_key] = symbol
                added_dispatch_keys.append(dispatch_key)

            trial_specializations = dict(specializations)
            lowered_sources: list[tuple[GenericFunctionSourceV2, dict[str, Any], set[str]]] = []
            for function_source in concrete_function_sources:
                used: set[str] = set()
                body_ir = lower_pure_declaration(
                    function_source,
                    witness_index=closed_witness_index,
                    protocol_methods_for_lowerer=protocol_methods_index,
                    specializations=trial_specializations,
                    defer_missing_witnesses=defer_missing_witnesses,
                    used_specializations=used,
                )
                lowered_sources.append((function_source, body_ir, used))

            # Atomic admission boundary: registration starts only after every
            # specialized method body has lowered successfully.
            for function_source, body_ir, used in lowered_sources:
                register_lowered_pure_declaration(function_source, body_ir)
                registered_method_symbols.add(function_source.name)
                if used:
                    method_constraint_specializations[function_source.name] = tuple(sorted(used))

            base_witnesses = _build_protocol_witnesses_v2(
                concrete_methods,
                protocol_by_name,
                protocol_hash_by_name,
                function_templates,
                types,
                method_constraint_specializations,
                associated_bindings,
            )
            if len(base_witnesses) != 1:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_WITNESS",
                    f"generic impl specialization for {canonical_receiver} : {protocol_name} did not produce exactly one base witness",
                )
            base_witness = base_witnesses[0]
            if (base_witness.protocol_name, base_witness.receiver_source_type) != witness_key:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_WITNESS",
                    f"generic impl base witness key mismatch for {canonical_receiver} : {protocol_name}",
                )
            resolved_receiver = types.materialize_source_type(canonical_receiver)
            receiver_shape = _GenericImplReceiverPatternV2.from_template(
                declaration,
                template,
                types=types,
            )
            all_method_hashes = tuple(sorted(
                (
                    method.name,
                    function_templates[_method_symbol(canonical_receiver, method.name)].template_hash,
                )
                for method in concrete_methods
            ))
            all_method_dependencies = tuple(sorted(
                (
                    method.name,
                    method_constraint_specializations.get(
                        _method_symbol(canonical_receiver, method.name),
                        (),
                    ),
                )
                for method in concrete_methods
                if method_constraint_specializations.get(
                    _method_symbol(canonical_receiver, method.name),
                    (),
                )
            ))
            specialization_payload: dict[str, Any] = {
                "schema": "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_SPECIALIZATION_R1",
                "template_hash": template.template_hash,
                "protocol_hash": template.protocol_hash,
                "coherence_policy": GENERIC_PROTOCOL_IMPL_COHERENCE_POLICY_V2,
                "demand_policy": GENERIC_PROTOCOL_IMPL_DEMAND_POLICY_V2,
                "receiver_source_type": canonical_receiver,
                "receiver_runtime_type": resolved_receiver.type_id,
                "type_argument_ids": list(type_argument_ids),
                "methods": [
                    {"name": name, "template_hash": method_hash}
                    for name, method_hash in all_method_hashes
                ],
                "associated_types": [
                    {"name": name, "source_type": source_type, "type_id": type_id}
                    for name, source_type, type_id in base_witness.associated_types
                ],
                "base_witness_hash": base_witness.witness_hash,
            }
            if prerequisite_witness_bindings:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_SPECIALIZATION_R2"
                specialization_payload["prerequisite_policy"] = GENERIC_PROTOCOL_IMPL_PREREQUISITE_POLICY_V2
                specialization_payload["prerequisite_witnesses"] = [
                    {
                        "type_parameter_ordinal": ordinal,
                        "protocol_hash": prerequisite_protocol_hash,
                        "witness_hash": prerequisite_witness_hash,
                    }
                    for ordinal, prerequisite_protocol_hash, prerequisite_witness_hash in prerequisite_witness_bindings
                ]
                if prerequisite_associated_constraint_bindings:
                    specialization_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_SPECIALIZATION_R3"
                    specialization_payload["prerequisite_associated_constraints"] = [
                        {
                            "type_parameter_ordinal": ordinal,
                            "associated_name": associated_name,
                            "required_type_id": required_type_id,
                        }
                        for ordinal, associated_name, required_type_id in prerequisite_associated_constraint_bindings
                    ]
            if all_method_dependencies:
                specialization_payload["method_constraint_specializations"] = [
                    {"name": name, "specialization_hashes": list(hashes)}
                    for name, hashes in all_method_dependencies
                ]
            if receiver_shape.has_associated_projections:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_SPECIALIZATION_R6"
                specialization_payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
                specialization_payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_PATTERN_POLICY_V2
                specialization_payload["associated_projection_validation_policy"] = GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_VALIDATION_POLICY_V2
                specialization_payload["pattern_overlap_policy"] = GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2
                specialization_payload["receiver_pattern"] = template.receiver_pattern
                specialization_payload["receiver_associated_projections"] = [
                    {"root": root, "member": member, "actual_type_id": type_id}
                    for root, member, type_id in receiver_associated_projection_bindings
                ]
            elif receiver_shape.nonlinear:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_SPECIALIZATION_R5"
                specialization_payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
                specialization_payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_NONLINEAR_PATTERN_POLICY_V2
                specialization_payload["pattern_overlap_policy"] = GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2
                specialization_payload["receiver_pattern"] = template.receiver_pattern
            elif not receiver_shape.direct:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_SPECIALIZATION_R4"
                specialization_payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
                specialization_payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_RECEIVER_PATTERN_POLICY_V2
                specialization_payload["receiver_pattern"] = template.receiver_pattern
            impl_specialization_hash = _hash(specialization_payload)
            final_witness_payload: dict[str, Any] = {
                "schema": "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_WITNESS_R1",
                "protocol_hash": base_witness.protocol_hash,
                "receiver_runtime_type": base_witness.receiver_runtime_type,
                "base_witness_hash": base_witness.witness_hash,
                "impl_template_hash": template.template_hash,
                "impl_specialization_hash": impl_specialization_hash,
            }
            if prerequisite_witness_bindings:
                final_witness_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_WITNESS_R2"
                final_witness_payload["prerequisite_witnesses"] = [
                    {
                        "type_parameter_ordinal": ordinal,
                        "protocol_hash": prerequisite_protocol_hash,
                        "witness_hash": prerequisite_witness_hash,
                    }
                    for ordinal, prerequisite_protocol_hash, prerequisite_witness_hash in prerequisite_witness_bindings
                ]
                if prerequisite_associated_constraint_bindings:
                    final_witness_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_WITNESS_R3"
                    final_witness_payload["prerequisite_associated_constraints"] = [
                        {
                            "type_parameter_ordinal": ordinal,
                            "associated_name": associated_name,
                            "required_type_id": required_type_id,
                        }
                        for ordinal, associated_name, required_type_id in prerequisite_associated_constraint_bindings
                    ]
            if receiver_shape.has_associated_projections:
                final_witness_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_WITNESS_R6"
                final_witness_payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
                final_witness_payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_PATTERN_POLICY_V2
                final_witness_payload["associated_projection_validation_policy"] = GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_VALIDATION_POLICY_V2
                final_witness_payload["pattern_overlap_policy"] = GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2
                final_witness_payload["receiver_pattern"] = template.receiver_pattern
                final_witness_payload["receiver_associated_projections"] = [
                    {"root": root, "member": member, "actual_type_id": type_id}
                    for root, member, type_id in receiver_associated_projection_bindings
                ]
            elif receiver_shape.nonlinear:
                final_witness_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_WITNESS_R5"
                final_witness_payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
                final_witness_payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_NONLINEAR_PATTERN_POLICY_V2
                final_witness_payload["pattern_overlap_policy"] = GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2
                final_witness_payload["receiver_pattern"] = template.receiver_pattern
            elif not receiver_shape.direct:
                final_witness_payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_WITNESS_R4"
                final_witness_payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
                final_witness_payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_RECEIVER_PATTERN_POLICY_V2
                final_witness_payload["receiver_pattern"] = template.receiver_pattern
            final_witness_hash = _hash(final_witness_payload)
            final_witness = ProtocolWitnessV2(
                base_witness.protocol_name,
                base_witness.protocol_hash,
                base_witness.receiver_source_type,
                base_witness.receiver_runtime_type,
                base_witness.method_template_hashes,
                final_witness_hash,
                base_witness.method_constraint_specializations,
                base_witness.associated_types,
                receiver_associated_projection_bindings,
            )
            impl_specialization = GenericProtocolImplSpecializationV2(
                template.template_hash,
                protocol_name,
                canonical_receiver,
                resolved_receiver.type_id,
                type_argument_ids,
                all_method_hashes,
                base_witness.associated_types,
                impl_specialization_hash,
                final_witness_hash,
                prerequisite_witness_bindings,
                prerequisite_associated_constraint_bindings,
                receiver_associated_projection_bindings,
            )

            constrained_specialization_map.clear()
            constrained_specialization_map.update(trial_specializations)
            if specializations is not constrained_specialization_map:
                specializations.clear()
                specializations.update(trial_specializations)
            closed_witness_index[witness_key] = final_witness
            closed_witnesses.append(final_witness)
            generic_impl_specialization_map[witness_key] = impl_specialization
            resolution = _ProtocolWitnessResolutionV2(
                final_witness,
                tuple(sorted(concrete_dispatch.items())),
                tuple(sorted(
                    ((item.name, item) for item in concrete_function_sources),
                    key=lambda item: item[0],
                )),
            )
            generic_impl_resolution_cache[witness_key] = resolution
            return resolution
        except Exception:
            for dispatch_key in added_dispatch_keys:
                method_dispatch.pop(dispatch_key, None)
            for symbol in added_source_symbols:
                function_by_name.pop(symbol, None)
            raise
        finally:
            generic_impl_resolution_stack.discard(witness_key)

    def resolve_generic_method(
        receiver_source_type: str,
        method_name: str,
        specializations: dict[str, ConstrainedFunctionSpecializationV2],
        defer_missing_witnesses: bool,
    ) -> _ProtocolWitnessResolutionV2 | None:
        canonical_receiver = _canon_type(receiver_source_type, all_arities)
        receiver_ref = parse_type_ref_v2(canonical_receiver, all_arities)
        if receiver_ref.kind != "user_generic":
            return None
        protocol_names = generic_impl_method_index.get((receiver_ref.name, method_name), ())
        if not protocol_names:
            return None
        matching_protocols: list[str] = []
        for protocol_name in protocol_names:
            candidates = generic_impl_index.get((receiver_ref.name, protocol_name), ())
            if any(
                _match_generic_protocol_impl_receiver_v2(
                    declaration,
                    template,
                    canonical_receiver,
                    types,
                ) is not None
                for declaration, template in candidates
            ):
                matching_protocols.append(protocol_name)
        if not matching_protocols:
            return None
        if len(matching_protocols) != 1:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                f"receiver {canonical_receiver} has ambiguous generic method {method_name!r} across protocols {sorted(matching_protocols)}",
            )
        return resolve_generic_protocol_witness(
            matching_protocols[0],
            canonical_receiver,
            specializations,
            defer_missing_witnesses,
        )

    protocol_witness_resolver = resolve_generic_protocol_witness
    generic_method_resolver = resolve_generic_method
    remaining_groups = dict(protocol_groups)

    while remaining_groups:
        progress = False
        completed_groups: list[tuple[str, str, str]] = []
        blocked_dependencies: dict[tuple[str, str, str], set[tuple[str, str]]] = {}

        for group_key in sorted(remaining_groups):
            _group, receiver_type, protocol_name = group_key
            block_methods = remaining_groups[group_key]
            protocol = protocol_by_name[protocol_name]
            provided = {method.name: method for method in block_methods}
            required = {method.name: method for method in protocol.methods}
            missing = sorted(set(required) - set(provided))
            if missing:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_MISSING_METHOD",
                    f"impl {receiver_type} : {protocol_name} is missing required methods {missing}",
                )

            trial_specializations = dict(constrained_specialization_map)
            lowered_required: list[tuple[str, GenericFunctionSourceV2, dict[str, Any], set[str]]] = []
            deferred: _DeferredProtocolWitnessV2 | None = None
            for method_name in sorted(required):
                symbol = _method_symbol(receiver_type, method_name)
                declaration = method_declaration_by_symbol.get(symbol)
                if declaration is None:
                    _fail(
                        "TEVS_V2_PROGRAM_PROTOCOL_WITNESS",
                        f"method source for {receiver_type}.{method_name} is unavailable",
                    )
                used: set[str] = set()
                try:
                    body_ir = lower_pure_declaration(
                        declaration,
                        witness_index=closed_witness_index,
                        protocol_methods_for_lowerer=protocol_methods_index,
                        specializations=trial_specializations,
                        defer_missing_witnesses=True,
                        used_specializations=used,
                    )
                except _DeferredProtocolWitnessV2 as error:
                    deferred = error
                    blocked_dependencies.setdefault(group_key, set()).add(error.key)
                    break
                lowered_required.append((symbol, declaration, body_ir, used))

            if deferred is not None:
                continue

            # Atomic group admission: no method template or specialization from this
            # stratum is published until every required method has lowered.
            constrained_specialization_map.clear()
            constrained_specialization_map.update(trial_specializations)
            for symbol, declaration, body_ir, used in lowered_required:
                register_lowered_pure_declaration(declaration, body_ir)
                registered_method_symbols.add(symbol)
                method_constraint_specializations[symbol] = tuple(sorted(used))

            witnesses = _build_protocol_witnesses_v2(
                block_methods,
                protocol_by_name,
                protocol_hash_by_name,
                function_templates,
                types,
                method_constraint_specializations,
                program.associated_type_bindings,
            )
            if len(witnesses) != 1:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_WITNESS",
                    f"impl {receiver_type} : {protocol_name} did not produce exactly one witness",
                )
            witness = witnesses[0]
            conformance_key = (witness.protocol_name, witness.receiver_source_type)
            if conformance_key != (protocol_name, receiver_type):
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_WITNESS",
                    f"witness conformance key mismatch for {receiver_type} : {protocol_name}",
                )
            closed_witnesses.append(witness)
            closed_witness_index[conformance_key] = witness
            completed_groups.append(group_key)
            progress = True

        for group_key in completed_groups:
            remaining_groups.pop(group_key, None)

        if progress:
            continue

        unresolved = sorted(
            {dependency for dependencies in blocked_dependencies.values() for dependency in dependencies}
        )
        missing_authority = [
            dependency
            for dependency in unresolved
            if dependency not in closed_witness_index and dependency not in witness_producer
        ]
        if missing_authority:
            protocol_name, receiver_type = missing_authority[0]
            _fail(
                "TEVS_V2_PROGRAM_CONSTRAINT_WITNESS",
                f"type {receiver_type} has no explicit witness producer for protocol {protocol_name!r}",
            )
        cycle_summary = [
            {
                "impl": [group_key[1], group_key[2]],
                "waits_for": [list(item) for item in sorted(blocked_dependencies.get(group_key, set()))],
            }
            for group_key in sorted(remaining_groups)
        ]
        _fail(
            "TEVS_V2_PROGRAM_PROTOCOL_WITNESS_CYCLE",
            f"protocol witness dependency cycle: {cycle_summary}",
        )

    protocol_witnesses = tuple(sorted(
        closed_witnesses,
        key=lambda item: (item.protocol_name, item.receiver_source_type, item.witness_hash),
    ))
    protocol_witness_index = _protocol_witness_index_v2(protocol_witnesses)

    # Extra methods in tagged impls and untagged impls are not witness-producing
    # unless transitively inlined by a required method. Compile them only after the
    # witness closure exists, so a helper can safely consume an already-closed
    # witness without manufacturing a cycle.
    for declaration in sorted(method_functions, key=lambda item: item.name):
        if declaration.name in registered_method_symbols:
            continue
        register_pure_declaration(
            declaration,
            witness_index=protocol_witness_index,
            protocol_methods_for_lowerer=protocol_methods_index,
            specializations=constrained_specialization_map,
        )
        registered_method_symbols.add(declaration.name)

    # Ordinary functions are lowered only after all protocol witnesses exist.
    # Constrained source templates themselves remain source-only and are inlined
    # after concrete type arguments and exact witnesses are known.
    for declaration in sorted(functions_for_compile, key=lambda item: item.name):
        if declaration.name in method_function_names or declaration.constraints:
            continue
        register_pure_declaration(
            declaration,
            witness_index=protocol_witness_index,
            protocol_methods_for_lowerer=protocol_methods_index,
            specializations=constrained_specialization_map,
        )

    recursive_templates: dict[str, RecursivePureFunctionTemplateV2] = {}
    for declaration in sorted(program.recursive_functions, key=lambda item: item.name):
        lowerer = _ExpressionLowererV2(
            declaration.type_parameters,
            declaration.parameters,
            declaration.return_type,
            record_by_name,
            all_arities,
            self_parameter_types=declaration.parameters,
            self_return_type=declaration.return_type,
            function_sources=function_by_name,
            recursive_function_names=tuple(recursive_by_name),
            method_dispatch=method_dispatch,
            protocol_witness_index=protocol_witness_index,
            protocol_hashes=protocol_hash_by_name,
            protocol_methods=protocol_methods_index,
            constrained_template_hashes=constrained_template_hash_by_name,
            constrained_specializations=constrained_specialization_map,
            type_registry=types,
            protocol_witness_resolver=protocol_witness_resolver,
            generic_method_resolver=generic_method_resolver,
            inline_stack=(),
        )
        lowered = lowerer.lower(declaration.body, expected=declaration.return_type)
        if not _type_equal(lowered.type_text, declaration.return_type, all_arities):
            _fail(
                "TEVS_V2_PROGRAM_RECURSION_RETURN",
                f"recursive function {declaration.name!r} body has {lowered.type_text}, declared {declaration.return_type}",
            )
        recursive_templates[declaration.name] = recursive_functions.register(
            program.program_id,
            declaration.name,
            declaration.type_parameters,
            declaration.parameters,
            declaration.return_type,
            lowered.ir,
            measure_parameter=declaration.measure_parameter,
            max_depth=declaration.max_depth,
            maximum_steps=declaration.maximum_steps,
        )

    entry = _compile_entry(
        entry_for_compile,
        types,
        functions,
        recursive_functions,
        function_templates,
        recursive_templates,
    )

    protocol_witnesses = tuple(sorted(
        closed_witnesses,
        key=lambda item: (item.protocol_name, item.receiver_source_type, item.witness_hash),
    ))
    generic_impl_specializations = tuple(sorted(
        generic_impl_specialization_map.values(),
        key=lambda item: (item.protocol_name, item.receiver_source_type, item.specialization_hash),
    ))

    record_hashes = tuple(
        sorted(
            (template.qualified_name, template.template_hash)
            for template in record_templates.values()
        )
    )
    function_hashes = tuple(
        sorted(
            (template.qualified_name, template.template_hash)
            for template in function_templates.values()
        )
    )
    recursive_hashes = tuple(
        sorted(
            (template.qualified_name, template.template_hash)
            for template in recursive_templates.values()
        )
    )
    constrained_specializations = tuple(
        sorted(
            constrained_specialization_map.values(),
            key=lambda item: (item.function_name, item.specialization_hash),
        )
    )
    identity = {
        "schema": "TEV_SCRIPT_PROGRAM_V2_SEMANTIC_IDENTITY_V1",
        "program_id": program.program_id,
        "language_version": program.language_version,
        "record_templates": [
            {"qualified_name": name, "template_hash": template_hash}
            for name, template_hash in record_hashes
        ],
        "function_templates": [
            {"qualified_name": name, "template_hash": template_hash}
            for name, template_hash in function_hashes
        ],
        "recursive_function_templates": [
            {"qualified_name": name, "template_hash": template_hash}
            for name, template_hash in recursive_hashes
        ],
        "entry_hash": entry.entry_hash,
    }
    if protocol_hashes:
        identity["protocols"] = [
            {"qualified_name": name, "protocol_hash": protocol_hash}
            for name, protocol_hash in protocol_hashes
        ]
    if protocol_witnesses:
        identity["protocol_witnesses"] = [
            {
                "protocol_name": witness.protocol_name,
                "receiver_source_type": witness.receiver_source_type,
                "witness_hash": witness.witness_hash,
            }
            for witness in protocol_witnesses
        ]
    if constrained_template_hashes:
        identity["constrained_function_templates"] = [
            {"qualified_name": name, "template_hash": template_hash}
            for name, template_hash in constrained_template_hashes
        ]
    if constrained_specializations:
        identity["constrained_function_specializations"] = [
            {
                "function_name": item.function_name,
                "specialization_hash": item.specialization_hash,
            }
            for item in constrained_specializations
        ]
    if generic_impl_templates:
        identity["generic_protocol_impl_templates"] = [
            {
                "record_name": item.record_name,
                "protocol_name": item.protocol_name,
                "template_hash": item.template_hash,
            }
            for item in generic_impl_templates
        ]
    if generic_impl_specializations:
        identity["generic_protocol_impl_specializations"] = [
            {
                "protocol_name": item.protocol_name,
                "receiver_source_type": item.receiver_source_type,
                "specialization_hash": item.specialization_hash,
                "witness_hash": item.witness_hash,
            }
            for item in generic_impl_specializations
        ]
    return CompiledProgramV2(
        "TEV_SCRIPT_COMPILED_PROGRAM_V2_V1",
        program.program_id,
        program.language_version,
        _hash(identity),
        record_hashes,
        function_hashes,
        recursive_hashes,
        types.type_descriptors(),
        entry,
        types,
        functions,
        recursive_functions,
        protocol_hashes,
        protocol_witnesses,
        constrained_template_hashes,
        constrained_specializations,
        generic_impl_templates,
        generic_impl_specializations,
    )

def run_program_v2(compiled: CompiledProgramV2) -> ProgramRunReceiptV2:
    if not isinstance(compiled, CompiledProgramV2):
        _fail("TEVS_V2_PROGRAM_RUN", "run requires CompiledProgramV2")
    if compiled.entry.function_kind == "pure":
        call = compiled.functions.call(compiled.entry.instantiation, compiled.entry.arguments)  # type: ignore[arg-type]
    elif compiled.entry.function_kind == "recursive":
        call = compiled.recursive_functions.call(compiled.entry.instantiation, compiled.entry.arguments)  # type: ignore[arg-type]
    else:
        _fail("TEVS_V2_PROGRAM_RUN", f"unknown compiled function kind {compiled.entry.function_kind!r}")
    if call.result_type != compiled.entry.declared_runtime_type:
        _fail(
            "TEVS_V2_PROGRAM_ENTRY_TYPE",
            f"entry declared {compiled.entry.declared_runtime_type}, call returned {call.result_type}",
        )
    payload = {
        "schema": "TEV_SCRIPT_PROGRAM_V2_RUN_RECEIPT_V1",
        "program_semantic_hash": compiled.semantic_hash,
        "entry_hash": compiled.entry.entry_hash,
        "entry_name": compiled.entry.name,
        "function_kind": compiled.entry.function_kind,
        "callable_id": compiled.entry.instantiation.callable_id,
        "call_receipt_hash": call.receipt_hash,
        "result_type": call.result_type,
        "result_encoded": call.result_encoded,
        "result_hash": call.result_hash,
    }
    return ProgramRunReceiptV2(
        payload["schema"],
        compiled.semantic_hash,
        compiled.entry.entry_hash,
        compiled.entry.name,
        compiled.entry.instantiation.callable_id,
        call.receipt_hash,
        call.result_type,
        call.result_encoded,
        call.result_hash,
        _hash(payload),
    )

def compile_and_run_program_v2(source: str) -> tuple[CompiledProgramV2, ProgramRunReceiptV2]:
    compiled = compile_program_v2(source)
    return compiled, run_program_v2(compiled)


class _ProgramParser:
    def __init__(self, source: str) -> None:
        if not isinstance(source, str):
            _fail("TEVS_V2_PROGRAM_SOURCE", "source must be text")
        if len(source.encode("utf-8")) > MAX_SOURCE_BYTES_V2:
            _fail("TEVS_V2_PROGRAM_SOURCE", f"source exceeds {MAX_SOURCE_BYTES_V2} bytes")
        self.source = source
        self.tokens = list(_tokenize(source))
        self.index = 0
        self.declaration_count = 0

    def parse(self) -> SourceProgramV2:
        self._expect_word("script")
        program_id = self._expect("IDENT").text
        if _NAME.fullmatch(program_id) is None:
            _fail("TEVS_V2_PROGRAM_ID", f"invalid program id {program_id!r}")
        self._expect_word("version")
        version = self._expect("STRING").value
        self._expect("SEMI")
        records: list[GenericRecordSourceV2] = []
        functions: list[GenericFunctionSourceV2] = []
        recursive_functions: list[RecursiveFunctionSourceV2] = []
        methods: list[MethodSourceV2] = []
        protocols: list[ProtocolSourceV2] = []
        associated_type_bindings: list[AssociatedTypeBindingSourceV2] = []
        generic_protocol_impls: list[GenericProtocolImplSourceV2] = []
        entry: EntrySourceV2 | None = None
        while not self._at("EOF"):
            self.declaration_count += 1
            if self.declaration_count > MAX_SOURCE_DECLARATIONS_V2:
                _fail("TEVS_V2_PROGRAM_BUDGET", f"declarations exceed {MAX_SOURCE_DECLARATIONS_V2}")
            if self._is_word("generic"):
                self._advance()
                if self._is_word("record"):
                    records.append(self._record())
                elif self._is_word("fn"):
                    functions.append(self._function(require_type_parameters=True))
                elif self._is_word("impl"):
                    generic_protocol_impls.append(self._generic_impl())
                else:
                    _fail("TEVS_V2_PROGRAM_DECL", "generic must introduce record, fn, or impl")
                continue
            if self._is_word("fn"):
                functions.append(self._function(require_type_parameters=False))
                continue
            if self._is_word("recursive"):
                self._advance()
                recursive_functions.append(self._recursive_function())
                continue
            if self._is_word("protocol"):
                protocols.append(self._protocol())
                continue
            if self._is_word("impl"):
                impl_methods, impl_associated_types = self._impl()
                methods.extend(impl_methods)
                associated_type_bindings.extend(impl_associated_types)
                continue
            if self._is_word("entry"):
                if entry is not None:
                    _fail("TEVS_V2_PROGRAM_ENTRY", "V2 pure program requires exactly one entry")
                entry = self._entry()
                continue
            _fail("TEVS_V2_PROGRAM_DECL", f"unexpected top-level token {self._current().text!r}")
        if entry is None:
            _fail("TEVS_V2_PROGRAM_ENTRY", "V2 pure program requires exactly one entry")
        return SourceProgramV2(
            program_id,
            str(version),
            tuple(records),
            tuple(functions),
            tuple(recursive_functions),
            entry,
            tuple(methods),
            tuple(protocols),
            tuple(associated_type_bindings),
            tuple(generic_protocol_impls),
        )

    def _record(self) -> GenericRecordSourceV2:
        self._expect_word("record")
        name = self._expect_local_name()
        type_parameters = self._type_parameters()
        self._expect("LBRACE")
        fields: list[tuple[str, str]] = []
        while not self._at("RBRACE"):
            field = self._expect_local_name()
            self._expect("COLON")
            type_text = self._type_text_until({"SEMI"})
            self._expect("SEMI")
            fields.append((field, type_text))
        self._expect("RBRACE")
        if not fields:
            _fail("TEVS_V2_PROGRAM_RECORD", f"generic record {name!r} requires fields")
        return GenericRecordSourceV2(name, type_parameters, tuple(fields))

    def _protocol(self) -> ProtocolSourceV2:
        self._expect_word("protocol")
        name = self._expect_local_name()
        self._expect("LBRACE")
        methods: list[ProtocolMethodSourceV2] = []
        associated_types: list[str] = []
        seen_methods: set[str] = set()
        seen_associated: set[str] = set()
        while not self._at("RBRACE"):
            if self._is_word("type"):
                self._advance()
                associated_name = self._expect_local_name()
                if associated_name in seen_associated:
                    _fail("TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_ASSOCIATED_TYPE", f"duplicate associated type {associated_name!r}")
                seen_associated.add(associated_name)
                self._expect("SEMI")
                associated_types.append(associated_name)
                continue
            self._expect_word("fn")
            method_name = self._expect_local_name()
            if method_name in seen_methods:
                _fail("TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_METHOD", f"duplicate protocol method {method_name!r}")
            seen_methods.add(method_name)
            self._expect("LPAREN")
            receiver_name = self._expect_local_name()
            if receiver_name != "self":
                _fail("TEVS_V2_PROGRAM_PROTOCOL_SELF", "protocol method must declare self as first receiver parameter")
            parameters: list[tuple[str, str]] = []
            if self._match("COMMA"):
                while True:
                    parameter = self._expect_local_name()
                    if parameter == "self":
                        _fail("TEVS_V2_PROGRAM_PROTOCOL_SELF", "self cannot be redeclared as a protocol parameter")
                    self._expect("COLON")
                    type_text = self._type_text_until({"COMMA", "RPAREN"})
                    parameters.append((parameter, type_text))
                    if not self._match("COMMA"):
                        break
            self._expect("RPAREN")
            self._expect("ARROW")
            return_type = self._type_text_until({"SEMI"})
            self._expect("SEMI")
            methods.append(ProtocolMethodSourceV2(method_name, tuple(parameters), return_type))
        self._expect("RBRACE")
        if not methods:
            _fail("TEVS_V2_PROGRAM_PROTOCOL", "protocol requires at least one method")
        return ProtocolSourceV2(name, tuple(methods), tuple(associated_types))

    def _generic_impl(self) -> GenericProtocolImplSourceV2:
        self._expect_word("impl")
        type_parameters, constraints, associated_constraints = self._function_type_parameters(context="generic impl")
        receiver_type = self._type_text_until({"COLON", "LBRACE"})
        implementation_group = f"generic_impl_block_{self.declaration_count}"
        if not self._match("COLON"):
            _fail("TEVS_V2_PROGRAM_GENERIC_IMPL_PROTOCOL", "generic impl must implement exactly one protocol")
        protocol_name = self._expect_local_name()
        self._expect("LBRACE")
        methods: list[MethodSourceV2] = []
        associated_types: list[tuple[str, str]] = []
        seen_associated: set[str] = set()
        while not self._at("RBRACE"):
            if self._is_word("type"):
                self._advance()
                associated_name = self._expect_local_name()
                if associated_name in seen_associated:
                    _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_DUPLICATE", f"duplicate generic impl associated type {associated_name!r}")
                seen_associated.add(associated_name)
                self._expect("EQUAL")
                type_text = self._type_text_until({"SEMI"})
                self._expect("SEMI")
                associated_types.append((associated_name, type_text))
                continue
            self._expect_word("fn")
            name = self._expect_local_name()
            self._expect("LPAREN")
            receiver_name = self._expect_local_name()
            if receiver_name != "self":
                _fail("TEVS_V2_PROGRAM_METHOD_SELF", "generic impl method must declare self as its first receiver parameter")
            parameters: list[tuple[str, str]] = []
            if self._match("COMMA"):
                while True:
                    parameter = self._expect_local_name()
                    if parameter == "self":
                        _fail("TEVS_V2_PROGRAM_METHOD_SELF", "self cannot be redeclared as a generic impl parameter")
                    self._expect("COLON")
                    type_text = self._type_text_until({"COMMA", "RPAREN"})
                    parameters.append((parameter, type_text))
                    if not self._match("COMMA"):
                        break
            self._expect("RPAREN")
            self._expect("ARROW")
            return_type = self._type_text_until({"EQUAL"})
            self._expect("EQUAL")
            body = self._expression(0, 1)
            self._expect("SEMI")
            methods.append(MethodSourceV2(
                receiver_type, name, tuple(parameters), return_type, body,
                (protocol_name,), implementation_group,
            ))
        self._expect("RBRACE")
        if not methods:
            _fail("TEVS_V2_PROGRAM_GENERIC_IMPL", "generic impl requires at least one method")
        return GenericProtocolImplSourceV2(
            type_parameters, receiver_type, protocol_name, tuple(methods),
            tuple(associated_types), implementation_group, constraints, associated_constraints,
        )

    def _impl(self) -> tuple[tuple[MethodSourceV2, ...], tuple[AssociatedTypeBindingSourceV2, ...]]:
        self._expect_word("impl")
        receiver_type = self._type_text_until({"COLON", "LBRACE"})
        implementation_group = f"impl_block_{self.declaration_count}"
        protocol_names: tuple[str, ...] = ()
        if self._match("COLON"):
            protocol_names = (self._expect_local_name(),)
        self._expect("LBRACE")
        methods: list[MethodSourceV2] = []
        associated_types: list[AssociatedTypeBindingSourceV2] = []
        seen_associated: set[str] = set()
        while not self._at("RBRACE"):
            if self._is_word("type"):
                if not protocol_names:
                    _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_IMPL", "associated type binding requires impl Receiver : Protocol")
                self._advance()
                associated_name = self._expect_local_name()
                if associated_name in seen_associated:
                    _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_DUPLICATE", f"duplicate associated type binding {associated_name!r}")
                seen_associated.add(associated_name)
                self._expect("EQUAL")
                type_text = self._type_text_until({"SEMI"})
                self._expect("SEMI")
                associated_types.append(AssociatedTypeBindingSourceV2(receiver_type, protocol_names, associated_name, type_text, implementation_group))
                continue
            self._expect_word("fn")
            name = self._expect_local_name()
            self._expect("LPAREN")
            receiver_name = self._expect_local_name()
            if receiver_name != "self":
                _fail("TEVS_V2_PROGRAM_METHOD_SELF", "impl method must declare self as its first receiver parameter")
            parameters: list[tuple[str, str]] = []
            if self._match("COMMA"):
                while True:
                    parameter = self._expect_local_name()
                    if parameter == "self":
                        _fail("TEVS_V2_PROGRAM_METHOD_SELF", "self cannot be redeclared as a normal method parameter")
                    self._expect("COLON")
                    type_text = self._type_text_until({"COMMA", "RPAREN"})
                    parameters.append((parameter, type_text))
                    if not self._match("COMMA"):
                        break
            self._expect("RPAREN")
            self._expect("ARROW")
            return_type = self._type_text_until({"EQUAL"})
            self._expect("EQUAL")
            body = self._expression(0, 1)
            self._expect("SEMI")
            methods.append(MethodSourceV2(receiver_type, name, tuple(parameters), return_type, body, protocol_names, implementation_group))
        self._expect("RBRACE")
        if not methods:
            _fail("TEVS_V2_PROGRAM_IMPL", "impl requires at least one method")
        return tuple(methods), tuple(associated_types)

    def _function(self, *, require_type_parameters: bool) -> GenericFunctionSourceV2:
        self._expect_word("fn")
        name = self._expect_local_name()
        constraints: tuple[tuple[str, str], ...] = ()
        associated_constraints: tuple[tuple[str, str, str], ...] = ()
        if require_type_parameters:
            type_parameters, constraints, associated_constraints = self._function_type_parameters()
        else:
            if self._at("LT"):
                _fail("TEVS_V2_PROGRAM_GENERIC", "plain fn must not declare type parameters; use generic fn")
            type_parameters = ()
        self._expect("LPAREN")
        parameters: list[tuple[str, str]] = []
        if not self._at("RPAREN"):
            while True:
                parameter = self._expect_local_name()
                self._expect("COLON")
                type_text = self._type_text_until({"COMMA", "RPAREN"})
                parameters.append((parameter, type_text))
                if not self._match("COMMA"):
                    break
        self._expect("RPAREN")
        self._expect("ARROW")
        return_type = self._type_text_until({"EQUAL"})
        self._expect("EQUAL")
        body = self._expression(0, 1)
        self._expect("SEMI")
        return GenericFunctionSourceV2(
            name, type_parameters, tuple(parameters), return_type, body, constraints, associated_constraints
        )

    def _recursive_function(self) -> RecursiveFunctionSourceV2:
        self._expect_word("fn")
        name = self._expect_local_name()
        type_parameters = self._type_parameters() if self._at("LT") else ()
        self._expect("LPAREN")
        parameters: list[tuple[str, str]] = []
        if not self._at("RPAREN"):
            while True:
                parameter = self._expect_local_name()
                self._expect("COLON")
                type_text = self._type_text_until({"COMMA", "RPAREN"})
                parameters.append((parameter, type_text))
                if not self._match("COMMA"):
                    break
        self._expect("RPAREN")
        self._expect("ARROW")
        return_type = self._type_text_until_word("decreases")
        self._expect_word("decreases")
        measure_parameter = self._expect_local_name()
        self._expect_word("max_depth")
        max_depth_token = self._expect("NUMBER")
        if "." in max_depth_token.text:
            _fail("TEVS_V2_PROGRAM_RECURSION", "max_depth must be an integer")
        max_depth = int(max_depth_token.text, 10)
        maximum_steps = 1_000_000
        if self._is_word("max_steps"):
            self._advance()
            max_steps_token = self._expect("NUMBER")
            if "." in max_steps_token.text:
                _fail("TEVS_V2_PROGRAM_RECURSION", "max_steps must be an integer")
            maximum_steps = int(max_steps_token.text, 10)
        self._expect("EQUAL")
        body = self._expression(0, 1)
        self._expect("SEMI")
        return RecursiveFunctionSourceV2(
            name,
            type_parameters,
            tuple(parameters),
            return_type,
            body,
            measure_parameter,
            max_depth,
            maximum_steps,
        )

    def _entry(self) -> EntrySourceV2:
        self._expect_word("entry")
        name = self._expect_local_name()
        self._expect("COLON")
        declared_type = self._type_text_until({"EQUAL"})
        self._expect("EQUAL")
        if self._entry_rhs_is_direct_call():
            function_name = self._expect_local_name()
            type_arguments = self._source_type_argument_list() if self._at("LT") else ()
            self._expect("LPAREN")
            arguments: list[str] = []
            if not self._at("RPAREN"):
                while True:
                    arguments.append(self._raw_argument_text())
                    if not self._match("COMMA"):
                        break
            self._expect("RPAREN")
            self._expect("SEMI")
            return EntrySourceV2(name, declared_type, function_name, type_arguments, tuple(arguments))
        expression = self._expression(0, 1)
        self._expect("SEMI")
        return EntrySourceV2(name, declared_type, "", (), (), expression)

    def _entry_rhs_is_direct_call(self) -> bool:
        if not self._at("IDENT"):
            return False
        cursor = self.index + 1
        if cursor >= len(self.tokens):
            return False
        if self.tokens[cursor].kind == "LT":
            angle = 0
            while cursor < len(self.tokens):
                token = self.tokens[cursor]
                if token.kind == "LT":
                    angle += 1
                elif token.kind == "GT":
                    angle -= 1
                    if angle == 0:
                        cursor += 1
                        break
                    if angle < 0:
                        return False
                elif token.kind in {"SEMI", "EQUAL", "ARROW", "FAT_ARROW", "EOF"}:
                    return False
                cursor += 1
            if angle != 0:
                return False
        if cursor >= len(self.tokens) or self.tokens[cursor].kind != "LPAREN":
            return False
        paren = 0
        while cursor < len(self.tokens):
            token = self.tokens[cursor]
            if token.kind == "LPAREN":
                paren += 1
            elif token.kind == "RPAREN":
                paren -= 1
                if paren == 0:
                    return cursor + 1 < len(self.tokens) and self.tokens[cursor + 1].kind == "SEMI"
                if paren < 0:
                    return False
            elif token.kind == "EOF":
                return False
            cursor += 1
        return False

    def _function_type_parameters(
        self,
        *,
        context: str = "generic function",
    ) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...], tuple[tuple[str, str, str], ...]]:
        self._expect("LT")
        parameters: list[str] = []
        constraints: list[tuple[str, str]] = []
        associated_constraints: list[tuple[str, str, str]] = []
        while True:
            parameter = self._expect_local_name()
            parameters.append(parameter)
            parameter_constraints: list[tuple[str, str]] = []
            parameter_associated_constraints: list[tuple[str, str, str]] = []
            if self._match("COLON"):
                while True:
                    protocol_name = self._expect_local_name()
                    parameter_constraints.append((parameter, protocol_name))
                    if self._match("LT"):
                        seen_associated: set[str] = set()
                        if self._at("GT"):
                            _fail(
                                "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT",
                                f"protocol refinement for {parameter!r} requires at least one associated equality",
                            )
                        while True:
                            associated_name = self._expect_local_name()
                            if associated_name in seen_associated:
                                _fail(
                                    "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_DUPLICATE",
                                    f"duplicate associated refinement {parameter}::{associated_name}",
                                )
                            seen_associated.add(associated_name)
                            self._expect("EQUAL")
                            required_type = self._type_text_until({"COMMA", "GT"})
                            parameter_associated_constraints.append((parameter, associated_name, required_type))
                            if not self._match("COMMA"):
                                break
                            if self._at("GT"):
                                _fail(
                                    "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT",
                                    "associated refinement list cannot end with a comma",
                                )
                        self._expect("GT")
                    if not self._match("PLUS"):
                        break
                protocol_names = [protocol_name for _parameter, protocol_name in parameter_constraints]
                if len(set(protocol_names)) != len(protocol_names):
                    _fail(
                        "TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_DUPLICATE",
                        f"protocol intersection for {parameter!r} repeats a protocol",
                    )
                parameter_constraints.sort(key=lambda item: item[1])
                parameter_associated_constraints.sort(key=lambda item: (item[1], item[2]))
                constraints.extend(parameter_constraints)
                associated_constraints.extend(parameter_associated_constraints)
            if not self._match("COMMA"):
                break
        self._expect("GT")
        if not parameters or len(parameters) > 16 or len(set(parameters)) != len(parameters):
            _fail("TEVS_V2_PROGRAM_GENERIC", f"{context} requires 1..16 unique type parameters")
        return tuple(parameters), tuple(constraints), tuple(associated_constraints)

    def _type_parameters(self) -> tuple[str, ...]:
        self._expect("LT")
        result: list[str] = []
        while True:
            result.append(self._expect_local_name())
            if not self._match("COMMA"):
                break
        self._expect("GT")
        if not result or len(result) > 16 or len(set(result)) != len(result):
            _fail("TEVS_V2_PROGRAM_GENERIC", "generic declaration requires 1..16 unique type parameters")
        return tuple(result)

    def _looks_like_call_type_arguments(self) -> bool:
        if not self._at("LT"):
            return False
        depth = 0
        cursor = self.index
        while cursor < len(self.tokens):
            token = self.tokens[cursor]
            if token.kind == "LT":
                depth += 1
            elif token.kind == "GT":
                depth -= 1
                if depth == 0:
                    return cursor + 1 < len(self.tokens) and self.tokens[cursor + 1].kind == "LPAREN"
                if depth < 0:
                    return False
            elif token.kind in {"SEMI", "EQUAL", "ARROW", "FAT_ARROW", "EOF"} and depth > 0:
                return False
            cursor += 1
        return False

    def _source_type_argument_list(self) -> tuple[str, ...]:
        self._expect("LT")
        result: list[str] = []
        while True:
            result.append(self._type_text_until({"COMMA", "GT"}))
            if not self._match("COMMA"):
                break
        self._expect("GT")
        return tuple(result)

    def _type_text_until_word(self, word: str) -> str:
        start = self.index
        angle = 0
        while True:
            token = self._current()
            if token.kind == "EOF":
                _fail("TEVS_V2_PROGRAM_TYPE", f"unterminated type expression before {word!r}")
            if angle == 0 and token.kind == "IDENT" and token.text == word:
                break
            if token.kind == "LT":
                angle += 1
            elif token.kind == "GT":
                if angle == 0:
                    _fail("TEVS_V2_PROGRAM_TYPE", "unbalanced > in type expression")
                angle -= 1
            self._advance()
        if self.index == start or angle != 0:
            _fail("TEVS_V2_PROGRAM_TYPE", "empty or unbalanced type expression")
        return _canonical_token_text(self.tokens[start:self.index])

    def _type_text_until(self, stops: set[str]) -> str:
        start = self.index
        angle = 0
        while True:
            token = self._current()
            if token.kind == "EOF":
                _fail("TEVS_V2_PROGRAM_TYPE", "unterminated type expression")
            if token.kind == "GE" and angle > 0 and "EQUAL" in stops:
                # In a type context `T>=expr` means closing generic `>` followed by assignment `=`.
                # Preserve `>=` as a comparison everywhere outside the type parser.
                self.tokens[self.index:self.index + 1] = [
                    _Token("GT", ">", None, token.start, token.start + 1),
                    _Token("EQUAL", "=", None, token.start + 1, token.end),
                ]
                token = self._current()
            if angle == 0 and token.kind in stops:
                break
            if token.kind == "LT":
                angle += 1
            elif token.kind == "GT":
                if angle == 0:
                    if "GT" in stops:
                        break
                    _fail("TEVS_V2_PROGRAM_TYPE", "unbalanced > in type expression")
                angle -= 1
            self._advance()
        if self.index == start or angle != 0:
            _fail("TEVS_V2_PROGRAM_TYPE", "empty or unbalanced type expression")
        return _canonical_token_text(self.tokens[start:self.index])

    def _raw_argument_text(self) -> str:
        start_index = self.index
        paren = bracket = brace = angle = 0
        while True:
            token = self._current()
            if token.kind == "EOF":
                _fail("TEVS_V2_PROGRAM_ENTRY", "unterminated entry argument")
            if paren == bracket == brace == angle == 0 and token.kind in {"COMMA", "RPAREN"}:
                break
            if token.kind == "LPAREN": paren += 1
            elif token.kind == "RPAREN":
                if paren == 0: break
                paren -= 1
            elif token.kind == "LBRACKET": bracket += 1
            elif token.kind == "RBRACKET": bracket -= 1
            elif token.kind == "LBRACE": brace += 1
            elif token.kind == "RBRACE": brace -= 1
            elif token.kind == "LT": angle += 1
            elif token.kind == "GT" and angle > 0: angle -= 1
            if min(paren, bracket, brace, angle) < 0:
                _fail("TEVS_V2_PROGRAM_ENTRY", "unbalanced entry argument")
            self._advance()
        if self.index == start_index or any((paren, bracket, brace, angle)):
            _fail("TEVS_V2_PROGRAM_ENTRY", "empty or unbalanced entry argument")
        first = self.tokens[start_index]
        last = self.tokens[self.index - 1]
        return self.source[first.start:last.end].strip()

    def _expression(self, min_prec: int, depth: int) -> SourceExprV2:
        if depth > MAX_SOURCE_EXPRESSION_NESTING_V2:
            _fail("TEVS_V2_PROGRAM_EXPRESSION", f"expression nesting exceeds {MAX_SOURCE_EXPRESSION_NESTING_V2}")
        left = self._unary(depth + 1)
        while True:
            operator = _binary_operator(self._current())
            if operator is None:
                break
            precedence = _BINARY_PRECEDENCE[operator]
            if precedence < min_prec:
                break
            self._advance()
            right = self._expression(precedence + 1, depth + 1)
            left = SourceExprV2("binary", operator, (left, right))
        return left

    def _unary(self, depth: int) -> SourceExprV2:
        if self._match("MINUS"):
            return SourceExprV2("unary", "MINUS", (self._unary(depth + 1),))
        if self._is_word("not"):
            self._advance()
            return SourceExprV2("unary", "NOT", (self._unary(depth + 1),))
        return self._postfix(depth + 1)

    def _postfix(self, depth: int) -> SourceExprV2:
        value = self._primary(depth + 1)
        while self._match("DOT"):
            member = self._expect_local_name()
            if self._match("LPAREN"):
                arguments = self._comma_expressions("RPAREN", depth + 1)
                self._expect("RPAREN")
                value = SourceExprV2("method_call", member, (value, *arguments))
            else:
                value = SourceExprV2("field", member, (value,))
        return value

    def _primary(self, depth: int) -> SourceExprV2:
        token = self._current()
        if token.kind == "NUMBER":
            self._advance()
            return SourceExprV2("number", token.text)
        if token.kind == "STRING":
            self._advance()
            return SourceExprV2("string", token.value)
        if self._is_word("true") or self._is_word("false"):
            self._advance()
            return SourceExprV2("bool", token.text == "true")
        if self._is_word("if"):
            self._advance()
            condition = self._expression(0, depth + 1)
            self._expect_word("then")
            then_expr = self._expression(0, depth + 1)
            self._expect_word("else")
            else_expr = self._expression(0, depth + 1)
            return SourceExprV2("if", None, (condition, then_expr, else_expr))
        if self._is_word("select"):
            self._advance(); self._expect_word("first_within"); self._expect("LBRACE")
            candidates: list[SourceExprV2] = []
            while not self._at("RBRACE"):
                if len(candidates)>=MAX_PURE_TASKS_V4:
                    _fail("TEVS_V2_PROGRAM_SELECT_BOUND",f"select first_within supports at most {MAX_PURE_TASKS_V4} candidates")
                candidate=self._expression(0,depth+1)
                if candidate.kind!="step_limit":
                    _fail("TEVS_V2_PROGRAM_SELECT_CANDIDATE","select first_within candidates must use within_steps")
                candidates.append(candidate); self._expect("SEMI")
            self._expect("RBRACE")
            if not candidates:
                _fail("TEVS_V2_PROGRAM_SELECT_BOUND","select first_within requires at least one candidate")
            return SourceExprV2("priority_select",PRIORITY_SELECT_POLICY_V4,tuple(candidates))
        if self._is_word("within_steps"):
            self._advance()
            maximum_token=self._expect("NUMBER")
            if "." in maximum_token.text:
                _fail("TEVS_V2_PROGRAM_STEP_LIMIT","within_steps requires an integer step limit")
            maximum_steps=int(maximum_token.text,10)
            if not 1<=maximum_steps<=MAX_PURE_EVAL_STEPS_V4:
                _fail("TEVS_V2_PROGRAM_STEP_LIMIT",f"within_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
            self._expect_word("do")
            body=self._expression(0,depth+1)
            return SourceExprV2("step_limit",maximum_steps,(body,))
        if self._is_word("task") and self._peek().kind == "IDENT" and self._peek().text == "scope":
            self._advance(); self._expect_word("scope"); self._expect("LBRACE")
            bindings: list[tuple[str, str]] = []
            bodies: list[SourceExprV2] = []
            seen: set[str] = set()
            while self._is_word("spawn"):
                self._advance()
                name = self._expect_local_name()
                if name in seen:
                    _fail("TEVS_V2_PROGRAM_TASK_DAG_BINDING", f"duplicate spawned task {name!r}")
                if len(bindings) >= MAX_PURE_TASKS_V4:
                    _fail("TEVS_V2_PROGRAM_TASK_DAG_BOUND", f"task scope supports at most {MAX_PURE_TASKS_V4} spawned tasks")
                seen.add(name)
                self._expect("COLON")
                type_text = self._type_text_until({"EQUAL"})
                self._expect("EQUAL")
                body = self._expression(0, depth + 1)
                self._expect("SEMI")
                bindings.append((name, type_text)); bodies.append(body)
            if not bindings:
                _fail("TEVS_V2_PROGRAM_TASK_DAG_BOUND", "task scope requires at least one spawn")
            self._expect_word("return")
            join = self._expression(0, depth + 1)
            self._expect("SEMI"); self._expect("RBRACE")
            return SourceExprV2("task_dag", tuple(bindings), (*bodies, join))
        if self._is_word("await"):
            self._advance()
            if not self._is_word("all"):
                return SourceExprV2("task_await", self._expect_local_name())
            self._advance()
            self._expect("LPAREN")
            bindings: list[tuple[str, str]] = []
            bodies: list[SourceExprV2] = []
            seen: set[str] = set()
            if self._at("RPAREN"):
                _fail("TEVS_V2_PROGRAM_TASK", "await all requires at least one child task")
            while True:
                name = self._expect_local_name()
                if name.startswith("__tev_"):
                    _fail("TEVS_V2_PROGRAM_TASK_BINDING", "task binding uses reserved compiler prefix")
                if name in seen:
                    _fail("TEVS_V2_PROGRAM_TASK_BINDING", f"duplicate task binding {name!r}")
                seen.add(name)
                if len(bindings) >= MAX_PURE_TASKS_V4:
                    _fail("TEVS_V2_PROGRAM_TASK_BOUND", f"await all supports at most {MAX_PURE_TASKS_V4} child tasks")
                self._expect("COLON")
                type_text = self._type_text_until({"EQUAL"})
                self._expect("EQUAL")
                body = self._expression(0, depth + 1)
                bindings.append((name, type_text))
                bodies.append(body)
                if not self._match("COMMA"):
                    break
                if self._at("RPAREN"):
                    break
            self._expect("RPAREN")
            self._expect("FAT_ARROW")
            join = self._expression(0, depth + 1)
            return SourceExprV2("task_scope", tuple(bindings), (*bodies, join))
        if self._is_word("while"):
            self._advance()
            accumulator_name = self._expect_local_name()
            self._expect("COLON")
            accumulator_type = self._type_text_until({"EQUAL"})
            self._expect("EQUAL")
            initial = self._expression(0, depth + 1)
            self._expect_word("when")
            condition = self._expression(0, depth + 1)
            self._expect_word("max_iterations")
            maximum_token = self._expect("NUMBER")
            if "." in maximum_token.text:
                _fail("TEVS_V2_PROGRAM_WHILE", "max_iterations must be an integer")
            maximum_iterations = int(maximum_token.text, 10)
            self._expect_word("do")
            body = self._expression(0, depth + 1)
            return SourceExprV2(
                "while",
                (accumulator_name, accumulator_type, maximum_iterations),
                (initial, condition, body),
            )
        if self._is_word("for"):
            self._advance()
            bindings = [self._expect_local_name()]
            if self._match("COMMA"):
                bindings.append(self._expect_local_name())
            self._expect_word("in")
            collection = self._expression(0, depth + 1)
            self._expect_word("fold")
            accumulator_name = self._expect_local_name()
            self._expect("COLON")
            accumulator_type = self._type_text_until({"EQUAL"})
            self._expect("EQUAL")
            initial = self._expression(0, depth + 1)
            self._expect_word("do")
            body = self._expression(0, depth + 1)
            return SourceExprV2(
                "for_fold",
                (tuple(bindings), accumulator_name, accumulator_type),
                (collection, initial, body),
            )
        if self._is_word("match"):
            self._advance()
            subject = self._expression(0, depth + 1)
            self._expect("LBRACE")
            patterns: list[tuple[str, str | None]] = []
            bodies: list[SourceExprV2] = []
            while not self._at("RBRACE"):
                variant = self._expect_local_name()
                binding: str | None = None
                if self._match("LPAREN"):
                    binding = self._expect_local_name()
                    self._expect("RPAREN")
                self._expect("FAT_ARROW")
                body = self._expression(0, depth + 1)
                self._expect("SEMI")
                patterns.append((variant, binding))
                bodies.append(body)
            self._expect("RBRACE")
            if not patterns:
                _fail("TEVS_V2_PROGRAM_MATCH", "match requires at least one arm")
            return SourceExprV2("match", tuple(patterns), (subject, *bodies))
        if self._is_word("set") and self._peek().kind == "LBRACE":
            self._advance()
            return SourceExprV2("set", None, self._braced_items(depth + 1))
        if self._is_word("map") and self._peek().kind == "LBRACE":
            self._advance()
            self._expect("LBRACE")
            pairs: list[SourceExprV2] = []
            if not self._at("RBRACE"):
                while True:
                    key = self._expression(0, depth + 1)
                    self._expect("COLON")
                    value = self._expression(0, depth + 1)
                    pairs.append(SourceExprV2("pair", None, (key, value)))
                    if not self._match("COMMA"):
                        break
                    if self._at("RBRACE"):
                        break
            self._expect("RBRACE")
            return SourceExprV2("map", None, tuple(pairs))
        if token.kind == "LBRACKET":
            self._advance()
            items = self._comma_expressions("RBRACKET", depth + 1)
            self._expect("RBRACKET")
            return SourceExprV2("bracket", None, items)
        if token.kind == "LPAREN":
            self._advance()
            value = self._expression(0, depth + 1)
            self._expect("RPAREN")
            return value
        if token.kind == "IDENT":
            self._advance()
            name = token.text
            type_arguments: tuple[str, ...] = ()
            if self._at("LT") and self._looks_like_call_type_arguments():
                type_arguments = self._source_type_argument_list()
            if self._at("LPAREN"):
                self._advance()
                positional: list[SourceExprV2] = []
                named: list[tuple[str, SourceExprV2]] = []
                if not self._at("RPAREN"):
                    while True:
                        if self._at("IDENT") and self._peek().kind == "EQUAL":
                            field = self._advance().text
                            self._expect("EQUAL")
                            named.append((field, self._expression(0, depth + 1)))
                        else:
                            positional.append(self._expression(0, depth + 1))
                        if not self._match("COMMA"):
                            break
                        if self._at("RPAREN"):
                            break
                self._expect("RPAREN")
                if positional and named:
                    _fail("TEVS_V2_PROGRAM_CALL", "a V2 call cannot mix positional and named arguments")
                return SourceExprV2(
                    "call",
                    (name, type_arguments, tuple(field for field, _ in named)),
                    tuple(positional) if positional else tuple(value for _, value in named),
                )
            if type_arguments:
                _fail("TEVS_V2_PROGRAM_CALL", f"explicit type arguments on {name!r} require a call")
            if "." in name:
                parts = name.split(".")
                value = SourceExprV2("name", parts[0])
                for field in parts[1:]:
                    value = SourceExprV2("field", field, (value,))
                return value
            return SourceExprV2("name", name)
        _fail("TEVS_V2_PROGRAM_EXPRESSION", f"unexpected expression token {token.text!r}")

    def _braced_items(self, depth: int) -> tuple[SourceExprV2, ...]:
        self._expect("LBRACE")
        items = self._comma_expressions("RBRACE", depth + 1)
        self._expect("RBRACE")
        return items

    def _comma_expressions(self, close: str, depth: int) -> tuple[SourceExprV2, ...]:
        result: list[SourceExprV2] = []
        if self._at(close):
            return ()
        while True:
            result.append(self._expression(0, depth + 1))
            if not self._match("COMMA"):
                break
            if self._at(close):
                break
        return tuple(result)

    def _expect_local_name(self) -> str:
        value = self._expect("IDENT").text
        if _NAME.fullmatch(value) is None:
            _fail("TEVS_V2_PROGRAM_NAME", f"expected local name, got {value!r}")
        if value.startswith("__tev_"):
            _fail("TEVS_V2_PROGRAM_RESERVED_NAME", f"source name {value!r} uses reserved compiler prefix '__tev_'")
        return value

    def _current(self) -> _Token: return self.tokens[self.index]
    def _peek(self, offset: int = 1) -> _Token: return self.tokens[min(self.index + offset, len(self.tokens) - 1)]
    def _at(self, kind: str) -> bool: return self._current().kind == kind
    def _advance(self) -> _Token:
        token = self._current(); self.index += 1; return token
    def _match(self, kind: str) -> bool:
        if self._at(kind): self.index += 1; return True
        return False
    def _expect(self, kind: str) -> _Token:
        token = self._current()
        if token.kind != kind:
            _fail("TEVS_V2_PROGRAM_SYNTAX", f"expected {kind}, got {token.kind} {token.text!r} at offset {token.start}")
        self.index += 1
        return token
    def _is_word(self, word: str) -> bool: return self._at("IDENT") and self._current().text == word
    def _expect_word(self, word: str) -> None:
        token = self._expect("IDENT")
        if token.text != word:
            _fail("TEVS_V2_PROGRAM_SYNTAX", f"expected {word!r}, got {token.text!r} at offset {token.start}")


class _DeferredProtocolWitnessV2(Exception):
    def __init__(self, protocol_name: str, receiver_source_type: str) -> None:
        super().__init__(protocol_name, receiver_source_type)
        self.protocol_name = protocol_name
        self.receiver_source_type = receiver_source_type

    @property
    def key(self) -> tuple[str, str]:
        return (self.protocol_name, self.receiver_source_type)


class _ExpressionLowererV2:
    def __init__(
        self,
        type_parameters: Sequence[str],
        parameters: Sequence[tuple[str, str]],
        return_type: str,
        records: Mapping[str, GenericRecordSourceV2],
        generic_arities: Mapping[str, int],
        *,
        self_parameter_types: Sequence[tuple[str, str]] | None = None,
        self_return_type: str | None = None,
        function_sources: Mapping[str, GenericFunctionSourceV2] | None = None,
        recursive_function_names: Sequence[str] = (),
        method_dispatch: Mapping[tuple[str, str], str] | None = None,
        protocol_witness_index: Mapping[tuple[str, str], ProtocolWitnessV2] | None = None,
        protocol_hashes: Mapping[str, str] | None = None,
        protocol_methods: Mapping[str, frozenset[str]] | None = None,
        constrained_template_hashes: Mapping[str, str] | None = None,
        constrained_specializations: dict[str, ConstrainedFunctionSpecializationV2] | None = None,
        type_registry: GenericRegistryV2 | None = None,
        constrained_parameter_methods: Mapping[str, frozenset[str]] | None = None,
        defer_missing_witnesses: bool = False,
        used_constrained_specializations: set[str] | None = None,
        inline_stack: tuple[str, ...] = (),
        inline_counter: list[int] | None = None,
        parameter_ir_names: Mapping[str, str] | None = None,
        type_substitutions: Mapping[str, TypeRefV2] | None = None,
        associated_type_substitutions: Mapping[tuple[str, str], TypeRefV2] | None = None,
        protocol_witness_resolver: Callable[[str, str, dict[str, ConstrainedFunctionSpecializationV2], bool], _ProtocolWitnessResolutionV2 | None] | None = None,
        generic_method_resolver: Callable[[str, str, dict[str, ConstrainedFunctionSpecializationV2], bool], _ProtocolWitnessResolutionV2 | None] | None = None,
    ) -> None:
        self.type_parameters = set(type_parameters)
        self.generic_arities = dict(generic_arities)
        self.records = dict(records)
        self.type_substitutions = dict(type_substitutions or {})
        self.associated_type_substitutions = dict(associated_type_substitutions or {})
        self.parameter_types: dict[str, str] = {}
        for name, type_text in parameters:
            if name in self.parameter_types:
                _fail("TEVS_V2_PROGRAM_PARAMETER", f"duplicate parameter {name!r}")
            self.parameter_types[name] = self._specialize_type_text(type_text)
        self.return_type = self._specialize_type_text(return_type)
        self.self_parameter_types = (
            tuple(self._specialize_type_text(type_text) for _name, type_text in self_parameter_types)
            if self_parameter_types is not None
            else None
        )
        self.self_return_type = (
            self._specialize_type_text(self_return_type)
            if self_return_type is not None
            else None
        )
        if (self.self_parameter_types is None) != (self.self_return_type is None):
            _fail("TEVS_V2_PROGRAM_RECURSION", "self call signature must be supplied completely or not at all")
        self.function_sources = dict(function_sources or {})
        self.recursive_function_names = frozenset(recursive_function_names)
        self.method_dispatch = dict(method_dispatch or {})
        self.protocol_witness_index = dict(protocol_witness_index or {})
        self.protocol_hashes = dict(protocol_hashes or {})
        self.protocol_methods = dict(protocol_methods or {})
        self.constrained_template_hashes = dict(constrained_template_hashes or {})
        self.constrained_specializations = constrained_specializations if constrained_specializations is not None else {}
        self.type_registry = type_registry
        self.constrained_parameter_methods = dict(constrained_parameter_methods or {})
        self.defer_missing_witnesses = bool(defer_missing_witnesses)
        self.used_constrained_specializations = used_constrained_specializations if used_constrained_specializations is not None else set()
        self.protocol_witness_resolver = protocol_witness_resolver
        self.generic_method_resolver = generic_method_resolver
        self.inline_stack = tuple(inline_stack)
        self.inline_counter = inline_counter if inline_counter is not None else [0]
        self.parameter_ir_names = dict(parameter_ir_names or {})

    def _specialize_type_text(self, type_text: str) -> str:
        ref = parse_type_ref_v2(type_text, self.generic_arities)
        return _render_type(_substitute_type(ref, self.type_substitutions, self.associated_type_substitutions))

    def lower(self, expression: SourceExprV2, *, expected: str | None = None) -> _Lowered:
        expected = self._specialize_type_text(expected) if expected is not None else None
        kind = expression.kind
        if kind == "name":
            name = str(expression.value)
            actual = self.parameter_types.get(name)
            if actual is None:
                if name == "None":
                    return self._none(expected)
                _fail("TEVS_V2_PROGRAM_NAME", f"unknown value name {name!r}")
            _require_expected(actual, expected, self.generic_arities)
            return _Lowered(
                actual,
                {"op": "PARAM", "name": self.parameter_ir_names.get(name, name), "type": actual},
            )
        if kind == "number":
            raw = str(expression.value)
            inferred = "Rat" if "." in raw else "Int"
            actual = expected if expected in {"Int", "Rat"} else inferred
            if actual == "Int":
                if "." in raw:
                    _fail("TEVS_V2_PROGRAM_LITERAL", f"decimal literal {raw!r} cannot be Int")
                encoded = {"$int": str(int(raw, 10))}
            elif actual == "Rat":
                value = Fraction(raw)
                encoded = {"$rat": [str(value.numerator), str(value.denominator)]}
            else:
                _fail("TEVS_V2_PROGRAM_LITERAL", f"numeric literal cannot satisfy expected type {expected!r}")
            return _Lowered(actual, {"op": "CONST", "type": actual, "value": encoded})
        if kind == "string":
            _require_expected("Text", expected, self.generic_arities)
            return _Lowered("Text", {"op": "CONST", "type": "Text", "value": expression.value})
        if kind == "bool":
            _require_expected("Bool", expected, self.generic_arities)
            return _Lowered("Bool", {"op": "CONST", "type": "Bool", "value": bool(expression.value)})
        if kind == "unary":
            operator = str(expression.value)
            child = self.lower(expression.children[0])
            if operator == "NOT":
                if child.type_text != "Bool": _fail("TEVS_V2_PROGRAM_OPERATOR", "not requires Bool")
                actual = "Bool"
            elif operator == "MINUS" and child.type_text in {"Int", "Rat"}:
                actual = child.type_text
            else:
                _fail("TEVS_V2_PROGRAM_OPERATOR", f"invalid unary {operator} for {child.type_text}")
            _require_expected(actual, expected, self.generic_arities)
            return _Lowered(actual, {"op": "UNARY", "operator": operator, "operand_type": child.type_text, "result_type": actual, "operand": child.ir})
        if kind == "binary":
            return self._binary(expression, expected)
        if kind == "field":
            return self._field_expression(expression, expected)
        if kind == "method_call":
            return self._method_call_expression(expression, expected)
        if kind == "if":
            condition = self.lower(expression.children[0], expected="Bool")
            then_value = self.lower(expression.children[1], expected=expected) if expected is not None else self.lower(expression.children[1])
            branch_type = then_value.type_text
            else_value = self.lower(expression.children[2], expected=branch_type)
            _require_expected(branch_type, expected, self.generic_arities)
            return _Lowered(branch_type, {"op": "IF", "result_type": branch_type, "condition": condition.ir, "then": then_value.ir, "else": else_value.ir})
        if kind == "priority_select":
            return self._priority_select_expression(expression, expected)
        if kind == "step_limit":
            return self._step_limit_expression(expression, expected)
        if kind == "task_scope":
            return self._task_scope_expression(expression, expected)
        if kind == "task_dag":
            return self._task_dag_expression(expression, expected)
        if kind == "task_await":
            _fail("TEVS_V2_PROGRAM_TASK_AWAIT", "await <task> is only valid inside task scope")
        if kind == "while":
            return self._while_expression(expression, expected)
        if kind == "for_fold":
            return self._for_fold_expression(expression, expected)
        if kind == "match":
            return self._match_expression(expression, expected)
        if kind == "bracket":
            if expected is None:
                _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", "[...] requires expected List<T,N> or Array<T,N>")
            ref = parse_type_ref_v2(expected, self.generic_arities)
            if ref.kind not in {"list", "array"}:
                _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"[...] cannot construct {expected}")
            item_type = _render_type(ref.arguments[0])
            items = [self.lower(item, expected=item_type).ir for item in expression.children]
            op = "LIST" if ref.kind == "list" else "ARRAY"
            return _Lowered(expected, {"op": op, "type": expected, "items": items})
        if kind == "set":
            if expected is None:
                _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", "set{...} requires expected Set<T,N>")
            ref = parse_type_ref_v2(expected, self.generic_arities)
            if ref.kind != "set": _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"set{{...}} cannot construct {expected}")
            item_type = _render_type(ref.arguments[0])
            items = [self.lower(item, expected=item_type).ir for item in expression.children]
            return _Lowered(expected, {"op": "SET", "type": expected, "items": items})
        if kind == "map":
            if expected is None:
                _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", "map{...} requires expected Map<K,V,N>")
            ref = parse_type_ref_v2(expected, self.generic_arities)
            if ref.kind != "map": _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"map{{...}} cannot construct {expected}")
            key_type, value_type = (_render_type(item) for item in ref.arguments)
            entries = []
            for pair in expression.children:
                key = self.lower(pair.children[0], expected=key_type)
                value = self.lower(pair.children[1], expected=value_type)
                entries.append({"key": key.ir, "value": value.ir})
            return _Lowered(expected, {"op": "MAP", "type": expected, "entries": entries})
        if kind == "call":
            return self._call(expression, expected)
        _fail("TEVS_V2_PROGRAM_EXPRESSION", f"unsupported source expression kind {kind!r}")

    def _field_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        if len(expression.children) != 1:
            _fail("TEVS_V2_PROGRAM_FIELD", "field access requires exactly one receiver")
        field_name = str(expression.value)
        receiver = self.lower(expression.children[0])
        receiver_ref = parse_type_ref_v2(receiver.type_text, self.generic_arities)
        if receiver_ref.kind != "user_generic":
            _fail("TEVS_V2_PROGRAM_FIELD", f"field access requires a declared record receiver, got {receiver.type_text}")
        declaration = self.records.get(receiver_ref.name)
        if declaration is None:
            _fail("TEVS_V2_PROGRAM_FIELD", f"record type {receiver_ref.name!r} is not declared in this program")
        if len(receiver_ref.arguments) != len(declaration.type_parameters):
            _fail("TEVS_V2_PROGRAM_FIELD", f"record type argument mismatch for {receiver_ref.name!r}")
        field_types = dict(declaration.fields)
        field_source_type = field_types.get(field_name)
        if field_source_type is None:
            _fail("TEVS_V2_PROGRAM_FIELD", f"record {receiver_ref.name!r} has no field {field_name!r}")
        substitutions = dict(zip(declaration.type_parameters, receiver_ref.arguments, strict=True))
        field_ref = parse_type_ref_v2(field_source_type, self.generic_arities)
        field_type = _render_type(_substitute_type(field_ref, substitutions))
        _require_expected(field_type, expected, self.generic_arities)
        return _Lowered(
            field_type,
            {
                "op": "FIELD",
                "record_type": receiver.type_text,
                "field": field_name,
                "result_type": field_type,
                "record": receiver.ir,
            },
        )

    def _method_call_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        if not expression.children:
            _fail("TEVS_V2_PROGRAM_METHOD_CALL", "method call requires a receiver")
        method_name = str(expression.value)
        receiver_source = expression.children[0]
        if receiver_source.kind == "name":
            constrained_methods = self.constrained_parameter_methods.get(str(receiver_source.value))
            if constrained_methods is not None and method_name not in constrained_methods:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_METHOD",
                    f"method {method_name!r} is not declared by the active protocol constraint for {receiver_source.value!r}",
                )
        counter_before = self.inline_counter[0]
        receiver = self.lower(receiver_source)
        self.inline_counter[0] = counter_before
        receiver_type = self._specialize_type_text(receiver.type_text)
        symbol = self.method_dispatch.get((receiver_type, method_name))
        if symbol is None and self.generic_method_resolver is not None:
            resolution = self.generic_method_resolver(
                receiver_type,
                method_name,
                self.constrained_specializations,
                self.defer_missing_witnesses,
            )
            if resolution is not None:
                self.protocol_witness_index[(resolution.witness.protocol_name, receiver_type)] = resolution.witness
                self.method_dispatch.update(dict(resolution.method_dispatch))
                self.function_sources.update(dict(resolution.function_sources))
                symbol = self.method_dispatch.get((receiver_type, method_name))
        if symbol is None:
            _fail(
                "TEVS_V2_PROGRAM_METHOD_DISPATCH",
                f"no method {method_name!r} is implemented for receiver type {receiver_type}",
            )
        return self._inline_pure_call(
            symbol,
            (),
            (),
            (receiver_source, *expression.children[1:]),
            expected,
        )

    def _priority_select_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        if expression.value!=PRIORITY_SELECT_POLICY_V4 or not 1<=len(expression.children)<=MAX_PURE_TASKS_V4:
            _fail("TEVS_V2_PROGRAM_SELECT_BOUND",f"select first_within requires 1..{MAX_PURE_TASKS_V4} candidates")
        candidates=[]; result_type=expected
        for index,candidate in enumerate(expression.children):
            if candidate.kind!="step_limit" or len(candidate.children)!=1:
                _fail("TEVS_V2_PROGRAM_SELECT_CANDIDATE","select first_within candidates must use within_steps")
            maximum_steps=int(candidate.value)
            body=self.lower(candidate.children[0],expected=result_type) if result_type is not None else self.lower(candidate.children[0])
            if result_type is None:
                result_type=body.type_text
            _require_expected(body.type_text,result_type,self.generic_arities)
            candidates.append({"maximum_steps":maximum_steps,"body":body.ir})
        assert result_type is not None
        _require_expected(result_type,expected,self.generic_arities)
        return _Lowered(result_type,{
            "op":"PRIORITY_SELECT",
            "result_type":result_type,
            "selection_policy":PRIORITY_SELECT_POLICY_V4,
            "candidates":candidates,
        })

    def _step_limit_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        if len(expression.children)!=1:
            _fail("TEVS_V2_PROGRAM_STEP_LIMIT","within_steps requires exactly one body expression")
        maximum_steps=int(expression.value)
        if not 1<=maximum_steps<=MAX_PURE_EVAL_STEPS_V4:
            _fail("TEVS_V2_PROGRAM_STEP_LIMIT",f"within_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
        body=self.lower(expression.children[0],expected=expected) if expected is not None else self.lower(expression.children[0])
        result_type=body.type_text
        _require_expected(result_type,expected,self.generic_arities)
        return _Lowered(result_type,{
            "op":"STEP_LIMIT",
            "result_type":result_type,
            "maximum_steps":maximum_steps,
            "body":body.ir,
        })

    def _task_scope_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        bindings = tuple(expression.value)
        if not 1 <= len(bindings) <= MAX_PURE_TASKS_V4 or len(expression.children) != len(bindings) + 1:
            _fail("TEVS_V2_PROGRAM_TASK_BOUND", f"await all requires 1..{MAX_PURE_TASKS_V4} child tasks")
        names = [str(name) for name, _type_text in bindings]
        if len(set(names)) != len(names):
            _fail("TEVS_V2_PROGRAM_TASK_BINDING", "await all task bindings must be unique")
        if any(name.startswith("__tev_") for name in names):
            _fail("TEVS_V2_PROGRAM_TASK_BINDING", "await all task binding uses reserved compiler prefix")
        shadowed = sorted(set(self.parameter_types).intersection(names))
        if shadowed:
            _fail("TEVS_V2_PROGRAM_TASK_BINDING", f"await all task bindings shadow existing values: {shadowed}")
        if self.self_parameter_types is not None and any(_source_expression_contains_self_call(child) for child in expression.children):
            _fail("TEVS_V2_PROGRAM_TASK_RECURSION", "self(...) inside await all is forbidden in structured-concurrency R1")
        canonical_types = [self._specialize_type_text(str(type_text)) for _name, type_text in bindings]
        lowered_tasks = [
            self.lower(child, expected=task_type)
            for child, task_type in zip(expression.children[:-1], canonical_types, strict=True)
        ]
        for name, task_type in zip(names, canonical_types, strict=True):
            self.parameter_types[name] = task_type
        try:
            join = self.lower(expression.children[-1], expected=expected) if expected is not None else self.lower(expression.children[-1])
        finally:
            for name in names:
                self.parameter_types.pop(name, None)
        result_type = join.type_text
        _require_expected(result_type, expected, self.generic_arities)
        return _Lowered(
            result_type,
            {
                "op": "TASK_SCOPE",
                "result_type": result_type,
                "join_policy": TASK_JOIN_POLICY_V4,
                "cancellation_policy": TASK_CANCELLATION_POLICY_V4,
                "tasks": [
                    {"name": name, "type": task_type, "body": lowered.ir}
                    for name, task_type, lowered in zip(names, canonical_types, lowered_tasks, strict=True)
                ],
                "join": join.ir,
            },
        )

    def _task_dag_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        bindings=tuple(expression.value)
        if not 1<=len(bindings)<=MAX_PURE_TASKS_V4 or len(expression.children)!=len(bindings)+1:
            _fail("TEVS_V2_PROGRAM_TASK_DAG_BOUND",f"task scope requires 1..{MAX_PURE_TASKS_V4} spawned tasks")
        names=[str(name) for name,_type_text in bindings]
        if len(set(names))!=len(names):
            _fail("TEVS_V2_PROGRAM_TASK_DAG_BINDING","spawned task names must be unique")
        shadowed=sorted(set(self.parameter_types).intersection(names))
        if shadowed:
            _fail("TEVS_V2_PROGRAM_TASK_DAG_BINDING",f"spawned tasks shadow existing values: {shadowed}")
        if self.self_parameter_types is not None and any(_source_expression_contains_self_call(child) for child in expression.children):
            _fail("TEVS_V2_PROGRAM_TASK_RECURSION","self(...) inside task scope is forbidden in structured-concurrency R1")
        task_types={name:self._specialize_type_text(str(type_text)) for name,type_text in bindings}
        task_names=frozenset(task_types)

        def rewrite(node: SourceExprV2) -> tuple[SourceExprV2,frozenset[str]]:
            if node.kind=="task_dag":
                _fail("TEVS_V2_PROGRAM_TASK_DAG_NESTING","nested task scope is not supported in R1")
            if node.kind=="task_await":
                name=str(node.value)
                if name not in task_names:
                    _fail("TEVS_V2_PROGRAM_TASK_AWAIT",f"await references unknown task {name!r}")
                synthetic=f"__tev_task_await_{name}"
                return SourceExprV2("name",synthetic),frozenset({name})
            children=[]; dependencies:set[str]=set()
            for child in node.children:
                rewritten,observed=rewrite(child); children.append(rewritten); dependencies.update(observed)
            return SourceExprV2(node.kind,node.value,tuple(children)),frozenset(dependencies)

        lowered_tasks=[]
        task_sources=sorted(
            zip(bindings,expression.children[:-1],strict=True),
            key=lambda item:str(item[0][0]),
        )
        for (name,_type_text),body in task_sources:
            rewritten,dependencies=rewrite(body)
            if name in dependencies:
                _fail("TEVS_V2_PROGRAM_TASK_DAG_CYCLE",f"task {name!r} cannot await itself")
            synthetic_names=[]
            for dependency in sorted(dependencies):
                synthetic=f"__tev_task_await_{dependency}"; synthetic_names.append(synthetic)
                self.parameter_types[synthetic]=task_types[dependency]
                self.parameter_ir_names[synthetic]=dependency
            try:
                lowered=self.lower(rewritten,expected=task_types[name])
            finally:
                for synthetic in synthetic_names:
                    self.parameter_types.pop(synthetic,None); self.parameter_ir_names.pop(synthetic,None)
            lowered_tasks.append({"name":name,"type":task_types[name],"dependencies":sorted(dependencies),"body":lowered.ir})

        rewritten_join,join_dependencies=rewrite(expression.children[-1])
        synthetic_names=[]
        for dependency in sorted(join_dependencies):
            synthetic=f"__tev_task_await_{dependency}"; synthetic_names.append(synthetic)
            self.parameter_types[synthetic]=task_types[dependency]
            self.parameter_ir_names[synthetic]=dependency
        try:
            join=self.lower(rewritten_join,expected=expected) if expected is not None else self.lower(rewritten_join)
        finally:
            for synthetic in synthetic_names:
                self.parameter_types.pop(synthetic,None); self.parameter_ir_names.pop(synthetic,None)
        result_type=join.type_text
        _require_expected(result_type,expected,self.generic_arities)
        return _Lowered(result_type,{
            "op":"TASK_DAG",
            "result_type":result_type,
            "join_policy":TASK_JOIN_POLICY_V4,
            "cancellation_policy":TASK_CANCELLATION_POLICY_V4,
            "tasks":lowered_tasks,
            "join":join.ir,
        })

    def _while_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        accumulator_name, accumulator_type, maximum_iterations = expression.value
        accumulator_type = self._specialize_type_text(str(accumulator_type))
        if accumulator_name in self.parameter_types:
            _fail("TEVS_V2_PROGRAM_WHILE", f"while accumulator {accumulator_name!r} shadows an existing value")
        initial = self.lower(expression.children[0], expected=accumulator_type)
        self.parameter_types[str(accumulator_name)] = accumulator_type
        try:
            condition = self.lower(expression.children[1], expected="Bool")
            body = self.lower(expression.children[2], expected=accumulator_type)
        finally:
            self.parameter_types.pop(str(accumulator_name), None)
        _require_expected(accumulator_type, expected, self.generic_arities)
        return _Lowered(
            accumulator_type,
            {
                "op": "WHILE_FOLD",
                "accumulator_name": str(accumulator_name),
                "accumulator_type": accumulator_type,
                "maximum_iterations": int(maximum_iterations),
                "initial": initial.ir,
                "condition": condition.ir,
                "body": body.ir,
            },
        )

    def _for_fold_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        bindings, accumulator_name, accumulator_type = expression.value
        accumulator_type = self._specialize_type_text(str(accumulator_type))
        collection = self.lower(expression.children[0])
        collection_ref = parse_type_ref_v2(collection.type_text, self.generic_arities)
        if collection_ref.kind in {"list", "array", "set"}:
            expected_bindings = (_render_type(collection_ref.arguments[0]),)
        elif collection_ref.kind == "map":
            expected_bindings = (
                _render_type(collection_ref.arguments[0]),
                _render_type(collection_ref.arguments[1]),
            )
        else:
            _fail("TEVS_V2_PROGRAM_FOR", f"for-in requires bounded collection, got {collection.type_text}")
        if len(bindings) != len(expected_bindings):
            _fail(
                "TEVS_V2_PROGRAM_FOR",
                f"{collection_ref.kind} iteration requires {len(expected_bindings)} binding(s), got {len(bindings)}",
            )
        names = [str(item) for item in bindings]
        if len(set(names)) != len(names):
            _fail("TEVS_V2_PROGRAM_FOR", "for-in bindings must be unique")
        if str(accumulator_name) in names:
            _fail("TEVS_V2_PROGRAM_FOR", "for accumulator cannot reuse an iteration binding")
        occupied = set(self.parameter_types)
        if str(accumulator_name) in occupied or occupied.intersection(names):
            _fail("TEVS_V2_PROGRAM_FOR", "for bindings/accumulator cannot shadow existing values")
        initial = self.lower(expression.children[1], expected=accumulator_type)
        self.parameter_types[str(accumulator_name)] = accumulator_type
        for name, type_text in zip(names, expected_bindings, strict=True):
            self.parameter_types[name] = type_text
        try:
            body = self.lower(expression.children[2], expected=accumulator_type)
        finally:
            self.parameter_types.pop(str(accumulator_name), None)
            for name in names:
                self.parameter_types.pop(name, None)
        _require_expected(accumulator_type, expected, self.generic_arities)
        return _Lowered(
            accumulator_type,
            {
                "op": "FOR_FOLD",
                "collection_type": collection.type_text,
                "accumulator_name": str(accumulator_name),
                "accumulator_type": accumulator_type,
                "bindings": [
                    {"name": name, "type": type_text}
                    for name, type_text in zip(names, expected_bindings, strict=True)
                ],
                "collection": collection.ir,
                "initial": initial.ir,
                "body": body.ir,
            },
        )

    def _match_expression(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        subject = self.lower(expression.children[0])
        subject_ref = parse_type_ref_v2(subject.type_text, self.generic_arities)
        if subject_ref.kind == "option":
            variants = {"None": None, "Some": _render_type(subject_ref.arguments[0])}
        elif subject_ref.kind == "result":
            variants = {
                "Ok": _render_type(subject_ref.arguments[0]),
                "Err": _render_type(subject_ref.arguments[1]),
            }
        else:
            _fail(
                "TEVS_V2_PROGRAM_MATCH",
                f"source V2 match currently requires Option/Result subject, got {subject.type_text}",
            )
        patterns = expression.value
        bodies = expression.children[1:]
        if len(patterns) != len(bodies):
            raise AssertionError("match parser invariant")
        observed = [variant for variant, _binding in patterns]
        if len(set(observed)) != len(observed) or set(observed) != set(variants):
            _fail(
                "TEVS_V2_PROGRAM_MATCH",
                f"match arms must be exhaustive exactly {sorted(variants)}, got {observed}",
            )
        lowered_arms: list[dict[str, Any]] = []
        result_type = expected
        for (variant, binding), body in zip(patterns, bodies, strict=True):
            payload_type = variants[variant]
            if payload_type is None:
                if binding is not None:
                    _fail("TEVS_V2_PROGRAM_MATCH", f"payload-free variant {variant} cannot bind a value")
            else:
                if binding is None:
                    _fail("TEVS_V2_PROGRAM_MATCH", f"payload variant {variant} requires binding")
                if binding in self.parameter_types:
                    _fail("TEVS_V2_PROGRAM_MATCH", f"match binding {binding!r} shadows an existing value")
                self.parameter_types[binding] = payload_type
            try:
                lowered = self.lower(body, expected=result_type) if result_type is not None else self.lower(body)
            finally:
                if payload_type is not None and binding is not None:
                    self.parameter_types.pop(binding, None)
            if result_type is None:
                result_type = lowered.type_text
            elif not _type_equal(lowered.type_text, result_type, self.generic_arities):
                _fail("TEVS_V2_PROGRAM_MATCH", f"match arm {variant} returns {lowered.type_text}, expected {result_type}")
            arm: dict[str, Any] = {"variant": variant, "body": lowered.ir}
            if payload_type is not None and binding is not None:
                arm["binding"] = {"name": binding, "type": payload_type}
            lowered_arms.append(arm)
        assert result_type is not None
        return _Lowered(
            result_type,
            {
                "op": "MATCH",
                "subject_type": subject.type_text,
                "result_type": result_type,
                "subject": subject.ir,
                "arms": lowered_arms,
            },
        )

    def _binary(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        operator = str(expression.value)
        left = self.lower(expression.children[0])
        right = self.lower(expression.children[1])
        numeric = {"Int", "Rat"}
        if operator in {"AND", "OR"}:
            if left.type_text != right.type_text or left.type_text != "Bool":
                _fail("TEVS_V2_PROGRAM_OPERATOR", f"{operator} requires Bool/Bool")
            result = "Bool"
        elif operator in {"EQEQ", "NE"}:
            if not (_type_equal(left.type_text, right.type_text, self.generic_arities) or {left.type_text, right.type_text} <= numeric):
                _fail("TEVS_V2_PROGRAM_OPERATOR", f"equality requires equal types or numeric pair, got {left.type_text},{right.type_text}")
            result = "Bool"
        elif operator in {"LT", "LE", "GT", "GE"}:
            if left.type_text not in numeric or right.type_text not in numeric:
                _fail("TEVS_V2_PROGRAM_OPERATOR", f"ordering requires numeric pair, got {left.type_text},{right.type_text}")
            result = "Bool"
        elif operator in {"PLUS", "MINUS", "STAR"}:
            if left.type_text not in numeric or right.type_text not in numeric:
                _fail("TEVS_V2_PROGRAM_OPERATOR", f"arithmetic requires concrete numeric types, got {left.type_text},{right.type_text}")
            result = "Int" if left.type_text == right.type_text == "Int" else "Rat"
        elif operator == "SLASH":
            if left.type_text not in numeric or right.type_text not in numeric:
                _fail("TEVS_V2_PROGRAM_OPERATOR", f"division requires numeric pair, got {left.type_text},{right.type_text}")
            result = "Rat"
        else:
            _fail("TEVS_V2_PROGRAM_OPERATOR", f"unsupported operator {operator!r}")
        _require_expected(result, expected, self.generic_arities)
        return _Lowered(result, {
            "op": "BINARY",
            "operator": operator,
            "left_type": left.type_text,
            "right_type": right.type_text,
            "result_type": result,
            "left": left.ir,
            "right": right.ir,
        })

    def _call(self, expression: SourceExprV2, expected: str | None) -> _Lowered:
        name, type_arguments, named_fields = expression.value
        args = expression.children
        if name == "self":
            if type_arguments:
                _fail("TEVS_V2_PROGRAM_RECURSION", "self(...) cannot carry explicit type arguments")
            if self.self_parameter_types is None or self.self_return_type is None:
                _fail("TEVS_V2_PROGRAM_RECURSION_CONTEXT", "self(...) is only valid inside recursive fn")
            if named_fields:
                _fail("TEVS_V2_PROGRAM_RECURSION", "self(...) uses positional arguments only")
            _arity("self", args, len(self.self_parameter_types))
            lowered_arguments = [
                self.lower(argument, expected=expected_type).ir
                for argument, expected_type in zip(args, self.self_parameter_types, strict=True)
            ]
            _require_expected(self.self_return_type, expected, self.generic_arities)
            return _Lowered(
                self.self_return_type,
                {"op": "SELF_CALL", "arguments": lowered_arguments},
            )
        if name in self.function_sources:
            return self._inline_pure_call(
                str(name),
                tuple(type_arguments),
                tuple(named_fields),
                args,
                expected,
            )
        if "." in str(name) and name not in _RESERVED_SOURCE_CALL_NAMES:
            if type_arguments or named_fields:
                _fail("TEVS_V2_PROGRAM_METHOD_CALL", "R1 method calls use positional value arguments and no explicit type arguments")
            parts = str(name).split(".")
            receiver: SourceExprV2 = SourceExprV2("name", parts[0])
            for field_name in parts[1:-1]:
                receiver = SourceExprV2("field", field_name, (receiver,))
            return self._method_call_expression(
                SourceExprV2("method_call", parts[-1], (receiver, *args)),
                expected,
            )
        if name in self.recursive_function_names:
            _fail(
                "TEVS_V2_PROGRAM_CALL_RECURSIVE",
                f"pure expression cannot call recursive function {name!r}; only self(...) inside recursive fn has recursive authority",
            )
        if type_arguments:
            _fail(
                "TEVS_V2_PROGRAM_CALL",
                f"builtin/constructor call {name!r} does not accept explicit type arguments",
            )
        if named_fields:
            return self._record_constructor(str(name), tuple(named_fields), args, expected)
        if name == "len":
            _arity(name, args, 1)
            collection = self.lower(args[0])
            ref = parse_type_ref_v2(collection.type_text, self.generic_arities)
            if ref.kind not in {"list", "array", "set", "map"}:
                _fail("TEVS_V2_PROGRAM_CALL", f"len requires collection, got {collection.type_text}")
            _require_expected("Int", expected, self.generic_arities)
            return _Lowered("Int", {"op": "LEN", "collection_type": collection.type_text, "collection": collection.ir})
        if name in {"list.push", "list.get", "array.get", "array.set", "set.add", "set.contains", "map.put", "map.get"}:
            return self._collection_call(name, args, expected)
        if name == "Some":
            _arity(name, args, 1)
            if expected is None: _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", "Some(...) requires expected Option<T>")
            ref = parse_type_ref_v2(expected, self.generic_arities)
            if ref.kind != "option": _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"Some cannot construct {expected}")
            payload_type = _render_type(ref.arguments[0])
            payload = self.lower(args[0], expected=payload_type)
            return _Lowered(expected, {"op": "VARIANT", "type": expected, "variant": "Some", "payload": payload.ir})
        if name in {"Ok", "Err"}:
            _arity(name, args, 1)
            if expected is None: _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"{name}(...) requires expected Result<T,E>")
            ref = parse_type_ref_v2(expected, self.generic_arities)
            if ref.kind != "result": _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"{name} cannot construct {expected}")
            payload_type = _render_type(ref.arguments[0 if name == "Ok" else 1])
            payload = self.lower(args[0], expected=payload_type)
            return _Lowered(expected, {"op": "VARIANT", "type": expected, "variant": name, "payload": payload.ir})
        _fail("TEVS_V2_PROGRAM_CALL", f"unsupported V2 pure call {name!r}")

    def _inline_pure_call(
        self,
        name: str,
        type_arguments: tuple[str, ...],
        named_fields: tuple[str, ...],
        args: Sequence[SourceExprV2],
        expected: str | None,
    ) -> _Lowered:
        declaration = self.function_sources.get(name)
        if declaration is None:
            _fail("TEVS_V2_PROGRAM_CALL", f"unknown pure function {name!r}")
        if named_fields:
            _fail("TEVS_V2_PROGRAM_CALL", "source pure function calls use positional arguments only")
        if name in self.inline_stack:
            cycle = " -> ".join((*self.inline_stack, name))
            _fail("TEVS_V2_PROGRAM_CALL_CYCLE", f"pure function call cycle: {cycle}")
        if len(self.inline_stack) >= MAX_PURE_INLINE_DEPTH_V2:
            _fail(
                "TEVS_V2_PROGRAM_INLINE_DEPTH",
                f"pure function inline depth would exceed {MAX_PURE_INLINE_DEPTH_V2}",
            )
        if len(type_arguments) != len(declaration.type_parameters):
            _fail(
                "TEVS_V2_PROGRAM_CALL_ARITY",
                f"function {name!r} expects {len(declaration.type_parameters)} type arguments, got {len(type_arguments)}",
            )
        if len(args) != len(declaration.parameters):
            _fail(
                "TEVS_V2_PROGRAM_CALL_ARITY",
                f"function {name!r} expects {len(declaration.parameters)} value arguments, got {len(args)}",
            )

        call_type_refs: list[TypeRefV2] = []
        for type_text in type_arguments:
            parsed = parse_type_ref_v2(type_text, self.generic_arities)
            call_type_refs.append(_substitute_type(parsed, self.type_substitutions, self.associated_type_substitutions))
        substitutions = dict(zip(declaration.type_parameters, call_type_refs, strict=True))
        constrained_parameter_methods: dict[str, frozenset[str]] = {}
        if declaration.constraints:
            if self.type_registry is None:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_CONTEXT",
                    f"constrained function {name!r} requires compile-time type registry context",
                )
            template_hash = self.constrained_template_hashes.get(name)
            if template_hash is None:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_TEMPLATE",
                    f"constrained function {name!r} has no source template hash",
                )
            type_argument_ids: list[str] = []
            concrete_source_types: dict[str, str] = {}
            for type_parameter, type_ref in zip(declaration.type_parameters, call_type_refs, strict=True):
                source_type = _render_type(type_ref)
                try:
                    resolved = self.type_registry.materialize_source_type(source_type)
                except TevScriptError as error:
                    _fail(
                        "TEVS_V2_PROGRAM_CONSTRAINT_CONCRETE",
                        f"constrained call {name!r} requires concrete type argument for {type_parameter!r}: {error.diagnostic.message}",
                    )
                concrete_source_types[type_parameter] = source_type
                type_argument_ids.append(resolved.type_id)

            binding_payloads: list[dict[str, str]] = []
            binding_tuples: list[tuple[str, str, str]] = []
            associated_binding_payloads: list[dict[str, str]] = []
            associated_binding_tuples: list[tuple[str, str, str]] = []
            associated_constraint_payloads: list[dict[str, str]] = []
            associated_constraint_tuples: list[tuple[str, str, str]] = []
            call_associated_substitutions = dict(self.associated_type_substitutions)
            protocols_by_type_parameter = _constraint_protocols_by_parameter_v2(declaration)
            constraint_methods_by_type_parameter: dict[str, set[str]] = {
                type_parameter: set()
                for type_parameter in protocols_by_type_parameter
            }
            processed_associated_constraints: set[tuple[str, str]] = set()
            validated_bindings: dict[tuple[str, str], _ValidatedProtocolWitnessBindingV2] = {}
            for type_parameter, protocol_name in declaration.constraints:
                source_type = concrete_source_types[type_parameter]
                witness = self.protocol_witness_index.get((protocol_name, source_type))
                if witness is None and self.protocol_witness_resolver is not None:
                    resolution = self.protocol_witness_resolver(
                        protocol_name,
                        source_type,
                        self.constrained_specializations,
                        self.defer_missing_witnesses,
                    )
                    if resolution is not None:
                        witness = resolution.witness
                        self.protocol_witness_index[(protocol_name, source_type)] = witness
                        self.method_dispatch.update(dict(resolution.method_dispatch))
                        self.function_sources.update(dict(resolution.function_sources))
                if witness is None:
                    if self.defer_missing_witnesses:
                        raise _DeferredProtocolWitnessV2(protocol_name, source_type)
                    _fail(
                        "TEVS_V2_PROGRAM_CONSTRAINT_WITNESS",
                        f"type {source_type} has no explicit witness for protocol {protocol_name!r}",
                    )
                validated_binding = _ProtocolWitnessBindingResolverV2.validate(
                    witness=witness,
                    protocol_name=protocol_name,
                    receiver_source_type=source_type,
                    protocol_hashes=self.protocol_hashes,
                    types=self.type_registry,
                    diagnostic_code="TEVS_V2_PROGRAM_CONSTRAINT_WITNESS",
                    contract_mismatch_message=(
                        f"witness for {source_type} and {protocol_name!r} is not bound to the active protocol contract"
                    ),
                    runtime_mismatch_message=(
                        f"witness runtime receiver mismatch for {source_type} and {protocol_name!r}"
                    ),
                )
                validated_bindings[(type_parameter, protocol_name)] = validated_binding
                binding_payloads.append({
                    "type_parameter": type_parameter,
                    "protocol_hash": validated_binding.protocol_hash,
                    "witness_hash": validated_binding.witness.witness_hash,
                })
                binding_tuples.append((
                    type_parameter,
                    validated_binding.protocol_hash,
                    validated_binding.witness.witness_hash,
                ))
                constraint_methods_by_type_parameter[type_parameter].update(
                    self.protocol_methods.get(protocol_name, frozenset())
                )
            for type_parameter, protocol_name in declaration.constraints:
                validated_binding = validated_bindings[(type_parameter, protocol_name)]
                for associated_name, associated_source_type in validated_binding.associated_source_types:
                    associated_type_id = validated_binding.associated_type_id(associated_name)
                    assert associated_type_id is not None
                    key = (type_parameter, associated_name)
                    associated_ref = parse_type_ref_v2(associated_source_type, self.generic_arities)
                    prior_associated = call_associated_substitutions.get(key)
                    if prior_associated is not None and prior_associated != associated_ref:
                        _fail(
                            "TEVS_V2_PROGRAM_ASSOCIATED_TYPE_WITNESS",
                            f"conflicting associated type projection for {type_parameter}::{associated_name}",
                        )
                    call_associated_substitutions[key] = associated_ref
                    associated_binding_payloads.append({
                        "type_parameter": type_parameter,
                        "associated_name": associated_name,
                        "associated_type_id": associated_type_id,
                    })
                    associated_binding_tuples.append((type_parameter, associated_name, associated_type_id))

            for type_parameter, associated_name, required_type in declaration.associated_constraints:
                owner_bindings = [
                    (protocol_name, binding)
                    for (binding_parameter, protocol_name), binding in validated_bindings.items()
                    if binding_parameter == type_parameter
                    and binding.associated_type_id(associated_name) is not None
                ]
                if len(owner_bindings) != 1:
                    continue
                owner_protocol_name, owner_binding = owner_bindings[0]
                observed_type_id = owner_binding.associated_type_id(associated_name)
                assert observed_type_id is not None
                specification = _AssociatedConstraintSpecificationV2.from_validated_source(
                    target_type_parameter=type_parameter,
                    associated_name=associated_name,
                    required_type=required_type,
                    type_parameters=declaration.type_parameters,
                    generic_arities=self.generic_arities,
                )
                _required_source_type, required_type_id = specification.resolve(
                    type_substitutions=substitutions,
                    associated_substitutions=call_associated_substitutions,
                    types=self.type_registry,
                    diagnostic_code="TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_TYPE",
                    message_prefix=f"refinement {type_parameter}::{associated_name} requires type",
                )
                processed_associated_constraints.add((type_parameter, associated_name))
                if observed_type_id != required_type_id:
                    source_type = concrete_source_types[type_parameter]
                    _fail(
                        "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_MISMATCH",
                        f"witness {source_type}:{owner_protocol_name} binds {associated_name}={observed_type_id}, required {required_type_id}",
                    )
                associated_constraint_payloads.append({
                    "type_parameter": type_parameter,
                    "associated_name": associated_name,
                    "required_type_id": required_type_id,
                })
                associated_constraint_tuples.append((type_parameter, associated_name, required_type_id))

            expected_associated_constraints = {
                (type_parameter, associated_name)
                for type_parameter, associated_name, _required_type in declaration.associated_constraints
            }
            missing_processed_constraints = sorted(
                expected_associated_constraints - processed_associated_constraints
            )
            if missing_processed_constraints:
                _fail(
                    "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_WITNESS",
                    f"constrained function {name!r} has refinements not bound by its witness set: {missing_processed_constraints}",
                )

            for parameter_name, parameter_type in declaration.parameters:
                parameter_ref = parse_type_ref_v2(parameter_type, self.generic_arities)
                if parameter_ref.kind == "named" and parameter_ref.name in protocols_by_type_parameter:
                    constrained_parameter_methods[parameter_name] = frozenset(
                        constraint_methods_by_type_parameter.get(parameter_ref.name, set())
                    )

            protocol_intersection_payloads: list[dict[str, Any]] = []
            protocol_intersection_tuples: list[tuple[str, str]] = []
            bindings_by_type_parameter: dict[str, list[tuple[str, str]]] = {}
            for binding_type_parameter, protocol_hash, witness_hash in binding_tuples:
                bindings_by_type_parameter.setdefault(binding_type_parameter, []).append(
                    (protocol_hash, witness_hash)
                )
            type_id_by_parameter = dict(zip(declaration.type_parameters, type_argument_ids, strict=True))
            for intersection_type_parameter, protocol_names in protocols_by_type_parameter.items():
                if len(protocol_names) <= 1:
                    continue
                witness_set = sorted(bindings_by_type_parameter.get(intersection_type_parameter, ()))
                if len(witness_set) != len(protocol_names):
                    _fail(
                        "TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_WITNESS",
                        f"intersection {intersection_type_parameter}:{'+'.join(protocol_names)} does not have its exact witness set",
                    )
                intersection_payload = {
                    "schema": "TEV_SCRIPT_V2_PROTOCOL_INTERSECTION_R1",
                    "type_parameter": intersection_type_parameter,
                    "receiver_type_id": type_id_by_parameter[intersection_type_parameter],
                    "collision_policy": PROTOCOL_INTERSECTION_POLICY_V2,
                    "witness_set": [
                        {"protocol_hash": protocol_hash, "witness_hash": witness_hash}
                        for protocol_hash, witness_hash in witness_set
                    ],
                }
                intersection_hash = _hash(intersection_payload)
                protocol_intersection_payloads.append({
                    "type_parameter": intersection_type_parameter,
                    "intersection_hash": intersection_hash,
                })
                protocol_intersection_tuples.append((intersection_type_parameter, intersection_hash))
            protocol_intersection_payloads.sort(key=lambda item: item["type_parameter"])
            protocol_intersection_tuples.sort()

            associated_constraint_payloads.sort(
                key=lambda item: (item["type_parameter"], item["associated_name"], item["required_type_id"])
            )
            associated_constraint_tuples.sort()
            specialization_payload = {
                "schema": "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_SPECIALIZATION_R1",
                "template_hash": template_hash,
                "type_argument_ids": type_argument_ids,
                "constraint_bindings": binding_payloads,
            }
            if associated_binding_payloads:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_SPECIALIZATION_R2"
                specialization_payload["associated_type_bindings"] = associated_binding_payloads
            if associated_constraint_payloads:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_SPECIALIZATION_R3"
                specialization_payload["associated_constraint_bindings"] = associated_constraint_payloads
            if protocol_intersection_payloads:
                specialization_payload["schema"] = "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_SPECIALIZATION_R4"
                specialization_payload["protocol_intersection_policy"] = PROTOCOL_INTERSECTION_POLICY_V2
                specialization_payload["protocol_intersections"] = protocol_intersection_payloads
            specialization_hash = _hash(specialization_payload)
            specialization = ConstrainedFunctionSpecializationV2(
                name,
                template_hash,
                tuple(type_argument_ids),
                tuple(binding_tuples),
                specialization_hash,
                tuple(associated_binding_tuples),
                tuple(associated_constraint_tuples),
                tuple(protocol_intersection_tuples),
            )
            prior = self.constrained_specializations.get(specialization_hash)
            if prior is not None and prior != specialization:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_SPECIALIZATION",
                    f"specialization hash collision for constrained function {name!r}",
                )
            self.constrained_specializations[specialization_hash] = specialization
            self.used_constrained_specializations.add(specialization_hash)

        if not declaration.constraints:
            call_associated_substitutions = dict(self.associated_type_substitutions)

        substituted_parameters = tuple(
            (
                parameter_name,
                _render_type(
                    _substitute_type(
                        parse_type_ref_v2(parameter_type, self.generic_arities),
                        substitutions,
                        call_associated_substitutions,
                    )
                ),
            )
            for parameter_name, parameter_type in declaration.parameters
        )
        substituted_return = _render_type(
            _substitute_type(
                parse_type_ref_v2(declaration.return_type, self.generic_arities),
                substitutions,
                call_associated_substitutions,
            )
        )
        if _type_ref_contains_associated_v2(parse_type_ref_v2(substituted_return, self.generic_arities)):
            _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_UNRESOLVED", f"constrained call {name!r} leaves unresolved return projection {substituted_return}")
        _require_expected(substituted_return, expected, self.generic_arities)

        lowered_arguments = [
            self.lower(argument, expected=parameter_type)
            for argument, (_parameter_name, parameter_type) in zip(
                args,
                substituted_parameters,
                strict=True,
            )
        ]
        call_id = self.inline_counter[0]
        self.inline_counter[0] += 1
        ir_names = {
            parameter_name: f"__tev_call_{call_id}_{parameter_name}"
            for parameter_name, _parameter_type in substituted_parameters
        }
        combined_substitutions = dict(self.type_substitutions)
        combined_substitutions.update(substitutions)
        combined_associated_substitutions = dict(self.associated_type_substitutions)
        combined_associated_substitutions.update(call_associated_substitutions)
        nested = _ExpressionLowererV2(
            declaration.type_parameters,
            substituted_parameters,
            substituted_return,
            self.records,
            self.generic_arities,
            function_sources=self.function_sources,
            recursive_function_names=tuple(self.recursive_function_names),
            method_dispatch=self.method_dispatch,
            protocol_witness_index=self.protocol_witness_index,
            protocol_hashes=self.protocol_hashes,
            protocol_methods=self.protocol_methods,
            constrained_template_hashes=self.constrained_template_hashes,
            constrained_specializations=self.constrained_specializations,
            type_registry=self.type_registry,
            constrained_parameter_methods=constrained_parameter_methods,
            defer_missing_witnesses=self.defer_missing_witnesses,
            used_constrained_specializations=self.used_constrained_specializations,
            protocol_witness_resolver=self.protocol_witness_resolver,
            generic_method_resolver=self.generic_method_resolver,
            inline_stack=(*self.inline_stack, name),
            inline_counter=self.inline_counter,
            parameter_ir_names=ir_names,
            type_substitutions=combined_substitutions,
            associated_type_substitutions=combined_associated_substitutions,
        )
        body = nested.lower(declaration.body, expected=substituted_return)
        if not _type_equal(body.type_text, substituted_return, self.generic_arities):
            _fail(
                "TEVS_V2_PROGRAM_CALL_RETURN",
                f"inlined function {name!r} returns {body.type_text}, expected {substituted_return}",
            )
        body_ir = body.ir
        for (parameter_name, parameter_type), argument in reversed(
            list(zip(substituted_parameters, lowered_arguments, strict=True))
        ):
            body_ir = {
                "op": "LET",
                "name": ir_names[parameter_name],
                "type": parameter_type,
                "result_type": substituted_return,
                "value": argument.ir,
                "body": body_ir,
            }
        return _Lowered(substituted_return, body_ir)

    def _none(self, expected: str | None) -> _Lowered:
        if expected is None:
            _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", "None requires expected Option<T>")
        ref = parse_type_ref_v2(expected, self.generic_arities)
        if ref.kind != "option": _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"None cannot construct {expected}")
        return _Lowered(expected, {"op": "VARIANT", "type": expected, "variant": "None"})

    def _collection_call(self, name: str, args: Sequence[SourceExprV2], expected: str | None) -> _Lowered:
        arities = {"list.push": 2, "list.get": 2, "array.get": 2, "array.set": 3, "set.add": 2, "set.contains": 2, "map.put": 3, "map.get": 2}
        _arity(name, args, arities[name])
        collection = self.lower(args[0])
        ref = parse_type_ref_v2(collection.type_text, self.generic_arities)
        required_kind = name.split(".", 1)[0]
        if ref.kind != required_kind:
            _fail("TEVS_V2_PROGRAM_CALL", f"{name} requires {required_kind} collection, got {collection.type_text}")
        if name == "list.push":
            item_type = _render_type(ref.arguments[0]); item = self.lower(args[1], expected=item_type); result = collection.type_text
            ir = {"op": "LIST_PUSH", "collection_type": result, "collection": collection.ir, "item": item.ir}
        elif name == "list.get":
            item_type = _render_type(ref.arguments[0]); index = self.lower(args[1], expected="Int"); result = item_type
            ir = {"op": "LIST_GET", "collection_type": collection.type_text, "result_type": item_type, "collection": collection.ir, "index": index.ir}
        elif name == "array.get":
            item_type = _render_type(ref.arguments[0]); index = self.lower(args[1], expected="Int"); result = item_type
            ir = {"op": "ARRAY_GET", "collection_type": collection.type_text, "result_type": item_type, "collection": collection.ir, "index": index.ir}
        elif name == "array.set":
            item_type = _render_type(ref.arguments[0]); index = self.lower(args[1], expected="Int"); item = self.lower(args[2], expected=item_type); result = collection.type_text
            ir = {"op": "ARRAY_SET", "collection_type": result, "collection": collection.ir, "index": index.ir, "item": item.ir}
        elif name == "set.add":
            item_type = _render_type(ref.arguments[0]); item = self.lower(args[1], expected=item_type); result = collection.type_text
            ir = {"op": "SET_ADD", "collection_type": result, "collection": collection.ir, "item": item.ir}
        elif name == "set.contains":
            item_type = _render_type(ref.arguments[0]); item = self.lower(args[1], expected=item_type); result = "Bool"
            ir = {"op": "SET_CONTAINS", "collection_type": collection.type_text, "collection": collection.ir, "item": item.ir}
        elif name == "map.put":
            key_type, value_type = (_render_type(item) for item in ref.arguments)
            key = self.lower(args[1], expected=key_type); value = self.lower(args[2], expected=value_type); result = collection.type_text
            ir = {"op": "MAP_PUT", "collection_type": result, "collection": collection.ir, "key": key.ir, "value": value.ir}
        else:
            key_type, value_type = (_render_type(item) for item in ref.arguments)
            key = self.lower(args[1], expected=key_type); result = f"Option<{value_type}>"
            ir = {"op": "MAP_LOOKUP", "collection_type": collection.type_text, "result_type": result, "collection": collection.ir, "key": key.ir}
        _require_expected(result, expected, self.generic_arities)
        return _Lowered(result, ir)

    def _record_constructor(self, name: str, field_names: tuple[str, ...], args: Sequence[SourceExprV2], expected: str | None) -> _Lowered:
        if expected is None:
            _fail("TEVS_V2_PROGRAM_LITERAL_CONTEXT", f"record constructor {name} requires expected generic record type")
        expected_ref = parse_type_ref_v2(expected, self.generic_arities)
        declaration = self.records.get(name)
        if declaration is None or expected_ref.kind != "user_generic" or expected_ref.name not in {name, declaration.name}:
            _fail("TEVS_V2_PROGRAM_RECORD", f"constructor {name!r} does not match expected {expected!r}")
        if len(expected_ref.arguments) != len(declaration.type_parameters):
            _fail("TEVS_V2_PROGRAM_RECORD", "generic record argument arity mismatch")
        substitutions = dict(zip(declaration.type_parameters, expected_ref.arguments, strict=True))
        field_types = {
            field_name: _render_type(_substitute_type(parse_type_ref_v2(type_text, self.generic_arities), substitutions))
            for field_name, type_text in declaration.fields
        }
        if len(field_names) != len(args) or set(field_names) != set(field_types):
            _fail("TEVS_V2_PROGRAM_RECORD", f"constructor {name} requires exactly fields {sorted(field_types)}")
        values = dict(zip(field_names, args, strict=True))
        fields = [
            {"name": field, "expr": self.lower(values[field], expected=field_types[field]).ir}
            for field in sorted(field_types)
        ]
        return _Lowered(expected, {"op": "RECORD", "type": expected, "fields": fields})


def _compile_entry(
    entry: EntrySourceV2,
    types: GenericRegistryV2,
    functions: GenericPureFunctionRegistryV2,
    recursive_functions: RecursivePureFunctionRegistryV2,
    templates: Mapping[str, GenericPureFunctionTemplateV2],
    recursive_templates: Mapping[str, RecursivePureFunctionTemplateV2],
) -> CompiledEntryV2:
    pure_template = templates.get(entry.function_name)
    recursive_template = recursive_templates.get(entry.function_name)
    if (pure_template is None) == (recursive_template is None):
        _fail(
            "TEVS_V2_PROGRAM_ENTRY",
            f"entry must reference exactly one declared pure/recursive function {entry.function_name!r}",
        )
    resolved_type_arguments = tuple(types.resolve_source_type(text) for text in entry.type_arguments)
    if pure_template is not None:
        function_kind = "pure"
        template_hash = pure_template.template_hash
        instantiation = functions.instantiate(pure_template, resolved_type_arguments)
    else:
        assert recursive_template is not None
        function_kind = "recursive"
        template_hash = recursive_template.template_hash
        instantiation = recursive_functions.instantiate(recursive_template, resolved_type_arguments)
    if len(entry.argument_texts) != len(instantiation.parameter_type_ids):
        _fail(
            "TEVS_V2_PROGRAM_ENTRY",
            f"entry expected {len(instantiation.parameter_type_ids)} arguments, got {len(entry.argument_texts)}",
        )
    arguments: list[Any] = []
    encodings: list[Any] = []
    constructors = types.constructor_names()
    for source_text, expected_type in zip(
        entry.argument_texts,
        instantiation.parameter_type_ids,
        strict=True,
    ):
        parsed = parse_contextual_literal_v2(
            source_text,
            expected_type,
            types.table,
            constructor_names=constructors,
        )
        arguments.append(parsed.value)
        encodings.append(parsed.encoded)
    declared = types.resolve_source_type(entry.declared_type)
    types.materialize_resolved_type(declared)
    if declared.type_id != instantiation.return_type_id:
        _fail(
            "TEVS_V2_PROGRAM_ENTRY_TYPE",
            f"entry declares {declared.type_id}, function returns {instantiation.return_type_id}",
        )
    identity = {
        "schema": "TEV_SCRIPT_PROGRAM_V2_ENTRY_IDENTITY_V1",
        "name": entry.name,
        "declared_runtime_type": declared.type_id,
        "function_kind": function_kind,
        "function_template_hash": template_hash,
        "function_instantiation_hash": instantiation.instantiation_hash,
        "type_argument_ids": [item.type_id for item in resolved_type_arguments],
        "arguments": [
            {"type": type_id, "value": encoded}
            for type_id, encoded in zip(instantiation.parameter_type_ids, encodings, strict=True)
        ],
    }
    return CompiledEntryV2(
        entry.name,
        _canon_type(entry.declared_type, types.generic_arities()),
        declared.type_id,
        entry.function_name,
        function_kind,
        template_hash,
        instantiation,
        tuple(item.type_id for item in resolved_type_arguments),
        tuple(arguments),
        tuple(encodings),
        _hash(identity),
    )

def _validate_pure_function_call_graph(
    functions: Sequence[GenericFunctionSourceV2],
    *,
    recursive_function_names: set[str],
    record_names: set[str],
) -> None:
    function_names = {item.name for item in functions}
    parameter_names = {item.name: {name for name, _type_text in item.parameters} for item in functions}
    graph: dict[str, set[str]] = {name: set() for name in function_names}

    def visit(owner: str, expression: SourceExprV2) -> None:
        if expression.kind == "call":
            name, _type_arguments, _named_fields = expression.value
            name = str(name)
            if name in function_names:
                graph[owner].add(name)
            elif name in recursive_function_names:
                _fail(
                    "TEVS_V2_PROGRAM_CALL_RECURSIVE",
                    f"pure function {owner!r} cannot call recursive function {name!r}",
                )
            elif name in record_names or name in _RESERVED_SOURCE_CALL_NAMES:
                pass
            elif "." in name and name.split(".", 1)[0] in parameter_names.get(owner, set()):
                # Static method dispatch is resolved by the expression lowerer from
                # the exact receiver type; the scheduler/runtime never dispatches it.
                pass
            else:
                _fail(
                    "TEVS_V2_PROGRAM_CALL",
                    f"pure function {owner!r} references unknown/unavailable call {name!r}",
                )
        for child in expression.children:
            visit(owner, child)

    for declaration in functions:
        visit(declaration.name, declaration.body)

    remaining = {name: set(dependencies) for name, dependencies in graph.items()}
    ready = sorted(name for name, dependencies in remaining.items() if not dependencies)
    removed: list[str] = []
    while ready:
        name = ready.pop(0)
        if name in removed:
            continue
        removed.append(name)
        for other in sorted(remaining):
            if name in remaining[other]:
                remaining[other].remove(name)
                if not remaining[other] and other not in removed and other not in ready:
                    ready.append(other)
                    ready.sort()
    if len(removed) != len(graph):
        cycle_nodes = sorted(name for name in graph if name not in removed)
        cycle_edges = {
            name: sorted(dep for dep in graph[name] if dep in cycle_nodes)
            for name in cycle_nodes
        }
        _fail(
            "TEVS_V2_PROGRAM_CALL_CYCLE",
            f"pure function call graph is cyclic: {cycle_edges}",
        )


def _record_registration_order(records: Sequence[GenericRecordSourceV2]) -> tuple[str, ...]:
    by_name = _index_records(records)
    arities = {item.name: len(item.type_parameters) for item in records}
    graph: dict[str, set[str]] = {name: set() for name in by_name}
    for declaration in records:
        for _field, type_text in declaration.fields:
            ref = parse_type_ref_v2(type_text, arities)
            dependencies = _generic_dependencies(ref)
            unknown = dependencies - set(by_name)
            if unknown:
                _fail("TEVS_V2_PROGRAM_RECORD_DEP", f"record {declaration.name!r} references undeclared generic records {sorted(unknown)}")
            graph[declaration.name].update(dependencies)
    ready = sorted(name for name, deps in graph.items() if not deps)
    result: list[str] = []
    remaining = {name: set(deps) for name, deps in graph.items()}
    while ready:
        name = ready.pop(0)
        if name in result: continue
        result.append(name)
        for other in sorted(remaining):
            if name in remaining[other]:
                remaining[other].remove(name)
                if not remaining[other] and other not in result and other not in ready:
                    ready.append(other); ready.sort()
    if len(result) != len(records):
        cycle = sorted(name for name in remaining if name not in result)
        _fail("TEVS_V2_PROGRAM_RECORD_CYCLE", f"generic record dependency cycle: {cycle}")
    return tuple(result)


def _generic_dependencies(ref: TypeRefV2) -> set[str]:
    result = {ref.name} if ref.kind == "user_generic" else set()
    for child in ref.arguments:
        result.update(_generic_dependencies(child))
    return result


def _method_symbol(receiver_type: str, method_name: str) -> str:
    digest = _hash({
        "schema": "TEV_SCRIPT_V2_METHOD_SYMBOL_R1",
        "receiver_type": receiver_type,
        "method_name": method_name,
    })[:24]
    return f"__tev_method_{digest}"


GENERIC_PROTOCOL_IMPL_COHERENCE_POLICY_V2 = "non_overlapping_exact_receiver_v1"
GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2 = "non_overlapping_structural_receiver_v1"
GENERIC_PROTOCOL_IMPL_RECEIVER_PATTERN_POLICY_V2 = "linear_structural_pattern_v1"
GENERIC_PROTOCOL_IMPL_NONLINEAR_PATTERN_POLICY_V2 = "nonlinear_first_order_pattern_v1"
GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2 = "first_order_unification_occurs_check_v1"
GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_PATTERN_POLICY_V2 = "anchored_forward_associated_projection_v1"
GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_VALIDATION_POLICY_V2 = "prerequisite_witness_type_id_equality_v1"
GENERIC_PROTOCOL_IMPL_DEMAND_POLICY_V2 = "demand_specialization_only_v1"
GENERIC_PROTOCOL_IMPL_PREREQUISITE_POLICY_V2 = "resolve_all_before_specialization_v1"


def _specialize_source_expression_types_v2(
    expression: SourceExprV2,
    substitutions: Mapping[str, TypeRefV2],
    arities: Mapping[str, int],
    associated_substitutions: Mapping[tuple[str, str], TypeRefV2] | None = None,
) -> SourceExprV2:
    value = expression.value
    if expression.kind == "call":
        name, type_arguments, named_fields = value
        specialized_type_arguments = tuple(
            _render_type(_substitute_type(parse_type_ref_v2(str(item), arities), substitutions, associated_substitutions))
            for item in type_arguments
        )
        value = (name, specialized_type_arguments, named_fields)
    elif expression.kind in {"task_scope", "task_dag"}:
        value = tuple(
            (
                name,
                _render_type(_substitute_type(parse_type_ref_v2(str(type_text), arities), substitutions, associated_substitutions)),
            )
            for name, type_text in value
        )
    elif expression.kind == "while":
        accumulator_name, accumulator_type, maximum = value
        value = (
            accumulator_name,
            _render_type(_substitute_type(parse_type_ref_v2(str(accumulator_type), arities), substitutions, associated_substitutions)),
            maximum,
        )
    elif expression.kind == "for_fold":
        bindings, accumulator_name, accumulator_type = value
        value = (
            bindings,
            accumulator_name,
            _render_type(_substitute_type(parse_type_ref_v2(str(accumulator_type), arities), substitutions, associated_substitutions)),
        )
    return SourceExprV2(
        expression.kind,
        value,
        tuple(
            _specialize_source_expression_types_v2(
                child, substitutions, arities, associated_substitutions
            )
            for child in expression.children
        ),
    )


def _validate_generic_impl_symbolic_type_v2(
    type_text: str,
    *,
    type_parameters: frozenset[str],
    types: GenericRegistryV2,
    context: str,
    associated_authority: Mapping[str, frozenset[str]] | None = None,
) -> str:
    arities = types.generic_arities()
    ref = parse_type_ref_v2(type_text, arities)

    def visit(item: TypeRefV2) -> None:
        if item.kind == "associated":
            root, member = associated_type_parts_v2(item)
            allowed = (associated_authority or {}).get(root, frozenset())
            if root not in type_parameters or member not in allowed:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_PROJECTION",
                    f"{context} contains unauthorized associated projection {root}::{member}",
                )
            return
        if item.kind == "named":
            if item.name in type_parameters:
                return
            try:
                resolved = types.resolve_source_type(item.name)
                types.materialize_resolved_type(resolved)
            except TevScriptError as error:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_TYPE",
                    f"{context} contains unresolved type {item.name!r}: {error.diagnostic.message}",
                )
            return
        for child in item.arguments:
            visit(child)

    visit(ref)
    return _render_type(ref)


def _type_parameter_alpha_substitutions_v2(
    type_parameters: Sequence[str],
) -> dict[str, TypeRefV2]:
    return {
        name: TypeRefV2("named", f"__T{index}")
        for index, name in enumerate(type_parameters)
    }


@dataclass(frozen=True, slots=True)
class _GenericImplReceiverMatchV2:
    substitutions: tuple[tuple[str, TypeRefV2], ...]
    source_arguments: tuple[str, ...]
    type_argument_ids: tuple[str, ...]
    associated_observations: tuple[tuple[str, str, str, str], ...] = ()

    def substitution_map(self) -> dict[str, TypeRefV2]:
        return dict(self.substitutions)

    def validate_associated_projections(
        self,
        *,
        associated_substitutions: Mapping[tuple[str, str], TypeRefV2],
        types: GenericRegistryV2,
        receiver_source_type: str,
    ) -> tuple[tuple[str, str, str], ...]:
        validated: list[tuple[str, str, str]] = []
        for root, member, actual_source_type, actual_type_id in self.associated_observations:
            expected_ref = associated_substitutions.get((root, member))
            if expected_ref is None:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_RECEIVER_ASSOCIATED_WITNESS",
                    f"receiver pattern projection {root}::{member} has no prerequisite witness binding for {receiver_source_type}",
                )
            expected_source_type = _render_type(expected_ref)
            expected = types.materialize_source_type(expected_source_type)
            if expected.type_id != actual_type_id:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_RECEIVER_ASSOCIATED_MISMATCH",
                    f"receiver {receiver_source_type} binds projection {root}::{member} to {actual_type_id}, expected {expected.type_id}",
                )
            validated.append((root, member, actual_type_id))
        return tuple(sorted(validated))


@dataclass(frozen=True, slots=True)
class _GenericImplReceiverPatternV2:
    source_type: str
    record_name: str
    type_parameters: tuple[str, ...]
    type_ref: TypeRefV2
    direct: bool

    @classmethod
    def build(
        cls,
        receiver_type: str,
        *,
        type_parameters: Sequence[str],
        records: Mapping[str, GenericRecordSourceV2],
        types: GenericRegistryV2,
        associated_authority: Mapping[str, frozenset[str]] | None = None,
    ) -> "_GenericImplReceiverPatternV2":
        parameters = tuple(type_parameters)
        parameter_set = frozenset(parameters)
        canonical = _validate_generic_impl_symbolic_type_v2(
            receiver_type,
            type_parameters=parameter_set,
            types=types,
            context="generic impl receiver pattern",
            associated_authority=associated_authority,
        )
        ref = parse_type_ref_v2(canonical, types.generic_arities())
        if ref.kind != "user_generic" or ref.name not in records:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN",
                f"generic impl receiver must be a declared generic record, got {canonical}",
            )
        occurrences: list[str] = []
        anchored_parameters: set[str] = set()

        def visit(item: TypeRefV2) -> None:
            if item.kind == "associated":
                root, member = associated_type_parts_v2(item)
                if root not in anchored_parameters:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_RECEIVER_ASSOCIATED_ANCHOR",
                        f"receiver pattern projection {root}::{member} requires an earlier nominal occurrence of {root}",
                    )
                return
            if item.kind == "named" and item.name in parameter_set:
                occurrences.append(item.name)
                anchored_parameters.add(item.name)
                return
            for child in item.arguments:
                visit(child)

        visit(ref)
        if set(occurrences) != parameter_set:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN",
                f"generic impl receiver {canonical} must expose every impl type parameter at least once",
            )
        first_occurrence_order: list[str] = []
        seen_occurrences: set[str] = set()
        for occurrence in occurrences:
            if occurrence in seen_occurrences:
                continue
            seen_occurrences.add(occurrence)
            first_occurrence_order.append(occurrence)
        if tuple(first_occurrence_order) != parameters:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN",
                f"generic impl receiver type parameter first-occurrence DFS order must match {parameters}",
            )
        direct = (
            len(ref.arguments) == len(parameters)
            and all(
                argument.kind == "named" and argument.name == parameter
                for argument, parameter in zip(ref.arguments, parameters, strict=True)
            )
        )
        return cls(canonical, ref.name, parameters, ref, direct)

    def alpha_shape_key(self) -> str:
        parameter_ordinals = {name: index for index, name in enumerate(self.type_parameters)}
        alpha = _type_parameter_alpha_substitutions_v2(self.type_parameters)
        associated_pairs: set[tuple[str, str]] = set()
        stack = [self.type_ref]
        while stack:
            current = stack.pop()
            if current.kind == "associated":
                root, member = associated_type_parts_v2(current)
                if root in parameter_ordinals:
                    associated_pairs.add((root, member))
            stack.extend(current.arguments)
        associated = {
            (root, member): TypeRefV2(
                "associated", f"__T{parameter_ordinals[root]}::{member}"
            )
            for root, member in associated_pairs
        }
        return _render_type(_substitute_type(self.type_ref, alpha, associated))

    @property
    def has_associated_projections(self) -> bool:
        stack = [self.type_ref]
        while stack:
            current = stack.pop()
            if current.kind == "associated":
                return True
            stack.extend(current.arguments)
        return False

    @property
    def nonlinear(self) -> bool:
        parameter_set = frozenset(self.type_parameters)
        counts = {name: 0 for name in self.type_parameters}

        def visit(item: TypeRefV2) -> None:
            if item.kind == "named" and item.name in parameter_set:
                counts[item.name] += 1
                return
            for child in item.arguments:
                visit(child)

        visit(self.type_ref)
        return any(count > 1 for count in counts.values())

    @classmethod
    def from_template(
        cls,
        declaration: GenericProtocolImplSourceV2,
        template: GenericProtocolImplTemplateV2,
        *,
        types: GenericRegistryV2,
    ) -> "_GenericImplReceiverPatternV2":
        ref = parse_type_ref_v2(template.receiver_pattern, types.generic_arities())
        direct = (
            len(ref.arguments) == len(declaration.type_parameters)
            and all(
                argument.kind == "named" and argument.name == parameter
                for argument, parameter in zip(ref.arguments, declaration.type_parameters, strict=True)
            )
        )
        return cls(
            template.receiver_pattern,
            template.record_name,
            declaration.type_parameters,
            ref,
            direct,
        )

    def match(
        self,
        receiver_source_type: str,
        *,
        types: GenericRegistryV2,
    ) -> _GenericImplReceiverMatchV2 | None:
        arities = types.generic_arities()
        actual = parse_type_ref_v2(_canon_type(receiver_source_type, arities), arities)
        bindings: dict[str, TypeRefV2] = {}
        observations: list[tuple[str, str, str, str]] = []
        parameter_set = frozenset(self.type_parameters)

        def bind(pattern: TypeRefV2, value: TypeRefV2) -> bool:
            if pattern.kind == "associated":
                root, member = associated_type_parts_v2(pattern)
                if root not in bindings:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_RECEIVER_ASSOCIATED_ANCHOR",
                        f"receiver pattern projection {root}::{member} was reached before binding {root}",
                    )
                actual_source_type = _render_type(value)
                actual_resolved = types.materialize_source_type(actual_source_type)
                observations.append((root, member, actual_source_type, actual_resolved.type_id))
                return True
            if pattern.kind == "named" and pattern.name in parameter_set:
                prior = bindings.get(pattern.name)
                if prior is not None:
                    return prior == value
                bindings[pattern.name] = value
                return True
            if (
                pattern.kind != value.kind
                or pattern.name != value.name
                or pattern.const_arguments != value.const_arguments
                or len(pattern.arguments) != len(value.arguments)
            ):
                return False
            return all(bind(left, right) for left, right in zip(pattern.arguments, value.arguments, strict=True))

        if not bind(self.type_ref, actual):
            return None
        if set(bindings) != parameter_set:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN",
                f"generic impl pattern {self.source_type} did not bind its exact type parameter set",
            )
        source_arguments: list[str] = []
        type_argument_ids: list[str] = []
        substitutions: list[tuple[str, TypeRefV2]] = []
        for parameter in self.type_parameters:
            argument = bindings[parameter]
            substitutions.append((parameter, argument))
            source_argument = _render_type(argument)
            resolved = types.materialize_source_type(source_argument)
            source_arguments.append(source_argument)
            type_argument_ids.append(resolved.type_id)
        return _GenericImplReceiverMatchV2(
            tuple(substitutions),
            tuple(source_arguments),
            tuple(type_argument_ids),
            tuple(observations),
        )

    def overlaps(self, other: "_GenericImplReceiverPatternV2") -> bool:
        if self.record_name != other.record_name:
            return False
        left_parameters = frozenset(self.type_parameters)
        right_parameters = frozenset(other.type_parameters)
        substitution: dict[tuple[str, ...], object] = {}

        def term(item: TypeRefV2, side: str, variables: frozenset[str]) -> object:
            if item.kind == "named" and item.name in variables:
                return ("$var", side, item.name)
            if item.kind == "associated":
                root, member = associated_type_parts_v2(item)
                return ("$assoc", side, root, member)
            return (
                "$node",
                item.kind,
                item.name,
                item.const_arguments,
                tuple(term(child, side, variables) for child in item.arguments),
            )

        def is_variable(value: object) -> bool:
            return (
                isinstance(value, tuple)
                and len(value) in {3, 4}
                and value[0] in {"$var", "$assoc"}
            )

        def dereference(value: object) -> object:
            seen: set[tuple[str, ...]] = set()
            while is_variable(value) and value in substitution and value not in seen:
                assert isinstance(value, tuple)
                seen.add(value)
                value = substitution[value]
            return value

        def occurs(variable: tuple[str, ...], value: object) -> bool:
            value = dereference(value)
            if value == variable:
                return True
            if isinstance(value, tuple) and len(value) == 5 and value[0] == "$node":
                return any(occurs(variable, child) for child in value[4])
            return False

        def unify(left: object, right: object) -> bool:
            left = dereference(left)
            right = dereference(right)
            if left == right:
                return True
            if is_variable(left):
                assert isinstance(left, tuple)
                if occurs(left, right):
                    return False
                substitution[left] = right
                return True
            if is_variable(right):
                assert isinstance(right, tuple)
                if occurs(right, left):
                    return False
                substitution[right] = left
                return True
            if not (
                isinstance(left, tuple)
                and isinstance(right, tuple)
                and len(left) == 5
                and len(right) == 5
                and left[0] == "$node"
                and right[0] == "$node"
            ):
                return False
            if left[1:4] != right[1:4] or len(left[4]) != len(right[4]):
                return False
            return all(unify(a, b) for a, b in zip(left[4], right[4], strict=True))

        return unify(
            term(self.type_ref, "left", left_parameters),
            term(other.type_ref, "right", right_parameters),
        )


@dataclass(frozen=True, slots=True)
class _ClosedGenericImplRefinementDomainV2:
    receiver_alpha_key: str
    entries: tuple[tuple[int, str, str, str], ...]

    @classmethod
    def build(
        cls,
        declaration: GenericProtocolImplSourceV2,
        receiver_shape: _GenericImplReceiverPatternV2,
        *,
        protocols: Mapping[str, ProtocolSourceV2],
        types: GenericRegistryV2,
    ) -> "_ClosedGenericImplRefinementDomainV2":
        ordinals = {name: index for index, name in enumerate(declaration.type_parameters)}
        protocols_by_parameter = {
            name: tuple(
                protocol_name
                for parameter, protocol_name in declaration.constraints
                if parameter == name
            )
            for name in declaration.type_parameters
        }
        entries: list[tuple[int, str, str, str]] = []
        for type_parameter, associated_name, required_type in declaration.associated_constraints:
            specification = _AssociatedConstraintSpecificationV2.from_validated_source(
                target_type_parameter=type_parameter,
                associated_name=associated_name,
                required_type=required_type,
                type_parameters=declaration.type_parameters,
                generic_arities=types.generic_arities(),
            )
            if specification.dependent:
                continue
            owner_protocol = _associated_owner_protocol_v2(
                function_name=f"generic impl {declaration.receiver_type} : {declaration.protocol_name}",
                type_parameter=type_parameter,
                associated_name=associated_name,
                protocol_names=protocols_by_parameter.get(type_parameter, ()),
                protocols=protocols,
                diagnostic_code="TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_ASSOCIATED",
            )
            required = types.materialize_source_type(specification.required_source_type)
            entries.append((
                ordinals[type_parameter],
                owner_protocol,
                associated_name,
                required.type_id,
            ))
        return cls(receiver_shape.alpha_shape_key(), tuple(sorted(entries)))

    def proven_disjoint(self, other: "_ClosedGenericImplRefinementDomainV2") -> bool:
        if self.receiver_alpha_key != other.receiver_alpha_key:
            return False
        left = {(ordinal, protocol, member): type_id for ordinal, protocol, member, type_id in self.entries}
        right = {(ordinal, protocol, member): type_id for ordinal, protocol, member, type_id in other.entries}
        for key in sorted(left.keys() & right.keys()):
            if left[key] != right[key]:
                return True
        return False


def _validate_generic_impl_internal_method_graph_v2(
    declarations: Sequence[GenericProtocolImplSourceV2],
) -> None:
    for declaration in declarations:
        method_names = {method.name for method in declaration.methods}
        graph: dict[str, set[str]] = {name: set() for name in method_names}

        def visit(owner: str, expression: SourceExprV2) -> None:
            if expression.kind == "call":
                name, _type_arguments, _named_fields = expression.value
                parts = str(name).split(".")
                if len(parts) == 2 and parts[0] == "self" and parts[1] in method_names:
                    graph[owner].add(parts[1])
            elif expression.kind == "method_call" and expression.children:
                receiver = expression.children[0]
                if receiver.kind == "name" and receiver.value == "self":
                    method_name = str(expression.value)
                    if method_name in method_names:
                        graph[owner].add(method_name)
            for child in expression.children:
                visit(owner, child)

        for method in declaration.methods:
            visit(method.name, method.body)

        remaining = {name: set(dependencies) for name, dependencies in graph.items()}
        ready = sorted(name for name, dependencies in remaining.items() if not dependencies)
        removed: list[str] = []
        while ready:
            name = ready.pop(0)
            if name in removed:
                continue
            removed.append(name)
            for other in sorted(remaining):
                if name in remaining[other]:
                    remaining[other].remove(name)
                    if not remaining[other] and other not in removed and other not in ready:
                        ready.append(other)
                        ready.sort()
        if len(removed) != len(graph):
            cycle_nodes = sorted(name for name in graph if name not in removed)
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_METHOD_CYCLE",
                f"generic impl {declaration.receiver_type} : {declaration.protocol_name} has internal method cycle {cycle_nodes}",
            )


def _validate_generic_impl_constraints_v2(
    declarations: Sequence[GenericProtocolImplSourceV2],
    protocols: Mapping[str, ProtocolSourceV2],
    generic_arities: Mapping[str, int],
) -> None:
    if not declarations:
        return
    adapters = tuple(
        GenericFunctionSourceV2(
            f"__tev_generic_impl_constraint_{index}",
            declaration.type_parameters,
            (),
            "Int",
            SourceExprV2("number", "0"),
            declaration.constraints,
            declaration.associated_constraints,
        )
        for index, declaration in enumerate(declarations)
    )
    _validate_function_constraints_v2(adapters, protocols, generic_arities)


def _validate_generic_impl_associated_constraint_targets_v2(
    declarations: Sequence[GenericProtocolImplSourceV2],
    types: GenericRegistryV2,
    protocols: Mapping[str, ProtocolSourceV2],
) -> None:
    if not declarations:
        return
    adapters = tuple(
        GenericFunctionSourceV2(
            f"__tev_generic_impl_constraint_{index}",
            declaration.type_parameters,
            (),
            "Int",
            SourceExprV2("number", "0"),
            declaration.constraints,
            declaration.associated_constraints,
        )
        for index, declaration in enumerate(declarations)
    )
    _validate_associated_constraint_targets_v2(adapters, types, protocols)


def _prepare_generic_protocol_impl_templates_v2(
    program_id: str,
    declarations: Sequence[GenericProtocolImplSourceV2],
    records: Mapping[str, GenericRecordSourceV2],
    protocols: Mapping[str, ProtocolSourceV2],
    protocol_hashes: Mapping[str, str],
    types: GenericRegistryV2,
    concrete_methods: Sequence[MethodSourceV2],
) -> tuple[
    tuple[GenericProtocolImplTemplateV2, ...],
    dict[tuple[str, str], tuple[tuple[GenericProtocolImplSourceV2, GenericProtocolImplTemplateV2], ...]],
]:
    if not declarations:
        return (), {}
    arities = types.generic_arities()
    concrete_method_receivers: dict[
        tuple[str, str],
        dict[str, _GenericImplReceiverPatternV2],
    ] = {}
    concrete_protocol_receivers: dict[
        tuple[str, str],
        dict[str, _GenericImplReceiverPatternV2],
    ] = {}
    for method in concrete_methods:
        canonical_receiver = _canon_type(method.receiver_type, arities)
        receiver_ref = parse_type_ref_v2(canonical_receiver, arities)
        if receiver_ref.kind != "user_generic":
            continue
        exact_shape = _GenericImplReceiverPatternV2(
            canonical_receiver,
            receiver_ref.name,
            (),
            receiver_ref,
            False,
        )
        concrete_method_receivers.setdefault((receiver_ref.name, method.name), {})[
            canonical_receiver
        ] = exact_shape
        for protocol_name in method.protocols:
            concrete_protocol_receivers.setdefault((receiver_ref.name, protocol_name), {})[
                canonical_receiver
            ] = exact_shape

    by_key: dict[
        tuple[str, str],
        list[tuple[GenericProtocolImplSourceV2, GenericProtocolImplTemplateV2]],
    ] = {}
    generic_family_methods: dict[
        str,
        list[tuple[
            _GenericImplReceiverPatternV2,
            frozenset[str],
            str,
            _ClosedGenericImplRefinementDomainV2,
        ]],
    ] = {}
    templates: list[GenericProtocolImplTemplateV2] = []
    for declaration in declarations:
        if not declaration.type_parameters or len(set(declaration.type_parameters)) != len(declaration.type_parameters):
            _fail("TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN", "generic impl requires unique type parameters")
        type_parameters = frozenset(declaration.type_parameters)
        protocol = protocols.get(declaration.protocol_name)
        if protocol is None:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_PROTOCOL",
                f"generic impl references unknown protocol {declaration.protocol_name!r}",
            )
        associated_authority: dict[str, frozenset[str]] = {}
        for type_parameter in declaration.type_parameters:
            member_owner_counts: dict[str, int] = {}
            for constrained_parameter, prerequisite_protocol_name in declaration.constraints:
                if constrained_parameter != type_parameter:
                    continue
                prerequisite_protocol = protocols.get(prerequisite_protocol_name)
                if prerequisite_protocol is None:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_PROTOCOL",
                        f"generic impl references unknown prerequisite protocol {prerequisite_protocol_name!r}",
                    )
                for associated_name in prerequisite_protocol.associated_types:
                    member_owner_counts[associated_name] = member_owner_counts.get(associated_name, 0) + 1
            associated_authority[type_parameter] = frozenset(
                name for name, count in member_owner_counts.items() if count == 1
            )
        receiver_shape = _GenericImplReceiverPatternV2.build(
            declaration.receiver_type,
            type_parameters=declaration.type_parameters,
            records=records,
            types=types,
            associated_authority=associated_authority,
        )
        receiver_pattern = receiver_shape.source_type
        receiver_ref = receiver_shape.type_ref
        refinement_domain = _ClosedGenericImplRefinementDomainV2.build(
            declaration,
            receiver_shape,
            protocols=protocols,
            types=types,
        )
        key = (receiver_ref.name, declaration.protocol_name)
        prior_same_protocol = by_key.setdefault(key, [])
        for prior_declaration, prior_template in prior_same_protocol:
            prior_shape = _GenericImplReceiverPatternV2.from_template(
                prior_declaration,
                prior_template,
                types=types,
            )
            if receiver_shape.overlaps(prior_shape):
                prior_domain = _ClosedGenericImplRefinementDomainV2.build(
                    prior_declaration,
                    prior_shape,
                    protocols=protocols,
                    types=types,
                )
                if not refinement_domain.proven_disjoint(prior_domain):
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                        f"generic impl receiver patterns {prior_template.receiver_pattern} and {receiver_pattern} overlap for protocol {declaration.protocol_name!r}",
                    )
        for concrete_receiver, concrete_shape in sorted(
            concrete_protocol_receivers.get(key, {}).items()
        ):
            if receiver_shape.overlaps(concrete_shape):
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                    f"generic impl receiver pattern {receiver_pattern} overlaps concrete protocol impl {concrete_receiver} : {declaration.protocol_name}",
                )

        provided_methods = {method.name: method for method in declaration.methods}
        required_methods = {method.name: method for method in protocol.methods}
        missing_methods = sorted(set(required_methods) - set(provided_methods))
        if missing_methods:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_SIGNATURE",
                f"generic impl {receiver_pattern} : {declaration.protocol_name} is missing methods {missing_methods}",
            )
        if len(provided_methods) != len(declaration.methods):
            _fail("TEVS_V2_PROGRAM_GENERIC_IMPL_SIGNATURE", "generic impl repeats a method name")
        method_names = set(provided_methods)
        concrete_collisions: list[tuple[str, str]] = []
        for method_name in sorted(method_names):
            for concrete_receiver, concrete_shape in sorted(
                concrete_method_receivers.get((receiver_ref.name, method_name), {}).items()
            ):
                if receiver_shape.overlaps(concrete_shape):
                    concrete_collisions.append((method_name, concrete_receiver))
        if concrete_collisions:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                f"generic impl receiver pattern {receiver_pattern} has concrete method overlap {concrete_collisions}",
            )
        prior_generic_entries = generic_family_methods.setdefault(receiver_ref.name, [])
        for prior_shape, prior_method_names, prior_protocol_name, prior_domain in prior_generic_entries:
            generic_collisions = sorted(method_names & prior_method_names)
            if generic_collisions and receiver_shape.overlaps(prior_shape):
                same_protocol_disjoint = (
                    prior_protocol_name == declaration.protocol_name
                    and refinement_domain.proven_disjoint(prior_domain)
                )
                if not same_protocol_disjoint:
                    _fail(
                        "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                        f"generic impl methods {generic_collisions} overlap another generic impl on receiver patterns {prior_shape.source_type} and {receiver_pattern}",
                    )
        prior_generic_entries.append((
            receiver_shape,
            frozenset(method_names),
            declaration.protocol_name,
            refinement_domain,
        ))

        provided_associated = dict(declaration.associated_types)
        if len(provided_associated) != len(declaration.associated_types):
            _fail("TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_TYPE", "generic impl repeats an associated type")
        required_associated = set(protocol.associated_types)
        if set(provided_associated) != required_associated:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_TYPE",
                f"generic impl associated types must equal {sorted(required_associated)}, got {sorted(provided_associated)}",
            )
        canonical_associated = {
            name: _validate_generic_impl_symbolic_type_v2(
                type_text,
                type_parameters=type_parameters,
                types=types,
                associated_authority=associated_authority,
                context=f"generic impl associated type {name}",
            )
            for name, type_text in provided_associated.items()
        }

        for method_name, contract in required_methods.items():
            implementation = provided_methods[method_name]
            implementation_parameters = tuple(
                _validate_generic_impl_symbolic_type_v2(
                    type_text,
                    type_parameters=type_parameters,
                    types=types,
                    context=f"generic impl method {method_name} parameter {parameter_name}",
                )
                for parameter_name, type_text in implementation.parameters
            )
            implementation_return = _validate_generic_impl_symbolic_type_v2(
                implementation.return_type,
                type_parameters=type_parameters,
                types=types,
                associated_authority=associated_authority,
                context=f"generic impl method {method_name} return",
            )
            contract_parameters = tuple(
                _project_protocol_type_v2(
                    type_text,
                    associated_source_types=canonical_associated,
                    arities=arities,
                    allow_unresolved_associated=True,
                )
                for _parameter_name, type_text in contract.parameters
            )
            contract_return = _project_protocol_type_v2(
                contract.return_type,
                associated_source_types=canonical_associated,
                arities=arities,
                allow_unresolved_associated=True,
            )
            if implementation_parameters != contract_parameters or implementation_return != contract_return:
                _fail(
                    "TEVS_V2_PROGRAM_GENERIC_IMPL_SIGNATURE",
                    f"generic impl method {receiver_pattern}.{method_name} does not match protocol {declaration.protocol_name}",
                )
        for method in declaration.methods:
            for parameter_name, type_text in method.parameters:
                _validate_generic_impl_symbolic_type_v2(
                    type_text,
                    type_parameters=type_parameters,
                    types=types,
                    associated_authority=associated_authority,
                    context=f"generic impl method {method.name} parameter {parameter_name}",
                )
            _validate_generic_impl_symbolic_type_v2(
                method.return_type,
                type_parameters=type_parameters,
                types=types,
                associated_authority=associated_authority,
                context=f"generic impl method {method.name} return",
            )
            for body_type_text in _source_expression_type_texts_v2(method.body):
                _validate_generic_impl_symbolic_type_v2(
                    body_type_text,
                    type_parameters=type_parameters,
                    types=types,
                    associated_authority=associated_authority,
                    context=f"generic impl method {method.name} body type",
                )

        parameter_ordinals = {name: index for index, name in enumerate(declaration.type_parameters)}
        prerequisite_constraints = tuple(sorted(
            (parameter_ordinals[type_parameter], protocol_hashes[protocol_name])
            for type_parameter, protocol_name in declaration.constraints
        ))

        alpha = _type_parameter_alpha_substitutions_v2(declaration.type_parameters)
        alpha_associated_substitutions = {
            (type_parameter, associated_name): TypeRefV2(
                "associated", f"__T{parameter_ordinals[type_parameter]}::{associated_name}"
            )
            for type_parameter, associated_names in associated_authority.items()
            for associated_name in associated_names
        }

        def alpha_type(type_text: str) -> str:
            return _render_type(_substitute_type(
                parse_type_ref_v2(type_text, arities),
                alpha,
                alpha_associated_substitutions,
            ))

        prerequisite_specifications = tuple(
            _AssociatedConstraintSpecificationV2.from_validated_source(
                target_type_parameter=type_parameter,
                associated_name=associated_name,
                required_type=required_type,
                type_parameters=declaration.type_parameters,
                generic_arities=arities,
            )
            for type_parameter, associated_name, required_type in declaration.associated_constraints
        )
        has_dependent_prerequisite_refinement = any(
            specification.dependent for specification in prerequisite_specifications
        )
        prerequisite_associated_constraints = tuple(sorted(
            (
                parameter_ordinals[type_parameter],
                associated_name,
                alpha_type(required_type),
            )
            for type_parameter, associated_name, required_type in declaration.associated_constraints
        ))

        alpha_receiver = _render_type(_substitute_type(receiver_ref, alpha, alpha_associated_substitutions))
        alpha_associated = [
            {"name": name, "type": alpha_type(type_text)}
            for name, type_text in sorted(canonical_associated.items())
        ]
        alpha_methods = []
        for method in sorted(declaration.methods, key=lambda item: item.name):
            alpha_body = _specialize_source_expression_types_v2(
                method.body, alpha, arities, alpha_associated_substitutions
            )
            alpha_methods.append({
                "name": method.name,
                "parameters": [
                    {"name": parameter_name, "type": alpha_type(type_text)}
                    for parameter_name, type_text in method.parameters
                ],
                "return_type": alpha_type(method.return_type),
                "body": _source_expression_hash_payload_v2(alpha_body),
            })
        payload = {
            "schema": "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R1",
            "owner_id": program_id,
            "coherence_policy": GENERIC_PROTOCOL_IMPL_COHERENCE_POLICY_V2,
            "demand_policy": GENERIC_PROTOCOL_IMPL_DEMAND_POLICY_V2,
            "protocol_hash": protocol_hashes[declaration.protocol_name],
            "type_parameter_count": len(declaration.type_parameters),
            "receiver_pattern": alpha_receiver,
            "associated_types": alpha_associated,
            "methods": alpha_methods,
        }
        if prerequisite_constraints:
            payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R2"
            payload["prerequisite_policy"] = GENERIC_PROTOCOL_IMPL_PREREQUISITE_POLICY_V2
            payload["prerequisite_constraints"] = [
                {"type_parameter_ordinal": ordinal, "protocol_hash": protocol_hash}
                for ordinal, protocol_hash in prerequisite_constraints
            ]
            if prerequisite_associated_constraints:
                payload["schema"] = (
                    "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R4"
                    if has_dependent_prerequisite_refinement
                    else "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R3"
                )
                if has_dependent_prerequisite_refinement:
                    payload["dependent_associated_constraint_policy"] = "witness_type_id_equality_v1"
                payload["prerequisite_associated_constraints"] = [
                    {
                        "type_parameter_ordinal": ordinal,
                        "associated_name": associated_name,
                        "required_source_type": required_source_type,
                    }
                    for ordinal, associated_name, required_source_type in prerequisite_associated_constraints
                ]
        if receiver_shape.has_associated_projections:
            payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R7"
            payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
            payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_PATTERN_POLICY_V2
            payload["associated_projection_validation_policy"] = GENERIC_PROTOCOL_IMPL_ASSOCIATED_RECEIVER_VALIDATION_POLICY_V2
            payload["pattern_overlap_policy"] = GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2
        elif receiver_shape.nonlinear:
            payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R6"
            payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
            payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_NONLINEAR_PATTERN_POLICY_V2
            payload["pattern_overlap_policy"] = GENERIC_PROTOCOL_IMPL_PATTERN_OVERLAP_POLICY_V2
        elif not receiver_shape.direct:
            payload["schema"] = "TEV_SCRIPT_V2_GENERIC_PROTOCOL_IMPL_TEMPLATE_R5"
            payload["coherence_policy"] = GENERIC_PROTOCOL_IMPL_STRUCTURAL_COHERENCE_POLICY_V2
            payload["receiver_pattern_policy"] = GENERIC_PROTOCOL_IMPL_RECEIVER_PATTERN_POLICY_V2
        template = GenericProtocolImplTemplateV2(
            declaration.type_parameters,
            receiver_pattern,
            receiver_ref.name,
            declaration.protocol_name,
            protocol_hashes[declaration.protocol_name],
            _hash(payload),
            prerequisite_constraints,
            prerequisite_associated_constraints,
        )
        prior_same_protocol.append((declaration, template))
        templates.append(template)
    frozen_index = {
        key: tuple(sorted(items, key=lambda pair: pair[1].template_hash))
        for key, items in by_key.items()
    }
    return tuple(sorted(templates, key=lambda item: (item.record_name, item.protocol_name, item.template_hash))), frozen_index


def _match_generic_protocol_impl_receiver_v2(
    declaration: GenericProtocolImplSourceV2,
    template: GenericProtocolImplTemplateV2,
    receiver_source_type: str,
    types: GenericRegistryV2,
) -> tuple[dict[str, TypeRefV2], tuple[str, ...], tuple[str, ...]] | None:
    pattern = _GenericImplReceiverPatternV2.from_template(
        declaration,
        template,
        types=types,
    )
    return pattern.match(receiver_source_type, types=types)


def _specialize_generic_protocol_impl_source_v2(
    declaration: GenericProtocolImplSourceV2,
    template: GenericProtocolImplTemplateV2,
    receiver_source_type: str,
    types: GenericRegistryV2,
    associated_substitutions: Mapping[tuple[str, str], TypeRefV2] | None = None,
) -> tuple[
    tuple[MethodSourceV2, ...],
    tuple[AssociatedTypeBindingSourceV2, ...],
    tuple[GenericFunctionSourceV2, ...],
    dict[tuple[str, str], str],
    tuple[str, ...],
]:
    matched = _match_generic_protocol_impl_receiver_v2(
        declaration,
        template,
        receiver_source_type,
        types,
    )
    if matched is None:
        _fail(
            "TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN",
            f"generic impl template {template.receiver_pattern} does not match {receiver_source_type}",
        )
    substitutions = matched.substitution_map()
    type_argument_ids = matched.type_argument_ids
    arities = types.generic_arities()
    canonical_receiver = _canon_type(receiver_source_type, arities)
    resolved_receiver = types.materialize_source_type(canonical_receiver)
    group_hash = _hash({
        "schema": "TEV_SCRIPT_V2_GENERIC_IMPL_SPECIALIZED_GROUP_R1",
        "template_hash": template.template_hash,
        "receiver_runtime_type": resolved_receiver.type_id,
        "type_argument_ids": list(type_argument_ids),
    })
    implementation_group = f"generic_impl_specialized_{group_hash}"

    def specialize_type(type_text: str) -> str:
        ref = parse_type_ref_v2(type_text, arities)
        specialized = _substitute_type(ref, substitutions, associated_substitutions)
        if _type_ref_contains_associated_v2(specialized):
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_TYPE",
                f"generic impl specialization leaves unresolved associated type in {type_text!r}",
            )
        result = _render_type(specialized)
        resolved = types.resolve_source_type(result)
        types.materialize_resolved_type(resolved)
        return result

    concrete_methods: list[MethodSourceV2] = []
    function_sources: list[GenericFunctionSourceV2] = []
    dispatch: dict[tuple[str, str], str] = {}
    for method in declaration.methods:
        parameters = tuple(
            (parameter_name, specialize_type(type_text))
            for parameter_name, type_text in method.parameters
        )
        return_type = specialize_type(method.return_type)
        body = _specialize_source_expression_types_v2(
            method.body, substitutions, arities, associated_substitutions
        )
        concrete = MethodSourceV2(
            canonical_receiver,
            method.name,
            parameters,
            return_type,
            body,
            (declaration.protocol_name,),
            implementation_group,
        )
        concrete_methods.append(concrete)
        symbol = _method_symbol(canonical_receiver, method.name)
        key = (canonical_receiver, method.name)
        if key in dispatch:
            _fail(
                "TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE",
                f"generic impl specialization repeats method {method.name!r} for {canonical_receiver}",
            )
        dispatch[key] = symbol
        function_sources.append(GenericFunctionSourceV2(
            symbol,
            (),
            (("self", canonical_receiver), *parameters),
            return_type,
            body,
        ))

    associated_bindings = tuple(
        AssociatedTypeBindingSourceV2(
            canonical_receiver,
            (declaration.protocol_name,),
            associated_name,
            specialize_type(type_text),
            implementation_group,
        )
        for associated_name, type_text in declaration.associated_types
    )
    return (
        tuple(concrete_methods),
        associated_bindings,
        tuple(function_sources),
        dispatch,
        type_argument_ids,
    )


def _desugar_methods_v2(
    methods: Sequence[MethodSourceV2],
    records: Mapping[str, GenericRecordSourceV2],
) -> tuple[tuple[GenericFunctionSourceV2, ...], dict[tuple[str, str], str]]:
    arities = {name: len(item.type_parameters) for name, item in records.items()}
    functions: list[GenericFunctionSourceV2] = []
    dispatch: dict[tuple[str, str], str] = {}
    for method in methods:
        receiver_type = _canon_type(method.receiver_type, arities)
        receiver_ref = parse_type_ref_v2(receiver_type, arities)
        if receiver_ref.kind != "user_generic" or receiver_ref.name not in records:
            _fail(
                "TEVS_V2_PROGRAM_METHOD_RECEIVER",
                f"impl receiver must be a declared record type, got {receiver_type}",
            )
        key = (receiver_type, method.name)
        if key in dispatch:
            _fail(
                "TEVS_V2_PROGRAM_METHOD_DUPLICATE",
                f"duplicate method {method.name!r} for receiver {receiver_type}",
            )
        symbol = _method_symbol(receiver_type, method.name)
        dispatch[key] = symbol
        functions.append(GenericFunctionSourceV2(
            symbol,
            (),
            (("self", receiver_type), *method.parameters),
            method.return_type,
            method.body,
        ))
    return tuple(functions), dispatch


def _validate_method_types_v2(methods: Sequence[MethodSourceV2], types: GenericRegistryV2) -> None:
    arities = types.generic_arities()
    seen: set[tuple[str, str]] = set()
    for method in methods:
        receiver_type = _canon_type(method.receiver_type, arities)
        key = (receiver_type, method.name)
        if key in seen:
            _fail("TEVS_V2_PROGRAM_METHOD_DUPLICATE", f"duplicate method {method.name!r} for receiver {receiver_type}")
        seen.add(key)
        try:
            resolved_receiver = types.materialize_source_type(receiver_type)
            descriptor = types.table.require(resolved_receiver.type_id, context="impl receiver")
        except TevScriptError as error:
            _fail("TEVS_V2_PROGRAM_METHOD_RECEIVER", f"impl receiver {receiver_type!r} is not a concrete resolvable record: {error.diagnostic.message}")
        if descriptor.kind != "record":
            _fail("TEVS_V2_PROGRAM_METHOD_RECEIVER", f"impl receiver {receiver_type!r} is not a record")
        for parameter_name, type_text in method.parameters:
            try:
                resolved = types.materialize_source_type(_canon_type(type_text, arities))
            except TevScriptError as error:
                _fail("TEVS_V2_PROGRAM_METHOD_TYPE", f"method {method.name!r} parameter {parameter_name!r} is not concrete: {error.diagnostic.message}")
        try:
            resolved_return = types.materialize_source_type(_canon_type(method.return_type, arities))
        except TevScriptError as error:
            _fail("TEVS_V2_PROGRAM_METHOD_TYPE", f"method {method.name!r} return type is not concrete: {error.diagnostic.message}")


def _index_protocols(protocols: Sequence[ProtocolSourceV2]) -> dict[str, ProtocolSourceV2]:
    result: dict[str, ProtocolSourceV2] = {}
    for item in protocols:
        if item.name in result:
            _fail("TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE", f"duplicate protocol {item.name!r}")
        result[item.name] = item
    return result


def _type_ref_contains_associated_v2(ref: TypeRefV2) -> bool:
    return ref.kind == "associated" or any(_type_ref_contains_associated_v2(child) for child in ref.arguments)


def _validate_protocol_type_ref_v2(
    ref: TypeRefV2,
    *,
    protocol_name: str,
    associated_names: frozenset[str],
    types: GenericRegistryV2,
) -> None:
    if ref.kind == "associated":
        root, member = associated_type_parts_v2(ref)
        if root != "Self" or member not in associated_names:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_ASSOCIATED_TYPE",
                f"protocol {protocol_name!r} references unauthorized associated projection {root}::{member}",
            )
        return
    if ref.kind == "named":
        try:
            resolved = types.resolve_source_type(ref.name)
            types.materialize_resolved_type(resolved)
        except TevScriptError as error:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_TYPE",
                f"protocol {protocol_name!r} type {ref.name!r} is not concrete: {error.diagnostic.message}",
            )
        return
    for child in ref.arguments:
        _validate_protocol_type_ref_v2(
            child,
            protocol_name=protocol_name,
            associated_names=associated_names,
            types=types,
        )


def _project_protocol_type_v2(
    type_text: str,
    *,
    associated_source_types: Mapping[str, str],
    arities: Mapping[str, int],
    allow_unresolved_associated: bool = False,
) -> str:
    ref = parse_type_ref_v2(type_text, arities)
    associated_substitutions = {
        ("Self", name): parse_type_ref_v2(source_type, arities)
        for name, source_type in associated_source_types.items()
    }
    projected = _substitute_type(ref, {}, associated_substitutions)
    if _type_ref_contains_associated_v2(projected) and not allow_unresolved_associated:
        _fail(
            "TEVS_V2_PROGRAM_PROTOCOL_ASSOCIATED_TYPE",
            f"protocol method type {type_text!r} contains unresolved associated projection",
        )
    return _render_type(projected)


def _compile_protocol_contracts_v2(
    program_id: str,
    protocols: Mapping[str, ProtocolSourceV2],
    types: GenericRegistryV2,
) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
    arities = types.generic_arities()
    by_name: dict[str, str] = {}
    hashes: list[tuple[str, str]] = []
    for name, protocol in sorted(protocols.items()):
        associated_names = tuple(sorted(protocol.associated_types))
        if len(set(associated_names)) != len(associated_names):
            _fail("TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_ASSOCIATED_TYPE", f"protocol {name!r} repeats an associated type")
        associated_set = frozenset(associated_names)
        canonical_methods = []
        for method in sorted(protocol.methods, key=lambda item: item.name):
            parameter_types = []
            for _parameter_name, type_text in method.parameters:
                canonical = _canon_type(type_text, arities)
                ref = parse_type_ref_v2(canonical, arities)
                if _type_ref_contains_associated_v2(ref):
                    _validate_protocol_type_ref_v2(ref, protocol_name=name, associated_names=associated_set, types=types)
                else:
                    try:
                        resolved = types.resolve_source_type(canonical)
                        types.materialize_resolved_type(resolved)
                    except TevScriptError as error:
                        _fail(
                            "TEVS_V2_PROGRAM_PROTOCOL_TYPE",
                            f"protocol {name!r} method {method.name!r} parameter type {canonical!r} is not concrete: {error.diagnostic.message}",
                        )
                parameter_types.append(canonical)
            return_type = _canon_type(method.return_type, arities)
            return_ref = parse_type_ref_v2(return_type, arities)
            if _type_ref_contains_associated_v2(return_ref):
                _validate_protocol_type_ref_v2(return_ref, protocol_name=name, associated_names=associated_set, types=types)
            else:
                try:
                    resolved_return = types.resolve_source_type(return_type)
                    types.materialize_resolved_type(resolved_return)
                except TevScriptError as error:
                    _fail(
                        "TEVS_V2_PROGRAM_PROTOCOL_TYPE",
                        f"protocol {name!r} method {method.name!r} return type {return_type!r} is not concrete: {error.diagnostic.message}",
                    )
            canonical_methods.append({
                "name": method.name,
                "parameter_types": parameter_types,
                "return_type": return_type,
            })
        payload = {
            "schema": "TEV_SCRIPT_V2_PROTOCOL_R1",
            "owner_id": program_id,
            "name": name,
            "methods": canonical_methods,
        }
        if associated_names:
            payload["schema"] = "TEV_SCRIPT_V2_PROTOCOL_R2"
            payload["associated_types"] = list(associated_names)
        protocol_hash = _hash(payload)
        by_name[name] = protocol_hash
        hashes.append((f"{program_id}.{name}", protocol_hash))
    return tuple(hashes), by_name


def _build_protocol_witnesses_v2(
    methods: Sequence[MethodSourceV2],
    protocols: Mapping[str, ProtocolSourceV2],
    protocol_hashes: Mapping[str, str],
    function_templates: Mapping[str, GenericPureFunctionTemplateV2],
    types: GenericRegistryV2,
    method_constraint_specializations: Mapping[str, Sequence[str]] | None = None,
    associated_type_bindings: Sequence[AssociatedTypeBindingSourceV2] = (),
) -> tuple[ProtocolWitnessV2, ...]:
    arities = types.generic_arities()
    groups: dict[tuple[str, str, str], list[MethodSourceV2]] = {}
    for method in methods:
        for protocol_name in method.protocols:
            receiver_type = _canon_type(method.receiver_type, arities)
            groups.setdefault((method.implementation_group, receiver_type, protocol_name), []).append(method)
    binding_groups: dict[tuple[str, str, str], list[AssociatedTypeBindingSourceV2]] = {}
    for binding in associated_type_bindings:
        receiver_type = _canon_type(binding.receiver_type, arities)
        for protocol_name in binding.protocols:
            binding_groups.setdefault((binding.implementation_group, receiver_type, protocol_name), []).append(binding)

    witnesses: list[ProtocolWitnessV2] = []
    seen_conformance: set[tuple[str, str]] = set()
    for (group, receiver_type, protocol_name), block_methods in sorted(groups.items(), key=lambda item: item[0]):
        protocol = protocols.get(protocol_name)
        if protocol is None:
            _fail("TEVS_V2_PROGRAM_PROTOCOL_UNKNOWN", f"impl references unknown protocol {protocol_name!r}")
        conformance_key = (receiver_type, protocol_name)
        if conformance_key in seen_conformance:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_IMPL",
                f"duplicate protocol implementation {protocol_name!r} for {receiver_type}",
            )
        seen_conformance.add(conformance_key)
        provided = {method.name: method for method in block_methods}
        required = {method.name: method for method in protocol.methods}
        missing = sorted(set(required) - set(provided))
        if missing:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_MISSING_METHOD",
                f"impl {receiver_type} : {protocol_name} is missing required methods {missing}",
            )

        block_bindings = binding_groups.get((group, receiver_type, protocol_name), [])
        binding_by_name: dict[str, AssociatedTypeBindingSourceV2] = {}
        for binding in block_bindings:
            if binding.name in binding_by_name:
                _fail("TEVS_V2_PROGRAM_ASSOCIATED_TYPE_DUPLICATE", f"duplicate associated type binding {binding.name!r}")
            binding_by_name[binding.name] = binding
        required_associated = set(protocol.associated_types)
        missing_associated = sorted(required_associated - set(binding_by_name))
        if missing_associated:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_MISSING_ASSOCIATED_TYPE",
                f"impl {receiver_type} : {protocol_name} is missing associated types {missing_associated}",
            )
        extra_associated = sorted(set(binding_by_name) - required_associated)
        if extra_associated:
            _fail(
                "TEVS_V2_PROGRAM_PROTOCOL_UNKNOWN_ASSOCIATED_TYPE",
                f"impl {receiver_type} : {protocol_name} binds undeclared associated types {extra_associated}",
            )
        associated_entries: list[tuple[str, str, str]] = []
        associated_source_types: dict[str, str] = {}
        for associated_name in sorted(required_associated):
            binding = binding_by_name[associated_name]
            canonical_source = _canon_type(binding.type_text, arities)
            try:
                resolved_associated = types.resolve_source_type(canonical_source)
                types.materialize_resolved_type(resolved_associated)
            except TevScriptError as error:
                _fail(
                    "TEVS_V2_PROGRAM_ASSOCIATED_TYPE_BINDING",
                    f"associated type {receiver_type}::{associated_name} must resolve concretely: {error.diagnostic.message}",
                )
            associated_source_types[associated_name] = canonical_source
            associated_entries.append((associated_name, canonical_source, resolved_associated.type_id))

        method_hashes: list[tuple[str, str]] = []
        method_constraint_bindings: list[tuple[str, tuple[str, ...]]] = []
        constraint_map = method_constraint_specializations or {}
        for method_name, contract in sorted(required.items()):
            implementation = provided[method_name]
            contract_parameters = tuple(
                _project_protocol_type_v2(type_text, associated_source_types=associated_source_types, arities=arities)
                for _name, type_text in contract.parameters
            )
            implementation_parameters = tuple(_canon_type(type_text, arities) for _name, type_text in implementation.parameters)
            contract_return = _project_protocol_type_v2(
                contract.return_type,
                associated_source_types=associated_source_types,
                arities=arities,
            )
            implementation_return = _canon_type(implementation.return_type, arities)
            if contract_parameters != implementation_parameters or contract_return != implementation_return:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_SIGNATURE",
                    f"method {receiver_type}.{method_name} does not match protocol {protocol_name} signature",
                )
            symbol = _method_symbol(receiver_type, method_name)
            template = function_templates.get(symbol)
            if template is None:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_WITNESS",
                    f"method implementation template for {receiver_type}.{method_name} is unavailable",
                )
            method_hashes.append((method_name, template.template_hash))
            dependencies = tuple(sorted(set(str(item) for item in constraint_map.get(symbol, ()))))
            if dependencies:
                method_constraint_bindings.append((method_name, dependencies))
        resolved_receiver = types.resolve_source_type(receiver_type)
        types.materialize_resolved_type(resolved_receiver)
        protocol_hash = protocol_hashes[protocol_name]
        witness_payload = {
            "schema": "TEV_SCRIPT_V2_PROTOCOL_WITNESS_R1",
            "protocol_hash": protocol_hash,
            "receiver_source_type": receiver_type,
            "receiver_runtime_type": resolved_receiver.type_id,
            "methods": [
                {"name": name, "template_hash": template_hash}
                for name, template_hash in method_hashes
            ],
        }
        if method_constraint_bindings:
            witness_payload["schema"] = "TEV_SCRIPT_V2_PROTOCOL_WITNESS_R2"
            witness_payload["method_constraint_specializations"] = [
                {"name": name, "specialization_hashes": list(hashes)}
                for name, hashes in method_constraint_bindings
            ]
        if associated_entries:
            witness_payload["schema"] = "TEV_SCRIPT_V2_PROTOCOL_WITNESS_R3"
            witness_payload["associated_types"] = [
                {"name": name, "source_type": source_type, "type_id": type_id}
                for name, source_type, type_id in associated_entries
            ]
        witness_hash = _hash(witness_payload)
        witnesses.append(ProtocolWitnessV2(
            protocol_name,
            protocol_hash,
            receiver_type,
            resolved_receiver.type_id,
            tuple(method_hashes),
            witness_hash,
            tuple(method_constraint_bindings),
            tuple(associated_entries),
        ))
    return tuple(sorted(witnesses, key=lambda item: (item.protocol_name, item.receiver_source_type, item.witness_hash)))


def _source_hash_value_v2(value: Any) -> Any:
    if isinstance(value, SourceExprV2):
        return _source_expression_hash_payload_v2(value)
    if isinstance(value, Fraction):
        return {"$rat": [str(value.numerator), str(value.denominator)]}
    if isinstance(value, tuple):
        return [_source_hash_value_v2(item) for item in value]
    if isinstance(value, list):
        return [_source_hash_value_v2(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _source_hash_value_v2(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    _fail("TEVS_V2_PROGRAM_CONSTRAINT_TEMPLATE", f"unsupported constrained source value {type(value).__name__}")


def _source_expression_hash_payload_v2(expression: SourceExprV2) -> dict[str, Any]:
    return {
        "kind": expression.kind,
        "value": _source_hash_value_v2(expression.value),
        "children": [_source_expression_hash_payload_v2(child) for child in expression.children],
    }


def _source_expression_type_texts_v2(expression: SourceExprV2) -> tuple[str, ...]:
    result: list[str] = []
    if expression.kind == "call":
        _name, type_arguments, _named_fields = expression.value
        result.extend(str(item) for item in type_arguments)
    elif expression.kind in {"task_scope", "task_dag"}:
        result.extend(str(type_text) for _name, type_text in expression.value)
    elif expression.kind == "while":
        _accumulator_name, accumulator_type, _maximum = expression.value
        result.append(str(accumulator_type))
    elif expression.kind == "for_fold":
        _bindings, _accumulator_name, accumulator_type = expression.value
        result.append(str(accumulator_type))
    for child in expression.children:
        result.extend(_source_expression_type_texts_v2(child))
    return tuple(result)


PROTOCOL_INTERSECTION_POLICY_V2 = "disjoint_surface_v1"


def _constraint_protocols_by_parameter_v2(
    function: GenericFunctionSourceV2,
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for type_parameter, protocol_name in function.constraints:
        grouped.setdefault(type_parameter, []).append(protocol_name)
    return {
        type_parameter: tuple(protocol_names)
        for type_parameter, protocol_names in grouped.items()
    }


def _associated_owner_protocol_v2(
    *,
    function_name: str,
    type_parameter: str,
    associated_name: str,
    protocol_names: Sequence[str],
    protocols: Mapping[str, ProtocolSourceV2],
    diagnostic_code: str,
) -> str:
    owners = [
        protocol_name
        for protocol_name in protocol_names
        if associated_name in protocols[protocol_name].associated_types
    ]
    if len(owners) != 1:
        _fail(
            diagnostic_code,
            f"function {function_name!r} cannot resolve {type_parameter}::{associated_name} to exactly one protocol in intersection {list(protocol_names)}",
        )
    return owners[0]


def _validate_protocol_intersection_surfaces_v2(
    *,
    function_name: str,
    type_parameter: str,
    protocol_names: Sequence[str],
    protocols: Mapping[str, ProtocolSourceV2],
) -> None:
    if len(protocol_names) <= 1:
        return
    seen_methods: dict[str, str] = {}
    seen_associated: dict[str, str] = {}
    for protocol_name in protocol_names:
        protocol = protocols[protocol_name]
        for method in protocol.methods:
            prior = seen_methods.get(method.name)
            if prior is not None:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_METHOD_COLLISION",
                    f"function {function_name!r} intersection for {type_parameter!r} has method {method.name!r} in both {prior!r} and {protocol_name!r}",
                )
            seen_methods[method.name] = protocol_name
        for associated_name in protocol.associated_types:
            prior = seen_associated.get(associated_name)
            if prior is not None:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_ASSOCIATED_COLLISION",
                    f"function {function_name!r} intersection for {type_parameter!r} has associated type {associated_name!r} in both {prior!r} and {protocol_name!r}",
                )
            seen_associated[associated_name] = protocol_name


def _validate_function_constraints_v2(
    functions: Sequence[GenericFunctionSourceV2],
    protocols: Mapping[str, ProtocolSourceV2],
    generic_arities: Mapping[str, int] | None = None,
) -> None:
    for function in functions:
        type_parameters = set(function.type_parameters)
        seen_constraints: set[tuple[str, str]] = set()
        for parameter, protocol_name in function.constraints:
            if parameter not in type_parameters:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_PARAMETER",
                    f"function {function.name!r} constrains unknown type parameter {parameter!r}",
                )
            key = (parameter, protocol_name)
            if key in seen_constraints:
                _fail(
                    "TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_DUPLICATE",
                    f"function {function.name!r} repeats protocol {protocol_name!r} for {parameter!r}",
                )
            seen_constraints.add(key)
            if protocol_name not in protocols:
                _fail(
                    "TEVS_V2_PROGRAM_CONSTRAINT_PROTOCOL",
                    f"function {function.name!r} references unknown protocol {protocol_name!r}",
                )
        protocols_by_parameter = _constraint_protocols_by_parameter_v2(function)
        for type_parameter, protocol_names in protocols_by_parameter.items():
            _validate_protocol_intersection_surfaces_v2(
                function_name=function.name,
                type_parameter=type_parameter,
                protocol_names=protocol_names,
                protocols=protocols,
            )

        seen_associated_constraints: set[tuple[str, str]] = set()
        for type_parameter, associated_name, required_type in function.associated_constraints:
            key = (type_parameter, associated_name)
            if key in seen_associated_constraints:
                _fail(
                    "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_DUPLICATE",
                    f"function {function.name!r} repeats associated refinement {type_parameter}::{associated_name}",
                )
            seen_associated_constraints.add(key)
            protocol_names = protocols_by_parameter.get(type_parameter, ())
            if not protocol_names:
                _fail(
                    "TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT",
                    f"function {function.name!r} refines {type_parameter}::{associated_name} without protocol constraint",
                )
            _associated_owner_protocol_v2(
                function_name=function.name,
                type_parameter=type_parameter,
                associated_name=associated_name,
                protocol_names=protocol_names,
                protocols=protocols,
                diagnostic_code="TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT",
            )
            _AssociatedConstraintSpecificationV2.build(
                function_name=function.name,
                target_type_parameter=type_parameter,
                associated_name=associated_name,
                required_type=required_type,
                type_parameters=function.type_parameters,
                protocols_by_parameter=protocols_by_parameter,
                protocols=protocols,
                generic_arities=generic_arities or {},
            )

        for type_text in [
            *(item[1] for item in function.parameters),
            function.return_type,
            *_source_expression_type_texts_v2(function.body),
        ]:
            ref = parse_type_ref_v2(type_text, generic_arities or {})
            stack = [ref]
            while stack:
                current = stack.pop()
                if current.kind == "associated":
                    root, member = associated_type_parts_v2(current)
                    protocol_names = protocols_by_parameter.get(root, ())
                    if not protocol_names:
                        _fail(
                            "TEVS_V2_PROGRAM_ASSOCIATED_TYPE_CONSTRAINT",
                            f"function {function.name!r} projects {root}::{member} without constraining {root}",
                        )
                    _associated_owner_protocol_v2(
                        function_name=function.name,
                        type_parameter=root,
                        associated_name=member,
                        protocol_names=protocol_names,
                        protocols=protocols,
                        diagnostic_code="TEVS_V2_PROGRAM_ASSOCIATED_TYPE_CONSTRAINT",
                    )
                stack.extend(current.arguments)


def _validate_associated_constraint_targets_v2(
    functions: Sequence[GenericFunctionSourceV2],
    types: GenericRegistryV2,
    protocols: Mapping[str, ProtocolSourceV2],
) -> None:
    arities = types.generic_arities()
    for function in functions:
        protocols_by_parameter = _constraint_protocols_by_parameter_v2(function)
        for type_parameter, associated_name, required_type in function.associated_constraints:
            specification = _AssociatedConstraintSpecificationV2.build(
                function_name=function.name,
                target_type_parameter=type_parameter,
                associated_name=associated_name,
                required_type=required_type,
                type_parameters=function.type_parameters,
                protocols_by_parameter=protocols_by_parameter,
                protocols=protocols,
                generic_arities=arities,
            )
            specification.validate_static_types(
                types=types,
                diagnostic_code="TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_TYPE",
                message_prefix=(
                    f"function {function.name!r} refinement {type_parameter}::{associated_name} requires type"
                ),
            )


def _constrained_function_template_hashes_v2(
    program_id: str,
    functions: Sequence[GenericFunctionSourceV2],
    generic_arities: Mapping[str, int] | None = None,
    protocols: Mapping[str, ProtocolSourceV2] | None = None,
) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
    items: list[tuple[str, str]] = []
    by_name: dict[str, str] = {}
    arities = dict(generic_arities or {})
    for function in sorted((item for item in functions if item.constraints), key=lambda item: item.name):
        payload = {
            "schema": "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_TEMPLATE_R1",
            "owner_id": program_id,
            "name": function.name,
            "type_parameters": list(function.type_parameters),
            "constraints": [
                {"type_parameter": parameter, "protocol_name": protocol_name}
                for parameter, protocol_name in function.constraints
            ],
            "parameters": [
                {"name": name, "type": type_text}
                for name, type_text in function.parameters
            ],
            "return_type": function.return_type,
            "body": _source_expression_hash_payload_v2(function.body),
        }
        if function.associated_constraints:
            payload["schema"] = "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_TEMPLATE_R2"
            payload["associated_constraints"] = [
                {
                    "type_parameter": type_parameter,
                    "associated_name": associated_name,
                    "required_source_type": _canon_type(required_type, arities),
                }
                for type_parameter, associated_name, required_type in sorted(function.associated_constraints)
            ]
        protocols_by_parameter = _constraint_protocols_by_parameter_v2(function)
        intersections = [
            {
                "type_parameter": type_parameter,
                "protocol_names": list(protocol_names),
            }
            for type_parameter, protocol_names in protocols_by_parameter.items()
            if len(protocol_names) > 1
        ]
        if intersections:
            payload["schema"] = "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_TEMPLATE_R3"
            payload["protocol_intersection_policy"] = PROTOCOL_INTERSECTION_POLICY_V2
            payload["protocol_intersections"] = intersections

        protocol_table = protocols or {}
        protocols_by_parameter = _constraint_protocols_by_parameter_v2(function)
        associated_specifications = tuple(
            _AssociatedConstraintSpecificationV2.build(
                function_name=function.name,
                target_type_parameter=type_parameter,
                associated_name=associated_name,
                required_type=required_type,
                type_parameters=function.type_parameters,
                protocols_by_parameter=protocols_by_parameter,
                protocols=protocol_table,
                generic_arities=arities,
            )
            for type_parameter, associated_name, required_type in function.associated_constraints
        )
        if any(specification.dependent for specification in associated_specifications):
            parameter_ordinals = {
                name: index for index, name in enumerate(function.type_parameters)
            }
            alpha = _type_parameter_alpha_substitutions_v2(function.type_parameters)
            associated_authority: dict[str, frozenset[str]] = {}
            for type_parameter in function.type_parameters:
                names: set[str] = set()
                for protocol_name in protocols_by_parameter.get(type_parameter, ()):
                    names.update(protocol_table[protocol_name].associated_types)
                associated_authority[type_parameter] = frozenset(names)
            alpha_associated_substitutions = {
                (type_parameter, associated_name): TypeRefV2(
                    "associated", f"__T{parameter_ordinals[type_parameter]}::{associated_name}"
                )
                for type_parameter, associated_names in associated_authority.items()
                for associated_name in associated_names
            }

            def alpha_type(type_text: str) -> str:
                return _render_type(_substitute_type(
                    parse_type_ref_v2(type_text, arities),
                    alpha,
                    alpha_associated_substitutions,
                ))

            alpha_body = _specialize_source_expression_types_v2(
                function.body, alpha, arities, alpha_associated_substitutions
            )
            payload = {
                "schema": "TEV_SCRIPT_V2_CONSTRAINED_FUNCTION_TEMPLATE_R4",
                "owner_id": program_id,
                "name": function.name,
                "dependent_associated_constraint_policy": "witness_type_id_equality_v1",
                "type_parameter_count": len(function.type_parameters),
                "constraints": [
                    {
                        "type_parameter_ordinal": parameter_ordinals[type_parameter],
                        "protocol_name": protocol_name,
                    }
                    for type_parameter, protocol_name in function.constraints
                ],
                "associated_constraints": [
                    {
                        "type_parameter_ordinal": parameter_ordinals[type_parameter],
                        "associated_name": associated_name,
                        "required_source_type": alpha_type(required_type),
                    }
                    for type_parameter, associated_name, required_type in sorted(
                        function.associated_constraints,
                        key=lambda item: (parameter_ordinals[item[0]], item[1], item[2]),
                    )
                ],
                "parameters": [
                    {"name": name, "type": alpha_type(type_text)}
                    for name, type_text in function.parameters
                ],
                "return_type": alpha_type(function.return_type),
                "body": _source_expression_hash_payload_v2(alpha_body),
            }
            dependent_intersections = [
                {
                    "type_parameter_ordinal": parameter_ordinals[type_parameter],
                    "protocol_names": list(protocol_names),
                }
                for type_parameter, protocol_names in protocols_by_parameter.items()
                if len(protocol_names) > 1
            ]
            if dependent_intersections:
                payload["protocol_intersection_policy"] = PROTOCOL_INTERSECTION_POLICY_V2
                payload["protocol_intersections"] = dependent_intersections
        template_hash = _hash(payload)
        by_name[function.name] = template_hash
        items.append((f"{program_id}.{function.name}", template_hash))
    return tuple(items), by_name


def _protocol_witness_index_v2(
    witnesses: Sequence[ProtocolWitnessV2],
) -> dict[tuple[str, str], ProtocolWitnessV2]:
    result: dict[tuple[str, str], ProtocolWitnessV2] = {}
    for witness in witnesses:
        key = (witness.protocol_name, witness.receiver_source_type)
        if key in result:
            _fail(
                "TEVS_V2_PROGRAM_CONSTRAINT_WITNESS",
                f"duplicate witness index for protocol {witness.protocol_name!r} and {witness.receiver_source_type}",
            )
        result[key] = witness
    return result


def _protocol_method_index_v2(
    protocols: Mapping[str, ProtocolSourceV2],
) -> dict[str, frozenset[str]]:
    return {
        name: frozenset(method.name for method in protocol.methods)
        for name, protocol in protocols.items()
    }


def _substitute_type(
    ref: TypeRefV2,
    substitutions: Mapping[str, TypeRefV2],
    associated_substitutions: Mapping[tuple[str, str], TypeRefV2] | None = None,
) -> TypeRefV2:
    if ref.kind == "named" and ref.name in substitutions:
        return substitutions[ref.name]
    if ref.kind == "associated":
        root, member = associated_type_parts_v2(ref)
        replacement = (associated_substitutions or {}).get((root, member))
        if replacement is not None:
            return replacement
        return ref
    return TypeRefV2(
        ref.kind,
        ref.name,
        tuple(_substitute_type(child, substitutions, associated_substitutions) for child in ref.arguments),
        ref.const_arguments,
    )


def _index_records(records: Sequence[GenericRecordSourceV2]) -> dict[str, GenericRecordSourceV2]:
    result: dict[str, GenericRecordSourceV2] = {}
    for item in records:
        if item.name in result: _fail("TEVS_V2_PROGRAM_DUPLICATE", f"duplicate generic record {item.name!r}")
        result[item.name] = item
    return result


def _index_functions(functions: Sequence[GenericFunctionSourceV2]) -> dict[str, GenericFunctionSourceV2]:
    result: dict[str, GenericFunctionSourceV2] = {}
    for item in functions:
        if item.name in result: _fail("TEVS_V2_PROGRAM_DUPLICATE", f"duplicate generic function {item.name!r}")
        result[item.name] = item
    return result


def _index_recursive_functions(
    functions: Sequence[RecursiveFunctionSourceV2],
) -> dict[str, RecursiveFunctionSourceV2]:
    result: dict[str, RecursiveFunctionSourceV2] = {}
    for item in functions:
        if item.name in result:
            _fail("TEVS_V2_PROGRAM_DUPLICATE", f"duplicate recursive function {item.name!r}")
        result[item.name] = item
    return result


def _canon_type(text: str, arities: Mapping[str, int]) -> str:
    return _render_type(parse_type_ref_v2(text, arities))


def _render_type(ref: TypeRefV2) -> str:
    if ref.kind in {"named", "associated"}: return ref.name
    if ref.kind == "option": return f"Option<{_render_type(ref.arguments[0])}>"
    if ref.kind == "result": return f"Result<{_render_type(ref.arguments[0])},{_render_type(ref.arguments[1])}>"
    if ref.kind in {"list", "array", "set"}:
        return f"{ref.name}<{_render_type(ref.arguments[0])},{ref.const_arguments[0]}>"
    if ref.kind == "map":
        return f"Map<{_render_type(ref.arguments[0])},{_render_type(ref.arguments[1])},{ref.const_arguments[0]}>"
    if ref.kind == "user_generic":
        return f"{ref.name}<{','.join(_render_type(item) for item in ref.arguments)}>"
    _fail("TEVS_V2_PROGRAM_TYPE", f"cannot render type kind {ref.kind!r}")


def _type_equal(left: str, right: str, arities: Mapping[str, int]) -> bool:
    return _canon_type(left, arities) == _canon_type(right, arities)


def _require_expected(actual: str, expected: str | None, arities: Mapping[str, int]) -> None:
    if expected is not None and not _type_equal(actual, expected, arities):
        _fail("TEVS_V2_PROGRAM_TYPE", f"expected {expected}, got {actual}")


def _arity(name: str, args: Sequence[Any], expected: int) -> None:
    if len(args) != expected:
        _fail("TEVS_V2_PROGRAM_CALL", f"{name} expects {expected} arguments, got {len(args)}")


_BINARY_PRECEDENCE = {"OR": 1, "AND": 2, "EQEQ": 3, "NE": 3, "LT": 4, "LE": 4, "GT": 4, "GE": 4, "PLUS": 5, "MINUS": 5, "STAR": 6, "SLASH": 6}


def _source_expression_contains_self_call(expression: SourceExprV2) -> bool:
    if expression.kind == "call":
        name, _type_arguments, _named_fields = expression.value
        if name == "self":
            return True
    return any(_source_expression_contains_self_call(child) for child in expression.children)


def _binary_operator(token: _Token) -> str | None:
    if token.kind in _BINARY_PRECEDENCE:
        return token.kind
    if token.kind == "IDENT" and token.text == "and": return "AND"
    if token.kind == "IDENT" and token.text == "or": return "OR"
    return None


def _tokenize(source: str) -> tuple[_Token, ...]:
    result: list[_Token] = []
    i = 0
    decoder = json.JSONDecoder()
    punctuation = {
        ";": "SEMI", ":": "COLON", ",": "COMMA", "=": "EQUAL",
        "(": "LPAREN", ")": "RPAREN", "{": "LBRACE", "}": "RBRACE",
        "[": "LBRACKET", "]": "RBRACKET", "<": "LT", ">": "GT",
        "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", ".": "DOT",
    }
    while i < len(source):
        ch = source[i]
        if ch.isspace(): i += 1; continue
        if source.startswith("//", i):
            end = source.find("\n", i + 2); i = len(source) if end < 0 else end + 1; continue
        if source.startswith("::", i): result.append(_Token("DCOLON", "::", None, i, i + 2)); i += 2; continue
        if source.startswith("->", i): result.append(_Token("ARROW", "->", None, i, i + 2)); i += 2; continue
        if source.startswith("=>", i): result.append(_Token("FAT_ARROW", "=>", None, i, i + 2)); i += 2; continue
        if source.startswith("==", i): result.append(_Token("EQEQ", "==", None, i, i + 2)); i += 2; continue
        if source.startswith("!=", i): result.append(_Token("NE", "!=", None, i, i + 2)); i += 2; continue
        if source.startswith("<=", i): result.append(_Token("LE", "<=", None, i, i + 2)); i += 2; continue
        if source.startswith(">=", i): result.append(_Token("GE", ">=", None, i, i + 2)); i += 2; continue
        if ch == '"':
            try: value, consumed = decoder.raw_decode(source[i:])
            except json.JSONDecodeError as exc: _fail("TEVS_V2_PROGRAM_STRING", f"invalid string at offset {i}: {exc.msg}")
            if not isinstance(value, str): _fail("TEVS_V2_PROGRAM_STRING", "only string JSON literal allowed")
            result.append(_Token("STRING", source[i:i+consumed], value, i, i + consumed)); i += consumed; continue
        match = re.match(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", source[i:])
        if match:
            raw = match.group(0); result.append(_Token("NUMBER", raw, raw, i, i + len(raw))); i += len(raw); continue
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", source[i:])
        if match:
            raw = match.group(0); result.append(_Token("IDENT", raw, raw, i, i + len(raw))); i += len(raw); continue
        kind = punctuation.get(ch)
        if kind is not None:
            result.append(_Token(kind, ch, None, i, i + 1)); i += 1; continue
        _fail("TEVS_V2_PROGRAM_SYNTAX", f"invalid source token {ch!r} at offset {i}")
    result.append(_Token("EOF", "", None, len(source), len(source)))
    return tuple(result)


def _canonical_token_text(tokens: Sequence[_Token]) -> str:
    # Type tokens have a canonical compact representation independent of whitespace.
    return "".join(token.text for token in tokens)


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
