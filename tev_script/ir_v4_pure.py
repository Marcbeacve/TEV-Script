from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from .diagnostics import TevScriptError
from .ir_v4_collections import (
    array_get,
    array_items,
    array_set,
    list_get,
    list_items,
    list_push,
    list_set,
    map_entries,
    map_lookup,
    map_put,
    set_add,
    set_contains,
    set_items,
)
from .ir_v4_values import (
    ArrayValueV4,
    ListValueV4,
    MapValueV4,
    RecordValueV4,
    SetValueV4,
    TypeDescriptorV4,
    TypeTableV4,
    VariantValueV4,
    decode_v4_value,
    encode_v4_value,
    v4_values_equal,
)

MAX_PURE_EXPRESSION_NESTING_V4 = 128
MAX_PURE_EVAL_STEPS_V4 = 1_000_000
MAX_PURE_WHILE_ITERATIONS_V4 = 4096
MAX_PURE_TASKS_V4 = 64
TASK_JOIN_POLICY_V4 = "all_success_v1"
TASK_CANCELLATION_POLICY_V4 = "cancel_siblings_on_failure_v1"
PRIORITY_SELECT_POLICY_V4 = "canonical_priority_first_within_steps_v1"
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BINARY = frozenset({"AND", "OR", "EQEQ", "NE", "LT", "LE", "GT", "GE", "PLUS", "MINUS", "STAR", "SLASH"})
_UNARY = frozenset({"NOT", "MINUS"})


@dataclass(frozen=True, slots=True)
class TypedValueV4:
    type_id: str
    value: Any


@dataclass(frozen=True, slots=True)
class TaskChildEvaluationV4:
    name: str
    result: TypedValueV4
    evaluation_steps: int
    bounded_loop_iterations: int


@dataclass(frozen=True, slots=True)
class PrioritySelectCandidateOutcomeV4:
    index: int
    result: TypedValueV4 | None
    evaluation_steps: int
    bounded_loop_iterations: int
    error: Exception | None


class TaskScopeExecutionStrategyV4(Protocol):
    def run(
        self,
        tasks: Sequence[Mapping[str, Any]],
        evaluate_child: Callable[[Mapping[str, Any]], TaskChildEvaluationV4],
    ) -> Sequence[TaskChildEvaluationV4]: ...


@dataclass(frozen=True, slots=True)
class PureBindingV4:
    name: str
    type_id: str
    value: Any


@dataclass(frozen=True, slots=True)
class PureValidationV4:
    schema: str
    type_table_hash: str
    expression_hash: str
    result_type: str
    static_step_upper_bound: int
    bounded_loop_iteration_upper_bound: int
    validation_hash: str


@dataclass(frozen=True, slots=True)
class PureEvaluationReceiptV4:
    schema: str
    type_table_hash: str
    expression_hash: str
    environment_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    evaluation_steps: int
    static_step_upper_bound: int
    maximum_steps: int
    bounded_loop_iterations: int
    receipt_hash: str


class _OperationalCancellationV4(Exception):
    pass


class _BudgetV4:
    def __init__(self, maximum: int, *, cancel_check: Callable[[], bool] | None = None) -> None:
        if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= MAX_PURE_EVAL_STEPS_V4:
            _fail("TEVS_IR_V4_PURE_BUDGET", f"maximum steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
        self.maximum = maximum
        self.steps = 0
        self.loop_iterations = 0
        self.cancel_check = cancel_check

    def consume(self, count: int = 1) -> None:
        if self.cancel_check is not None and self.cancel_check():
            raise _OperationalCancellationV4("lower-priority speculative candidate cancelled")
        self.steps += count
        if self.steps > self.maximum:
            _fail("TEVS_IR_V4_PURE_BUDGET", f"pure evaluation step budget {self.maximum} exceeded")

    def loop(self, count: int = 1) -> None:
        self.loop_iterations += count

    def absorb(self, *, steps: int, loop_iterations: int) -> None:
        if steps < 0 or loop_iterations < 0:
            _fail("TEVS_IR_V4_PURE_BUDGET", "cannot absorb negative task accounting")
        self.steps += steps
        self.loop_iterations += loop_iterations
        if self.steps > self.maximum:
            _fail("TEVS_IR_V4_PURE_BUDGET", f"pure evaluation step budget {self.maximum} exceeded")


def validate_pure_v4(
    expression: Mapping[str, Any],
    table: TypeTableV4,
    parameter_types: Mapping[str, str] | None = None,
) -> PureValidationV4:
    canonical = canonical_expression_v4(expression)
    type_table_hash = hash_type_table_v4(table)
    expression_hash = _hash(canonical)
    environment: dict[str, str] = {}
    for name, type_id in sorted((parameter_types or {}).items()):
        _name(name); table.require(type_id, context=f"pure parameter {name}")
        environment[name] = type_id
    result_type, steps, loops = _typecheck(canonical, table, environment, depth=1)
    if steps > MAX_PURE_EVAL_STEPS_V4:
        _fail(
            "TEVS_IR_V4_PURE_STATIC_BUDGET",
            f"static pure step upper bound {steps} exceeds {MAX_PURE_EVAL_STEPS_V4}",
        )
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_PURE_VALIDATION_V1",
        "type_table_hash": type_table_hash,
        "expression_hash": expression_hash,
        "result_type": result_type,
        "static_step_upper_bound": steps,
        "bounded_loop_iteration_upper_bound": loops,
    }
    return PureValidationV4(
        payload["schema"],
        type_table_hash,
        expression_hash,
        result_type,
        steps,
        loops,
        _hash(payload),
    )


def _typecheck(
    node: Mapping[str, Any],
    table: TypeTableV4,
    environment: Mapping[str, str],
    *,
    depth: int,
) -> tuple[str, int, int]:
    if depth > MAX_PURE_EXPRESSION_NESTING_V4:
        _fail("TEVS_IR_V4_PURE_NESTING", f"type-check nesting exceeds {MAX_PURE_EXPRESSION_NESTING_V4}")
    op = str(node["op"])

    def check(child: Mapping[str, Any], env: Mapping[str, str] = environment) -> tuple[str, int, int]:
        return _typecheck(child, table, env, depth=depth + 1)

    def unary_child(child: Mapping[str, Any], expected: str, context: str) -> tuple[int, int]:
        actual, steps, loops = check(child)
        if actual != expected:
            _fail("TEVS_IR_V4_PURE_TYPE", f"{context}: expected {expected}, got {actual}")
        return steps, loops

    if op == "CONST":
        type_id = str(node["type"]); table.require(type_id, context="CONST")
        decode_v4_value(type_id, node["value"], table, context="CONST static")
        return type_id, 1, 0
    if op == "PARAM":
        name = str(node["name"]); type_id = str(node["type"]); table.require(type_id, context="PARAM")
        actual = environment.get(name)
        if actual is None: _fail("TEVS_IR_V4_PURE_PARAM", f"undeclared parameter {name!r}")
        if actual != type_id: _fail("TEVS_IR_V4_PURE_TYPE", f"parameter {name!r} expected {actual}, node claims {type_id}")
        return type_id, 1, 0
    if op == "CONVERT_INT_TO_RAT":
        steps, loops = unary_child(node["operand"], "Int", "CONVERT_INT_TO_RAT")
        return "Rat", 1 + steps, loops
    if op == "UNARY":
        operand_type = str(node["operand_type"]); result_type = str(node["result_type"])
        table.require(operand_type, context="UNARY operand"); table.require(result_type, context="UNARY result")
        steps, loops = unary_child(node["operand"], operand_type, "UNARY")
        operator = str(node["operator"])
        valid = (operator == "NOT" and operand_type == result_type == "Bool") or (
            operator == "MINUS" and operand_type == result_type and operand_type in {"Int", "Rat"}
        )
        if not valid: _fail("TEVS_IR_V4_PURE_TYPE", f"invalid unary contract {operator} {operand_type}->{result_type}")
        return result_type, 1 + steps, loops
    if op == "BINARY":
        lt, rt, result_type = str(node["left_type"]), str(node["right_type"]), str(node["result_type"])
        for type_id in (lt, rt, result_type): table.require(type_id, context="BINARY")
        left_type, ls, ll = check(node["left"]); right_type, rs, rl = check(node["right"])
        if left_type != lt or right_type != rt: _fail("TEVS_IR_V4_PURE_TYPE", f"BINARY child types are {left_type},{right_type}; claims {lt},{rt}")
        _require_binary_contract(str(node["operator"]), lt, rt, result_type)
        return result_type, 1 + ls + rs, ll + rl
    if op == "IF":
        cond_type, cs, cl = check(node["condition"])
        if cond_type != "Bool": _fail("TEVS_IR_V4_PURE_TYPE", "IF condition must be Bool")
        then_type, ts, tl = check(node["then"]); else_type, es, el = check(node["else"])
        result_type = str(node["result_type"]); table.require(result_type, context="IF result")
        if then_type != result_type or else_type != result_type: _fail("TEVS_IR_V4_PURE_TYPE", f"IF branches must both be {result_type}")
        return result_type, 1 + cs + max(ts, es), cl + max(tl, el)
    if op == "LET":
        name, declared, result_type = str(node["name"]), str(node["type"]), str(node["result_type"])
        table.require(declared, context="LET type"); table.require(result_type, context="LET result")
        value_type, vs, vl = check(node["value"])
        if value_type != declared: _fail("TEVS_IR_V4_PURE_TYPE", f"LET {name} expected {declared}, got {value_type}")
        nested = dict(environment); nested[name] = declared
        body_type, bs, bl = check(node["body"], nested)
        if body_type != result_type: _fail("TEVS_IR_V4_PURE_TYPE", f"LET body expected {result_type}, got {body_type}")
        return result_type, 1 + vs + bs, vl + bl
    if op == "RECORD":
        type_id = str(node["type"]); descriptor = table.require(type_id, context="RECORD")
        if descriptor.kind != "record": _fail("TEVS_IR_V4_PURE_TYPE", "RECORD requires record descriptor")
        fields = {str(item["name"]): item["expr"] for item in node["fields"]}
        expected = dict(descriptor.fields)
        if set(fields) != set(expected): _fail("TEVS_IR_V4_PURE_RECORD", "record field set mismatch")
        steps, loops = 1, 0
        for name, field_type in descriptor.fields:
            actual, child_steps, child_loops = check(fields[name])
            if actual != field_type: _fail("TEVS_IR_V4_PURE_TYPE", f"record field {name} expected {field_type}, got {actual}")
            steps += child_steps; loops += child_loops
        return type_id, steps, loops
    if op == "FIELD":
        record_type, result_type, field = str(node["record_type"]), str(node["result_type"]), str(node["field"])
        descriptor = table.require(record_type, context="FIELD")
        if descriptor.kind != "record" or dict(descriptor.fields).get(field) != result_type: _fail("TEVS_IR_V4_PURE_TYPE", "FIELD descriptor contract mismatch")
        actual, steps, loops = check(node["record"])
        if actual != record_type: _fail("TEVS_IR_V4_PURE_TYPE", f"FIELD record expected {record_type}, got {actual}")
        return result_type, 1 + steps, loops
    if op == "VARIANT":
        type_id, variant = str(node["type"]), str(node["variant"]); descriptor = table.require(type_id, context="VARIANT")
        payload_type = _variant_payload_type(descriptor, variant); steps, loops = 1, 0
        if payload_type is None:
            if "payload" in node: _fail("TEVS_IR_V4_PURE_VARIANT", f"{variant} cannot carry payload")
        else:
            if "payload" not in node: _fail("TEVS_IR_V4_PURE_VARIANT", f"{variant} requires payload")
            actual, child_steps, child_loops = check(node["payload"])
            if actual != payload_type: _fail("TEVS_IR_V4_PURE_TYPE", f"VARIANT payload expected {payload_type}, got {actual}")
            steps += child_steps; loops += child_loops
        return type_id, steps, loops
    if op in {"LIST", "ARRAY", "SET"}:
        type_id = str(node["type"]); descriptor = table.require(type_id, context=op)
        if descriptor.kind != op.lower() or descriptor.element_type is None: _fail("TEVS_IR_V4_PURE_TYPE", f"{op} descriptor mismatch")
        steps, loops = 1, 0
        for raw in node["items"]:
            actual, child_steps, child_loops = check(raw)
            if actual != descriptor.element_type: _fail("TEVS_IR_V4_PURE_TYPE", f"{op} item expected {descriptor.element_type}, got {actual}")
            steps += child_steps; loops += child_loops
        if descriptor.kind == "array":
            assert descriptor.length is not None
            if len(node["items"]) != descriptor.length: _fail("TEVS_IR_V4_COLLECTION_LENGTH", f"{type_id} literal requires exact length {descriptor.length}")
        elif descriptor.capacity is not None and len(node["items"]) > descriptor.capacity:
            _fail("TEVS_IR_V4_COLLECTION_OVERFLOW", f"{type_id} literal exceeds capacity")
        return type_id, steps, loops
    if op == "MAP":
        type_id = str(node["type"]); descriptor = table.require(type_id, context="MAP")
        if descriptor.kind != "map" or descriptor.key_type is None or descriptor.value_type is None: _fail("TEVS_IR_V4_PURE_TYPE", "MAP descriptor mismatch")
        steps, loops = 1, 0
        for raw in node["entries"]:
            kt, ks, kl = check(raw["key"]); vt, vs, vl = check(raw["value"])
            if kt != descriptor.key_type or vt != descriptor.value_type: _fail("TEVS_IR_V4_PURE_TYPE", f"MAP entry expected {descriptor.key_type}->{descriptor.value_type}, got {kt}->{vt}")
            steps += ks + vs; loops += kl + vl
        if descriptor.capacity is not None and len(node["entries"]) > descriptor.capacity: _fail("TEVS_IR_V4_COLLECTION_OVERFLOW", f"{type_id} literal exceeds capacity")
        return type_id, steps, loops
    if op == "LIST_PUSH":
        ct = str(node["collection_type"]); descriptor = _collection_descriptor(table, ct, "list"); assert descriptor.element_type is not None
        collection_type, cs, cl = check(node["collection"]); item_type, is_, il = check(node["item"])
        if collection_type != ct or item_type != descriptor.element_type: _fail("TEVS_IR_V4_PURE_TYPE", "LIST_PUSH contract mismatch")
        return ct, 1 + cs + is_, cl + il
    if op == "LIST_GET":
        ct, result_type = str(node["collection_type"]), str(node["result_type"]); descriptor = _collection_descriptor(table, ct, "list")
        if descriptor.element_type != result_type: _fail("TEVS_IR_V4_PURE_TYPE", "LIST_GET result mismatch")
        collection_type, cs, cl = check(node["collection"]); index_type, is_, il = check(node["index"])
        if collection_type != ct or index_type != "Int": _fail("TEVS_IR_V4_PURE_TYPE", "LIST_GET input contract mismatch")
        return result_type, 1 + cs + is_, cl + il
    if op == "LIST_SET":
        ct = str(node["collection_type"]); descriptor = _collection_descriptor(table, ct, "list"); assert descriptor.element_type is not None
        collection_type, cs, cl = check(node["collection"]); index_type, is_, il = check(node["index"]); item_type, xs, xl = check(node["item"])
        if collection_type != ct or index_type != "Int" or item_type != descriptor.element_type: _fail("TEVS_IR_V4_PURE_TYPE", "LIST_SET contract mismatch")
        return ct, 1 + cs + is_ + xs, cl + il + xl
    if op == "ARRAY_GET":
        ct, result_type = str(node["collection_type"]), str(node["result_type"]); descriptor = _collection_descriptor(table, ct, "array")
        if descriptor.element_type != result_type: _fail("TEVS_IR_V4_PURE_TYPE", "ARRAY_GET result mismatch")
        collection_type, cs, cl = check(node["collection"]); index_type, is_, il = check(node["index"])
        if collection_type != ct or index_type != "Int": _fail("TEVS_IR_V4_PURE_TYPE", "ARRAY_GET input contract mismatch")
        return result_type, 1 + cs + is_, cl + il
    if op == "ARRAY_SET":
        ct = str(node["collection_type"]); descriptor = _collection_descriptor(table, ct, "array"); assert descriptor.element_type is not None
        collection_type, cs, cl = check(node["collection"]); index_type, is_, il = check(node["index"]); item_type, xs, xl = check(node["item"])
        if collection_type != ct or index_type != "Int" or item_type != descriptor.element_type: _fail("TEVS_IR_V4_PURE_TYPE", "ARRAY_SET contract mismatch")
        return ct, 1 + cs + is_ + xs, cl + il + xl
    if op == "SET_ADD":
        ct = str(node["collection_type"]); descriptor = _collection_descriptor(table, ct, "set"); assert descriptor.element_type is not None
        collection_type, cs, cl = check(node["collection"]); item_type, is_, il = check(node["item"])
        if collection_type != ct or item_type != descriptor.element_type: _fail("TEVS_IR_V4_PURE_TYPE", "SET_ADD contract mismatch")
        return ct, 1 + cs + is_, cl + il
    if op == "SET_CONTAINS":
        ct = str(node["collection_type"]); descriptor = _collection_descriptor(table, ct, "set"); assert descriptor.element_type is not None
        collection_type, cs, cl = check(node["collection"]); item_type, is_, il = check(node["item"])
        if collection_type != ct or item_type != descriptor.element_type: _fail("TEVS_IR_V4_PURE_TYPE", "SET_CONTAINS contract mismatch")
        return "Bool", 1 + cs + is_, cl + il
    if op == "MAP_PUT":
        ct = str(node["collection_type"]); descriptor = _collection_descriptor(table, ct, "map"); assert descriptor.key_type is not None and descriptor.value_type is not None
        collection_type, cs, cl = check(node["collection"]); key_type, ks, kl = check(node["key"]); value_type, vs, vl = check(node["value"])
        if collection_type != ct or key_type != descriptor.key_type or value_type != descriptor.value_type: _fail("TEVS_IR_V4_PURE_TYPE", "MAP_PUT contract mismatch")
        return ct, 1 + cs + ks + vs, cl + kl + vl
    if op == "MAP_LOOKUP":
        ct, result_type = str(node["collection_type"]), str(node["result_type"]); descriptor = _collection_descriptor(table, ct, "map"); assert descriptor.key_type is not None and descriptor.value_type is not None
        expected = f"Option<{descriptor.value_type}>"
        option = table.require(result_type, context="MAP_LOOKUP")
        if result_type != expected or option.kind != "option" or option.argument != descriptor.value_type: _fail("TEVS_IR_V4_PURE_TYPE", f"MAP_LOOKUP result must be {expected}")
        collection_type, cs, cl = check(node["collection"]); key_type, ks, kl = check(node["key"])
        if collection_type != ct or key_type != descriptor.key_type: _fail("TEVS_IR_V4_PURE_TYPE", "MAP_LOOKUP input contract mismatch")
        return result_type, 1 + cs + ks, cl + kl
    if op == "LEN":
        ct = str(node["collection_type"]); descriptor = table.require(ct, context="LEN")
        if descriptor.kind not in {"list", "array", "set", "map"}: _fail("TEVS_IR_V4_PURE_TYPE", "LEN requires collection")
        actual, steps, loops = check(node["collection"])
        if actual != ct: _fail("TEVS_IR_V4_PURE_TYPE", f"LEN expected {ct}, got {actual}")
        return "Int", 1 + steps, loops
    if op == "MATCH":
        subject_type, result_type = str(node["subject_type"]), str(node["result_type"])
        descriptor=table.require(subject_type,context="MATCH subject")
        table.require(result_type,context="MATCH result")
        if descriptor.kind not in {"enum","option","result"}:
            _fail("TEVS_IR_V4_PURE_MATCH",f"MATCH requires enum/option/result, got {descriptor.kind}")
        actual_subject, subject_steps, subject_loops=check(node["subject"])
        if actual_subject!=subject_type:
            _fail("TEVS_IR_V4_PURE_TYPE",f"MATCH subject expected {subject_type}, got {actual_subject}")
        expected_variants=_match_variants(descriptor)
        observed=tuple(str(item["variant"]) for item in node["arms"])
        if set(observed)!=set(expected_variants) or len(observed)!=len(expected_variants):
            _fail("TEVS_IR_V4_PURE_MATCH",f"MATCH arms must be exhaustive exactly {expected_variants}, got {observed}")
        max_steps=0; max_loops=0
        for arm in node["arms"]:
            variant=str(arm["variant"]); payload_type=_variant_payload_type(descriptor,variant)
            nested=dict(environment); binding=arm.get("binding")
            if payload_type is None:
                if binding is not None:
                    _fail("TEVS_IR_V4_PURE_MATCH",f"payload-free variant {variant} cannot bind a value")
            else:
                if not isinstance(binding,Mapping):
                    _fail("TEVS_IR_V4_PURE_MATCH",f"payload variant {variant} requires binding")
                name=str(binding["name"]); declared=str(binding["type"])
                if declared!=payload_type:
                    _fail("TEVS_IR_V4_PURE_TYPE",f"MATCH {variant} binding expected {payload_type}, got {declared}")
                if name in nested:
                    _fail("TEVS_IR_V4_PURE_MATCH",f"MATCH binding {name!r} shadows an existing name")
                nested[name]=declared
            body_type, body_steps, body_loops=check(arm["body"],nested)
            if body_type!=result_type:
                _fail("TEVS_IR_V4_PURE_TYPE",f"MATCH {variant} body expected {result_type}, got {body_type}")
            max_steps=max(max_steps,body_steps); max_loops=max(max_loops,body_loops)
        return result_type,1+subject_steps+max_steps,subject_loops+max_loops
    if op == "TASK_SCOPE":
        result_type = str(node["result_type"]); table.require(result_type, context="TASK_SCOPE result")
        if node["join_policy"] != TASK_JOIN_POLICY_V4 or node["cancellation_policy"] != TASK_CANCELLATION_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_TASK_POLICY", "TASK_SCOPE requires the fixed structured-concurrency R1 policies")
        tasks = node["tasks"]
        nested = dict(environment)
        total_steps = 1
        total_loops = 0
        for task in tasks:
            name = str(task["name"]); task_type = str(task["type"]); table.require(task_type, context=f"TASK_SCOPE {name}")
            if name in nested:
                _fail("TEVS_IR_V4_PURE_TASK_BINDING", f"task binding {name!r} shadows an existing name")
            actual, steps, loops = check(task["body"], environment)
            if actual != task_type:
                _fail("TEVS_IR_V4_PURE_TYPE", f"task {name!r} expected {task_type}, got {actual}")
            nested[name] = task_type
            total_steps += steps
            total_loops += loops
        join_type, join_steps, join_loops = check(node["join"], nested)
        if join_type != result_type:
            _fail("TEVS_IR_V4_PURE_TYPE", f"TASK_SCOPE join expected {result_type}, got {join_type}")
        return result_type, total_steps + join_steps, total_loops + join_loops
    if op == "PRIORITY_SELECT":
        result_type=str(node["result_type"]); table.require(result_type,context="PRIORITY_SELECT result")
        if node["selection_policy"]!=PRIORITY_SELECT_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_SELECT_POLICY","PRIORITY_SELECT policy mismatch")
        candidates=tuple(node["candidates"])
        if not 1<=len(candidates)<=MAX_PURE_TASKS_V4:
            _fail("TEVS_IR_V4_PURE_SELECT_BOUND",f"PRIORITY_SELECT requires 1..{MAX_PURE_TASKS_V4} candidates")
        total_steps=1; total_loops=0; guaranteed=False
        for index,candidate in enumerate(candidates):
            maximum_steps=candidate["maximum_steps"]
            if isinstance(maximum_steps,bool) or not isinstance(maximum_steps,int) or not 1<=maximum_steps<=MAX_PURE_EVAL_STEPS_V4:
                _fail("TEVS_IR_V4_PURE_SELECT_BOUND",f"candidate {index} maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
            body_type,body_steps,body_loops=check(candidate["body"],environment)
            if body_type!=result_type:
                _fail("TEVS_IR_V4_PURE_TYPE",f"PRIORITY_SELECT candidate {index} expected {result_type}, got {body_type}")
            if not guaranteed:
                if body_steps<=maximum_steps:
                    total_steps+=body_steps; total_loops+=body_loops; guaranteed=True
                else:
                    total_steps+=maximum_steps+1; total_loops+=min(body_loops,maximum_steps)
        return result_type,total_steps,total_loops
    if op == "STEP_LIMIT":
        result_type=str(node["result_type"]); table.require(result_type,context="STEP_LIMIT result")
        maximum_steps=node["maximum_steps"]
        if isinstance(maximum_steps,bool) or not isinstance(maximum_steps,int) or not 1<=maximum_steps<=MAX_PURE_EVAL_STEPS_V4:
            _fail("TEVS_IR_V4_PURE_STEP_LIMIT",f"STEP_LIMIT maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
        body_type,body_steps,body_loops=check(node["body"],environment)
        if body_type!=result_type:
            _fail("TEVS_IR_V4_PURE_TYPE",f"STEP_LIMIT expected {result_type}, got {body_type}")
        return result_type,1+min(body_steps,maximum_steps),min(body_loops,maximum_steps)
    if op == "TASK_DAG":
        result_type=str(node["result_type"]); table.require(result_type,context="TASK_DAG result")
        if node["join_policy"]!=TASK_JOIN_POLICY_V4 or node["cancellation_policy"]!=TASK_CANCELLATION_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_POLICY","TASK_DAG requires fixed structured-concurrency policies")
        tasks=tuple(node["tasks"]); by_name={str(task["name"]):task for task in tasks}
        order=_task_dag_topological_order(tasks)
        task_types={name:str(task["type"]) for name,task in by_name.items()}
        total_steps=1; total_loops=0
        for name in order:
            task=by_name[name]; task_type=task_types[name]; table.require(task_type,context=f"TASK_DAG {name}")
            if name in environment:
                _fail("TEVS_IR_V4_PURE_TASK_BINDING",f"TASK_DAG binding {name!r} shadows an existing name")
            nested=dict(environment)
            for dependency in task["dependencies"]:
                nested[str(dependency)]=task_types[str(dependency)]
            actual,steps,loops=check(task["body"],nested)
            if actual!=task_type:
                _fail("TEVS_IR_V4_PURE_TYPE",f"TASK_DAG task {name!r} expected {task_type}, got {actual}")
            total_steps+=steps; total_loops+=loops
        join_env=dict(environment); join_env.update(task_types)
        join_type,join_steps,join_loops=check(node["join"],join_env)
        if join_type!=result_type:
            _fail("TEVS_IR_V4_PURE_TYPE",f"TASK_DAG join expected {result_type}, got {join_type}")
        return result_type,total_steps+join_steps,total_loops+join_loops
    if op == "SELF_CALL":
        _fail("TEVS_IR_V4_PURE_RECURSION_CONTEXT", "SELF_CALL requires a governed recursive-function context")
    if op == "WHILE_FOLD":
        acc_type, acc_name = str(node["accumulator_type"]), str(node["accumulator_name"])
        table.require(acc_type, context="WHILE_FOLD accumulator")
        initial_type, initial_steps, initial_loops = check(node["initial"])
        if initial_type != acc_type:
            _fail("TEVS_IR_V4_PURE_TYPE", f"WHILE_FOLD initial expected {acc_type}, got {initial_type}")
        nested = dict(environment); nested[acc_name] = acc_type
        condition_type, condition_steps, condition_loops = check(node["condition"], nested)
        if condition_type != "Bool":
            _fail("TEVS_IR_V4_PURE_TYPE", f"WHILE_FOLD condition must be Bool, got {condition_type}")
        body_type, body_steps, body_loops = check(node["body"], nested)
        if body_type != acc_type:
            _fail("TEVS_IR_V4_PURE_TYPE", f"WHILE_FOLD body expected {acc_type}, got {body_type}")
        maximum = int(node["maximum_iterations"])
        steps = 1 + initial_steps + (maximum + 1) * condition_steps + maximum * body_steps
        loops = initial_loops + (maximum + 1) * condition_loops + maximum * (1 + body_loops)
        return acc_type, steps, loops
    if op == "FOR_FOLD":
        ct, acc_type, acc_name = str(node["collection_type"]), str(node["accumulator_type"]), str(node["accumulator_name"])
        descriptor = table.require(ct, context="FOR_FOLD")
        bound = descriptor.length if descriptor.kind == "array" else descriptor.capacity
        if descriptor.kind not in {"list", "array", "set", "map"} or bound is None: _fail("TEVS_IR_V4_PURE_TYPE", "FOR_FOLD requires bounded collection")
        collection_type, cs, cl = check(node["collection"]); initial_type, is_, il = check(node["initial"])
        if collection_type != ct or initial_type != acc_type: _fail("TEVS_IR_V4_PURE_TYPE", "FOR_FOLD collection/initial mismatch")
        if descriptor.kind in {"list", "array", "set"}:
            assert descriptor.element_type is not None; expected_types = (descriptor.element_type,)
        else:
            assert descriptor.key_type is not None and descriptor.value_type is not None; expected_types = (descriptor.key_type, descriptor.value_type)
        bindings = [(str(item["name"]), str(item["type"])) for item in node["bindings"]]
        if tuple(type_id for _name, type_id in bindings) != expected_types: _fail("TEVS_IR_V4_PURE_TYPE", f"FOR_FOLD bindings must be {expected_types}")
        nested = dict(environment); nested[acc_name] = acc_type
        for name, type_id in bindings: nested[name] = type_id
        body_type, bs, bl = check(node["body"], nested)
        if body_type != acc_type: _fail("TEVS_IR_V4_PURE_TYPE", f"FOR_FOLD body expected {acc_type}, got {body_type}")
        steps = 1 + cs + is_ + bound * bs
        loops = cl + il + bound * (1 + bl)
        return acc_type, steps, loops
    raise AssertionError(op)


def evaluate_pure_v4(
    expression: Mapping[str, Any],
    table: TypeTableV4,
    bindings: Sequence[PureBindingV4] = (),
    *,
    maximum_steps: int = 100_000,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> PureEvaluationReceiptV4:
    """Evaluate one content-addressed, capability-free IR V4 expression."""

    type_table_hash = hash_type_table_v4(table)
    canonical_expression = canonical_expression_v4(expression)
    environment, environment_wire = _prepare_environment(bindings, table)
    validation = validate_pure_v4(
        canonical_expression,
        table,
        {name: binding.type_id for name, binding in environment.items()},
    )
    expression_hash = validation.expression_hash
    environment_hash = _hash(environment_wire)
    if maximum_steps < validation.static_step_upper_bound:
        _fail(
            "TEVS_IR_V4_PURE_BUDGET",
            f"maximum_steps {maximum_steps} is below static upper bound {validation.static_step_upper_bound}",
        )
    budget = _BudgetV4(maximum_steps)
    result = _eval(canonical_expression, table, environment, budget, depth=1, task_strategy=task_strategy)
    result_encoded = encode_v4_value(result.type_id, result.value, table, context="pure result")
    result_hash = _hash({"type": result.type_id, "value": result_encoded})
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_PURE_EVALUATION_RECEIPT_V1",
        "type_table_hash": type_table_hash,
        "expression_hash": expression_hash,
        "environment_hash": environment_hash,
        "result_type": result.type_id,
        "result_encoded": result_encoded,
        "result_hash": result_hash,
        "evaluation_steps": budget.steps,
        "static_step_upper_bound": validation.static_step_upper_bound,
        "maximum_steps": budget.maximum,
        "bounded_loop_iterations": budget.loop_iterations,
    }
    return PureEvaluationReceiptV4(
        payload["schema"],
        type_table_hash,
        expression_hash,
        environment_hash,
        result.type_id,
        result_encoded,
        result_hash,
        budget.steps,
        validation.static_step_upper_bound,
        budget.maximum,
        budget.loop_iterations,
        _hash(payload),
    )


def hash_type_table_v4(table: TypeTableV4) -> str:
    return _hash(
        {
            "schema": "TEV_SCRIPT_IR_V4_TYPE_TABLE_IDENTITY_V1",
            "maximum_value_nesting": table.maximum_value_nesting,
            "types": [_descriptor_wire(item) for item in sorted(table.descriptors, key=lambda item: item.type_id)],
        }
    )


def canonical_expression_v4(expression: Mapping[str, Any], *, depth: int = 1) -> dict[str, Any]:
    if depth > MAX_PURE_EXPRESSION_NESTING_V4:
        _fail("TEVS_IR_V4_PURE_NESTING", f"expression nesting exceeds {MAX_PURE_EXPRESSION_NESTING_V4}")
    if not isinstance(expression, Mapping) or not all(isinstance(key, str) for key in expression):
        _fail("TEVS_IR_V4_PURE_EXPRESSION", "expression must be an object with string keys")
    node = dict(expression)
    op = node.get("op")
    if not isinstance(op, str):
        _fail("TEVS_IR_V4_PURE_EXPRESSION", "expression requires string op")

    def child(value: Any) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            _fail("TEVS_IR_V4_PURE_EXPRESSION", f"{op} child must be an expression object")
        return canonical_expression_v4(value, depth=depth + 1)

    if op == "CONST":
        _exact(node, {"op", "type", "value"})
        _type_text(node["type"])
        return {"op": op, "type": node["type"], "value": _json_clone(node["value"])}
    if op == "PARAM":
        _exact(node, {"op", "name", "type"})
        _name(node["name"]); _type_text(node["type"])
        return {"op": op, "name": node["name"], "type": node["type"]}
    if op == "CONVERT_INT_TO_RAT":
        _exact(node, {"op", "operand"})
        return {"op": op, "operand": child(node["operand"])}
    if op == "UNARY":
        _exact(node, {"op", "operator", "operand_type", "result_type", "operand"})
        if node["operator"] not in _UNARY: _fail("TEVS_IR_V4_PURE_OPERATOR", f"unknown unary operator {node['operator']!r}")
        _type_text(node["operand_type"]); _type_text(node["result_type"])
        return {"op":op,"operator":node["operator"],"operand_type":node["operand_type"],"result_type":node["result_type"],"operand":child(node["operand"])}
    if op == "BINARY":
        _exact(node, {"op", "operator", "left_type", "right_type", "result_type", "left", "right"})
        if node["operator"] not in _BINARY: _fail("TEVS_IR_V4_PURE_OPERATOR", f"unknown binary operator {node['operator']!r}")
        for key in ("left_type","right_type","result_type"): _type_text(node[key])
        return {"op":op,"operator":node["operator"],"left_type":node["left_type"],"right_type":node["right_type"],"result_type":node["result_type"],"left":child(node["left"]),"right":child(node["right"])}
    if op == "IF":
        _exact(node, {"op", "result_type", "condition", "then", "else"})
        _type_text(node["result_type"])
        return {"op":op,"result_type":node["result_type"],"condition":child(node["condition"]),"then":child(node["then"]),"else":child(node["else"])}
    if op == "LET":
        _exact(node, {"op", "name", "type", "result_type", "value", "body"})
        _name(node["name"]); _type_text(node["type"]); _type_text(node["result_type"])
        return {"op":op,"name":node["name"],"type":node["type"],"result_type":node["result_type"],"value":child(node["value"]),"body":child(node["body"])}
    if op == "RECORD":
        _exact(node, {"op", "type", "fields"}); _type_text(node["type"])
        fields = node["fields"]
        if not isinstance(fields, list) or not 1 <= len(fields) <= 256: _fail("TEVS_IR_V4_PURE_RECORD", "RECORD fields require 1..256 entries")
        canonical_fields=[]; seen=set()
        for raw in fields:
            if not isinstance(raw,Mapping): _fail("TEVS_IR_V4_PURE_RECORD", "record field must be object")
            field=dict(raw); _exact(field,{"name","expr"}); name=_name(field["name"])
            if name in seen: _fail("TEVS_IR_V4_PURE_RECORD", f"duplicate field {name!r}")
            seen.add(name); canonical_fields.append({"name":name,"expr":child(field["expr"])})
        canonical_fields.sort(key=lambda item:item["name"])
        return {"op":op,"type":node["type"],"fields":canonical_fields}
    if op == "FIELD":
        _exact(node,{"op","record_type","field","result_type","record"})
        _type_text(node["record_type"]); _type_text(node["result_type"]); _name(node["field"])
        return {"op":op,"record_type":node["record_type"],"field":node["field"],"result_type":node["result_type"],"record":child(node["record"])}
    if op == "VARIANT":
        allowed={"op","type","variant"} | ({"payload"} if "payload" in node else set())
        _exact(node,allowed); _type_text(node["type"]); _name(node["variant"])
        result={"op":op,"type":node["type"],"variant":node["variant"]}
        if "payload" in node: result["payload"]=child(node["payload"])
        return result
    if op in {"LIST","ARRAY","SET"}:
        _exact(node,{"op","type","items"}); _type_text(node["type"])
        if not isinstance(node["items"],list): _fail("TEVS_IR_V4_PURE_COLLECTION", f"{op} items must be array")
        return {"op":op,"type":node["type"],"items":[child(item) for item in node["items"]]}
    if op == "MAP":
        _exact(node,{"op","type","entries"}); _type_text(node["type"])
        if not isinstance(node["entries"],list): _fail("TEVS_IR_V4_PURE_COLLECTION", "MAP entries must be array")
        entries=[]
        for raw in node["entries"]:
            if not isinstance(raw,Mapping): _fail("TEVS_IR_V4_PURE_COLLECTION", "map entry must be object")
            item=dict(raw); _exact(item,{"key","value"})
            entries.append({"key":child(item["key"]),"value":child(item["value"])})
        return {"op":op,"type":node["type"],"entries":entries}
    if op in {"LIST_PUSH","LIST_GET","LIST_SET","ARRAY_GET","ARRAY_SET","SET_ADD","SET_CONTAINS","MAP_PUT","MAP_LOOKUP","LEN"}:
        shapes={
            "LIST_PUSH":({"op","collection_type","collection","item"},("collection_type",),("collection","item")),
            "LIST_GET":({"op","collection_type","result_type","collection","index"},("collection_type","result_type"),("collection","index")),
            "LIST_SET":({"op","collection_type","collection","index","item"},("collection_type",),("collection","index","item")),
            "ARRAY_GET":({"op","collection_type","result_type","collection","index"},("collection_type","result_type"),("collection","index")),
            "ARRAY_SET":({"op","collection_type","collection","index","item"},("collection_type",),("collection","index","item")),
            "SET_ADD":({"op","collection_type","collection","item"},("collection_type",),("collection","item")),
            "SET_CONTAINS":({"op","collection_type","collection","item"},("collection_type",),("collection","item")),
            "MAP_PUT":({"op","collection_type","collection","key","value"},("collection_type",),("collection","key","value")),
            "MAP_LOOKUP":({"op","collection_type","result_type","collection","key"},("collection_type","result_type"),("collection","key")),
            "LEN":({"op","collection_type","collection"},("collection_type",),("collection",)),
        }
        keys,type_keys,child_keys=shapes[op]; _exact(node,keys)
        for key in type_keys:_type_text(node[key])
        result={"op":op}
        for key in type_keys:result[key]=node[key]
        for key in child_keys:result[key]=child(node[key])
        return result
    if op == "MATCH":
        _exact(node,{"op","subject_type","result_type","subject","arms"})
        _type_text(node["subject_type"]); _type_text(node["result_type"])
        raw_arms=node["arms"]
        if not isinstance(raw_arms,list) or not 1<=len(raw_arms)<=256:
            _fail("TEVS_IR_V4_PURE_MATCH","MATCH requires 1..256 arms")
        arms=[]; seen=set()
        for raw in raw_arms:
            if not isinstance(raw,Mapping):
                _fail("TEVS_IR_V4_PURE_MATCH","MATCH arm must be an object")
            arm=dict(raw)
            allowed={"variant","body"} | ({"binding"} if "binding" in arm else set())
            _exact(arm,allowed)
            variant=_name(arm["variant"])
            if variant in seen:
                _fail("TEVS_IR_V4_PURE_MATCH",f"duplicate MATCH variant {variant!r}")
            seen.add(variant)
            item={"variant":variant,"body":child(arm["body"])}
            if "binding" in arm:
                binding=arm["binding"]
                if not isinstance(binding,Mapping):
                    _fail("TEVS_IR_V4_PURE_MATCH","MATCH binding must be object")
                binding=dict(binding); _exact(binding,{"name","type"})
                item["binding"]={"name":_name(binding["name"]),"type":_type_text(binding["type"])}
            arms.append(item)
        arms.sort(key=lambda item:item["variant"])
        return {"op":op,"subject_type":node["subject_type"],"result_type":node["result_type"],"subject":child(node["subject"]),"arms":arms}
    if op == "TASK_SCOPE":
        _exact(node,{"op","result_type","join_policy","cancellation_policy","tasks","join"})
        _type_text(node["result_type"])
        if node["join_policy"] != TASK_JOIN_POLICY_V4 or node["cancellation_policy"] != TASK_CANCELLATION_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_TASK_POLICY", "TASK_SCOPE requires the fixed structured-concurrency R1 policies")
        raw_tasks=node["tasks"]
        if not isinstance(raw_tasks,list) or not 1<=len(raw_tasks)<=MAX_PURE_TASKS_V4:
            _fail("TEVS_IR_V4_PURE_TASK_BOUND",f"TASK_SCOPE requires 1..{MAX_PURE_TASKS_V4} tasks")
        tasks=[]; seen=set()
        for raw in raw_tasks:
            if not isinstance(raw,Mapping):
                _fail("TEVS_IR_V4_PURE_TASK", "TASK_SCOPE task must be an object")
            task=dict(raw); _exact(task,{"name","type","body"})
            name=_name(task["name"]); type_id=_type_text(task["type"])
            if name in seen:
                _fail("TEVS_IR_V4_PURE_TASK_BINDING",f"duplicate TASK_SCOPE task {name!r}")
            seen.add(name)
            tasks.append({"name":name,"type":type_id,"body":child(task["body"])})
        tasks.sort(key=lambda item:item["name"])
        return {
            "op":op,
            "result_type":node["result_type"],
            "join_policy":TASK_JOIN_POLICY_V4,
            "cancellation_policy":TASK_CANCELLATION_POLICY_V4,
            "tasks":tasks,
            "join":child(node["join"]),
        }
    if op == "PRIORITY_SELECT":
        _exact(node,{"op","result_type","selection_policy","candidates"})
        result_type=_type_text(node["result_type"])
        if node["selection_policy"]!=PRIORITY_SELECT_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_SELECT_POLICY","PRIORITY_SELECT policy mismatch")
        raw_candidates=node["candidates"]
        if not isinstance(raw_candidates,list) or not 1<=len(raw_candidates)<=MAX_PURE_TASKS_V4:
            _fail("TEVS_IR_V4_PURE_SELECT_BOUND",f"PRIORITY_SELECT requires 1..{MAX_PURE_TASKS_V4} candidates")
        candidates=[]
        for index,raw in enumerate(raw_candidates):
            if not isinstance(raw,Mapping):
                _fail("TEVS_IR_V4_PURE_SELECT","PRIORITY_SELECT candidate must be an object")
            candidate=dict(raw); _exact(candidate,{"maximum_steps","body"})
            maximum_steps=candidate["maximum_steps"]
            if isinstance(maximum_steps,bool) or not isinstance(maximum_steps,int) or not 1<=maximum_steps<=MAX_PURE_EVAL_STEPS_V4:
                _fail("TEVS_IR_V4_PURE_SELECT_BOUND",f"candidate {index} maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
            candidates.append({"maximum_steps":maximum_steps,"body":child(candidate["body"])})
        return {"op":op,"result_type":result_type,"selection_policy":PRIORITY_SELECT_POLICY_V4,"candidates":candidates}
    if op == "STEP_LIMIT":
        _exact(node,{"op","result_type","maximum_steps","body"})
        result_type=_type_text(node["result_type"]); maximum_steps=node["maximum_steps"]
        if isinstance(maximum_steps,bool) or not isinstance(maximum_steps,int) or not 1<=maximum_steps<=MAX_PURE_EVAL_STEPS_V4:
            _fail("TEVS_IR_V4_PURE_STEP_LIMIT",f"STEP_LIMIT maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")
        return {"op":op,"result_type":result_type,"maximum_steps":maximum_steps,"body":child(node["body"])}
    if op == "TASK_DAG":
        _exact(node,{"op","result_type","join_policy","cancellation_policy","tasks","join"})
        _type_text(node["result_type"])
        if node["join_policy"]!=TASK_JOIN_POLICY_V4 or node["cancellation_policy"]!=TASK_CANCELLATION_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_POLICY","TASK_DAG requires fixed structured-concurrency policies")
        raw_tasks=node["tasks"]
        if not isinstance(raw_tasks,list) or not 1<=len(raw_tasks)<=MAX_PURE_TASKS_V4:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_BOUND",f"TASK_DAG requires 1..{MAX_PURE_TASKS_V4} tasks")
        tasks=[]; seen=set()
        for raw in raw_tasks:
            if not isinstance(raw,Mapping):
                _fail("TEVS_IR_V4_PURE_TASK_DAG","TASK_DAG task must be an object")
            task=dict(raw); _exact(task,{"name","type","dependencies","body"})
            name=_name(task["name"]); type_id=_type_text(task["type"]); dependencies=task["dependencies"]
            if name in seen:
                _fail("TEVS_IR_V4_PURE_TASK_BINDING",f"duplicate TASK_DAG task {name!r}")
            if not isinstance(dependencies,list):
                _fail("TEVS_IR_V4_PURE_TASK_DAG_DEPENDENCY","TASK_DAG dependencies must be an array")
            dep_names=sorted({_name(item) for item in dependencies})
            if len(dep_names)!=len(dependencies):
                _fail("TEVS_IR_V4_PURE_TASK_DAG_DEPENDENCY",f"TASK_DAG task {name!r} has duplicate dependencies")
            seen.add(name)
            tasks.append({"name":name,"type":type_id,"dependencies":dep_names,"body":child(task["body"])})
        tasks.sort(key=lambda item:item["name"])
        _task_dag_topological_order(tuple(tasks))
        return {
            "op":op,
            "result_type":node["result_type"],
            "join_policy":TASK_JOIN_POLICY_V4,
            "cancellation_policy":TASK_CANCELLATION_POLICY_V4,
            "tasks":tasks,
            "join":child(node["join"]),
        }
    if op == "SELF_CALL":
        _exact(node,{"op","arguments"})
        raw_arguments=node["arguments"]
        if not isinstance(raw_arguments,list) or not 1<=len(raw_arguments)<=64:
            _fail("TEVS_IR_V4_PURE_SELF_CALL", "SELF_CALL requires 1..64 arguments")
        return {"op":op,"arguments":[child(item) for item in raw_arguments]}
    if op == "WHILE_FOLD":
        _exact(node,{"op","accumulator_name","accumulator_type","maximum_iterations","initial","condition","body"})
        _name(node["accumulator_name"]); _type_text(node["accumulator_type"])
        maximum=node["maximum_iterations"]
        if isinstance(maximum,bool) or not isinstance(maximum,int) or not 1<=maximum<=MAX_PURE_WHILE_ITERATIONS_V4:
            _fail("TEVS_IR_V4_PURE_WHILE_BOUND",f"WHILE_FOLD maximum_iterations must be 1..{MAX_PURE_WHILE_ITERATIONS_V4}")
        return {
            "op":op,
            "accumulator_name":node["accumulator_name"],
            "accumulator_type":node["accumulator_type"],
            "maximum_iterations":maximum,
            "initial":child(node["initial"]),
            "condition":child(node["condition"]),
            "body":child(node["body"]),
        }
    if op == "FOR_FOLD":
        _exact(node,{"op","collection_type","accumulator_name","accumulator_type","bindings","collection","initial","body"})
        _type_text(node["collection_type"]); _type_text(node["accumulator_type"]); _name(node["accumulator_name"])
        raw_bindings=node["bindings"]
        if not isinstance(raw_bindings,list) or not 1<=len(raw_bindings)<=2: _fail("TEVS_IR_V4_PURE_FOLD", "FOR_FOLD requires one or two bindings")
        bindings=[]; names={node["accumulator_name"]}
        for raw in raw_bindings:
            if not isinstance(raw,Mapping): _fail("TEVS_IR_V4_PURE_FOLD", "fold binding must be object")
            b=dict(raw); _exact(b,{"name","type"}); name=_name(b["name"]); _type_text(b["type"])
            if name in names:_fail("TEVS_IR_V4_PURE_FOLD",f"duplicate fold binding {name!r}")
            names.add(name); bindings.append({"name":name,"type":b["type"]})
        return {"op":op,"collection_type":node["collection_type"],"accumulator_name":node["accumulator_name"],"accumulator_type":node["accumulator_type"],"bindings":bindings,"collection":child(node["collection"]),"initial":child(node["initial"]),"body":child(node["body"])}
    _fail("TEVS_IR_V4_PURE_OPERATOR", f"unsupported pure op {op!r}")


def _eval(
    node: Mapping[str, Any],
    table: TypeTableV4,
    environment: Mapping[str, TypedValueV4],
    budget: _BudgetV4,
    *,
    depth: int,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> TypedValueV4:
    if depth > MAX_PURE_EXPRESSION_NESTING_V4:
        _fail("TEVS_IR_V4_PURE_NESTING", f"evaluation nesting exceeds {MAX_PURE_EXPRESSION_NESTING_V4}")
    budget.consume()
    op = str(node["op"])

    def ev(child: Mapping[str, Any], env: Mapping[str, TypedValueV4] = environment) -> TypedValueV4:
        return _eval(child, table, env, budget, depth=depth + 1, task_strategy=task_strategy)

    if op == "CONST":
        type_id=str(node["type"]); table.require(type_id,context="CONST")
        return TypedValueV4(type_id,decode_v4_value(type_id,node["value"],table,context="CONST"))
    if op == "PARAM":
        name=str(node["name"]); type_id=str(node["type"]); table.require(type_id,context="PARAM")
        binding=environment.get(name)
        if binding is None:_fail("TEVS_IR_V4_PURE_PARAM",f"missing parameter {name!r}")
        if binding.type_id!=type_id:_fail("TEVS_IR_V4_PURE_TYPE",f"parameter {name!r} expected {type_id}, got {binding.type_id}")
        return binding
    if op == "CONVERT_INT_TO_RAT":
        value=ev(node["operand"]); _require_type(value,"Int","CONVERT_INT_TO_RAT")
        return TypedValueV4("Rat",Fraction(value.value,1))
    if op == "UNARY":
        operand=ev(node["operand"]); operand_type=str(node["operand_type"]); result_type=str(node["result_type"])
        _require_type(operand,operand_type,"UNARY"); table.require(result_type,context="UNARY result")
        operator=str(node["operator"])
        if operator=="NOT" and operand_type==result_type=="Bool": result=not operand.value
        elif operator=="MINUS" and operand_type==result_type and operand_type in {"Int","Rat"}: result=-operand.value
        else:_fail("TEVS_IR_V4_PURE_TYPE",f"invalid unary contract {operator} {operand_type}->{result_type}")
        return _validated(result_type,result,table,"UNARY")
    if op == "BINARY":
        left=ev(node["left"]); right=ev(node["right"])
        lt=str(node["left_type"]); rt=str(node["right_type"]); result_type=str(node["result_type"]); operator=str(node["operator"])
        _require_type(left,lt,"BINARY left"); _require_type(right,rt,"BINARY right"); table.require(result_type,context="BINARY result")
        result=_binary(operator,lt,rt,result_type,left.value,right.value,table)
        return _validated(result_type,result,table,"BINARY")
    if op == "IF":
        condition=ev(node["condition"]); _require_type(condition,"Bool","IF condition")
        selected=node["then"] if condition.value else node["else"]
        result=ev(selected); _require_type(result,str(node["result_type"]),"IF branch")
        return result
    if op == "LET":
        name=str(node["name"]); declared=str(node["type"]); result_type=str(node["result_type"])
        value=ev(node["value"]); _require_type(value,declared,"LET value")
        nested=dict(environment); nested[name]=value
        result=ev(node["body"],nested); _require_type(result,result_type,"LET body")
        return result
    if op == "RECORD":
        type_id=str(node["type"]); descriptor=table.require(type_id,context="RECORD")
        if descriptor.kind!="record":_fail("TEVS_IR_V4_PURE_TYPE",f"RECORD requires record type, got {type_id}")
        field_nodes={str(item["name"]):item["expr"] for item in node["fields"]}
        expected={name:field_type for name,field_type in descriptor.fields}
        if set(field_nodes)!=set(expected):_fail("TEVS_IR_V4_PURE_RECORD","record field set mismatch")
        fields=[]
        for name,field_type in descriptor.fields:
            value=ev(field_nodes[name]); _require_type(value,field_type,f"RECORD field {name}"); fields.append((name,value.value))
        return _validated(type_id,RecordValueV4(type_id,tuple(fields)),table,"RECORD")
    if op == "FIELD":
        record_type=str(node["record_type"]); result_type=str(node["result_type"]); field=str(node["field"])
        descriptor=table.require(record_type,context="FIELD")
        if descriptor.kind!="record":_fail("TEVS_IR_V4_PURE_TYPE","FIELD requires record type")
        expected=dict(descriptor.fields).get(field)
        if expected!=result_type:_fail("TEVS_IR_V4_PURE_TYPE",f"field {field!r} is not {result_type!r}")
        record=ev(node["record"]); _require_type(record,record_type,"FIELD record")
        if not isinstance(record.value,RecordValueV4):_fail("TEVS_IR_V4_PURE_TYPE","FIELD runtime value is not record")
        actual=dict(record.value.fields)
        return TypedValueV4(result_type,actual[field])
    if op == "VARIANT":
        type_id=str(node["type"]); variant=str(node["variant"]); descriptor=table.require(type_id,context="VARIANT")
        payload_type=_variant_payload_type(descriptor,variant)
        has_payload="payload" in node
        if payload_type is None:
            if has_payload:_fail("TEVS_IR_V4_PURE_VARIANT",f"{variant} cannot carry payload")
            value=VariantValueV4(type_id,variant)
        else:
            if not has_payload:_fail("TEVS_IR_V4_PURE_VARIANT",f"{variant} requires payload")
            payload=ev(node["payload"]); _require_type(payload,payload_type,"VARIANT payload")
            value=VariantValueV4(type_id,variant,payload.value)
        return _validated(type_id,value,table,"VARIANT")
    if op in {"LIST","ARRAY","SET"}:
        type_id=str(node["type"]); descriptor=table.require(type_id,context=op)
        expected_kind=op.lower()
        if descriptor.kind!=expected_kind or descriptor.element_type is None:_fail("TEVS_IR_V4_PURE_TYPE",f"{op} requires {expected_kind} descriptor")
        items=[]
        for raw in node["items"]:
            item=ev(raw); _require_type(item,descriptor.element_type,f"{op} item"); items.append(item.value)
        if op=="LIST": value=ListValueV4(type_id,tuple(items))
        elif op=="ARRAY": value=ArrayValueV4(type_id,tuple(items))
        else: value=SetValueV4(type_id,tuple(items))
        return _validated(type_id,value,table,op)
    if op == "MAP":
        type_id=str(node["type"]); descriptor=table.require(type_id,context="MAP")
        if descriptor.kind!="map" or descriptor.key_type is None or descriptor.value_type is None:_fail("TEVS_IR_V4_PURE_TYPE","MAP requires map descriptor")
        entries=[]
        for raw in node["entries"]:
            key=ev(raw["key"]); value=ev(raw["value"])
            _require_type(key,descriptor.key_type,"MAP key"); _require_type(value,descriptor.value_type,"MAP value")
            entries.append((key.value,value.value))
        return _validated(type_id,MapValueV4(type_id,tuple(entries)),table,"MAP")
    if op == "LIST_PUSH":
        ct=str(node["collection_type"]); descriptor=_collection_descriptor(table,ct,"list")
        collection=ev(node["collection"]); item=ev(node["item"]); _require_type(collection,ct,"LIST_PUSH collection"); assert descriptor.element_type is not None; _require_type(item,descriptor.element_type,"LIST_PUSH item")
        return _validated(ct,list_push(collection.value,item.value,table),table,"LIST_PUSH")
    if op == "LIST_GET":
        ct=str(node["collection_type"]); result_type=str(node["result_type"]); descriptor=_collection_descriptor(table,ct,"list")
        if descriptor.element_type!=result_type:_fail("TEVS_IR_V4_PURE_TYPE","LIST_GET result type mismatch")
        collection=ev(node["collection"]); index=ev(node["index"]); _require_type(collection,ct,"LIST_GET collection"); _require_type(index,"Int","LIST_GET index")
        return TypedValueV4(result_type,list_get(collection.value,index.value,table))
    if op == "LIST_SET":
        ct=str(node["collection_type"]); descriptor=_collection_descriptor(table,ct,"list")
        collection=ev(node["collection"]); index=ev(node["index"]); item=ev(node["item"]); _require_type(collection,ct,"LIST_SET collection"); _require_type(index,"Int","LIST_SET index"); assert descriptor.element_type is not None; _require_type(item,descriptor.element_type,"LIST_SET item")
        return _validated(ct,list_set(collection.value,index.value,item.value,table),table,"LIST_SET")
    if op == "ARRAY_GET":
        ct=str(node["collection_type"]); result_type=str(node["result_type"]); descriptor=_collection_descriptor(table,ct,"array")
        if descriptor.element_type!=result_type:_fail("TEVS_IR_V4_PURE_TYPE","ARRAY_GET result type mismatch")
        collection=ev(node["collection"]); index=ev(node["index"]); _require_type(collection,ct,"ARRAY_GET collection"); _require_type(index,"Int","ARRAY_GET index")
        return TypedValueV4(result_type,array_get(collection.value,index.value,table))
    if op == "ARRAY_SET":
        ct=str(node["collection_type"]); descriptor=_collection_descriptor(table,ct,"array")
        collection=ev(node["collection"]); index=ev(node["index"]); item=ev(node["item"]); _require_type(collection,ct,"ARRAY_SET collection"); _require_type(index,"Int","ARRAY_SET index"); assert descriptor.element_type is not None; _require_type(item,descriptor.element_type,"ARRAY_SET item")
        return _validated(ct,array_set(collection.value,index.value,item.value,table),table,"ARRAY_SET")
    if op == "SET_ADD":
        ct=str(node["collection_type"]); descriptor=_collection_descriptor(table,ct,"set")
        collection=ev(node["collection"]); item=ev(node["item"]); _require_type(collection,ct,"SET_ADD collection"); assert descriptor.element_type is not None; _require_type(item,descriptor.element_type,"SET_ADD item")
        return _validated(ct,set_add(collection.value,item.value,table),table,"SET_ADD")
    if op == "SET_CONTAINS":
        ct=str(node["collection_type"]); descriptor=_collection_descriptor(table,ct,"set")
        collection=ev(node["collection"]); item=ev(node["item"]); _require_type(collection,ct,"SET_CONTAINS collection"); assert descriptor.element_type is not None; _require_type(item,descriptor.element_type,"SET_CONTAINS item")
        return TypedValueV4("Bool",set_contains(collection.value,item.value,table))
    if op == "MAP_PUT":
        ct=str(node["collection_type"]); descriptor=_collection_descriptor(table,ct,"map")
        collection=ev(node["collection"]); key=ev(node["key"]); value=ev(node["value"]); _require_type(collection,ct,"MAP_PUT collection"); assert descriptor.key_type is not None and descriptor.value_type is not None; _require_type(key,descriptor.key_type,"MAP_PUT key"); _require_type(value,descriptor.value_type,"MAP_PUT value")
        return _validated(ct,map_put(collection.value,key.value,value.value,table),table,"MAP_PUT")
    if op == "MAP_LOOKUP":
        ct=str(node["collection_type"]); result_type=str(node["result_type"]); descriptor=_collection_descriptor(table,ct,"map")
        assert descriptor.key_type is not None and descriptor.value_type is not None
        expected=f"Option<{descriptor.value_type}>"
        if result_type!=expected:_fail("TEVS_IR_V4_PURE_TYPE",f"MAP_LOOKUP result must be {expected}, got {result_type}")
        option=table.require(result_type,context="MAP_LOOKUP Option result")
        if option.kind!="option" or option.argument!=descriptor.value_type:_fail("TEVS_IR_V4_PURE_TYPE","MAP_LOOKUP Option descriptor mismatch")
        collection=ev(node["collection"]); key=ev(node["key"]); _require_type(collection,ct,"MAP_LOOKUP collection"); _require_type(key,descriptor.key_type,"MAP_LOOKUP key")
        lookup=map_lookup(collection.value,key.value,table)
        value=VariantValueV4(result_type,"Some",lookup.value) if lookup.found else VariantValueV4(result_type,"None")
        return _validated(result_type,value,table,"MAP_LOOKUP")
    if op == "LEN":
        ct=str(node["collection_type"]); descriptor=table.require(ct,context="LEN")
        if descriptor.kind not in {"list","array","set","map"}:_fail("TEVS_IR_V4_PURE_TYPE","LEN requires collection")
        collection=ev(node["collection"]); _require_type(collection,ct,"LEN collection")
        if isinstance(collection.value,ArrayValueV4): length=len(array_items(collection.value,table))
        elif isinstance(collection.value,ListValueV4): length=len(list_items(collection.value,table))
        elif isinstance(collection.value,SetValueV4): length=len(set_items(collection.value,table))
        elif isinstance(collection.value,MapValueV4): length=len(map_entries(collection.value,table))
        else:_fail("TEVS_IR_V4_PURE_TYPE","LEN runtime value is not collection")
        return TypedValueV4("Int",length)
    if op == "MATCH":
        subject_type, result_type=str(node["subject_type"]),str(node["result_type"])
        descriptor=table.require(subject_type,context="MATCH subject")
        subject=ev(node["subject"]); _require_type(subject,subject_type,"MATCH subject")
        if not isinstance(subject.value,VariantValueV4):
            _fail("TEVS_IR_V4_PURE_MATCH","MATCH runtime subject is not a variant value")
        selected=next((arm for arm in node["arms"] if str(arm["variant"])==subject.value.variant),None)
        if selected is None:
            _fail("TEVS_IR_V4_PURE_MATCH",f"no MATCH arm for variant {subject.value.variant!r}")
        nested=dict(environment); payload_type=_variant_payload_type(descriptor,subject.value.variant)
        binding=selected.get("binding")
        if payload_type is not None:
            if not subject.value.has_payload or not isinstance(binding,Mapping):
                _fail("TEVS_IR_V4_PURE_MATCH","payload MATCH runtime contract mismatch")
            nested[str(binding["name"])]=TypedValueV4(payload_type,subject.value.payload)
        result=ev(selected["body"],nested); _require_type(result,result_type,"MATCH body")
        return result
    if op == "TASK_SCOPE":
        if node["join_policy"] != TASK_JOIN_POLICY_V4 or node["cancellation_policy"] != TASK_CANCELLATION_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_TASK_POLICY", "TASK_SCOPE runtime policy mismatch")
        tasks=tuple(node["tasks"])

        def evaluate_child(task: Mapping[str, Any]) -> TaskChildEvaluationV4:
            name=str(task["name"]); task_type=str(task["type"])
            child_budget=_BudgetV4(budget.maximum)
            child_result=_eval(
                task["body"],
                table,
                environment,
                child_budget,
                depth=depth + 1,
                task_strategy=task_strategy,
            )
            _require_type(child_result,task_type,f"TASK_SCOPE task {name}")
            return TaskChildEvaluationV4(name,child_result,child_budget.steps,child_budget.loop_iterations)

        completed=(
            tuple(evaluate_child(task) for task in tasks)
            if task_strategy is None
            else tuple(task_strategy.run(tasks,evaluate_child))
        )
        expected_names=tuple(str(task["name"]) for task in tasks)
        if len(completed)!=len(tasks) or any(not isinstance(item,TaskChildEvaluationV4) for item in completed):
            _fail("TEVS_IR_V4_PURE_TASK_STRATEGY", "task strategy returned an invalid child result set")
        by_name={item.name:item for item in completed}
        if len(by_name)!=len(completed) or set(by_name)!=set(expected_names):
            _fail("TEVS_IR_V4_PURE_TASK_STRATEGY", "task strategy changed the canonical child task set")
        nested=dict(environment)
        for task in tasks:
            name=str(task["name"]); task_type=str(task["type"]); child=by_name[name]
            _require_type(child.result,task_type,f"TASK_SCOPE task {name}")
            budget.absorb(steps=child.evaluation_steps,loop_iterations=child.bounded_loop_iterations)
            nested[name]=child.result
        result=ev(node["join"],nested); _require_type(result,str(node["result_type"]),"TASK_SCOPE join")
        return result
    if op == "PRIORITY_SELECT":
        if node["selection_policy"]!=PRIORITY_SELECT_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_SELECT_POLICY","PRIORITY_SELECT runtime policy mismatch")
        result_type=str(node["result_type"]); candidates=tuple(node["candidates"])
        cooperative_runner=getattr(task_strategy,"run_select_cooperative",None) if task_strategy is not None else None
        select_runner=getattr(task_strategy,"run_select",None) if task_strategy is not None else None
        if callable(cooperative_runner) or callable(select_runner):
            indexed=tuple(enumerate(candidates))

            def validate_outcome(item: tuple[int,Mapping[str,Any]], outcome: PrioritySelectCandidateOutcomeV4) -> None:
                index,_candidate=item
                if not isinstance(outcome,PrioritySelectCandidateOutcomeV4) or outcome.index!=index:
                    _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","select strategy returned a mismatched candidate outcome")
                if outcome.evaluation_steps<0 or outcome.bounded_loop_iterations<0:
                    _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","select strategy returned negative accounting")
                if outcome.error is not None and outcome.result is not None:
                    _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","errored select outcome also returned a result")
                if outcome.error is None and outcome.result is None:
                    _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","successful select outcome omitted its result")

            def outcome_is_terminal(item: tuple[int,Mapping[str,Any]], outcome: PrioritySelectCandidateOutcomeV4) -> bool:
                validate_outcome(item,outcome)
                _index,candidate=item; maximum_steps=int(candidate["maximum_steps"])
                error=outcome.error
                if isinstance(error,_OperationalCancellationV4):
                    _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","operational cancellation became visible in semantic select prefix")
                return not (
                    isinstance(error,TevScriptError)
                    and error.diagnostic.code=="TEVS_IR_V4_PURE_BUDGET"
                    and outcome.evaluation_steps>maximum_steps
                )

            def evaluate_candidate(item: tuple[int,Mapping[str,Any]]) -> PrioritySelectCandidateOutcomeV4:
                index,candidate=item; maximum_steps=int(candidate["maximum_steps"]); child_budget=_BudgetV4(maximum_steps)
                try:
                    result=_eval(candidate["body"],table,environment,child_budget,depth=depth+1,task_strategy=None)
                except Exception as error:
                    return PrioritySelectCandidateOutcomeV4(index,None,child_budget.steps,child_budget.loop_iterations,error)
                return PrioritySelectCandidateOutcomeV4(index,result,child_budget.steps,child_budget.loop_iterations,None)

            def evaluate_candidate_cooperative(
                item: tuple[int,Mapping[str,Any]],
                cancel_check: Callable[[],bool],
            ) -> PrioritySelectCandidateOutcomeV4:
                index,candidate=item; maximum_steps=int(candidate["maximum_steps"])
                child_budget=_BudgetV4(maximum_steps,cancel_check=cancel_check)
                try:
                    result=_eval(candidate["body"],table,environment,child_budget,depth=depth+1,task_strategy=None)
                except Exception as error:
                    return PrioritySelectCandidateOutcomeV4(index,None,child_budget.steps,child_budget.loop_iterations,error)
                return PrioritySelectCandidateOutcomeV4(index,result,child_budget.steps,child_budget.loop_iterations,None)

            prefix_allowed=callable(cooperative_runner)
            outcomes=tuple(
                cooperative_runner(indexed,evaluate_candidate_cooperative,outcome_is_terminal)
                if prefix_allowed
                else select_runner(indexed,evaluate_candidate)
            )
            if not outcomes or len(outcomes)>len(indexed):
                _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","select strategy returned an invalid outcome count")
            if not prefix_allowed and len(outcomes)!=len(indexed):
                _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","legacy select strategy must return the complete outcome set")
            by_index={item.index:item for item in outcomes if isinstance(item,PrioritySelectCandidateOutcomeV4)}
            expected_indexes=set(range(len(outcomes)))
            if len(by_index)!=len(outcomes) or set(by_index)!=expected_indexes:
                _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","select strategy changed the canonical candidate-prefix indexes")
            for index in range(len(outcomes)):
                candidate=candidates[index]; outcome=by_index[index]; validate_outcome((index,candidate),outcome)
                maximum_steps=int(candidate["maximum_steps"]); error=outcome.error
                if isinstance(error,_OperationalCancellationV4):
                    _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","operational cancellation became visible in semantic select prefix")
                if error is not None:
                    if isinstance(error,TevScriptError) and error.diagnostic.code=="TEVS_IR_V4_PURE_BUDGET" and outcome.evaluation_steps>maximum_steps:
                        budget.absorb(steps=outcome.evaluation_steps,loop_iterations=outcome.bounded_loop_iterations)
                        continue
                    raise error
                assert outcome.result is not None
                _require_type(outcome.result,result_type,f"PRIORITY_SELECT candidate {index}")
                budget.absorb(steps=outcome.evaluation_steps,loop_iterations=outcome.bounded_loop_iterations)
                return outcome.result
            if len(outcomes)<len(candidates):
                _fail("TEVS_IR_V4_PURE_SELECT_STRATEGY","cooperative select strategy stopped before a semantic terminal outcome")
            _fail("TEVS_IR_V4_PURE_SELECT_EXHAUSTED","all PRIORITY_SELECT candidates exceeded their declared step budgets")
        for index,candidate in enumerate(candidates):
            maximum_steps=int(candidate["maximum_steps"]); child_budget=_BudgetV4(maximum_steps)
            try:
                result=_eval(candidate["body"],table,environment,child_budget,depth=depth+1,task_strategy=task_strategy)
            except TevScriptError as error:
                if error.diagnostic.code!="TEVS_IR_V4_PURE_BUDGET" or child_budget.steps<=maximum_steps:
                    raise
                budget.absorb(steps=child_budget.steps,loop_iterations=child_budget.loop_iterations)
                continue
            _require_type(result,result_type,f"PRIORITY_SELECT candidate {index}")
            budget.absorb(steps=child_budget.steps,loop_iterations=child_budget.loop_iterations)
            return result
        _fail("TEVS_IR_V4_PURE_SELECT_EXHAUSTED","all PRIORITY_SELECT candidates exceeded their declared step budgets")
    if op == "STEP_LIMIT":
        maximum_steps=int(node["maximum_steps"]); result_type=str(node["result_type"])
        child_budget=_BudgetV4(maximum_steps)
        result=_eval(node["body"],table,environment,child_budget,depth=depth+1,task_strategy=task_strategy)
        _require_type(result,result_type,"STEP_LIMIT body")
        budget.absorb(steps=child_budget.steps,loop_iterations=child_budget.loop_iterations)
        return result
    if op == "TASK_DAG":
        if node["join_policy"]!=TASK_JOIN_POLICY_V4 or node["cancellation_policy"]!=TASK_CANCELLATION_POLICY_V4:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_POLICY","TASK_DAG runtime policy mismatch")
        tasks=tuple(node["tasks"]); by_name={str(task["name"]):task for task in tasks}
        _task_dag_topological_order(tasks)
        completed: dict[str,TaskChildEvaluationV4]={}
        remaining=set(by_name)
        while remaining:
            ready_names=sorted(name for name in remaining if set(str(item) for item in by_name[name]["dependencies"])<=set(completed))
            if not ready_names:
                _fail("TEVS_IR_V4_PURE_TASK_DAG_CYCLE",f"TASK_DAG runtime dependency cycle among {sorted(remaining)}")
            ready=tuple(by_name[name] for name in ready_names)
            def evaluate_child(task: Mapping[str,Any]) -> TaskChildEvaluationV4:
                name=str(task["name"]); task_type=str(task["type"]); nested=dict(environment)
                for dependency in task["dependencies"]:
                    dep=str(dependency); nested[dep]=completed[dep].result
                child_budget=_BudgetV4(budget.maximum)
                child_result=_eval(task["body"],table,nested,child_budget,depth=depth+1,task_strategy=task_strategy)
                _require_type(child_result,task_type,f"TASK_DAG task {name}")
                return TaskChildEvaluationV4(name,child_result,child_budget.steps,child_budget.loop_iterations)
            wave=(
                tuple(evaluate_child(task) for task in ready)
                if task_strategy is None
                else tuple(task_strategy.run(ready,evaluate_child))
            )
            if len(wave)!=len(ready) or any(not isinstance(item,TaskChildEvaluationV4) for item in wave):
                _fail("TEVS_IR_V4_PURE_TASK_DAG_STRATEGY","task strategy returned an invalid TASK_DAG wave")
            wave_by_name={item.name:item for item in wave}
            if len(wave_by_name)!=len(wave) or set(wave_by_name)!=set(ready_names):
                _fail("TEVS_IR_V4_PURE_TASK_DAG_STRATEGY","task strategy changed the canonical TASK_DAG ready set")
            for name in ready_names:
                child=wave_by_name[name]; task_type=str(by_name[name]["type"])
                _require_type(child.result,task_type,f"TASK_DAG task {name}")
                budget.absorb(steps=child.evaluation_steps,loop_iterations=child.bounded_loop_iterations)
                completed[name]=child
            remaining.difference_update(ready_names)
        join_env=dict(environment)
        for task in tasks:
            name=str(task["name"]); join_env[name]=completed[name].result
        result=ev(node["join"],join_env); _require_type(result,str(node["result_type"]),"TASK_DAG join")
        return result
    if op == "SELF_CALL":
        _fail("TEVS_IR_V4_PURE_RECURSION_CONTEXT", "SELF_CALL requires a governed recursive-function context")
    if op == "WHILE_FOLD":
        acc_type, acc_name = str(node["accumulator_type"]), str(node["accumulator_name"])
        accumulator = ev(node["initial"]); _require_type(accumulator, acc_type, "WHILE_FOLD initial")
        maximum = int(node["maximum_iterations"])
        for _iteration in range(maximum):
            nested = dict(environment); nested[acc_name] = accumulator
            condition = ev(node["condition"], nested); _require_type(condition, "Bool", "WHILE_FOLD condition")
            if not condition.value:
                return accumulator
            budget.loop()
            accumulator = ev(node["body"], nested); _require_type(accumulator, acc_type, "WHILE_FOLD body")
        nested = dict(environment); nested[acc_name] = accumulator
        final_condition = ev(node["condition"], nested); _require_type(final_condition, "Bool", "WHILE_FOLD final condition")
        if final_condition.value:
            _fail(
                "TEVS_IR_V4_PURE_WHILE_BOUND",
                f"WHILE_FOLD condition remains true after maximum_iterations={maximum}",
            )
        return accumulator
    if op == "FOR_FOLD":
        ct=str(node["collection_type"]); acc_type=str(node["accumulator_type"]); acc_name=str(node["accumulator_name"])
        descriptor=table.require(ct,context="FOR_FOLD")
        bound=descriptor.length if descriptor.kind=="array" else descriptor.capacity
        if descriptor.kind not in {"list","array","set","map"} or bound is None:_fail("TEVS_IR_V4_PURE_TYPE","FOR_FOLD requires bounded collection")
        collection=ev(node["collection"]); _require_type(collection,ct,"FOR_FOLD collection")
        accumulator=ev(node["initial"]); _require_type(accumulator,acc_type,"FOR_FOLD initial")
        binding_specs=[(str(item["name"]),str(item["type"])) for item in node["bindings"]]
        rows, expected_types=_iteration_rows(collection.value,descriptor,table)
        if tuple(type_id for _name,type_id in binding_specs)!=expected_types:_fail("TEVS_IR_V4_PURE_TYPE",f"FOR_FOLD bindings must be {expected_types}")
        if len(rows)>bound:_fail("TEVS_IR_V4_PURE_BOUND","FOR_FOLD actual rows exceed static bound")
        if descriptor.kind=="array" and len(rows)!=bound:_fail("TEVS_IR_V4_PURE_BOUND","FOR_FOLD array row count must equal exact length")
        for row in rows:
            budget.loop()
            nested=dict(environment); nested[acc_name]=accumulator
            for (name,type_id),item in zip(binding_specs,row,strict=True): nested[name]=TypedValueV4(type_id,item)
            accumulator=ev(node["body"],nested); _require_type(accumulator,acc_type,"FOR_FOLD body")
        return accumulator
    raise AssertionError(op)


def _require_binary_contract(operator: str, lt: str, rt: str, result_type: str) -> None:
    numeric = {"Int", "Rat"}; vectors = {"Vec2", "Vec3"}
    valid = False
    if operator in {"AND", "OR"}:
        valid = lt == rt == result_type == "Bool"
    elif operator in {"EQEQ", "NE"}:
        valid = result_type == "Bool" and (lt == rt or (lt in numeric and rt in numeric))
    elif operator in {"LT", "LE", "GT", "GE"}:
        valid = result_type == "Bool" and lt in numeric and rt in numeric
    elif operator in {"PLUS", "MINUS"}:
        valid = (lt == rt == result_type == "Int") or (
            lt in numeric and rt in numeric and result_type == "Rat"
        ) or (lt == rt == result_type and lt in vectors)
    elif operator == "STAR":
        valid = (lt == rt == result_type == "Int") or (
            lt in numeric and rt in numeric and result_type == "Rat"
        ) or (lt in vectors and rt in numeric and result_type == lt) or (
            rt in vectors and lt in numeric and result_type == rt
        )
    elif operator == "SLASH":
        valid = (lt in numeric and rt in numeric and result_type == "Rat") or (
            lt in vectors and rt in numeric and result_type == lt
        )
    if not valid:
        _fail("TEVS_IR_V4_PURE_TYPE", f"operator {operator} does not accept {lt},{rt}->{result_type}")


def _binary(operator: str, lt: str, rt: str, result_type: str, left: Any, right: Any, table: TypeTableV4) -> Any:
    _require_binary_contract(operator, lt, rt, result_type)
    numeric={"Int","Rat"}; vectors={"Vec2","Vec3"}
    if operator in {"AND","OR"}:
        if lt==rt==result_type=="Bool": return bool(left and right) if operator=="AND" else bool(left or right)
    elif operator in {"EQEQ","NE"}:
        if result_type!="Bool": _fail("TEVS_IR_V4_PURE_TYPE","equality result must be Bool")
        if lt in numeric and rt in numeric: equal=Fraction(left)==Fraction(right)
        elif lt==rt: equal=v4_values_equal(lt,left,right,table)
        else:_fail("TEVS_IR_V4_PURE_TYPE",f"invalid equality types {lt}, {rt}")
        return equal if operator=="EQEQ" else not equal
    elif operator in {"LT","LE","GT","GE"}:
        if lt in numeric and rt in numeric and result_type=="Bool":
            a,b=Fraction(left),Fraction(right)
            return {"LT":a<b,"LE":a<=b,"GT":a>b,"GE":a>=b}[operator]
    elif operator in {"PLUS","MINUS"}:
        fn=(lambda a,b:a+b) if operator=="PLUS" else (lambda a,b:a-b)
        if lt==rt==result_type=="Int": return fn(left,right)
        if lt in numeric and rt in numeric and result_type=="Rat": return fn(Fraction(left),Fraction(right))
        if lt==rt==result_type and lt in vectors:return tuple(fn(a,b) for a,b in zip(left,right,strict=True))
    elif operator=="STAR":
        if lt==rt==result_type=="Int":return left*right
        if lt in numeric and rt in numeric and result_type=="Rat":return Fraction(left)*Fraction(right)
        if lt in vectors and rt in numeric and result_type==lt:return tuple(Fraction(item)*Fraction(right) for item in left)
        if rt in vectors and lt in numeric and result_type==rt:return tuple(Fraction(left)*Fraction(item) for item in right)
    elif operator=="SLASH":
        if rt in numeric and Fraction(right)==0:_fail("TEVS_IR_V4_PURE_DIVIDE_ZERO","division by zero")
        if lt in numeric and rt in numeric and result_type=="Rat":return Fraction(left)/Fraction(right)
        if lt in vectors and rt in numeric and result_type==lt:return tuple(Fraction(item)/Fraction(right) for item in left)
    _fail("TEVS_IR_V4_PURE_TYPE",f"operator {operator} does not accept {lt},{rt}->{result_type}")


def _iteration_rows(value: Any, descriptor: TypeDescriptorV4, table: TypeTableV4) -> tuple[tuple[tuple[Any,...],...],tuple[str,...]]:
    if descriptor.kind=="list":
        assert descriptor.element_type is not None and isinstance(value,ListValueV4)
        return tuple((item,) for item in list_items(value,table)),(descriptor.element_type,)
    if descriptor.kind=="array":
        assert descriptor.element_type is not None and isinstance(value,ArrayValueV4)
        return tuple((item,) for item in array_items(value,table)),(descriptor.element_type,)
    if descriptor.kind=="set":
        assert descriptor.element_type is not None and isinstance(value,SetValueV4)
        return tuple((item,) for item in set_items(value,table)),(descriptor.element_type,)
    if descriptor.kind=="map":
        assert descriptor.key_type is not None and descriptor.value_type is not None and isinstance(value,MapValueV4)
        return tuple((key,item) for key,item in map_entries(value,table)),(descriptor.key_type,descriptor.value_type)
    raise AssertionError(descriptor.kind)


def _task_dag_topological_order(tasks: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    by_name={str(task["name"]):task for task in tasks}
    names=set(by_name)
    for name,task in by_name.items():
        dependencies=tuple(str(item) for item in task["dependencies"])
        if name in dependencies:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_CYCLE",f"TASK_DAG task {name!r} cannot depend on itself")
        unknown=sorted(set(dependencies)-names)
        if unknown:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_DEPENDENCY",f"TASK_DAG task {name!r} has unknown dependencies {unknown}")
    remaining=set(names); completed:set[str]=set(); order:list[str]=[]
    while remaining:
        ready=sorted(name for name in remaining if set(str(item) for item in by_name[name]["dependencies"])<=completed)
        if not ready:
            _fail("TEVS_IR_V4_PURE_TASK_DAG_CYCLE",f"TASK_DAG dependency cycle among {sorted(remaining)}")
        order.extend(ready); completed.update(ready); remaining.difference_update(ready)
    return tuple(order)


def _match_variants(descriptor: TypeDescriptorV4) -> tuple[str, ...]:
    if descriptor.kind=="enum": return tuple(descriptor.variants)
    if descriptor.kind=="option": return ("None","Some")
    if descriptor.kind=="result": return ("Err","Ok")
    _fail("TEVS_IR_V4_PURE_MATCH",f"type {descriptor.type_id!r} is not matchable")


def _variant_payload_type(descriptor: TypeDescriptorV4, variant: str) -> str | None:
    if descriptor.kind=="enum":
        if variant not in descriptor.variants:_fail("TEVS_IR_V4_PURE_VARIANT",f"unknown enum variant {variant!r}")
        return None
    if descriptor.kind=="option":
        if variant=="None":return None
        if variant=="Some":assert descriptor.argument is not None; return descriptor.argument
    if descriptor.kind=="result":
        if variant=="Ok":assert descriptor.ok_type is not None; return descriptor.ok_type
        if variant=="Err":assert descriptor.err_type is not None; return descriptor.err_type
    _fail("TEVS_IR_V4_PURE_VARIANT",f"type {descriptor.type_id!r} has no variant {variant!r}")


def _collection_descriptor(table: TypeTableV4, type_id: str, kind: str) -> TypeDescriptorV4:
    descriptor=table.require(type_id,context=kind.upper())
    if descriptor.kind!=kind:_fail("TEVS_IR_V4_PURE_TYPE",f"expected {kind}, got {descriptor.kind}")
    return descriptor


def _prepare_environment(bindings: Sequence[PureBindingV4], table: TypeTableV4) -> tuple[dict[str,TypedValueV4],dict[str,Any]]:
    environment={}; wire=[]
    for binding in bindings:
        if not isinstance(binding,PureBindingV4):_fail("TEVS_IR_V4_PURE_ENV","bindings must be PureBindingV4")
        name=_name(binding.name); table.require(binding.type_id,context=f"binding {name}")
        if name in environment:_fail("TEVS_IR_V4_PURE_ENV",f"duplicate binding {name!r}")
        encoded=encode_v4_value(binding.type_id,binding.value,table,context=f"binding {name}")
        normalized=decode_v4_value(binding.type_id,encoded,table,context=f"binding {name}")
        environment[name]=TypedValueV4(binding.type_id,normalized)
        wire.append({"name":name,"type":binding.type_id,"value":encoded})
    wire.sort(key=lambda item:item["name"])
    return environment,{"schema":"TEV_SCRIPT_IR_V4_PURE_ENVIRONMENT_V1","bindings":wire}


def _validated(type_id: str, value: Any, table: TypeTableV4, context: str) -> TypedValueV4:
    encoded=encode_v4_value(type_id,value,table,context=context)
    return TypedValueV4(type_id,decode_v4_value(type_id,encoded,table,context=context))


def _require_type(value: TypedValueV4, expected: str, context: str) -> None:
    if value.type_id!=expected:_fail("TEVS_IR_V4_PURE_TYPE",f"{context}: expected {expected}, got {value.type_id}")


def _descriptor_wire(item: TypeDescriptorV4) -> dict[str,Any]:
    result={"type_id":item.type_id,"kind":item.kind}
    if item.kind=="record":result["fields"]=[{"name":name,"type":type_id} for name,type_id in item.fields]
    elif item.kind=="enum":result["variants"]=list(item.variants)
    elif item.kind=="option":result["argument"]=item.argument
    elif item.kind=="result":result.update({"ok_type":item.ok_type,"err_type":item.err_type})
    elif item.kind in {"list","set"}:result.update({"element_type":item.element_type,"capacity":item.capacity,"order_policy":item.order_policy})
    elif item.kind=="array":result.update({"element_type":item.element_type,"length":item.length,"order_policy":item.order_policy})
    elif item.kind=="map":result.update({"key_type":item.key_type,"value_type":item.value_type,"capacity":item.capacity,"order_policy":item.order_policy})
    return result


def _exact(node: Mapping[str,Any], keys: set[str]) -> None:
    if set(node)!=keys:_fail("TEVS_IR_V4_PURE_EXPRESSION",f"expression field set mismatch: expected {sorted(keys)}, got {sorted(node)}")


def _type_text(value: Any) -> str:
    if not isinstance(value,str) or not value:_fail("TEVS_IR_V4_PURE_TYPE","type id must be non-empty string")
    return value


def _name(value: Any) -> str:
    if not isinstance(value,str) or _NAME.fullmatch(value) is None:_fail("TEVS_IR_V4_PURE_NAME",f"invalid local name {value!r}")
    return value


def _json_clone(value: Any) -> Any:
    try:return json.loads(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True))
    except (TypeError,ValueError) as exc:_fail("TEVS_IR_V4_PURE_EXPRESSION",f"expression contains non-JSON value: {exc}")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code,message)
