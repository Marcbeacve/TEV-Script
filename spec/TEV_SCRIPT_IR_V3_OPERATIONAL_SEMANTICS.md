# TEV Script IR V3 operational semantics

Status: **normative V1 / IR V3 candidate V1**.

IR V3 is the runtime target for TEV Script V1 programs that cannot be erased into the certified IR V2 value domain. It retains the bounded deterministic abstract machine of IR V2 and adds only typed algebraic-value operations.

## 1. Program identity

An IR V3 program has:

```text
schema               = TEV_SCRIPT_PROGRAM_IR_V3
language_version     = 1.0.0
lowering_profile     = TEV_SCRIPT_V1_IR_V3_PROFILE_V1
source_schema        = TEV_SCRIPT_LINKED_PROGRAM_V1
source_semantic_hash = SHA-256 of the canonical linked V1 semantic program
semantic_hash        = SHA-256 of the canonical IR V3 semantic object
```

`source_semantic_hash` is part of IR V3 semantic identity. Two IR V3 programs cannot claim to represent different linked V1 programs while retaining the same IR semantic object.

The IR `semantic_hash` is computed before adding `semantic_hash`, `debug` and `debug_hash`, exactly as in IR V2.

## 2. Program semantic object

The semantic object contains:

- schema/version/lowering profile/source binding;
- program id;
- closed runtime type registry;
- entities;
- explicit boundary flags/budgets.

Debug/source-map data is excluded from semantic identity and separately hashed.

## 3. Abstract machine

Each handler executes over:

```text
(pc, operand-stack, locals, parameters, entity-state, emitted-buffer)
```

All values are strongly typed by canonical V3 type ids.

Invariants inherited from IR V2:

- every jump is forward;
- no backward edge exists in the runtime CFG;
- every reachable path terminates at `RETURN`;
- `RETURN` requires an empty operand stack;
- locals are readable only after definite initialization on every reaching path;
- at a CFG merge, incoming stack type vectors are identical;
- definitely initialized locals are intersected at merges;
- instruction execution is sequential and deterministic;
- runtime instruction and event-chain budgets fail closed.

IR V3 does not introduce runtime recursion, runtime loops, threads or implicit parallelism.

## 4. Existing instruction family

The following IR V2 operations remain with the same semantics, generalized to V3 storable type ids where appropriate:

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

```json
{"op":"CONST","type":"game.Damage","value":{"$record":{...}}}
```

The value is recursively decoded/validated against `type`. `Unit` is forbidden.

### 4.2 LOAD / STORE

State/local/parameter operations require exact declared canonical type ids. Assignment widening is already materialized by explicit conversion instructions before a store; stores themselves are exact-type operations.

### 4.3 CONVERT_INT_TO_RAT

Unchanged: pop `Int`, push exact `Rat(n,1)`.

### 4.4 UNARY

`not` accepts `Bool`; unary minus accepts numeric types. No algebraic-value unary operation exists.

### 4.5 BINARY

Arithmetic and ordering remain restricted to the V1 operator matrix.

`EQEQ` / `NE` additionally support same-type V3 records/enums/Option/Result with the recursive equality rules from the IR V3 value model.

No implicit structural conversion between different nominal record/enum types exists.

### 4.6 CALL_PURE

IR V3 runtime pure calls are restricted to the frozen portable built-ins (`vec2`, `vec3`, `min`, `max`) unless a later IR revision explicitly adds another runtime intrinsic. V1 user functions are lowered/inlined before runtime IR.

### 4.7 CALL_CAPABILITY

Capability calls use the entity-declared complete V3 signature. Arguments are popped in source order, validated by static flow, and the host result is recursively coerced/validated against the declared return type before entering TEV state/stack.

A `Unit` return pushes nothing.

### 4.8 EMIT_EVENT

Event argument types may be any V3 storable type. The instruction must exactly match the entity emitted-event declaration.

## 5. New record instructions

### 5.1 MAKE_RECORD

```json
{"op":"MAKE_RECORD","type":"game.Damage"}
```

Preconditions:

- `type` resolves to a record descriptor;
- if the descriptor has fields `(f0:T0, ..., fn:Tn)` in canonical field-name order, the operand stack ends with values `(v0:T0, ..., vn:Tn)` in that same order.

Operation:

1. pop all field values as one ordered argument vector;
2. create immutable `RecordValue(type, fields)`;
3. push one value of the nominal record type.

No source field order is retained.

### 5.2 LOAD_FIELD

```json
{
  "op":"LOAD_FIELD",
  "record_type":"game.Damage",
  "field":"amount",
  "result_type":"Int"
}
```

Preconditions:

- top of stack has exact `record_type`;
- registry descriptor contains `field` with exact `result_type`.

Operation:

- pop the record;
- push the immutable field value.

No reflection or dynamic field name exists.

## 6. New closed-variant instructions

`enum`, `Option` and `Result` share the abstract `VariantValue(type, tag, optional_payload)` representation.

### 6.1 MAKE_VARIANT

```json
{"op":"MAKE_VARIANT","type":"Option<Int>","variant":"Some"}
```

The registry/type parser determines payload arity/type:

- nominal enum variant: arity 0;
- `Option<T>.None`: arity 0;
- `Option<T>.Some`: arity 1 of `T`;
- `Result<T,E>.Ok`: arity 1 of `T`;
- `Result<T,E>.Err`: arity 1 of `E`.

For arity 1, pop one exact payload value. Push the constructed variant value.

Unknown type/variant or wrong stack type is invalid IR/runtime state and fails closed.

### 6.2 IS_VARIANT

```json
{"op":"IS_VARIANT","type":"Option<Int>","variant":"Some"}
```

Pop one value of exact `type`; push `Bool` indicating whether its tag equals `variant`.

This operation has no side effects and does not expose payload content.

### 6.3 UNWRAP_VARIANT

```json
{
  "op":"UNWRAP_VARIANT",
  "type":"Option<Int>",
  "variant":"Some",
  "result_type":"Int"
}
```

Preconditions:

- `variant` must be a payload-bearing variant of `type`;
- `result_type` must equal its payload type;
- top stack value has exact `type`.

Operation:

- pop the variant;
- if the runtime tag is not exactly `variant`, raise deterministic variant-unwrapping fault;
- push its payload with exact `result_type`.

`UNWRAP_VARIANT` is invalid for payload-free enum variants and `None`.

## 7. Lowering exhaustive match

A source `match` is lowered without runtime reflection.

The target expression is evaluated exactly once and stored in a compiler-generated local. Arms use `LOAD_LOCAL + IS_VARIANT + JUMP_IF_FALSE`. Payload-bearing arms use `LOAD_LOCAL + UNWRAP_VARIANT + STORE_LOCAL` to initialize the canonical arm binding.

All jumps remain forward.

Source exhaustiveness is already proved by linked static semantics. IR V3 does not add a wildcard/default runtime feature.

## 8. Short-circuit boolean semantics

As in the V1-to-IR-V2 lowering, source `and` / `or` MUST lower to forward conditional control flow. They MUST NOT lower to eager `BINARY AND/OR` when the right operand could contain an observation capability.

The runtime may retain `BINARY AND/OR` for already-evaluated Bool operands, but V1 source lowering must preserve source short-circuit observability.

## 9. Behavior and function erasure

IR V3 contains no runtime behavior objects and no user-function call frames.

Before IR V3:

- modules/imports/export are resolved/erased;
- behaviors are deterministically expanded into entity handlers/states;
- user pure functions are call-by-value inlined;
- bounded `for` is unrolled;
- lexical names are alpha-renamed;
- source algebraic expressions become explicit V3 value instructions.

Therefore runtime semantics remain small despite richer source semantics.

## 10. Type registry validation

Before runtime construction the validator MUST prove:

- every nominal type id is unique;
- descriptors are canonical and sorted;
- record fields are unique, sorted and storable;
- enum variants are unique, sorted and nonempty;
- all referenced nominal type ids exist;
- `Option`/`Result` type ids parse exactly and contain storable types;
- `Unit` appears only as an allowed signature return;
- record dependency graph is acyclic;
- type nesting is within the normative limit.

## 11. Typed CFG verification

IR V3 has a dedicated abstract interpreter. It includes all IR V2 flow checks plus stack effects for V3 operations.

Examples:

```text
MAKE_RECORD game.R:
  [..., F0, F1] -> [..., game.R]

LOAD_FIELD game.R.x:Int:
  [..., game.R] -> [..., Int]

MAKE_VARIANT Option<Int>.Some:
  [..., Int] -> [..., Option<Int>]

IS_VARIANT Option<Int>.Some:
  [..., Option<Int>] -> [..., Bool]

UNWRAP_VARIANT Option<Int>.Some:Int:
  [..., Option<Int>] -> [..., Int]
```

A stack mismatch, invalid descriptor, local-before-store, CFG merge mismatch or invalid variant operation is rejected before execution.

## 12. Runtime faults

Deterministic runtime faults include:

- instruction/event budget exhaustion;
- missing capability;
- capability input/output coercion failure;
- division by zero;
- invalid variant unwrap;
- corrupted checkpoint value;
- semantic/debug hash mismatch;
- runtime program boundary violation.

Malformed IR/type/value structures are rejected during runtime construction and are not deferred until a handler happens to execute them.

## 13. Event machine

The bounded FIFO event machine is inherited from IR V2.

A handled emitted event is:

1. recorded as emitted;
2. requeued locally if an exact handler exists;
3. processed under the maximum event-chain budget.

No thread or implicit parallel event dispatch is introduced.

## 14. Debug identity

IR V3 debug data may contain linked-source ids, source paths and instruction-to-component/source maps. It is excluded from semantic identity and protected by `debug_hash`.

Changing only debug paths must not change IR semantic bytes/hash.

## 15. Compatibility boundary

IR V2 remains immutable and authoritative for V0.2 and for the proven erasable V1 subset.

IR V3 is not a reinterpretation of IR V2. Hosts explicitly dispatch by `schema`:

```text
TEV_SCRIPT_PROGRAM_IR_V2 -> certified V2 validator/runtime
TEV_SCRIPT_PROGRAM_IR_V3 -> V3 validator/runtime
```

A V1 program that is IR-V2-lowerable may target IR V2 and emit a `TEV_SCRIPT_LOWERING_RECEIPT_V1`. A program requiring V1 runtime values targets IR V3.

## 16. Checkpoint/update boundary

IR V3 checkpoint and signed-update support are separate promotion gates.

A V3 runtime implementation is not considered feature-complete until:

- checkpoint V2 exact restore supports every V3 value kind;
- signed update can transition between validated V3 programs without reinterpreting old state;
- exact hash/type compatibility boundaries are enforced;
- cross-host canonical checkpoint/update receipts agree.
