# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
V0.2 exact source grammar / static semantics:      PASS CERTIFIED LOCAL
V0.2 source -> IR V2 closure:                      PASS CERTIFIED LOCAL
Python / JavaScript / C# conformance:              PASS CERTIFIED LOCAL
Unity Editor / PlayMode / Mono / IL2CPP:           PASS CERTIFIED LOCAL
Gate-5A..5E governed update chain:                  PASS CERTIFIED LOCAL / EXPLICIT BOUNDARIES
Gate-6A..6D Browser-WASM / WASI:                   PASS CERTIFIED LOCAL
Gate-7A..7E distributed determinism:                PASS CERTIFIED LOCAL
V0.2 language completeness:                        PASS CERTIFIED LOCAL

V1 lexical profile / exact grammar:                CLOSED CANDIDATE
V1 deterministic link model:                       CLOSED CANDIDATE V2
V1 normative resource budgets:                     CLOSED CANDIDATE
V1 linked semantic schema:                         CLOSED CANDIDATE
V1 Python AST / lexer / parser:                     IMPLEMENTED CANDIDATE
V1 versioned V0.2/V1 dispatcher:                   IMPLEMENTED CANDIDATE
V1 deterministic multi-file linker:                IMPLEMENTED CANDIDATE
V1 visibility / namespaces / nominal identity:     IMPLEMENTED CANDIDATE
V1 records / enums / Option / Result typing:        IMPLEMENTED CANDIDATE
V1 lexical scopes / immutability / match typing:   IMPLEMENTED CANDIDATE
V1 pure-function purity / DAG guards:               IMPLEMENTED CANDIDATE
V1 exact constant evaluator:                       IMPLEMENTED CANDIDATE
V1 behavior dependency/composition model:           IMPLEMENTED CANDIDATE
V1 capability/effect/event inference:               IMPLEMENTED CANDIDATE
V1 erasable features -> certified IR V2:            IMPLEMENTED CANDIDATE
V1 runtime record/enum/Option/Result values:         IR V3 PENDING
V1 JavaScript / C# parity:                          PENDING
V1 Browser-WASM / WASI parity:                     PENDING
V1 exact clean-commit certification:               PENDING
V1 stable release:                                  NO
```

## Autoridad V0.2 preservada

The exact certified V0.2 language-completeness candidate remains:

```text
COMMIT=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
PARENT=6a33404eb9712b5fae30367d1beb189d8e42f170
TEV_SCRIPT_LANGUAGE_COMPLETE=PASS_CERTIFIED_LOCAL
```

The V1 implementation is additive. The certified V0.2 parser/compiler/runtime files are not rewritten by the V1 candidate; V1-specific implementation lives in separate `*_v1.py` layers and lowers only into the already validated IR V2 contract when the source program is provably representable there.

## Rama de trabajo actual

```text
BRANCH=agent/tev-script-v1-irv2-lowering-v1
BASE_CERTIFIED_V0_2=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
PR1_STATE=DRAFT_OPEN_UNMERGED
STABLE_RELEASE=NO
```

No merge, tag, release or stable promotion is authorized by this candidate.

## Contenido implementado

### Phase A — frontend exacto

Implemented:

- dedicated V1 AST instead of overloading the V0.2 AST;
- exact V1 lexer, including multi-character token precedence and exact rational decimals;
- exact recursive parser for modules, imports, export, declarations, constructed types, records, enums, sum constructors, match, bounded for and behavior composition;
- source-version dispatcher that reroutes `0.2.0` through the certified V0.2 lexer/parser path;
- syntax budgets for source bytes, types, expressions, blocks, parameters, calls, match arms, static loops and locals;
- portable positive/negative syntax corpus.

### Phase B — deterministic linker

Implemented:

- exactly-one-root rule;
- declared module identity independent of filesystem paths;
- duplicate/missing import rejection;
- deterministic import-cycle witnesses;
- reachable-closure computation and unreachable-module exclusion;
- root-program/module-id collision rejection;
- direct-import visibility with private/export enforcement;
- separate type/function/behavior/capability/entity namespaces;
- longest-direct-module-prefix resolution for qualified symbols;
- global capability ids with identical-contract coalescing and conflicting-contract rejection;
- deterministic semantic symbol/index identity;
- portable linker corpus and determinism counterfactuals.

### Phase C — static semantics

Implemented candidate:

- nominal record/enum identities;
- recursive `Option<T>` / `Result<T,E>` type identities;
- exact `Int -> Rat` widening and no implicit narrowing;
- `Unit` placement restrictions, including nested constructed types;
- duplicate record-field / enum-variant rejection;
- record dependency-cycle rejection without relying on Python recursion;
- lexical scopes, immutable locals/parameters/loop/match bindings and state-only assignment;
- record construction/field typing, enum values, Option/Result contextual constructors;
- exact operator typing;
- exhaustive enum/Option/Result match;
- pure-function/effect separation;
- user-function DAG cycle/depth precheck independent of host recursion limits;
- handler capability requirements and emitted-event signatures;
- deterministic static semantic index.

### Phase D — constants and behavior composition

Implemented candidate:

- exact `Fraction`-based constant evaluation;
- constant records/enums/Option/Result/vectors;
- pure built-in and user-function constant evaluation;
- constant-evaluation step budget;
- capability usage rejected structurally in state initializers even under dead short-circuit branches;
- dependency-first behavior closure preserving explicit `use` order;
- iterative behavior traversal independent of host recursion limits;
- cycle, diamond/repeated-use, state-conflict and handler-signature rejection;
- behavior handlers see their dependency states but never sibling-only states;
- entity-local handlers see the full composed state closure;
- composed capability unions and cross-fragment event-signature checks.

### Phase F candidate — V1 erasable lowering to IR V2

Implemented on the current branch:

- explicit `analyze_ir_v2_lowering_boundary` classification;
- fail-closed `IR V3 REQUIRED` for runtime records, enums, Option, Result, field access, match or V1-valued capability/event surfaces;
- unused V1 type declarations do not block a program whose runtime surface is entirely IR-V2-compatible;
- V1-only constant intermediates may disappear before IR emission when constant evaluation proves the final runtime value is an IR-V2 value;
- modules/imports/export erase after deterministic linking;
- behaviors flatten into handler fragments in semantic execution order;
- bounded `for` statically unrolls with loop variables lowered as exact constants;
- nested lexical locals alpha-rename to deterministic IR locals;
- user pure functions inline with **call-by-value**: each argument is evaluated once into a temporary before substituting the function body;
- short-circuit `and/or` lowers to explicit jumps and a temporary Bool instead of the eager V0.2 `BINARY` operator;
- primitive custom capabilities lower to canonical IR V2 capability contracts;
- emitted-event `Int -> Rat` widening normalizes to the composed handler signature;
- final output passes through the existing IR V2 validator by construction before a bundle is returned.

## Portable conformance assets added for V1

```text
conformance/v1-source-syntax-cases.json
conformance/v1-linker-cases.json
conformance/v1-static-semantics-cases.json
conformance/v1-behavior-composition-cases.json
conformance/v1-constant-cases.json
conformance/v1-irv2-lowering-cases.json
```

Associated Python tests cover parser boundaries, deterministic linking, type/scope/effect rules, constants, behavior composition, IR-V2 lowering and observable execution on the existing Python `ScriptRuntime`.

## Unified local gate

`RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py` now covers:

1. Python `compileall` for implementation/tests;
2. strict JSON loading + content manifest for all V1 portable corpora;
3. all `test_v1_*.py` suites, including IR-V2 lowering/runtime semantics;
4. V0.2 Python regression suites `test_canonical.py`, `test_compiler.py`, `test_conformance.py`;
5. explicit terminal boundaries stating IR V3 and cross-runtime parity are not yet claimed.

Expected success terminals include:

```text
TEV_SCRIPT_V1_PYTHON_COMPILE=PASS
TEV_SCRIPT_V1_JSON_INPUTS=PASS
TEV_SCRIPT_V1_TESTS=PASS
TEV_SCRIPT_V0_2_PYTHON_REGRESSION=PASS
TEV_SCRIPT_V1_IRV2_ERASABLE_LOWERING=PASS_CANDIDATE
TEV_SCRIPT_V1_FRONTEND_STATIC_CLOSURE=PASS_CANDIDATE
V1_RUNTIME_IR3=NOT_IMPLEMENTED
V1_CROSS_RUNTIME_PARITY=NOT_CLAIMED
V1_STABLE_RELEASE=NO
```

## Verificación actual de esta sesión

The GitHub candidate and its test/gate content are published on the branch, but this ChatGPT runtime currently has no executable checkout of that branch and cannot obtain the public branch archive bytes through the available connector path. No GitHub Actions workflow is being introduced as a substitute.

Therefore the current status is deliberately:

```text
CODE_AND_CONFORMANCE_CORPORA=PUBLISHED_CANDIDATE
CURRENT_RUNTIME_DYNAMIC_GATE=NOT_REEXECUTED_HERE
V1_PASS_CERTIFIED=NO
```

Do not reinterpret `IMPLEMENTED CANDIDATE` as a fresh dynamic PASS.

## Hipótesis falsables activas

### H1 — path/order determinism

Changing only file paths, path separators or source-input enumeration order must preserve V1 linked/static identity and lowered IR bytes for an IR-V2-lowerable program.

### H2 — call-by-value preservation

Inlining `fn twice(x: Rat) -> Rat = x + x` with `twice(time.delta())` must call `time.delta` exactly once, not twice.

### H3 — short-circuit preservation

`false and probe.read()` and `true or probe.read()` must not invoke `probe.read` after V1 lowering even though V0.2's binary logical instruction is eager.

### H4 — behavior-order preservation

If behaviors A then B are used and both contribute `update`, observable effects must occur A then B then the entity-local fragment. Reversing explicit `use` order must change semantic identity.

### H5 — no lossy V1 runtime values

Any program requiring record/enum/Option/Result runtime storage, runtime field access, runtime match or V1-valued capability/event data must fail lowering until IR V3 is frozen.

### H6 — V0.2 non-regression

The V1 additions must leave certified V0.2 source-to-IR/runtime behavior unchanged.

## Tareas siguientes

1. Execute the unified V1 closure gate on an exact checkout and fix every failing counterfactual before promotion.
2. Freeze the final `TEV_SCRIPT_LINKED_PROGRAM_V1` emitter/canonical bytes using the now-implemented static semantic model.
3. Close the IR-V2 erasable profile with exact content-identity evidence.
4. Only then design and freeze **IR V3** for non-erasable V1 runtime values: records, enums, Option/Result, field access and match.
5. Implement IR V3 first in Python reference runtime, then JavaScript and C#, followed by Unity Core, Browser-WASM and WASI parity.
6. Re-run the V0.2 authoritative receipts byte-identically and perform one exact clean-commit certification before any V1 stable claim.

## Production boundaries unchanged

This V1 work does not close production signing-key provisioning/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN update campaigns, physical Unity Input System/Animator providers, evolutionary self-assembly or decentralized peer-to-peer trust.
