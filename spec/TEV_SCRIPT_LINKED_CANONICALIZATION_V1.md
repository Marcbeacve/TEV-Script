# TEV Script V1 linked-program canonicalization

Status: **normative V1 candidate V1**.

This document defines the canonical semantic representation of an accepted TEV Script V1 source set as `TEV_SCRIPT_LINKED_PROGRAM_V1`. It specializes the deterministic link model in `spec/TEV_SCRIPT_V1_LINK_MODEL.md`, uses the byte profile in `spec/CANONICAL_JSON_PROFILE_V1.md`, and is constrained by `schemas/tev_script_linked_program_v1.schema.json`.

It does not introduce a second linker, type system, evaluator, or runtime semantics. Its purpose is to make the already implemented source-semantic normalization rules explicit enough that independent frontends can reproduce the same linked-program bytes and `semantic_hash`.

## 1. Canonicalization boundary

Canonicalization runs only after all of these have succeeded:

1. V1 parsing;
2. deterministic multi-file linking;
3. visibility/name resolution;
4. nominal and constructed type resolution;
5. static semantic checking;
6. behavior composition validation;
7. constant-state-initializer validation/evaluation.

Rejected source has no canonical linked program.

The canonicalization input is therefore the accepted semantic program, not raw tokens, source paths, filesystem metadata, parser object identity, host dictionary order, or diagnostic spans.

The canonical linked artifact is **source semantic authority**. It is not executable runtime IR. Lowering to IR V2 or IR V3 is a separate, evidence-bound transformation.

## 2. Root object and semantic hash

The semantic object before hashing has exactly these top-level fields:

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

with:

```text
schema           = TEV_SCRIPT_LINKED_PROGRAM_V1
language_version = 1.0.0
```

Let `S` be this semantic object.

The linked semantic identity is:

```text
semantic_hash = SHA256(TEV_CANONICAL_JSON_V1(S))
```

The emitted linked artifact is then `S` plus the field:

```text
semantic_hash
```

The `semantic_hash` field is therefore **not** included in its own hash preimage.

Debug paths, source locations, timestamps, host identifiers and intermediate analysis hashes are not members of `S` and cannot affect linked semantic identity.

The final artifact bytes are `TEV_CANONICAL_JSON_V1` applied to the complete object containing `semantic_hash`. The in-memory canonical text has no required trailing line feed; artifact writers may persist the canonical document followed by exactly one LF according to the repository artifact policy.

## 3. Reachable closure

Only the root script and modules in its validated transitive import closure contribute to the linked semantic program.

A supplied but unreachable module is build/debug input only. Adding, removing, renaming, relocating or editing an unreachable supplied module must not change canonical linked bytes.

The root program id and every reachable module id have already passed the collision and uniqueness rules of `TEV_SCRIPT_V1_LINK_MODEL.md` before canonicalization begins.

## 4. Canonical collection ordering

Where source order has no V1 semantic meaning, canonicalization removes it by sorting on semantic identity.

### 4.1 Modules

`modules` is sorted lexically by `module_id`.

For each module:

- `imports` is sorted lexically by declared `module_id`;
- `exports` contains source-origin exported symbols only;
- `exports` is sorted by `(namespace, semantic_id)`.

Import declaration order is not semantic in V1.

### 4.2 Records

`records` is sorted lexically by nominal `type_id`.

Record fields are sorted lexically by field name before linked-program emission. Record declaration field order therefore does not contribute to semantic identity.

A record keeps its nominal `type_id`, `declared_in`, `exported` witness and canonical field type ids.

### 4.3 Enums

`enums` is sorted lexically by nominal `type_id`.

Enum variants are sorted lexically by variant name. Variant declaration order has no V1 runtime meaning in the V1 profile; variants have no ordinal semantic value.

### 4.4 Functions

`functions` is sorted lexically by semantic `function_id`.

The function call summary is a sorted set of semantic callable ids, as produced by static semantics. Source spelling of local parameter names does not survive canonicalization.

### 4.5 Behaviors

`behaviors` is sorted lexically by semantic `behavior_id`.

Within each behavior:

- states are sorted lexically by state name;
- local handler entries are sorted lexically by `event_id`;
- capability summaries are sorted lexically;
- the explicit `uses` sequence is **not sorted** because behavior-use order is semantic.

### 4.6 Entities

`entities` is sorted lexically by `entity_id`.

Within each entity:

- entity-local states are sorted lexically by state name;
- entity-local handler entries are sorted lexically by `event_id`;
- capability summaries are sorted lexically;
- the explicit `uses` sequence is **not sorted** because behavior-use order is semantic.

The linked artifact stores behavior declarations and entity-local declarations separately. Runtime lowering later expands behaviors according to the already validated composition order.

## 5. Capability-contract canonicalization

Capability ids are global semantic ids.

All reachable source declarations of the same capability id have already been required to resolve to one exact ABI:

```text
(capability_id, parameter type ids, return type id, kind)
```

Conflicting repeated declarations fail before canonical emission.

Identical repeated declarations collapse to one linked capability contract.

For the collapsed contract:

- `capability_id` is the global semantic id;
- `parameters`, `return_type`, and `kind` are the resolved ABI;
- `declared_in` is the lexically smallest declaring unit id among equivalent declarations;
- `exported` is true iff at least one equivalent source declaration is exported.

`capabilities` is sorted lexically by `capability_id`.

This deterministic owner witness is representational metadata inside the semantic artifact; it does not depend on source-file discovery order.

## 6. Canonical type identities

Primitive ids retain their portable names.

Nominal source types retain the identities established by linking:

```text
<module_id>.<local_type_name>
<program_id>.<local_type_name>
```

Constructed built-ins recursively include canonical argument identities:

```text
Option<T>
Result<T,E>
```

Canonicalization never substitutes structural aliases for nominal records/enums and never uses filesystem paths to construct type identity.

## 7. Constant-state normal forms

Every state initializer is evaluated by the bounded V1 constant evaluator before linked-program emission.

The linked program stores the **evaluated semantic value**, not the original initializer syntax.

Consequences include:

```text
1 + 1              ==canonical==> 2
0.1 + 0.2          ==canonical==> 3/10
```

Rationals are reduced exact fractions with a positive denominator.

Record constant values emit fields in canonical record-field order.

Enum, `Option`, and `Result` constants preserve nominal/constructed type identity and canonical constructor/value shape.

Therefore two accepted source initializers that compute the same typed constant value must emit identical linked initializer structure.

## 8. Alpha normalization

Source spelling of non-semantic lexical bindings is erased.

### 8.1 Function parameters

Function parameters are renamed deterministically by position:

```text
_p0, _p1, ...
```

References in the canonical function expression point to those canonical ids.

### 8.2 Handler parameters

Handler parameters are renamed deterministically by position using `_pN` names that avoid collision with visible state names.

### 8.3 Local bindings

Lexical `let`, bounded-loop and match-payload bindings receive deterministic `_lN` names allocated in semantic traversal order, while avoiding already reserved canonical names.

Renaming a source parameter, local variable, loop variable, `Some`/`Ok`/`Err` payload binding, or equivalent non-semantic binding must not change canonical linked bytes.

State names, event ids, entity ids, behavior ids, nominal type ids, function ids, capability ids and record field names are semantic names and are not alpha-erased.

V1 shadowing has already been rejected before this normalization; canonicalization never resolves ambiguity by renaming invalid source.

## 9. Expressions

Every canonical expression carries enough resolved information to avoid repeating source name resolution at runtime lowering.

Canonical expression nodes preserve:

- resolved result type id;
- operator identity;
- operand order;
- semantic callable id and callable kind;
- nominal enum/record type id;
- record field identity;
- algebraic constructor identity.

Grouping-only source syntax does not survive as a semantic node.

For calls, argument order is semantic and is preserved.

For binary expressions, left/right operand order is semantic and is preserved even where an algebraic rewrite might produce an equivalent mathematical value. Canonicalization is not an optimizing theorem prover.

## 10. Statements and executable order

Executable statement order is semantic and is preserved exactly after syntax sugar normalization.

The following source conveniences canonicalize to ordinary explicit capability calls:

```text
log ...      -> debug.log
move ...     -> motion.move2d
animate ...  -> animation.play
```

This removes syntax-spelling differences while preserving the same capability semantics.

`if` branch body order, bounded-`for` body order and `match` arm body order are preserved.

Canonicalization does not reorder statements for optimization.

## 11. Match normalization

A canonical match stores:

- the canonical target expression;
- canonical pattern constructor/type identity;
- alpha-normalized payload binding where present;
- arm bodies in the statically accepted semantic arm sequence.

The static semantic phase has already established exhaustiveness, uniqueness and constructor compatibility.

Pattern-binding source names do not contribute to identity; the selected constructor/type and executable arm semantics do.

## 12. Behavior composition order

Behavior-use order is intentionally semantic.

The source order of explicit `use` declarations survives in the linked behavior/entity `uses` sequence as resolved semantic behavior ids.

The validated behavior model defines dependency-first fragment expansion while preserving explicit use order. Lowering must use that semantic sequence and may not sort it.

Therefore changing:

```text
use A; use B;
```

to:

```text
use B; use A;
```

may change execution order and **must** change semantic identity when the resulting observable program differs.

## 13. Non-semantic perturbations

For the same accepted V1 program meaning, all conforming implementations must produce identical linked canonical bytes and hash when only any of these change:

- physical source paths;
- input source-set enumeration order;
- filesystem directory enumeration order;
- path separators;
- process locale or timezone;
- host map/dictionary iteration order;
- parameter/local/loop/match-binding spelling;
- record field declaration order;
- state declaration order;
- import declaration order;
- equivalent constant-expression spelling;
- presence or contents of unreachable supplied modules.

## 14. Semantic perturbations

Canonical identity must change when a change affects represented V1 semantics, including at least:

- program/module/nominal declaration identity;
- resolved type identity;
- function operation or callable identity;
- capability ABI or observation/effect kind;
- state name/type/value;
- executable statement order;
- expression operand order where represented;
- event id/signature;
- behavior-use order;
- constructor/variant selection;
- module version or exported semantic surface.

This list is not permission to ignore other semantic changes.

## 15. Schema and byte-budget closure

The complete linked object including `semantic_hash` must satisfy:

```text
schemas/tev_script_linked_program_v1.schema.json
```

and its canonical UTF-8 representation must not exceed the normative `MAX_LINKED_CANONICAL_JSON_BYTES` V1 budget.

Budget failure is a compile-time failure; implementations must not truncate canonical semantic data.

## 16. Conformance obligations

The following repository assets are normative executable evidence for this contract:

```text
conformance/v1-linked-program-cases.json
tests/test_v1_linked_program.py
tests/test_v1_linked_program_schema.py
tests/test_v1_linked_program_schema_negative.py
```

The conformance campaign must demonstrate both directions:

1. **equivalence lock** — known non-semantic source differences produce identical `canonical_json` and `semantic_hash`;
2. **difference lock** — known semantic differences produce different `semantic_hash` values.

The campaign also verifies invariance under source relocation/input permutation, constant normalization, alpha normalization, repeated equivalent capability collapse and exclusion of unreachable modules.

A future compiler implementation may use a different internal AST, linker data structure, algorithm or host language only if it reproduces this canonical artifact contract exactly.

## 17. Relationship to runtime lowering

`TEV_SCRIPT_LINKED_PROGRAM_V1` is the canonical source-semantic boundary.

IR V2 and IR V3 lowerers consume this boundary and bind their output to its `semantic_hash`. They must not repeat source-level import resolution or reinterpret source paths.

A lowering receipt proves the relation between one linked semantic identity and one runtime-IR identity. It does not alter linked canonicalization.

## 18. Change control

Changing any rule in this document that can change linked canonical bytes for an already accepted V1 program is a semantic-format change and must not be presented as a transparent refactor.

Such a change requires explicit versioning/admission of the affected canonical contract and re-certification of dependent lowering/runtime evidence.

Documentation-only clarification is permitted only when it preserves the already implemented and conformance-locked byte semantics.
