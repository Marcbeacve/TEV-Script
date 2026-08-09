# TEV Script IR V3 operational semantics

Status: **normative V1 / IR V3 candidate V2**.

This document is a focused executable companion to `spec/TEV_SCRIPT_IR_V3.md`. It freezes the identity envelope, stack effects and lowering obligations that the Python/JavaScript/C# validators and runtimes must reproduce.

## 1. Identity envelope

A canonical V3 program requires:

```text
schema               = TEV_SCRIPT_PROGRAM_IR_V3
language_version     = 1.0.0
lowering_profile     = TEV_SCRIPT_V1_IR_V3_PROFILE_V1
                         or TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1
source_schema        = TEV_SCRIPT_LINKED_PROGRAM_V1
                         or TEV_SCRIPT_PROGRAM_IR_V2
source_semantic_hash = exact semantic hash of that source artifact
program_id           = TEV source identifier
types                = closed canonical runtime type table
entities             = runtime entities
boundary             = explicit safety/resource boundary
semantic_hash        = canonical semantic IR hash
debug                = non-semantic metadata
debug_hash           = canonical debug hash
```

The profile and source schema are correlated:

```text
V1_IR_V3_PROFILE  <-> TEV_SCRIPT_LINKED_PROGRAM_V1
V2_LIFT_PROFILE   <-> TEV_SCRIPT_PROGRAM_IR_V2
```

`source_semantic_hash` participates in IR V3 semantic identity. The target therefore cannot silently be rebound to a different source semantic program.

## 2. Semantic hash

The V3 semantic hash is SHA-256 over canonical JSON of every semantic field except `semantic_hash`, `debug` and `debug_hash`.

Debug data is separately canonicalized and hashed. Changing source paths/debug maps must not alter V3 semantic identity.

## 3. Abstract machine

Each handler executes over:

```text
(pc, stack, locals, parameters, entity-state, emitted-buffer)
```

All stack slots have exact canonical type ids.

The V2 bounded-CFG invariants remain mandatory:

- jumps are forward only;
- no runtime loop/back-edge exists;
- every reachable path ends at `RETURN`;
- `RETURN` requires an empty stack;
- each CFG entry has a unique stack type vector;
- locals are readable only after definite initialization on every reaching path;
- local initialization sets merge by intersection;
- instruction/event budgets fail closed.

No runtime recursion, user-function stack, thread or implicit concurrency is introduced.

## 4. Retained V2 operations

The following operations retain their V2 semantics while using the V3 type table:

```text
CONST
LOAD_STATE
STORE_STATE
LOAD_LOCAL
STORE_LOCAL
LOAD_PARAM
CONVERT_INT_TO_RAT
UNARY
BINARY
CALL_PURE
CALL_CAPABILITY
EMIT_EVENT
JUMP_IF_FALSE
JUMP
RETURN
```

### 4.1 CONST

`CONST type value` decodes and validates `value` recursively against `type`, then pushes it. `Unit` cannot be used.

### 4.2 Loads and stores

Loads push the exact declared slot type. Stores consume the exact declared type; any source-level widening has already been materialized by `CONVERT_INT_TO_RAT`.

### 4.3 CALL_PURE

Runtime `CALL_PURE` is restricted to the frozen portable intrinsic set:

```text
vec2 vec3 min max
```

V1 user pure functions are validated and call-by-value inlined before IR emission.

### 4.4 CALL_CAPABILITY

Arguments are consumed according to the exact entity capability declaration. Host return values are recursively coerced/validated against the declared V3 return type. `Unit` pushes nothing.

### 4.5 BINARY equality

`EQEQ` and `NE` support same-type V3 algebraic values with recursive value equality. Numeric Int/Rat widening remains exact. Ordering remains numeric-only.

## 5. MAKE_RECORD

Shape:

```json
{
  "op":"MAKE_RECORD",
  "type":"game.Damage",
  "fields":["critical","amount"]
}
```

The `fields` array is **constructor evaluation order** and is semantic. It must contain each descriptor field exactly once but need not equal descriptor storage order.

If fields `f0...fn` were evaluated left-to-right, their typed values are present on the operand stack in that same order. `MAKE_RECORD` consumes them, maps them by the `fields` list, validates assignment compatibility and constructs one immutable nominal record stored in canonical descriptor field order.

This design preserves observable observations/effects embedded in constructor expressions while still making the resulting value canonical.

Stack effect:

```text
[..., T(field0), ..., T(fieldN)] -> [..., RecordType]
```

## 6. LOAD_FIELD

Shape:

```json
{
  "op":"LOAD_FIELD",
  "record_type":"game.Damage",
  "field":"amount",
  "result_type":"Int"
}
```

The descriptor must define the field with exact `result_type`.

Stack effect:

```text
[..., game.Damage] -> [..., Int]
```

No dynamic field names or reflection exist.

## 7. MAKE_VARIANT

Shape:

```json
{"op":"MAKE_VARIANT","type":"Option<Int>","variant":"Some","argc":1}
```

Descriptor-directed arities are:

```text
nominal enum variant -> argc 0
Option<T>.None       -> argc 0
Option<T>.Some       -> argc 1, payload T
Result<T,E>.Ok       -> argc 1, payload T
Result<T,E>.Err      -> argc 1, payload E
```

For `argc=1`, the exact payload is consumed before the immutable variant value is pushed.

## 8. TEST_VARIANT

Shape:

```json
{"op":"TEST_VARIANT","type":"Option<Int>","variant":"Some"}
```

It consumes one exact `type` value and pushes Bool indicating tag equality. The variant must exist for the descriptor.

```text
[..., Option<Int>] -> [..., Bool]
```

## 9. LOAD_VARIANT_PAYLOAD

Shape:

```json
{
  "op":"LOAD_VARIANT_PAYLOAD",
  "type":"Option<Int>",
  "variant":"Some",
  "payload_type":"Int"
}
```

The selected descriptor variant must have exactly one payload of `payload_type`.

The operation consumes one exact `type`. If the actual runtime tag is not the requested variant, execution fails deterministically; otherwise its payload is pushed.

A conforming compiler emits this operation only on a path guarded by the corresponding source match/`TEST_VARIANT` logic, but runtime validation still remains fail-closed.

## 10. Exhaustive match lowering

A linked V1 match is compiled into finite CFG, never a reflective runtime opcode.

Normative lowering:

1. evaluate the scrutinee exactly once;
2. store it in a compiler local;
3. process arms in linked canonical/source-semantic order;
4. `LOAD_LOCAL` + `TEST_VARIANT`;
5. `JUMP_IF_FALSE` to the next arm;
6. if payload-bearing, reload the scrutinee, `LOAD_VARIANT_PAYLOAD`, then `STORE_LOCAL` for the alpha-normalized binding;
7. emit the arm body;
8. jump to common match end when necessary.

All branches are forward. Source exhaustiveness has already been proved; the IR verifier proves type/CFG correctness independently.

## 11. Boolean short-circuit lowering

Source `and` and `or` preserve short-circuit observability. They lower to conditional forward jumps, not eager `BINARY AND/OR`, whenever evaluation of the right operand could be observable.

This is required because observation capabilities are permitted in handler expressions.

## 12. Compile-time erasure before V3

IR V3 does not contain modules, imports, exports, behavior objects, user-function frames or source `for` loops.

Before V3 emission:

```text
imports/names -> resolved
authority visibility -> checked
behaviors -> deterministically expanded
user pure functions -> call-by-value inlined
for -> bounded unrolling
lexical names -> alpha normalized
records/variants/match -> explicit typed V3 instructions
```

The runtime remains intentionally small despite the richer source language.

## 13. Closed type-table validation

Runtime construction must reject the program unless the entire `types` table is valid before any entity executes.

The validator proves at least:

- six primitive descriptors + Unit exist exactly once;
- all `type_id` values are unique and canonically ordered;
- record fields and enum variants are canonical/unique;
- Option/Result descriptor ids agree with their arguments;
- all referenced types exist;
- Unit occurs only in permitted signature-return positions;
- record dependencies are acyclic;
- type/value nesting is within `maximum_value_nesting`;
- no host-object/reference boundary is enabled.

## 14. Typed CFG verification

The V3 abstract interpreter extends the V2 flow verifier with descriptor-aware stack effects.

Examples:

```text
MAKE_RECORD R fields=[a,b]
  [..., T(a), T(b)] -> [..., R]

LOAD_FIELD R.a:A
  [..., R] -> [..., A]

MAKE_VARIANT Option<A>.Some argc=1
  [..., A] -> [..., Option<A>]

TEST_VARIANT Option<A>.Some
  [..., Option<A>] -> [..., Bool]

LOAD_VARIANT_PAYLOAD Option<A>.Some:A
  [..., Option<A>] -> [..., A]
```

The verifier rejects invalid descriptors, stack underflow, mismatched operands, invalid jumps, local-before-store, incompatible CFG joins and stack leaks before runtime construction succeeds.

## 15. Runtime value/capability faults

After structural + flow validation, deterministic runtime faults still include:

- missing capability binding;
- invalid capability return coercion;
- division by zero;
- invalid variant payload extraction;
- instruction budget exhaustion;
- event-chain budget exhaustion.

Malformed IR/value/type tables are construction-time failures, not deferred execution failures.

## 16. Event machine

V3 inherits the bounded FIFO local event model. Emitted V3 values are recorded canonically and requeued only when an exact local handler exists.

No implicit cross-entity routing, networking or concurrency is introduced.

## 17. V2 lift profile

A separately certified adapter may lift valid IR V2 into V3 using:

```text
lowering_profile     = TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1
source_schema        = TEV_SCRIPT_PROGRAM_IR_V2
source_semantic_hash = V2 semantic hash
```

The adapter adds the closed primitive type table and V3 envelope without numeric loss. Equivalent runtime behavior does not imply equal V2/V3 semantic hashes.

## 18. Checkpoint/update boundary

Runtime V3 is not complete until `TEV_SCRIPT_RUNTIME_CHECKPOINT_V2` supports all V3 state values and signed-update/replay campaigns are repeated on V3.

Checkpoint restore remains exact-program only and must bind:

- checkpoint schema;
- program id;
- IR schema;
- V3 semantic hash;
- source semantic hash;
- complete typed state set.

## 19. Promotion condition

IR V3 may be called frozen only after structural schema, type-table validator, typed CFG verifier, Python runtime, V1→V3 lowering, V2→V3 lift, value canonicalization, checkpoint V2 and the cross-runtime Browser/WASI campaigns all pass from exact reproducible content.

Until then the correct state is `IR_V3=IMPLEMENTATION_CANDIDATE` and `LANGUAGE_STABLE=NO`.
