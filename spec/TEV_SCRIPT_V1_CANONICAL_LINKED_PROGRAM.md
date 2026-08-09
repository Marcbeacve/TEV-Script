# TEV Script V1 canonical linked-program contract

Status: **normative candidate V1**.

This document fixes the canonical semantic representation produced after V1 parsing, linking and static validation and before any runtime-IR lowering.

The artifact schema is `TEV_SCRIPT_LINKED_PROGRAM_V1` and its structural shape is constrained by `schemas/tev_script_linked_program_v1.schema.json`.

## 1. Purpose

A V1 source program can contain syntax that is semantically irrelevant to runtime behavior:

- filesystem paths;
- input source enumeration order;
- parameter/local binding spellings;
- record field declaration order;
- entity state declaration order;
- alternative constant expressions with the same exact value.

Those differences MUST NOT leak into the canonical linked-program semantic hash.

Conversely, explicitly semantic order and identity MUST remain visible:

- behavior `use` order;
- executable statement order;
- expression operand order;
- module/declaration identity;
- event ids;
- state ids;
- record/enum nominal identity;
- capability contracts;
- pure-function computation.

## 2. Hash boundary

The canonical semantic object contains:

```text
schema
language_version
program_id
modules
capabilities
records
enums
functions
behaviors
entities
```

`semantic_hash` is computed as SHA-256 over the repository canonical JSON profile applied to that object **before** adding `semantic_hash`.

No debug/source path, timestamp, filesystem identity, process environment or host-specific object is inside the hash boundary.

After hashing, the final transport object adds:

```text
semantic_hash = lowercase SHA-256 hex
```

## 3. Compilation units

The root script itself is represented by `program_id` plus root declarations/entities. It is not duplicated in the `modules` array.

Reachable modules are represented exactly once and sorted lexically by `module_id`.

For each module:

- `version` is semantic;
- `imports` sort lexically because import source order is not semantic;
- exported declarations sort by `(namespace, semantic_id)`;
- private declarations remain represented in their declaration arrays but not in the module export set.

Unreachable supplied modules are excluded completely from the canonical linked program.

## 4. Declaration identity and ordering

Canonical arrays are ordered as follows:

- capabilities: global `capability_id`;
- records: nominal `type_id`;
- enums: nominal `type_id`;
- functions: semantic `function_id`;
- behaviors: semantic `behavior_id`;
- entities: local `entity_id`.

Record fields sort lexically by field name. Enum variants sort lexically by variant name because V1 defines no ordinal semantics.

Behavior `uses` preserve explicit source order because composition order is semantic.

Entity `uses` preserve explicit source order for the same reason.

Local behavior/entity state declarations sort by state name because declaration order has no V1 execution semantics.

Local handlers sort by event id because different event declarations do not execute by declaration order. The executable statement list inside each handler is never sorted.

## 5. Capability declarations

Capabilities have global ids and may be declared identically in more than one reachable unit.

The canonical capability array contains one entry per unique global capability contract.

For repeated identical declarations:

- parameter types, return type and kind must already be identical;
- one deterministic representative `declared_in` is chosen by lexical owner id;
- `exported` is true when at least one reachable declaration exports that capability;
- module export sets still record which modules actually export it.

Conflicting repeated declarations fail before canonicalization.

Built-in portable capabilities are implicit in the language/profile and are not duplicated in the top-level custom capability declaration array. Their use remains explicit in handler/entity capability summaries.

## 6. Type normalization

Every declared/reference type in the linked program uses its canonical type id.

Examples:

```text
Int
Rat
Root.Damage
math.Point
Option<Int>
Result<Root.Value,Text>
```

Whitespace, source qualification choices and import spelling do not survive type normalization.

## 7. State initializer normalization

Every state initializer has already passed constant evaluation.

The canonical linked program stores the **exact constant value**, not the source expression that produced it.

Therefore semantically equal constant initializers converge. Examples:

```text
1 + 1
2
```

both normalize to canonical `Int(2)` when the declared state type is `Int`.

Numeric widening is applied according to the declared state type before serialization; an `Int` constant assigned to `Rat` is represented as the exact rational value.

Record constant fields serialize in canonical record-field order. Enum/Option/Result constants use canonical nominal/constructed type ids and explicit constructor tags.

Vectors serialize as canonical pure `vec2`/`vec3` constructor expressions with exact rational components because the linked schema has one expression representation rather than a second vector-only literal encoding.

## 8. Alpha normalization

Source spelling of immutable lexical bindings is not semantic.

The linked program alpha-normalizes:

- pure-function parameters;
- event-handler parameters;
- `let` bindings;
- `for` variables;
- `Some`/`Ok`/`Err` match bindings.

Function parameters use deterministic `_pN` names in parameter order.

Handler parameters use deterministic `_pN` names while avoiding collisions with visible state ids.

Handler lexical bindings use deterministic `_lN` names allocated by semantic traversal order while avoiding visible state and parameter ids.

Every expression reference is rewritten to the corresponding canonical binding name.

State names are **not** alpha-normalized because state identity is semantic and externally observable through the runtime state model.

Event ids and declaration ids are likewise not alpha-normalized.

## 9. Expressions

Every expression in the linked program is typed and uses canonical symbol/type ids.

Groups/parentheses do not survive as semantic nodes.

Dotted source value names are normalized into a base canonical lexical/state name followed by explicit typed record-field nodes.

Pure function calls contain:

```text
callable_kind = pure_function
callable_id   = canonical function id
```

Observation capability expressions contain:

```text
callable_kind = observation_capability
callable_id   = global capability id
```

Effect capabilities are never expression nodes.

Implicit `Int -> Rat` widening remains a semantic typing rule and need not create a separate linked-expression conversion node. Downstream IR lowering must make the conversion explicit when its target IR requires it.

Record constructor field **expression order is preserved** because field expressions may contain observations. Record declaration field order is nonsemantic; constructor evaluation order is executable expression order.

Boolean `and/or` operand order is preserved and retains V1 short-circuit semantics.

## 10. Statement normalization

The linked program preserves executable statement order.

Surface sugar is normalized:

```text
log expr;      -> capability call debug.log(expr)
move expr;     -> capability call motion.move2d(expr)
animate expr;  -> capability call animation.play(expr)
```

This normalization changes syntax but not semantics and prevents downstream IR implementations from needing a second copy of sugar rules.

Assignment continues to target semantic state ids.

`for` retains exact signed lower/upper constants plus an alpha-normalized loop binding. Whether a target IR later unrolls it is a lowering decision.

`match` retains typed canonical patterns and alpha-normalized payload bindings. Whether a target IR has a native match operation is a lowering decision.

## 11. Behavior representation

Behavior declarations remain first-class compile-time semantic units in the linked program rather than being erased immediately.

Each behavior stores:

- semantic behavior id;
- owner module/root;
- export flag;
- explicit resolved `uses` in semantic order;
- local states only;
- local handlers only.

Entity declarations similarly store explicit resolved behavior uses plus local states/handlers.

This keeps one canonical source-semantic authority from which different target IRs can perform the same deterministic expansion.

The entity also stores the fully composed capability requirement set as a derived semantic summary because host authority checking depends on the complete requirement surface.

## 12. Handler capability summaries

Each canonical local handler contains the capabilities directly required by that fragment after expression/static analysis.

An entity's top-level capability summary is the union over the fully composed behavior/entity handler set.

Capabilities sort lexically because the requirement summary is set-like. This does not alter executable statement order.

## 13. Determinism counterfactuals

The canonical linked bytes and semantic hash MUST remain identical when only these change:

- source file path/location;
- source input enumeration order;
- parameter/local/loop/match-binding spelling;
- nonsemantic declaration ordering such as record field or state declaration order;
- constant source expression syntax that evaluates to the same exact typed value.

They MUST differ when a semantic element changes, including:

- behavior use order;
- statement order;
- pure-function operation/result semantics;
- state identity/type/value;
- event identity/signature;
- capability signature/kind;
- record or enum nominal/type content;
- executable expression operand order.

## 14. Downstream rule

`TEV_SCRIPT_LINKED_PROGRAM_V1` is the single semantic source for both:

- the erasable V1 -> `TEV_SCRIPT_PROGRAM_IR_V2` profile; and
- the future non-erasable V1 -> IR V3 profile.

A target lowerer may erase abstractions only when it proves the target representation preserves this linked semantic program. It may not re-resolve source files, imports or names independently using target-host behavior.
