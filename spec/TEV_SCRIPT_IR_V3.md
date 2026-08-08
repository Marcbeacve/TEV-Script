# TEV Script Program IR V3

Status: **normative design candidate V1**. Implementation and cross-runtime certification are pending.

IR V3 is the runtime representation required for the non-erasable TEV Script V1 value surface. It extends the bounded stack-machine model of `TEV_SCRIPT_PROGRAM_IR_V2`; it does not introduce reflection, dynamic code, recursion, unbounded control flow, implicit concurrency or host-native language values.

## 1. Design objective

IR V3 must represent exactly the V1 runtime constructs that cannot always disappear before execution:

- nominal records;
- nominal payload-free enums;
- `Option<T>`;
- `Result<T,E>`;
- runtime record construction and field access;
- runtime sum construction and variant inspection;
- exhaustive V1 match lowered to finite typed CFG;
- capabilities/events/state/locals carrying those value types.

Modules, imports, exports, behaviors, bounded `for`, and user pure-function declarations remain compile-time abstractions and do not become runtime objects.

## 2. Program envelope

A V3 program is:

```text
schema           = TEV_SCRIPT_PROGRAM_IR_V3
language_version = 1.0.0
program_id       = stable V1 program id
types            = canonical runtime type table
entities         = runtime entities
boundary         = explicit safety boundary
semantic_hash    = SHA-256 canonical semantic program hash
debug            = optional non-semantic metadata
debug_hash       = hash of debug metadata when present
```

`semantic_hash` excludes itself and all debug data.

The program must satisfy `schemas/tev_script_program_ir_v3.schema.json` and the typed CFG verifier defined by this document.

## 3. Runtime type table

Every V3 program carries a canonical type table sorted by `type_id`. The table is closed: every type referenced by runtime state, parameters, locals, capabilities, emitted events, values or instructions must resolve to exactly one descriptor.

### 3.1 Primitive descriptors

The portable profile defines:

```text
Bool Int Rat Text Vec2 Vec3 Unit
```

Descriptors use:

```json
{"type_id":"Int","kind":"primitive"}
{"type_id":"Unit","kind":"unit"}
```

`Unit` is never a runtime value. It may occur only as a capability return type.

### 3.2 Record descriptors

```json
{
  "type_id":"game.Damage",
  "kind":"record",
  "fields":[
    {"name":"amount","type":"Int"},
    {"name":"critical","type":"Bool"}
  ]
}
```

Fields are canonical by field name. Record type identity is nominal: a record is compatible only with the exact same `type_id`.

Recursive record dependencies remain forbidden; IR validation must detect direct and indirect cycles, including cycles through `Option` and `Result` descriptors.

### 3.3 Enum descriptors

```json
{
  "type_id":"game.Kind",
  "kind":"enum",
  "variants":["Fire","Ice","Physical"]
}
```

Variants are canonical lexical ids. They have no integer representation or ordering semantics.

### 3.4 Option descriptors

```json
{
  "type_id":"Option<Int>",
  "kind":"option",
  "argument":"Int"
}
```

Variants are exactly `None` and `Some`; only `Some` has one payload of the descriptor argument type.

### 3.5 Result descriptors

```json
{
  "type_id":"Result<Int,Text>",
  "kind":"result",
  "ok_type":"Int",
  "err_type":"Text"
}
```

Variants are exactly `Ok` and `Err`, each with one payload of its declared type.

## 4. Runtime value model

V3 values are immutable value-semantic data. No language value is a host object reference.

Primitive values retain the exact V0.2 portable encodings for Bool, Int, Rat, Text, Vec2 and Vec3.

V3 adds canonical typed JSON encodings.

### 4.1 Record value

```json
{
  "$record": {
    "type":"game.Damage",
    "fields":[
      {"name":"amount","value":{"$int":"12"}},
      {"name":"critical","value":false}
    ]
  }
}
```

Field entries are stored in canonical descriptor field order regardless of constructor source order.

### 4.2 Enum value

```json
{"$enum":{"type":"game.Kind","variant":"Fire"}}
```

### 4.3 Option values

```json
{"$option":{"type":"Option<Int>","variant":"None"}}
{"$option":{"type":"Option<Int>","variant":"Some","value":{"$int":"7"}}}
```

### 4.4 Result values

```json
{"$result":{"type":"Result<Int,Text>","variant":"Ok","value":{"$int":"7"}}}
{"$result":{"type":"Result<Int,Text>","variant":"Err","value":"invalid"}}
```

A runtime decoder validates the encoded type id, constructor tag, payload presence, payload type and record field set/order against the program type table before admitting the value.

## 5. Equality

IR V3 `BINARY EQEQ/NE` extends exact equality to all storable V1 types.

Rules:

- primitive semantics remain V0.2-compatible;
- `Int` and `Rat` may compare after exact `Int -> Rat` widening;
- records require identical nominal type ids and compare every canonical field recursively;
- enums require identical nominal type ids and compare the exact variant;
- Option/Result require identical constructed type ids and compare variant plus payload recursively;
- different nominal/constructed types are rejected by the verifier rather than coerced at runtime.

Ordering operators remain numeric-only.

## 6. Existing V2 instructions retained

IR V3 preserves the semantics of:

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

Their type fields now refer to V3 type-table ids where applicable.

`CALL_PURE` remains restricted to the finite portable pure builtin catalog after V1 user functions have been validated and inlined. User-defined runtime call stacks are not introduced.

## 7. New instruction: MAKE_RECORD

Shape:

```json
{
  "op":"MAKE_RECORD",
  "type":"game.Damage",
  "fields":["critical","amount"]
}
```

The `fields` array records **constructor evaluation order** and therefore may differ from canonical descriptor field order.

Stack contract:

1. before the instruction, one value for each listed field has been pushed left-to-right in `fields` order;
2. every name occurs exactly once and the set equals the record descriptor field set;
3. each stacked value must be assignment-compatible with that field type;
4. the instruction consumes all constructor values;
5. it creates one immutable record value in canonical descriptor field order;
6. it pushes the record value with the nominal record type.

This preserves observable evaluation order when field expressions contain observations.

## 8. New instruction: LOAD_FIELD

Shape:

```json
{
  "op":"LOAD_FIELD",
  "record_type":"game.Damage",
  "field":"amount",
  "result_type":"Int"
}
```

It consumes one value of exact nominal `record_type`, validates the field against the record descriptor, and pushes that field value. `result_type` must equal the descriptor field type.

There is no dynamic field-name lookup or reflection.

## 9. New instruction: MAKE_VARIANT

Shape:

```json
{"op":"MAKE_VARIANT","type":"Option<Int>","variant":"Some","argc":1}
```

The instruction is shared by enums, Option and Result.

Descriptor rules determine allowed variants and payload arity:

```text
enum           declared variant -> argc 0
Option<T>      None             -> argc 0
Option<T>      Some             -> argc 1, payload T
Result<T,E>    Ok               -> argc 1, payload T
Result<T,E>    Err              -> argc 1, payload E
```

For `argc=1`, one assignment-compatible payload is consumed. The resulting immutable variant value is pushed with the exact declared `type`.

## 10. New instruction: TEST_VARIANT

Shape:

```json
{"op":"TEST_VARIANT","type":"Option<Int>","variant":"Some"}
```

Consumes one value of exact `type`, verifies that `variant` exists for the descriptor and pushes `Bool` indicating whether the value carries that variant.

It has no effects and does not expose payload data.

## 11. New instruction: LOAD_VARIANT_PAYLOAD

Shape:

```json
{
  "op":"LOAD_VARIANT_PAYLOAD",
  "type":"Option<Int>",
  "variant":"Some",
  "payload_type":"Int"
}
```

The descriptor must define the selected variant with exactly one payload whose type equals `payload_type`.

The instruction consumes one value of exact `type`. If its runtime variant is not the requested payload-carrying variant, execution fails closed. Otherwise the payload is pushed.

A conforming lowering invokes this only on CFG paths already guarded by `TEST_VARIANT` for the same type/variant.

## 12. Match lowering

V1 `match` is not a reflective runtime operation. It lowers into existing bounded locals/jumps plus V3 variant instructions.

Normative strategy:

1. evaluate the scrutinee once;
2. store it in a compiler local;
3. for each canonical match arm, load the scrutinee and `TEST_VARIANT`;
4. branch forward when the test is false;
5. for payload arms, reload the scrutinee, `LOAD_VARIANT_PAYLOAD`, and bind the payload to an immutable compiler local;
6. execute the arm body;
7. jump forward to the common match end when necessary.

All jumps remain forward-only. No match can introduce unbounded control flow.

Source exhaustiveness is proven before IR emission. IR validation separately ensures every emitted variant operation is type-valid; it does not need to recover the source-level exhaustiveness proof from arbitrary CFG.

## 13. Record construction lowering

A runtime record constructor evaluates field expressions in source/canonical-linked constructor order, pushes each result, then emits `MAKE_RECORD` with that same field-name order.

The constructed value itself stores fields canonically by descriptor order.

This distinction is mandatory: **evaluation order is semantic; storage order is canonical**.

## 14. Option and Result lowering

```text
Some(expr) -> expr ; MAKE_VARIANT Option<T> Some argc=1
None       -> MAKE_VARIANT Option<T> None argc=0
Ok(expr)   -> expr ; MAKE_VARIANT Result<T,E> Ok argc=1
Err(expr)  -> expr ; MAKE_VARIANT Result<T,E> Err argc=1
```

Enum values similarly use `MAKE_VARIANT <enum> <variant> argc=0`.

## 15. Capability ABI V2

IR V3 capabilities retain the explicit synchronous request model but may use any storable V3 type in parameters or as a non-Unit return type.

The runtime validates both input arguments and returned host values against the exact type table.

A host adapter must convert host-specific representations into portable V3 values at the boundary. The language runtime never exposes arbitrary host object identity.

`Unit` remains allowed only as a return type.

Asynchronous capability semantics remain deferred; V3 does not silently turn callbacks/promises/tasks into language values.

## 16. Events

Event parameter signatures may use any storable V3 value type.

`EMIT_EVENT` validates exact argument arity/types. Local event queue ordering and bounded chain semantics remain the V0.2 model.

The emitted-event receipt representation must serialize V3 values canonically.

## 17. State, locals and parameters

All state/local/parameter types must resolve to storable V3 descriptors. `Unit` is rejected.

State initial values are canonical V3 typed values validated against the declared state type before runtime construction.

Runtime mutation remains state-only at source semantics; IR compiler locals remain internal mutable stack-machine storage used to implement immutable source bindings and lowering temporaries.

## 18. Typed CFG verifier

The V3 verifier extends the V2 typed stack/definite-initialization analysis.

Each reachable instruction entry has one exact abstract state:

```text
stack: tuple[type_id]
definitely_initialized_locals: set[local_name]
```

Join points require identical stack shapes/types. Definite-local sets merge by intersection.

The verifier statically checks every new instruction against the type table.

All jumps remain forward-only and target instruction indices in `[0, instruction_count]`. Consequently arbitrary IR V3 programs remain bounded even without recovering source structure.

## 19. Runtime errors

Runtime failures are deterministic categorized failures, including:

- missing capability;
- capability argument/result type mismatch;
- division by zero;
- invalid record field access;
- invalid variant payload extraction;
- instruction stack underflow/type mismatch;
- event-chain budget exhaustion;
- checkpoint/program identity mismatch.

They are not language exceptions or user catchable control flow.

## 20. Canonical checkpoint V2

V3 requires a checkpoint revision capable of storing every V3 state value.

The intended schema is `TEV_SCRIPT_RUNTIME_CHECKPOINT_V2` and remains bound to:

- exact `program_id`;
- exact IR semantic hash;
- complete entity set;
- complete typed state set;
- canonical V3 value bytes.

Checkpoint restoration is exact-program only. It is not a migration mechanism between semantic program versions.

Checkpoint V2 implementation/certification is a required V1 runtime gate, not implicitly inherited from V0.2 checkpoint V1.

## 21. Signed updates

V3 does not weaken the certified signed-update authority model. A signed package selects an exact canonical target program/semantic identity.

However Gate-5/6/7 V0.2 update evidence does not automatically certify V3 values. Signed update, checkpoint/restart, Browser-WASM and WASI campaigns must be repeated for the V3 runtime payload before V1 promotion.

## 22. Determinism requirements

Given the same valid IR V3, initial state, capability observations and ordered invocations, conforming hosts must produce byte-identical canonical state/event receipts.

Observable behavior must not depend on:

- host object identity;
- dictionary iteration order;
- host integer width;
- floating-point coercion;
- locale/timezone;
- garbage collector timing;
- source file path;
- runtime reflection order.

## 23. Compatibility with IR V2

IR V3 is a semantic superset, not an in-place reinterpretation of V2 bytes.

A V2-to-V3 adapter may lift a valid `TEV_SCRIPT_PROGRAM_IR_V2` program into V3 by:

- adding the required primitive type table;
- retaining V2 entity/state/handler/capability/event semantics;
- preserving instruction order/operands;
- translating primitive typed values without numeric loss.

Such an adapter must have its own conformance corpus. Existing V2 semantic hashes do not equal V3 semantic hashes merely because behavior is equivalent; the schema/type-table boundary changes the canonical runtime representation.

## 24. Explicit non-goals

IR V3 does not add:

- recursion or runtime user-function calls;
- unbounded loops/backward jumps;
- heap object identity;
- mutable records;
- references/pointers;
- reflection;
- general collections/maps;
- payload-carrying user enums beyond Option/Result;
- exceptions as control flow;
- async/await;
- threads or implicit concurrency;
- dynamic capability acquisition;
- runtime source compilation.

## 25. Promotion gates

IR V3 can be called frozen only after:

1. Draft 2020-12 schema closure;
2. Python structural + typed CFG validator PASS;
3. complete positive and negative instruction/value corpus;
4. Python reference runtime PASS;
5. V2-to-V3 compatibility corpus PASS;
6. V1 linked-program -> V3 lowering PASS;
7. exact V3 value canonicalization PASS;
8. checkpoint V2 PASS;
9. JavaScript and C# byte-parity PASS;
10. Browser-WASM and WASI AOT/runtime parity PASS;
11. signed-update replay/checkpoint campaigns repeated for V3;
12. V0.2 regression remains byte-identical;
13. exact clean commit/content-identity certification PASS.

Until then `TEV_SCRIPT_PROGRAM_IR_V3` is a design/implementation candidate and `LANGUAGE_STABLE=NO` remains mandatory.
