# TEV Script IR V3 portable value model

Status: **normative V1 / IR V3 candidate V1**.

This document defines the runtime value domain required to execute non-erasable TEV Script V1 programs. It extends the certified V0.2 portable value model without modifying IR V2 or its historical runtime behavior.

## 1. Design constraints

IR V3 runtime values MUST remain:

- finite;
- immutable from the language perspective;
- structurally serializable;
- independent of host object identity;
- independent of pointer/address identity;
- independent of reflection;
- independent of hash-map iteration order;
- deterministic under equality and canonical encoding;
- recursively bounded by the V1 type/value budgets.

IR V3 does not introduce a heap language, references, object identity, cyclic values, garbage-collector-visible semantics or host-native object handles.

## 2. Canonical type ids

Every runtime slot, state, parameter, local, capability argument/result and event argument has one canonical type id.

The grammar is:

```text
TypeId     := Primitive
            | Nominal
            | "Option<" TypeId ">"
            | "Result<" TypeId "," TypeId ">"

Primitive  := "Bool" | "Int" | "Rat" | "Text" | "Vec2" | "Vec3" | "Unit"
Nominal    := QualifiedId
QualifiedId:= IDENT ("." IDENT)+
```

`Unit` is a signature-only return type and is not a storable runtime value. It cannot appear inside `Option` or `Result`.

Type-id nesting is bounded by the V1 normative type-nesting budget.

## 3. Runtime type registry

Every IR V3 program carries a closed nominal type registry containing all runtime-reachable record and enum declarations.

### 3.1 Record descriptor

```json
{
  "kind": "record",
  "type_id": "game.Damage",
  "fields": [
    {"name": "amount", "type": "Int"},
    {"name": "critical", "type": "Bool"}
  ]
}
```

Rules:

- `type_id` is nominal identity;
- fields are unique;
- fields are stored in lexical field-name order in canonical IR;
- each field type is a storable canonical type id;
- record dependency graphs are acyclic;
- runtime values contain exactly the declared field set.

### 3.2 Enum descriptor

```json
{
  "kind": "enum",
  "type_id": "game.DamageKind",
  "variants": ["Fire", "Ice", "Physical"]
}
```

Rules:

- variants are payload-free in V1.0;
- variants are unique and lexically sorted in canonical IR;
- no numeric ordinal is semantic;
- host enum representations are not part of the language contract.

`Option<T>` and `Result<T,E>` are built-in closed variant families and do not require registry entries.

## 4. Abstract runtime values

The semantic runtime value domain is:

```text
BoolValue
IntValue
RatValue
TextValue
Vec2Value
Vec3Value
RecordValue(type_id, fields)
VariantValue(type_id, variant, optional_payload)
```

`RecordValue` and `VariantValue` are conceptual immutable values. A host implementation may use a class, struct, tuple or object internally, but host representation is not observable and must not introduce alias-sensitive behavior.

## 5. Canonical external encoding

The following encoding is used whenever an IR V3 value enters canonical JSON: program constants, checkpoints, conformance receipts and other portable evidence.

The expected type is always known from the surrounding typed contract. The encoded value therefore does not redundantly carry a type id.

### 5.1 Primitive values

IR V2 encodings remain unchanged:

```json
true
{"$int":"42"}
{"$rat":["1","10"]}
"text"
[
  {"$rat":["1","1"]},
  {"$rat":["0","1"]}
]
```

All integer/rational text remains canonical and normalized. `-0` is forbidden.

### 5.2 Record value

For expected type `game.Damage`:

```json
{
  "$record": {
    "amount": {"$int":"12"},
    "critical": false
  }
}
```

Rules:

- the object contains exactly the declared field set;
- each field value is recursively encoded using the descriptor field type;
- JSON canonicalization sorts object keys, so source field order cannot affect bytes;
- duplicate JSON keys are rejected by the strict JSON boundary before value validation.

### 5.3 Variant value

All closed sum values use one representation:

```json
{"$variant":{"tag":"Fire"}}
{"$variant":{"tag":"None"}}
{"$variant":{"tag":"Some","value":{"$int":"3"}}}
{"$variant":{"tag":"Ok","value":{"$int":"3"}}}
{"$variant":{"tag":"Err","value":"bad"}}
```

Interpretation is determined by the expected type:

- nominal enum: tag must be one declared variant and no `value` is allowed;
- `Option<T>`: `None` has no payload; `Some` has exactly one payload of `T`;
- `Result<T,E>`: `Ok` has one payload of `T`; `Err` has one payload of `E`.

This is a typed algebraic value, not an exception, nullable host reference or dictionary protocol.

## 6. Equality

`==` / `!=` are deterministic and type-directed.

- primitives retain V0.2 equality;
- `Int` and `Rat` may compare after exact `Int -> Rat` widening;
- records require identical nominal type id and then compare all fields recursively;
- enums require identical nominal type id and identical variant;
- `Option<T>` requires the same canonical `Option<T>` type and matching tag; `Some` payloads compare recursively;
- `Result<T,E>` requires the same canonical result type and matching tag; payloads compare recursively.

No reference identity participates.

Ordering operators remain numeric-only in V1.0.

## 7. Capability ABI

Capabilities may use any V3 signature type allowed by source semantics.

The host adapter receives/returns the semantic value represented by the declared TEV type. Host-specific objects may be used internally by an adapter, but before a value becomes visible to TEV execution it must be validated/coerced against the complete declared type recursively.

A malformed record field set, unknown enum variant, wrong sum tag, wrong payload type, missing payload or unexpected payload fails closed as a capability return coercion error.

Capability input/output cannot smuggle arbitrary host object references into TEV state.

## 8. Event ABI

Event parameters use the same V3 value domain. An emitted event is recorded with its canonical event id, declared parameter type list and recursively typed values.

Handled local events are requeued under the same bounded FIFO event-chain semantics as IR V2.

## 9. Checkpoint representation

IR V3 requires checkpoint schema `TEV_SCRIPT_RUNTIME_CHECKPOINT_V2`.

A V2 checkpoint is bound to:

- runtime checkpoint schema;
- program id;
- IR schema;
- program semantic hash;
- source linked semantic hash;
- complete entity set;
- complete typed state set.

Every state value is encoded recursively using this value model.

Checkpoint restore remains **exact only**: same IR schema, same program id, same program semantic hash, same source linked semantic hash and exact state type set. Checkpoints are not a migration mechanism.

## 10. Canonicality rules

Canonical value bytes must not depend on:

- host class/struct layout;
- pointer identity;
- dictionary insertion order;
- locale;
- timezone;
- process architecture;
- integer machine width;
- JavaScript `Number` representation;
- reflection metadata order.

All nested records and variants are recursively canonicalized under the repository canonical JSON profile.

## 11. Fail-closed invalid values

The runtime rejects at least:

- unknown nominal type ids;
- recursive/invalid registry descriptors;
- `Unit` used as a stored value;
- record values with missing/extra fields;
- record field type mismatch;
- enum value with unknown variant;
- enum value carrying a payload;
- `Option` unknown tag;
- `None` carrying a payload;
- `Some` without a payload;
- `Result` unknown tag;
- `Ok`/`Err` without a payload;
- payload type mismatch;
- noncanonical integer/rational encoding;
- type nesting beyond the normative budget.

No invalid value is repaired, truncated, default-filled or coerced through text/JSON blobs.
