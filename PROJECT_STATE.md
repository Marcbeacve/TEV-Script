# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
V0.2 exact source grammar / static semantics:      PASS CERTIFIED LOCAL
V0.2 source -> IR V2 closure:                      PASS CERTIFIED LOCAL
Python / JavaScript / C# conformance:              PASS CERTIFIED LOCAL
Unity Editor / PlayMode / Mono / IL2CPP:           PASS CERTIFIED LOCAL
Gate-5A transactional program swap:                PASS CERTIFIED LOCAL
Gate-5B transactional swap inside IL2CPP/AOT:      PASS CERTIFIED LOCAL
Gate-5C signed canonical update package:           PASS CERTIFIED LOCAL
Gate-5D durable anti-replay / restart restore:      PASS WITH EXPLICIT BOUNDARY
Gate-5E remote transport inside IL2CPP/AOT:         PASS LOOPBACK_HTTP
Gate-6A Unity Web / browser-WASM:                   PASS CERTIFIED LOCAL
Gate-6B pure Core browser-WASM AOT:                 PASS CERTIFIED LOCAL
Gate-6C pure Core WASI / Wasmtime:                  PASS CERTIFIED LOCAL
Gate-6D signed update Browser-WASM + WASI:          PASS CERTIFIED LOCAL
Gate-7A deterministic replay:                      PASS CERTIFIED LOCAL
Gate-7B cross-host byte lockstep:                  PASS CERTIFIED LOCAL
Gate-7C first-divergence localization:             PASS CERTIFIED LOCAL
Gate-7D canonical checkpoint / process restart:    PASS CERTIFIED LOCAL
Gate-7E signed-update lockstep:                    PASS CERTIFIED LOCAL
V0.2 language completeness:                        PASS CERTIFIED LOCAL

V1 exact grammar:                                  CLOSED CANDIDATE V2
V1 source semantic contract:                       CLOSED CANDIDATE V2
V1 deterministic link model:                      CLOSED CANDIDATE V1
V1 normative resource budgets:                    CLOSED CANDIDATE V1
V1 linked semantic program schema:                 CLOSED CANDIDATE V1
V1 reference frontend:                            PENDING IMPLEMENTATION
V1 deterministic linker:                          PENDING IMPLEMENTATION
V1 IR-V2 erasable lowering:                       PENDING IMPLEMENTATION
V1 IR V3 for non-erasable value kinds:            PENDING DESIGN/FREEZE
V1 cross-runtime conformance:                      PENDING

Stable release:                                    NO
```

## Progreso certificado V0.2

The exact certified V0.2 language-completeness candidate is:

```text
COMMIT=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
PARENT=6a33404eb9712b5fae30367d1beb189d8e42f170
TEV_SCRIPT_LANGUAGE_COMPLETE=PASS_CERTIFIED_LOCAL
```

The V0.2 closure includes exact lexical/source grammar, normative static semantics, source-to-IR closure, typed extensible capability catalogs, IR operational semantics, typed CFG/stack/local definite-initialization verification, canonical ABI identifiers, shared negative corpora, C# Core/Unity Core byte-identical mirrors and Browser-WASM/WASI AOT compile-smoke coverage.

The certified Gate-7 chain additionally covers deterministic replay, Python/JavaScript/C#/Browser-WASM/WASI canonical lockstep, first-divergence localization, canonical checkpoint/restart continuation and signed-update lockstep.

## Log de cambios — V1 specification closure V2

V1 is now developed from the exact certified V0.2 head rather than from the older divergent semantic-freeze branch.

The V1 specification has been strengthened before implementation so the frontend cannot invent host-dependent semantics. The previous prose-only expression placeholder has been replaced by exact precedence productions and exact constructor/pattern syntax.

The following V1 decisions are now normative candidates:

- source version `1.0.0` for V1 roots and reachable modules;
- explicit finite source-set linking with no implicit network/registry/search-path resolution;
- exactly one root script and deterministic module-id-based linking;
- explicit private/export visibility with no wildcard import, aliases or implicit re-export;
- distinct type/function/behavior/capability/entity namespaces;
- longest-resolvable-symbol-prefix rule for dotted expression names and record field access;
- nominal record/enum type identity;
- exact record construction with named mandatory fields;
- enum value/pattern syntax `Type::Variant`;
- built-in `Option<T>` and `Result<T,E>` constructors/patterns;
- `Unit` restricted to capability return position;
- acyclic record dependencies and acyclic pure-function call graphs;
- capability-free pure functions;
- compile-time constant state initializers;
- nested immutable lexical bindings without shadowing;
- deterministic short-circuit boolean semantics;
- statically bounded half-open integer `for` ranges;
- exhaustive enum/Option/Result match with no wildcard/default arm;
- deterministic behavior expansion in explicit `use` order with cycle/diamond/conflict rejection;
- canonical `TEV_SCRIPT_LINKED_PROGRAM_V1` as a semantic layer before runtime IR;
- explicit split between IR-V2-erasable V1 abstractions and IR-V3-required runtime value kinds.

## Hipótesis falsables

### H1 — V1 frontend determinism

Given identical decoded semantic source units, changing file paths, input enumeration order, locale, timezone or dictionary iteration order must not change the canonical linked bytes or semantic hash.

### H2 — bounded composition

Every accepted V1 program must have statically bounded parsing, linking, type analysis, behavior expansion, pure-function evaluation/inlining, loop unrolling and runtime instruction emission according to `spec/TEV_SCRIPT_V1_BUDGETS.md`.

### H3 — V0.2 non-regression

Adding the V1 frontend/linker must leave every certified V0.2 canonical IR and conformance receipt byte-identical.

### H4 — no lossy V1 lowering

Any V1 program requiring records, enums, `Option`, `Result`, runtime field access or non-constant matching must fail closed until the corresponding IR V3 profile is frozen. No host-object, ad-hoc JSON or Text tunneling is conformant.

## Tareas

1. Implement Phase A: exact versioned AST, lexer and parser for every V1 production while preserving the V0.2 path.
2. Implement Phase B: deterministic source-set linker, import graph, visibility and namespace-aware resolution.
3. Implement Phase C: nominal/constructed type system, lexical scopes, constructors and static semantics.
4. Implement Phase D/E: purity graph, constant evaluator, effect inference, behavior expansion, bounded `for` and exhaustive `match`.
5. Close IR-V2-preserving lowering for erasable V1 features and prove V0.2 byte non-regression.
6. Freeze IR V3 before implementing non-erasable V1 runtime values.
7. Reproduce authoritative V1 semantics across Python, JavaScript, C#, Unity Core, Browser-WASM and WASI before any V1 promotion.

## Verificación de esta rama

This branch changes specification/governance content only at this stage. It does not claim a V1 frontend or runtime implementation PASS.

The new JSON feature matrix and linked-program schema were syntax-validated during authoring. Their semantic implementation remains intentionally pending and must be tested by executable conformance gates.

```text
V0_2_CERTIFIED_BASE_PRESERVED=YES
V1_SPECIFICATION_CLOSED_CANDIDATE=YES
V1_IMPLEMENTED=NO
V1_RUNTIME_CONFORMANT=NO
LANGUAGE_STABLE=NO
PR1_MERGED=NO
```

## Production boundaries unchanged

The V1 specification work does not close production signing-key provisioning/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN update campaigns, physical Unity Input System/Animator providers, safe evolutionary self-assembly or decentralized peer-to-peer consensus/trust.
