# TEV Script V1 deterministic link model

Status: **normative V1 candidate**. This document defines the semantic input model between parsing and runtime-IR lowering. It is deliberately separate from `TEV_SCRIPT_PROGRAM_IR_V2`.

## 1. Purpose

V1 introduces multiple source units, visibility, user functions, named value types and behavior composition. Those features cannot be left to filesystem order or host-language lookup rules. The linker therefore produces one deterministic `TEV_SCRIPT_LINKED_PROGRAM_V1` value before runtime lowering.

The linked program is a semantic artifact. Source paths, timestamps, directory enumeration order and host-specific file identities are debug/build data and are excluded from its semantic hash.

## 2. Link input

A link invocation receives an explicit finite set of decoded source units. Module discovery is not performed by the language runtime.

Each input unit must parse as exactly one of:

- one `script` root; or
- one `module` unit.

The linker requires exactly one script root. Every module is keyed by its declared `module_id`, never by a path-derived id.

The V1 core profile performs no network lookup, package-registry lookup, implicit parent-directory lookup, environment-variable lookup or current-working-directory lookup.

## 3. Version rule

The V1 target source header is `version "1.0.0"`.

A V1-capable frontend must continue to accept a standalone valid V0.2 root with `version "0.2.0"` through the certified V0.2 compilation path. V1-only declarations or imports are not permitted under a V0.2 header.

A V1 linked program has a `1.0.0` root and every reachable module must also declare `1.0.0`. Mixed V1 module versions fail closed in the initial V1 profile; no semver-range resolution is part of the language.

## 4. Import graph

For every unit, imports form directed edges from the importing unit to the declared module id.

The graph is validated before name resolution:

1. every imported module id exists exactly once;
2. duplicate module ids fail closed;
3. duplicate import statements inside one unit fail closed;
4. the import graph is acyclic;
5. unreachable supplied modules are ignored by the semantic linked program and may be reported as build diagnostics;
6. traversal order is lexicographic by Unicode code point over normalized module ids, never filesystem order.

The root plus its transitive import closure defines the linked module set.

## 5. Identifier model

Identifiers are ASCII and case-sensitive. Qualified ids use `.` as the segment separator. Empty segments are impossible by grammar.

The following semantic namespaces are distinct:

- **type namespace**: records and enums;
- **function namespace**: pure user functions and pure built-ins;
- **behavior namespace**: behaviors;
- **capability namespace**: capability ids;
- **entity namespace**: root entities.

Within one namespace and one unit, duplicate declarations fail closed. The language does not use host-language overload resolution for user-defined symbols.

## 6. Export and visibility

Module top-level declarations are private by default. `export` makes the declaration visible to importing units. Export does not recursively re-export any imported declaration.

The script root has no package export surface in V1.0. `export` is therefore syntactically valid only on module top-level declarations.

Capability declarations retain their explicitly declared qualified capability id. Export controls whether another unit may rely on that declaration; it does not rewrite the capability id.

## 7. Name resolution

Resolution is context-specific by namespace.

For a reference in unit `U`:

1. If the reference is syntactically qualified and its leading segments name a directly imported module, resolve only against exported declarations of that module.
2. Otherwise try a declaration in `U`'s corresponding local namespace.
3. Otherwise collect exported declarations with the referenced leaf name from all directly imported modules.
4. If exactly one candidate exists, resolve it.
5. If zero candidates exist, fail with an unknown-name diagnostic.
6. If more than one candidate exists, fail with an ambiguous-import diagnostic.

There is no implicit transitive-import visibility. A unit may use declarations from a transitive dependency only by importing that module directly.

Built-in primitive types and standard pure functions/capabilities are predeclared by the selected portable profile. A user declaration that collides with a predeclared id in the same semantic namespace fails closed.

### 7.1 Dotted expression names and record fields

For a dotted expression path such as `a.b.c`, the semantic resolver chooses the **longest resolvable symbol prefix** in the applicable namespace/environment. Remaining segments are field accesses and each must be valid on the preceding record value.

No dictionary or reflection fallback exists.

### 7.2 Enum variants

Enum values and enum patterns use `TypeName::Variant`. `::` is reserved for nominal variant selection and is never field access.

## 8. Type identity

Primitive types have their standard ids.

A declared record or enum has nominal type identity equal to:

`<declaring-module-id>.<local-type-name>` for module declarations, or `<program-id>.<local-type-name>` for root declarations.

Record **values** use structural equality over canonical fields, but assignability remains nominal. Two separately declared records with identical fields are not assignment-compatible.

`Option<T>` and `Result<T,E>` are built-in closed generic families. Their type identity recursively includes the canonical identity of their arguments.

`Unit` is not a storable value type and cannot occur in state, parameters, record fields, `Option`, or either `Result` argument. Its V1 use is capability return type only.

Recursive record dependencies, including indirect recursion through `Option` or `Result`, fail closed in V1.0.

## 9. Pure function graph

Every user function has one fully qualified semantic id and one explicit signature. Function bodies may reference parameters, constants, constructors, field access, pure built-ins and visible user pure functions.

The linker builds a directed function-call graph. Any cycle, including self recursion, fails closed. Capability references from a function fail closed even when the capability kind is `observation`.

The topological function order used by canonicalization is defined by dependency order with semantic-id lexical tie breaking. Implementations may inline functions after this graph is validated.

## 10. Constant expressions

State initializers must be compile-time constant expressions. A constant expression may contain:

- primitive literals;
- exact numeric operators whose operands are constant;
- `vec2` / `vec3` with constant arguments;
- record, enum, `Option`, and `Result` constructors with constant contents;
- pure built-ins documented as constant-foldable;
- user pure functions when every argument is constant and the acyclic call graph permits evaluation within the V1 budgets.

State, parameters, capabilities, current time, input, environment data and other runtime observations are forbidden in constant expressions.

## 11. Behavior dependency and expansion

A behavior may `use` visible behaviors. Each entity may also `use` visible behaviors.

The behavior dependency graph must be acyclic. Expansion is deterministic and order-sensitive:

1. process each `use` in source order;
2. recursively expand that behavior's own `use` declarations in source order;
3. append that behavior's local states and handler fragments;
4. after all entity `use` expansions, append entity-local states and handlers.

The same behavior appearing more than once in one entity's flattened dependency list is an error; V1 never silently deduplicates a diamond dependency.

State names after expansion must be unique. Handler fragments with the same event id must have exactly the same parameter signature. Behavior handler fragments may not contain `return;`.

For one event, executable fragment order is the flattened behavior order followed by the entity-local fragment. This order is semantic and must be preserved in lowering and hashing.

## 12. Capability-effect summary

For every handler fragment, collect the exact capability ids that may execute along any control-flow path. The entity summary is the set union over its fully expanded handlers.

For each requirement, the linked program stores capability id, parameter types, return type and kind. Conflicting signatures for the same capability id fail closed.

Pure functions contribute an empty capability set by definition.

## 13. Bounded iteration

`for i in A .. B` is a half-open integer range: `A <= i < B`.

Both bounds are signed integer literals after unary minus normalization. `B - A` must be non-negative and must not exceed the normative static-loop budget.

The loop variable has type `Int`, is immutable and has block scope. `break` and `continue` do not exist in V1.0. The frontend may unroll the loop only after budget validation.

## 14. Match analysis

Match is permitted over:

- a declared enum;
- `Option<T>`;
- `Result<T,E>`.

There is no wildcard/default pattern in V1.0.

An enum match must contain each declared variant exactly once. `Option` requires exactly `Some(binding)` and `None`. `Result` requires exactly `Ok(binding)` and `Err(binding)`.

Bindings are immutable and scoped only to their arm block. Duplicate arms, impossible constructors, missing arms and extra arms fail closed.

## 15. Canonical linked program

The semantic linked artifact has schema `TEV_SCRIPT_LINKED_PROGRAM_V1` and conforms to `schemas/tev_script_linked_program_v1.schema.json`.

Canonicalization rules:

- modules sort by `module_id`;
- imports sort lexically because import source order is not semantic;
- records sort by semantic type id;
- record fields sort by field name;
- enums sort by semantic type id and variants sort by variant name because enum declaration order has no V1 meaning;
- functions sort by semantic function id;
- capabilities sort by capability id;
- entities sort by entity id;
- entity states sort by state name after behavior expansion;
- event handlers sort by event id;
- behavior `use` order and executable statement order are preserved;
- expression operand order is preserved;
- source/debug paths are excluded from semantic data.

The `semantic_hash` is SHA-256 over the repository canonical JSON profile applied to the linked semantic object **before** adding `semantic_hash` or debug metadata.

## 16. Lowering boundary

The linked program is not runtime IR.

V1 features are partitioned for implementation safety:

### IR-V2 erasable features

These may lower to the certified IR V2 without adding runtime value kinds when their semantics are fully erased before IR validation:

- modules/imports/export;
- pure user functions by validated inlining;
- statically bounded `for` by validated unrolling;
- behavior composition by deterministic expansion;
- custom capabilities whose complete signature uses only IR-V2 portable types.

### IR-V3-required features

General runtime use of the following requires a separately frozen IR profile and runtime value model; they must not be encoded through ad-hoc strings or host objects:

- records;
- enums;
- `Option<T>`;
- `Result<T,E>`;
- runtime field access;
- non-constant exhaustive match over those values;
- custom capability parameters/returns containing those V1 value types.

A V1 compiler must fail closed rather than silently lower an IR-V3-required program through a lossy IR-V2 encoding.

## 17. Determinism counterfactuals

A conforming linker must produce the same semantic hash when only these vary:

- input source file order;
- source filesystem locations;
- path separators;
- process locale/timezone;
- map/dictionary iteration order.

It must produce a different semantic hash when a semantically relevant declaration, type, behavior-use order, executable statement, constant, capability signature or module version changes.
