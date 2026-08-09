# TEV Script V1 deterministic link model

Status: **normative V1 candidate V2**. This document defines the semantic layer between parsing and runtime-IR lowering. It is deliberately separate from `TEV_SCRIPT_PROGRAM_IR_V2`.

## 1. Purpose

V1 introduces multiple source units, visibility, user functions, named value types and behavior composition. Those features cannot depend on filesystem order, paths, locale, host dictionaries or host-language name lookup. The linker therefore produces one deterministic semantic program model before runtime lowering.

Source paths, timestamps, directory enumeration order and host-specific file identities are debug/build data and are excluded from semantic identity.

## 2. Link input and root identity

A link invocation receives an explicit finite set of decoded V1 source units. Module discovery is not performed by the language runtime.

Each input unit parses as exactly one `script` or one `module`. The linker requires exactly one script root. Every module is keyed by its declared `module_id`, never by a path-derived id.

The root `program_id` MUST NOT equal any reachable or supplied `module_id`. Such a collision fails closed with a link diagnostic. This prevents the root nominal namespace `<program_id>.<name>` from becoming indistinguishable from a module nominal namespace `<module_id>.<name>`.

The V1 core profile performs no network lookup, package-registry lookup, implicit parent-directory lookup, environment-variable lookup or current-working-directory lookup.

## 3. Version rule

The V1 target source header is `version "1.0.0"`.

A V1-capable frontend must continue to accept a standalone valid V0.2 root with `version "0.2.0"` through the certified V0.2 compilation path. V1-only declarations or imports are not permitted under a V0.2 header.

A V1 linked program has a `1.0.0` root and every reachable module must also declare `1.0.0`. Mixed V1 module versions fail closed in the initial V1 profile; semver-range module resolution is not part of V1.0.

## 4. Import graph

For every unit, imports form directed edges from the importing unit to the declared module id.

The graph is validated before contextual name resolution:

1. every imported module id exists exactly once;
2. duplicate module ids fail closed;
3. duplicate import statements inside one unit fail closed;
4. the import graph is acyclic;
5. unreachable supplied modules are excluded from the semantic linked closure and may be reported as build diagnostics;
6. dependency traversal is deterministic and never depends on filesystem enumeration;
7. the root plus its transitive import closure defines the linked module set;
8. all linked-source byte/declaration/module budgets are checked fail-closed.

The canonical module list is sorted lexically by `module_id`. A separate dependency-first topological order may be retained for deterministic analyses that require dependencies before consumers.

## 5. Identifier model and namespaces

Identifiers are ASCII and case-sensitive. Qualified ids use `.` as the segment separator.

The semantic namespaces are distinct:

- **type namespace**: records, enums and predeclared types;
- **function namespace**: pure user functions and pure built-ins;
- **behavior namespace**: behaviors;
- **capability namespace**: capability ids;
- **entity namespace**: root entities.

Within one namespace and one unit, duplicate declarations fail closed. A name in one namespace does not automatically conflict with the same leaf spelling in another namespace; contextual use determines the namespace. Cross-namespace callable ambiguity is nevertheless rejected when an expression call could denote both a visible pure function and a visible observation capability.

User functions are not overloadable in V1.0. Built-in functions may have the fixed overload sets defined by the portable profile.

## 6. Export and visibility

Module top-level declarations are private by default. `export` makes the declaration visible to importing units. Export does not recursively re-export imported declarations.

The script root has no package export surface in V1.0. `export` is syntactically valid only on module top-level declarations.

There are no wildcard imports, import aliases or implicit re-exports in V1.0.

A unit may use a declaration from a transitive dependency only by importing that declaring module directly, except that a behavior's already-resolved internal dependency remains part of that behavior's semantic composition when the behavior itself is imported and used.

## 7. General name resolution

Resolution is context-specific by namespace.

For type/function/behavior references in unit `U`:

1. exact current-unit semantic id is considered;
2. if a syntactically qualified reference begins with one or more directly imported module ids, choose the **longest directly imported module prefix** and resolve only against exported declarations of that module;
3. otherwise consider an unqualified local declaration in the requested namespace;
4. then consider a matching predeclared portable symbol;
5. then an exact exported semantic id from direct imports;
6. then collect exported declarations with the requested leaf name from all direct imports;
7. exactly one candidate resolves;
8. zero candidates fail unknown-name;
9. multiple candidates fail ambiguous-name.

No tie is broken by source discovery order.

Built-in primitive types and standard pure functions/capabilities are predeclared by the selected portable profile. A user declaration that collides with a predeclared id in the same semantic namespace fails closed.

### 7.1 Dotted value names and record fields

For a dotted value path such as `value.position.x`, local/parameter/state lookup determines the value prefix and the remaining segments are statically validated record-field accesses. No dictionary or reflection fallback exists.

For qualified top-level symbol references, the linker uses the longest directly imported module prefix as described above. Runtime value field lookup never performs module resolution.

### 7.2 Enum variants

Enum values and enum patterns use `TypeName::Variant`. `::` is reserved for nominal variant selection and is never record field access.

## 8. Capability identity and repeated declarations

Capability ids are **global semantic ids explicitly written in the capability declaration**. They are not derived from the declaring module id.

Consequences:

1. capability resolution first considers an exact visible capability id;
2. dotted capability text is not reinterpreted as `module_id + local_name` merely because a module prefix matches;
3. export controls whether another unit may rely on a module's capability declaration but does not rewrite the capability id;
4. the same capability id may be declared in multiple reachable units only when parameter types, return type and capability kind are exactly identical after type resolution;
5. identical repeated declarations collapse to one semantic capability contract;
6. conflicting declarations for the same capability id fail closed even if no call site happens to execute that capability;
7. a built-in capability id cannot be redefined with a conflicting source contract.

This rule permits independent modules to state the same host requirement without creating artificial module-qualified capability identities.

## 9. Type identity

Primitive types have their standard ids.

A declared record or enum has nominal type identity:

- `<declaring-module-id>.<local-type-name>` for a module declaration;
- `<program-id>.<local-type-name>` for a root declaration.

The root/module-id collision prohibition in section 2 guarantees these two nominal domains cannot become textually identical by construction.

Record **values** use structural equality over canonical fields after nominal type equality is established, but assignability remains nominal. Separately declared records with identical fields are not assignment-compatible.

`Option<T>` and `Result<T,E>` are built-in closed generic families. Their type identity recursively includes the canonical identity of their arguments.

`Unit` is not a storable value type and cannot occur in state, parameters, record fields, `Option`, or either `Result` argument. Its V1 use is direct capability return type only.

Recursive record dependencies, including indirect recursion through `Option` or `Result`, fail closed in V1.0.

## 10. Pure function graph

Every user function has one fully qualified semantic id and one explicit signature. Function bodies may reference parameters, constructors, field access, pure built-ins and visible user pure functions.

The linker/static-semantic pipeline builds a directed user-function call graph. Any cycle, including self recursion, fails closed. The normative call-graph depth budget also applies before constant evaluation or inlining; accepted behavior must not depend on a host recursion limit.

Capability references from a pure function fail closed even when the capability kind is `observation`.

Dependency analysis is deterministic. Where a topological function order is needed, dependency order is used with semantic-id lexical tie breaking.

## 11. Constant expressions

State initializers must be compile-time constant expressions. A constant expression may contain:

- primitive literals;
- exact numeric/vector operators whose operands are constant;
- record, enum, `Option`, and `Result` constructors with constant contents;
- field access on constant records;
- pure built-ins documented as constant-foldable;
- user pure functions when every argument is constant and the validated acyclic call graph remains within the V1 budgets.

State, parameters, capabilities, current time, input, environment data and other runtime observations are forbidden in constant expressions.

Constant-ness is a static property of the expression tree: a capability call hidden in a short-circuited branch does not become a valid state initializer merely because that branch would not execute for one literal condition.

Pure arithmetic evaluation itself retains deterministic short-circuit evaluation and exact `Int`/`Rat` behavior, including deterministic division-by-zero failure.

## 12. Behavior dependency and expansion

A behavior may `use` visible behaviors. Each entity may also `use` visible behaviors.

The dependency graph is resolved before handler body type checking. Expansion is deterministic and dependency-first:

1. process each explicit `use` in source order;
2. recursively/iteratively expand that behavior's own `use` declarations in source order;
3. append the resolved behavior after its dependencies;
4. after all entity dependencies, append entity-local states and handler fragments.

The implementation algorithm must not depend on the host call-stack recursion limit.

The same behavior appearing more than once in one flattened closure is an error. V1 never silently deduplicates a diamond dependency or repeated explicit `use`.

The normative flattened-behavior budget is enforced before expansion can grow without bound.

State visibility rules:

- a behavior local declaration/handler sees states from its own dependency closure plus its own local states;
- an entity local declaration/handler sees states from every used behavior closure plus its own local states;
- a behavior fragment does **not** gain access to states from a sibling behavior merely because some entity later composes both behaviors.

State-name conflicts across composed components fail closed. Duplicate states inside one component remain a duplicate-state error rather than a cross-component conflict.

Handler fragments for the same event may compose only when their parameter type signatures are identical. Parameter names may differ because they are local bindings of each fragment. Behavior handler fragments may not contain explicit `return;`.

For one event, executable fragment order is the flattened behavior order followed by the entity-local fragment. This order is semantic and must be preserved in lowering and hashing.

## 13. Capability and event summaries after composition

Each locally checked handler fragment has a deterministic capability requirement set and emitted-event summary.

For a composed handler:

- capability requirements are the set union of all fragments for that event;
- fragment execution order remains explicit even though the capability summary is set-like;
- emitted-event signatures from all composed fragments must be mutually compatible;
- if a composed target handler exists, each emission must be assignment-compatible with its parameter signature and the canonical emitted signature is normalized to that target signature;
- if no target handler exists, independent emit sites for the same event must infer exactly the same signature;
- conflicts between sibling behavior fragments are detected at the composed entity boundary, not hidden because each behavior passed in isolation.

The entity summary is the union over its fully expanded handlers.

## 14. Bounded iteration

`for i in A .. B` is a half-open integer range: `A <= i < B`.

Both bounds are signed integer literals after unary-minus normalization. `B - A` must be non-negative and must not exceed the normative static-loop budget.

The loop variable has type `Int`, is immutable and has block scope. `break` and `continue` do not exist in V1.0. Implementations may unroll only after validating all relevant expansion budgets.

## 15. Match analysis

Match is permitted over a declared enum, `Option<T>`, or `Result<T,E>`.

There is no wildcard/default pattern in V1.0.

- enum: every declared variant exactly once;
- `Option`: exactly `Some(binding)` and `None`;
- `Result`: exactly `Ok(binding)` and `Err(binding)`.

Bindings are immutable and scoped only to their arm block. Duplicate arms, impossible constructors, missing arms and extra arms fail closed.

## 16. Canonical linked program

The final semantic linked artifact has schema `TEV_SCRIPT_LINKED_PROGRAM_V1` and conforms to `schemas/tev_script_linked_program_v1.schema.json` once the complete emitter is implemented.

Canonicalization rules include:

- modules sort by `module_id`;
- imports sort lexically because import source order is not semantic;
- records sort by semantic type id;
- record fields sort by field name;
- enums sort by semantic type id and variants sort by variant name because enum declaration order has no V1 meaning;
- functions sort by semantic function id;
- capabilities sort by global capability id and identical declarations collapse to one contract;
- entities sort by entity id;
- entity states sort by state name after behavior expansion;
- composed handler entries sort by event id;
- behavior `use` order and executable handler-fragment order are preserved;
- expression operand order and executable statement order are preserved;
- source/debug paths are excluded from semantic data.

The final `semantic_hash` is SHA-256 over the repository canonical JSON profile applied to the linked semantic object before adding the hash or debug metadata.

Intermediate linker/static-analysis hashes are diagnostic identities only and do not substitute for the final linked-program semantic hash.

## 17. Lowering boundary

The linked program is not runtime IR.

### IR-V2 erasable features

These may lower to the certified IR V2 without adding runtime value kinds when their semantics are completely erased before IR validation:

- modules/imports/export;
- pure user functions by validated inlining;
- statically bounded `for` by validated unrolling;
- behavior composition by deterministic expansion;
- custom capabilities whose complete signature uses only IR-V2 portable value types.

### IR-V3-required features

General runtime use of these requires a separately frozen IR profile and runtime value model:

- records;
- enums;
- `Option<T>`;
- `Result<T,E>`;
- runtime record field access;
- non-constant exhaustive match over those values;
- custom capability parameters/returns containing those V1 value kinds.

A V1 compiler must fail closed rather than silently lower an IR-V3-required program through strings, opaque JSON, host references or another lossy encoding.

## 18. Determinism counterfactuals

A conforming linker/static-semantic pipeline must preserve semantic identity when only these vary:

- input source-file enumeration order;
- source filesystem locations;
- path separators;
- process locale/timezone;
- map/dictionary iteration order;
- dependency discovery implementation details that do not alter explicit semantic order.

Semantic identity must change when a semantically relevant declaration, type, behavior-use order, executable statement, constant, capability signature, module version or other semantic input changes.
