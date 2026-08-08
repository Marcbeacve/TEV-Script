# TEV Script V1 semantic contract

Status: **closed normative candidate V2**.

This document defines the intended TEV Script V1 source semantics. It does not promote the repository from `0.2.0-preview`, does not claim a stable V1 runtime, and does not reinterpret any V0.2 Gate-5/6/7 certification. V1 promotion requires the implementation and conformance gates listed in `TEV_SCRIPT_V1_FEATURE_MATRIX.json`.

Normative companions:

- `spec/TEV_SCRIPT_V1.ebnf`
- `spec/TEV_SCRIPT_V1_LINK_MODEL.md`
- `spec/TEV_SCRIPT_V1_BUDGETS.md`
- `schemas/tev_script_linked_program_v1.schema.json`

## 1. Design objective

TEV Script V1 is a bounded, typed, deterministic reactive language for programs whose interaction with a host is mediated by explicit capabilities.

V1 increases composition, reuse and domain modeling while retaining decidable static boundaries.

The following remain invariants:

- no reflection;
- no `eval` or runtime source compilation;
- no runtime code generation;
- no unbounded loops;
- no recursion;
- no implicit physical effects;
- no implicit capability authority escalation;
- no host-native object references in language values;
- exact `Int` and `Rat` semantics;
- deterministic event ordering;
- deterministic multi-file linking;
- canonical semantic hashing;
- replaceable host runtimes;
- fail-closed behavior at every unresolved semantic boundary.

## 2. Compatibility and versioning

### 2.1 V0.2 compatibility

Every source program valid under the certified V0.2 grammar and semantics remains valid input to a V1-capable toolchain through the V0.2 compilation path.

A source header `version "0.2.0"` selects V0.2 semantics. V1-only syntax under that header is rejected.

V0.2 IR V2, runtime ABI, canonical receipts, Gate-5 update semantics, Gate-6 browser/WASI boundary and Gate-7 determinism/checkpoint claims remain immutable historical certification surfaces.

### 2.2 V1 target version

The V1 target source header is `version "1.0.0"`.

A linked V1 program contains exactly one V1 script root and zero or more V1 modules. All reachable modules must declare the exact target version in V1.0. Semver ranges and compatibility negotiation are outside the language.

Repository metadata must not claim `LANGUAGE_STABLE=YES` until every V1 promotion gate passes from one exact clean commit.

## 3. Source units

V1 has two source-unit kinds.

### 3.1 Script unit

The script is the unique linked-program root. It owns:

- `program_id`;
- root imports;
- root top-level declarations;
- one or more entities.

A linked program has exactly one script root.

### 3.2 Module unit

A module is a reusable semantic unit identified by its declared qualified `module_id`.

A module may contain imports and top-level declarations. It cannot contain entities in V1.0.

Module identity is never derived from a path. Renaming or relocating a source file without changing its semantic content cannot change the linked semantic hash.

## 4. Imports and visibility

Imports are explicit and finite.

The core language performs no network, registry, filesystem-search-path or environment lookup. The build invocation supplies the finite source set; the linker resolves declared module ids inside that set.

Rules:

- missing imports fail closed;
- duplicate module ids fail closed;
- duplicate imports in one unit fail closed;
- import cycles fail closed;
- import traversal is deterministic;
- module declarations are private by default;
- `export` exposes one module top-level declaration;
- wildcard exports do not exist;
- implicit re-export does not exist;
- import aliases do not exist in V1.0;
- transitive imports are not implicitly visible.

Exact lookup rules are normative in `TEV_SCRIPT_V1_LINK_MODEL.md`.

## 5. Semantic namespaces

V1 separates semantic namespaces for:

- types;
- pure functions;
- behaviors;
- capabilities;
- entities.

Name resolution is context-specific. Ambiguity never resolves by source discovery order.

User declarations cannot replace or shadow a predeclared symbol in the same semantic namespace of the selected portable profile.

## 6. Primitive and constructed types

Primitive types remain:

```text
Bool
Int
Rat
Text
Vec2
Vec3
Unit
```

V1 adds:

```text
record declarations
enum declarations
Option<T>
Result<T,E>
```

### 6.1 Value types

`Bool`, `Int`, `Rat`, `Text`, `Vec2`, `Vec3`, declared records, declared enums, `Option<T>` and `Result<T,E>` are value types when their contained type arguments are value types.

`Unit` is not a storable value. It is permitted only as the return type of a capability that produces no language value.

Consequently `Unit` is rejected in:

- entity or behavior state;
- event parameters;
- function parameters;
- function returns;
- record fields;
- `Option<Unit>`;
- either argument of `Result<...>`;
- capability parameters.

### 6.2 Numeric conversion

`Int -> Rat` is the only implicit numeric widening. There is no implicit `Rat -> Int` conversion and no host-dependent numeric coercion.

### 6.3 Recursive types

Recursive record types are forbidden in V1.0, including indirect recursion and recursion through `Option` or `Result`.

The type-dependency graph must therefore be acyclic and statically decidable.

## 7. Records

A record declaration defines an immutable nominal type with named typed fields.

Example:

```tevs
record Damage {
    amount: Int;
    critical: Bool;
}
```

Construction uses exact field names:

```tevs
Damage { amount = 12, critical = false }
```

Rules:

- type identity is nominal and module-qualified;
- fields are unique;
- field declaration order is not semantic;
- every field is mandatory at construction;
- duplicate field initializers fail closed;
- unknown field initializers fail closed;
- field initializer expressions must be assignment-compatible with field types;
- record values are immutable;
- record equality is structural over canonical fields after nominal type equality is established;
- two different record types are never assignment-compatible merely because their fields match;
- record fields cannot contain `Unit`;
- field access is statically resolved and exposes no reflection/dictionary semantics.

## 8. Enums

An enum declaration defines a closed nominal set of payload-free variants.

```tevs
enum DamageKind {
    Physical;
    Fire;
    Ice;
}
```

A value is written with `::`:

```tevs
DamageKind::Fire
```

Rules:

- enum type identity is nominal and module-qualified;
- variant names are unique within the enum;
- variants have no implicit integer representation;
- variant declaration order has no arithmetic or comparison meaning;
- equality/inequality are permitted only for the same enum type;
- ordering operators are not defined for enums;
- payload-carrying user enum variants are deferred.

## 9. Option and Result

`Option<T>` is the built-in closed sum type:

```text
Some(T)
None
```

`Result<T,E>` is the built-in closed sum type:

```text
Ok(T)
Err(E)
```

These are language values, not host exceptions or nullable host references.

`None` has no payload. `Some`, `Ok` and `Err` each have exactly one payload.

Type inference for a bare `None` requires an expected `Option<T>` type from its context; otherwise compilation fails as underconstrained. The same principle applies whenever a constructor does not by itself determine all generic arguments.

## 10. Pure user functions

V1 adds user-defined pure expression functions:

```tevs
fn clamp(value: Int, low: Int, high: Int) -> Int = min(max(value, low), high);
```

Rules:

- every parameter has an explicit type;
- return type is explicit and cannot be `Unit`;
- parameters are immutable;
- functions cannot read entity state;
- functions cannot emit events;
- functions cannot call capabilities, including observations;
- functions may call pure built-ins and visible pure user functions;
- the user-function call graph must be acyclic;
- there is no user-defined overloading in V1.0;
- there are no default arguments or variadic user functions;
- function evaluation is subject to the normative budgets;
- implementations may inline only after purity, typing and acyclicity have been established.

Function declarations are semantic program data even if an implementation later erases them during lowering.

## 11. Capability declarations

V1 allows typed custom capability declarations while retaining the standard portable catalog.

```tevs
capability world.temperature(Vec2) -> Rat observation;
capability audio.play(Text) -> Unit effect;
```

Capability kinds are exactly:

- `observation`: obtains host/environment data without commanding a physical mutation;
- `effect`: requests a host-side effect.

Rules:

- the full capability signature is semantic;
- conflicting visible declarations for one capability id fail closed;
- capability parameters cannot use `Unit`;
- a capability returning `Unit` cannot be used as an expression;
- an observation returning a value can be used as an expression in a handler but never in a pure function;
- a capability call used as a statement must return `Unit`;
- every capability used by a handler contributes to its statically inferred requirement set;
- a host cannot treat a missing required capability as successful execution;
- runtime availability may be narrower than source requirements, in which case invocation fails closed.

Custom capability signatures using records/enums/Option/Result require the future IR-V3 value profile. They cannot be tunneled through opaque host objects.

## 12. State and constants

Entity and behavior `state` is the only mutable language storage abstraction in V1.0.

State declarations require a compile-time constant initializer. Constant evaluation is defined by the deterministic link model and bounded by `TEV_SCRIPT_V1_BUDGETS.md`.

State values are owned by an entity instance. No reference aliasing semantics are exposed.

## 13. Locals and lexical scope

`let` creates an immutable lexical binding.

Unlike V0.2's intentionally narrow top-level-handler local rule, V1 allows `let` in nested blocks. Each block introduces a lexical scope.

Rules:

- a local cannot be reassigned;
- a loop variable cannot be reassigned;
- a match binding cannot be reassigned;
- parameters cannot be reassigned;
- assignment syntax targets entity state only;
- duplicate names in the same lexical scope fail closed;
- a nested scope may not shadow state, parameters or an enclosing local in V1.0; explicit shadowing is deferred to avoid accidental capture during lowering.

## 14. Expressions and operators

The concrete precedence grammar is normative in `TEV_SCRIPT_V1.ebnf`.

### 14.1 Boolean operators

`and`, `or`, and `not` require `Bool` operands and produce `Bool`.

Implementations must preserve deterministic short-circuit semantics:

- `a and b` evaluates `b` only when `a` is true;
- `a or b` evaluates `b` only when `a` is false.

Because handler expressions may include observation capabilities, short-circuit behavior is observable and semantic.

### 14.2 Equality

`==` and `!=` are defined for:

- same primitive value types;
- numeric `Int`/`Rat` after exact widening;
- same nominal record type by structural field equality;
- same nominal enum type;
- compatible `Option` values;
- compatible `Result` values.

Cross-nominal record/enum comparison is a type error.

### 14.3 Ordering

`< <= > >=` are defined only for numeric values in V1.0.

### 14.4 Arithmetic

`+ - * /` retain the V0.2 exact numeric/vector rules. Division by zero is a deterministic runtime error and cannot be host-undefined behavior.

V1 does not add implicit text concatenation or host operator overloading.

### 14.5 Field access

Field access is valid only on a statically known record type. Dotted paths use longest-symbol-prefix resolution as specified by the link model.

## 15. Statements

### 15.1 Assignment

Assignment mutates existing entity state only. Assigning to a local, parameter, loop variable or match binding is rejected.

### 15.2 Capability call statement

`call capability(args);` is reserved for capabilities whose selected signature returns `Unit`.

Pure function results must be consumed as expressions. Value-returning observations must be consumed as expressions.

### 15.3 Emit

`emit event(args);` queues a local entity event according to the deterministic event model inherited from V0.2.

All emit sites for a given event within one fully expanded entity must agree on one parameter signature, and every handler fragment for that event must use that same signature.

### 15.4 Return

`return;` terminates the current entity-local handler sequence.

Behavior handler fragments may not contain `return;` because a behavior cannot suppress later composition fragments accidentally.

Pure functions use expression bodies and therefore have no return statement.

## 16. If

`if` requires a `Bool` condition. Only the selected branch executes.

Nested lexical scopes follow section 13. The compiler must not evaluate capability calls from an unselected branch.

## 17. Bounded for

V1 has only static integer range iteration:

```tevs
for i in 0 .. 8 {
    ...
}
```

The range is half-open: `0,1,2,3,4,5,6,7`.

Rules:

- both bounds are compile-time signed integer literals;
- iteration count is `upper - lower`;
- negative iteration count is invalid rather than silently empty;
- count must not exceed the normative loop budget;
- loop variable is immutable `Int`;
- loop variable scope is the body;
- `break` and `continue` do not exist;
- nested loop count is bounded;
- implementations may unroll only after checking all expansion budgets.

General collection iteration is deferred until bounded collection semantics are separately frozen.

## 18. Match

V1 has exhaustive statement-level matching over enums, `Option`, and `Result`.

Example:

```tevs
match result {
    Ok(value) => { log "ok"; }
    Err(error) => { log "error"; }
}
```

Rules:

- no wildcard/default arm exists;
- duplicate arms fail closed;
- enum matches require every declared variant exactly once;
- `Option` requires exactly `Some(binding)` and `None`;
- `Result` requires exactly `Ok(binding)` and `Err(binding)`;
- bindings are immutable and arm-local;
- arm order is not used to make an otherwise non-exhaustive match valid;
- only the selected arm executes.

## 19. Behaviors and composition

A behavior is a compile-time semantic composition unit, not a runtime object, class or inheritance base.

```tevs
behavior Movement {
    state speed: Rat = 1.0;
    on update { ... }
}

entity Player {
    use Movement;
    ...
}
```

Behaviors may use other behaviors. The dependency graph must be acyclic.

Exact deterministic expansion is normative in `TEV_SCRIPT_V1_LINK_MODEL.md`.

Composition invariants:

- state collisions fail closed;
- duplicate flattened behavior inclusion fails closed;
- event signature conflicts fail closed;
- behavior handler fragments cannot return;
- handler fragment order derives from explicit `use` order, never module discovery order;
- capability requirements are the union of the expanded handler fragments;
- no inheritance, virtual dispatch, protected visibility, runtime trait object or subtype polymorphism exists.

## 20. Effect and authority model

Every handler has a deterministic capability requirement summary. Every entity has the set union of its expanded handler requirements.

The summary records complete selected signatures, not merely names.

Source declaration does not grant host authority. It states a requirement. The host adapter independently decides what capabilities are available, but it cannot claim successful execution of a missing effect.

There is no ambient host-object access.

## 21. Event model

V1 retains the local bounded event-chain model of V0.2 unless a later event-model version is separately frozen.

Events are not threads. `emit` does not create implicit parallel execution.

Event ordering, chain depth and fail-closed behavior remain deterministic.

Cross-entity event routing, distributed message delivery and implicit networking are not introduced by V1.0.

## 22. Determinism

For identical linked semantic inputs and compiler profile, semantic output must not depend on:

- input file enumeration order;
- source file paths;
- OS path separator;
- current working directory;
- locale;
- timezone;
- host integer width;
- JavaScript `Number` coercion;
- hash-map iteration order;
- thread scheduling;
- filesystem timestamp.

Semantically relevant explicit order remains significant where the contract says so, notably statement order and behavior `use` order.

## 23. Canonical linked program

Parsing and linking produce a `TEV_SCRIPT_LINKED_PROGRAM_V1` artifact before runtime-IR lowering.

This artifact:

- contains canonical semantic identities;
- contains normalized type ids;
- contains deterministic imports/declarations/entities;
- preserves semantically meaningful execution order;
- excludes source/debug paths from the semantic object;
- has a SHA-256 semantic hash under the existing canonical JSON profile.

The exact shape is frozen by `schemas/tev_script_linked_program_v1.schema.json` and the ordering rules in the link model.

## 24. Runtime IR boundary

V1 source completeness and runtime representation are separate questions.

### 24.1 Safe erasure to IR V2

The following may be compiled away before entering the certified IR V2 when validation proves semantic preservation:

- modules/imports/export;
- pure user functions;
- bounded `for`;
- behaviors;
- custom capabilities restricted to existing IR-V2 value types.

### 24.2 IR V3 requirement

General runtime values for records, enums, `Option`, `Result`, field access and non-constant match require a new frozen IR value profile.

The compiler must reject a program requiring that profile until IR V3 exists. Encoding those values as ad-hoc `Text`, JSON blobs, host references or implementation-specific objects is non-conformant.

This fail-closed split allows the V1 frontend/linker to mature without weakening the certified runtime boundary.

## 25. Diagnostics

A V1 frontend must preserve explicit diagnostic categories at minimum for:

- source decoding;
- lexical errors;
- parse errors;
- version errors;
- import/link errors;
- duplicate/ambiguous name errors;
- visibility errors;
- type errors;
- recursive type errors;
- purity violations;
- function recursion/call-cycle errors;
- constant-expression violations;
- capability declaration/use errors;
- behavior cycle/composition conflicts;
- event signature conflicts;
- boundedness/budget violations;
- match exhaustiveness errors;
- lowering-profile errors;
- IR validation errors.

Host exceptions are implementation failures or host-boundary errors, not language-level control flow.

## 26. Explicitly deferred from V1.0

V1.0 does not require or silently permit:

- `async` / `await`;
- unbounded or data-dependent loops;
- recursion;
- classes/inheritance;
- reflection;
- runtime code generation;
- user-defined generics;
- general map/dictionary values;
- payload-carrying user enum variants;
- threads or implicit concurrency;
- exceptions as control flow;
- host-native object references;
- package registry/network module resolution;
- import aliases;
- wildcard imports;
- implicit re-export;
- semver-range module negotiation.

Each requires a separate semantic and conformance decision.

## 27. Promotion gates

V1 may be called implemented only after all required source features are accepted by the reference frontend and deterministic linker with a complete negative corpus.

V1 may be called runtime-conformant only after the required IR profile and Python/JavaScript/C# runtime parity are closed.

V1 may be called stable only when all of these are true from one exact clean commit:

1. spec internal consistency PASS;
2. exact lexer/parser PASS;
3. static type/name/effect semantics PASS;
4. deterministic multi-file linker PASS;
5. canonical linked-program byte lock PASS;
6. all erasable V1 features lower deterministically to validated IR V2;
7. IR V3 is frozen and validated for all non-erasable V1 runtime values;
8. Python/JavaScript/C# authoritative V1 receipt parity PASS;
9. browser-WASM/WASI coverage is not regressed;
10. V1 negative boundary campaign PASS;
11. V0.2 regression corpus remains byte-identical;
12. exact clean commit/tree/content-identity certification PASS;
13. only then may repository metadata claim `LANGUAGE_VERSION=1.0.0` and `LANGUAGE_STABLE=YES`.
