# TEV Script IR V3 portable value model

Status: **normative V1 / IR V3 candidate V2**.

This document is a focused companion to `spec/TEV_SCRIPT_IR_V3.md`. The master IR V3 document defines the complete runtime representation; this file freezes the value/type boundary used by validators, runtimes, capability adapters, checkpoints and conformance receipts.

IR V3 extends the certified V0.2 value model without modifying IR V2 or reinterpreting its historical bytes.

## 1. Core invariants

Every admitted V3 value is finite, immutable from TEV semantics, recursively typed, structurally serializable and independent of host identity. TEV values never expose pointers, references, reflection objects, mutable host dictionaries, tasks/promises or arbitrary native instances.

Equality and canonical serialization cannot depend on locale, timezone, process architecture, garbage-collector timing, hash-map iteration order or source path.

`Unit` is never a runtime value. It is allowed only as a capability return type.

## 2. Closed type table

Every V3 program carries `types`, a closed canonical table sorted by `type_id`.

The table contains exactly the runtime type descriptors needed by the program plus the seven portable base descriptors:

```text
Bool Int Rat Text Vec2 Vec3 Unit
```

Descriptor forms are:

```json
{"type_id":"Int","kind":"primitive"}
{"type_id":"Unit","kind":"unit"}
{"type_id":"game.Damage","kind":"record","fields":[...]}
{"type_id":"game.Kind","kind":"enum","variants":[...]}
{"type_id":"Option<Int>","kind":"option","argument":"Int"}
{"type_id":"Result<Int,Text>","kind":"result","ok_type":"Int","err_type":"Text"}
```

The runtime does not re-derive constructed-type structure from source syntax. The descriptor table is authoritative and must agree exactly with every canonical type id.

### 2.1 Primitive and Unit descriptors

The six storable primitive descriptors are `primitive`; `Unit` is `unit`. They occur exactly once and cannot be shadowed by nominal types.

### 2.2 Record descriptors

Record `type_id` is nominal identity. Fields are unique and stored lexically by field name in the canonical table. Field types are storable V3 type ids.

Record dependency graphs are acyclic, including dependencies through Option and Result. The validator must prove this iteratively within the V1 nesting/resource budgets rather than relying on the host call stack.

### 2.3 Enum descriptors

V1 nominal enums are payload-free. Variants are unique, nonempty and lexically sorted. There is no semantic ordinal or host enum backing value.

### 2.4 Option and Result descriptors

`Option<T>` has exactly `None` and `Some(T)`.

`Result<T,E>` has exactly `Ok(T)` and `Err(E)`.

The descriptor canonical id must equal its recursively canonical arguments. `Unit` cannot appear as an argument.

## 3. Primitive value encoding

IR V3 deliberately preserves the V0.2 canonical primitive encodings.

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

`Vec2` and `Vec3` therefore remain direct arrays of canonical rational values. V3 does **not** introduce `$vec2` or `$vec3` wrappers.

Integer text is canonical decimal; `-0` is invalid. Rational numerator/denominator are normalized with positive nonzero denominator.

## 4. Composite value encoding

Unlike primitive values, V3 composite encodings intentionally repeat their exact canonical `type`. This redundancy is normative: it allows capability boundaries, checkpoint readers and independent hosts to reject a value whose claimed runtime type conflicts with the typed slot that contains it.

### 4.1 Record

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

The encoded type must be the exact record descriptor id. The field list must equal the descriptor field set exactly and use canonical descriptor field order. Every field value is recursively validated using the field's declared type.

Constructor **evaluation order is not this storage order**. Runtime `MAKE_RECORD.fields` records evaluation order separately; after construction the immutable value is stored canonically.

### 4.2 Enum

```json
{"$enum":{"type":"game.Kind","variant":"Fire"}}
```

The type must resolve to an enum descriptor and the variant must exist. No payload is allowed.

### 4.3 Option

```json
{"$option":{"type":"Option<Int>","variant":"None"}}
{"$option":{"type":"Option<Int>","variant":"Some","value":{"$int":"7"}}}
```

`None` has no value member. `Some` has exactly one recursively validated value of the descriptor argument type.

### 4.4 Result

```json
{"$result":{"type":"Result<Int,Text>","variant":"Ok","value":{"$int":"7"}}}
{"$result":{"type":"Result<Int,Text>","variant":"Err","value":"invalid"}}
```

`Ok` and `Err` always carry exactly one payload of the corresponding descriptor type.

## 5. Runtime semantic representation

A host may internally represent composite values using frozen classes, structs or tuples, but the following semantic facts are observable and therefore mandatory:

- exact canonical type id;
- record field names and recursively typed values;
- enum/Option/Result variant;
- payload only where defined;
- immutable value semantics;
- no reference-identity equality.

A host representation must not expose mutation through aliasing after a value has entered TEV state.

## 6. Equality

Equality is type-directed.

- primitive equality remains V0.2-compatible;
- numeric `Int`/`Rat` comparison may use exact widening;
- records require identical nominal type id, then recursively equal canonical fields;
- enums require identical nominal type id and variant;
- Option/Result require identical constructed type id and variant, then recursively equal payload where present.

Different nominal or constructed type ids are not structurally coerced.

Ordering remains numeric-only.

## 7. Capability boundary

A V3 capability signature may contain any storable V3 parameter type and any storable V3 or `Unit` return type.

Before a host-provided return enters TEV execution, the adapter/runtime must recursively coerce and validate it against the exact declared type. A malformed host value fails closed.

Invalid examples include missing/extra record fields, wrong record nominal type, unknown enum variant, `None` with payload, `Some` without payload, wrong Result arm payload, nested `Unit`, noncanonical integer/rational text or arbitrary host objects.

The capability boundary may provide ergonomic host conversion APIs, but those APIs cannot change TEV semantic values.

## 8. Event boundary

Events use the same value domain. Every emitted argument is validated against the exact event signature and then recorded canonically. If a local handler exists, the same semantic values are requeued under the bounded FIFO event model.

## 9. Checkpoint V2

`TEV_SCRIPT_RUNTIME_CHECKPOINT_V2` must encode state using exactly this V3 value model. The checkpoint binds both IR semantic identity and the originating linked V1 semantic identity.

Restore is exact-program only; checkpoints do not migrate state across semantic program versions.

## 10. Value depth and resource safety

The runtime boundary carries `maximum_value_nesting`, never exceeding the V1 type-nesting budget of 128.

Recursive value validation/encoding may be implemented iteratively; a conforming host must report TEV budget/type diagnostics rather than overflowing a host recursion limit first.

Record field count, type count, state count, arguments and other structural budgets remain those frozen by the V1/IR V3 contracts.

## 11. Fail-closed matrix

A value is rejected before use when any of these is false:

```text
expected type exists in closed type table
encoded composite type equals expected type
value form matches descriptor kind
record field set/order is exact
every nested value validates recursively
variant exists
variant payload arity is exact
payload type is exact/valid
Unit is absent from value positions
numeric text is canonical
value nesting stays inside boundary
```

No invalid value is repaired, truncated, default-filled, JSON-stringified or converted into an opaque host object.

## 12. Compatibility rule

IR V2 primitive value bytes remain valid primitive representations in IR V3. A V2-to-V3 lift therefore changes the program envelope/type table and semantic hash, but it must not introduce numeric or primitive-value loss.

This compatibility rule is a separate conformance gate and does not make V2 and V3 semantic hashes interchangeable.
