# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
V0.2 exact source grammar / static semantics:          PASS CERTIFIED LOCAL
V0.2 source -> IR V2 closure:                          PASS CERTIFIED LOCAL
V0.2 Python / JavaScript / C# conformance:             PASS CERTIFIED LOCAL
V0.2 Unity Editor / PlayMode / Mono / IL2CPP:          PASS CERTIFIED LOCAL
V0.2 Gate-5A..5E governed update chain:                PASS CERTIFIED LOCAL / EXPLICIT BOUNDARIES
V0.2 Gate-6A..6D Browser-WASM / WASI:                  PASS CERTIFIED LOCAL
V0.2 Gate-7A..7E distributed determinism:              PASS CERTIFIED LOCAL
V0.2 language completeness:                            PASS CERTIFIED LOCAL

V1 lexical / grammar / semantic contract:              CLOSED CANDIDATE
V1 deterministic multi-file linker:                    IMPLEMENTED CANDIDATE
V1 linked module UnitIndex.kind regression:            FIXED + REGRESSION ADDED
V1 nominal + constructed type system:                  IMPLEMENTED CANDIDATE
V1 scopes / purity / effects / events:                 IMPLEMENTED CANDIDATE
V1 constants / behaviors / bounded control flow:       IMPLEMENTED CANDIDATE
V1 canonical linked semantic program:                  IMPLEMENTED CANDIDATE
V1 erasable source semantics -> IR V2:                 IMPLEMENTED CANDIDATE
V1 full algebraic source semantics -> IR V3:           IMPLEMENTED CANDIDATE
IR V3 closed type table / codec / validator / CFG:     IMPLEMENTED CANDIDATE
IR V3 Python runtime:                                  IMPLEMENTED CANDIDATE
V1 Python production IR-only host:                     IMPLEMENTED CANDIDATE
V1 Python least-authority capability preflight:        IMPLEMENTED CANDIDATE
V1 Python reproducible-wheel production admission:     GATE IMPLEMENTED
IR V3 JavaScript runtime:                              IMPLEMENTED CANDIDATE
IR V3 C# runtime assembly:                             IMPLEMENTED CANDIDATE
IR V3 Python/JS/C# canonical receipt byte lock:        GATE IMPLEMENTED
IR V3 Runtime Checkpoint V2:                           IMPLEMENTED CANDIDATE
IR V3 checkpoint Python/JS/C# byte lock + restart:     GATE IMPLEMENTED
IR V3 Browser-WASM AOT runtime parity:                 GATE IMPLEMENTED
IR V3 WASI/Wasmtime runtime + process restart:         GATE IMPLEMENTED
IR V3 transactional hot swap:                          IMPLEMENTED CANDIDATE
IR V3 signed update package/body V2:                   IMPLEMENTED CANDIDATE
IR V3 signed update host campaign:                     GATE IMPLEMENTED
IR V3 signed update Browser-WASM campaign:             GATE IMPLEMENTED
IR V3 signed update WASI fresh/restore campaign:       GATE IMPLEMENTED
V1 full precertify orchestration:                       IMPLEMENTED CANDIDATE V5

Current exact-HEAD Python production gate:              NOT EXECUTED IN THIS CHAT RUNTIME
Current exact-HEAD dynamic full precertify:             NOT EXECUTED IN THIS CHAT RUNTIME
V1 CERTIFY_FULL:                                       NO
V1 LANGUAGE_STABLE:                                    NO
```

## Autoridad V0.2 preservada

The certified V0.2 language-completeness oracle remains:

```text
COMMIT=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
PARENT=6a33404eb9712b5fae30367d1beb189d8e42f170
TEV_SCRIPT_LANGUAGE_COMPLETE=PASS_CERTIFIED_LOCAL
```

V1 does not reinterpret those receipts. The C# V0.2 assembly remains `TevScript.Core` targeting `netstandard2.1`; V3 is compiled as the additive `TevScript.Core.V3` assembly. Normal V3 runtime consumers reference only `TevScript.Core.V3`. Signed-update gates additionally reference the already existing `TevScript.Update` assembly solely to reuse the managed ES256 verifier authority; the V3 runtime itself does not depend on that cryptographic provider.

## Rama de trabajo actual

```text
BRANCH=agent/tev-script-v1-irv3-spec-v1
BASE_CERTIFIED_V0_2=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
STABLE_RELEASE=NO
CERTIFY_FULL=NO
```

The branch is an implementation/certification candidate. No merge, tag or stable promotion follows merely from code presence.

## Cierre del lenguaje fuente V1

### Frontend and syntax

Implemented candidate:

- dedicated V1 AST;
- exact V1 lexical profile and grammar;
- versioned V0.2/V1 dispatcher preserving the certified V0.2 path;
- modules and imports;
- explicit module exports/private declarations;
- custom capability declarations;
- records and enums;
- `Option<T>` and `Result<T,E>`;
- pure user functions;
- behavior composition;
- bounded half-open integer `for`;
- exhaustive enum/Option/Result `match`;
- nested immutable lexical bindings;
- exact expression precedence and short-circuit semantics;
- explicit source/type/expression/block/loop/arity budgets.

### Deterministic linker

Implemented candidate:

- exactly one script root;
- module identity independent of paths;
- explicit finite source-set resolution;
- duplicate/missing import rejection;
- acyclic import graph;
- direct-import-only visibility;
- no implicit re-export;
- separate type/function/behavior/capability/entity namespaces;
- ambiguity rejection independent of filesystem/dictionary order;
- longest resolvable symbol prefix for dotted names;
- root program/module id collision rejection;
- nominal semantic ids;
- identical capability-contract coalescing and conflicting-contract rejection;
- canonical reachable closure excluding unreachable supplied modules.

The linked-program module normalizer now consumes the actual `UnitIndexV1.kind` contract. The erroneous `unit_kind` consumer was removed rather than hidden behind a compatibility alias, and `tests/test_v1_linked_program_unit_kind_regression.py` locks that field contract with a real multi-module program.

### Static semantics

Implemented candidate:

- nominal record and enum identity;
- closed `Option<T>` / `Result<T,E>` identities;
- recursive-record rejection;
- `Unit` placement restrictions;
- exact `Int -> Rat` widening only;
- immutable parameters/locals/loop/match bindings;
- state-only assignment;
- no lexical shadowing in V1.0;
- record construction and field typing;
- enum/Option/Result constructor typing;
- exhaustive match analysis;
- capability-free pure functions;
- acyclic pure-function graph with depth budget independent of host stack limits;
- effect and event-signature inference;
- compile-time constant state initializers;
- exact constant evaluation using rational arithmetic;
- deterministic behavior dependency expansion and conflict detection.

## Canonical source/runtime boundary

V1 compilation is deliberately split into semantic and runtime layers:

```text
V1 source set
   -> parse
   -> deterministic link
   -> static semantics
   -> TEV_SCRIPT_LINKED_PROGRAM_V1
        |-> erasable profile -> TEV_SCRIPT_PROGRAM_IR_V2
        |-> full V1 profile  -> TEV_SCRIPT_PROGRAM_IR_V3
```

`TEV_SCRIPT_LINKED_PROGRAM_V1` is the source-semantic authority. It canonicalizes nominal identities, alpha-renames non-semantic local names and stores state initializers as normalized semantic values. Runtime targets do not repeat source name resolution.

## IR V2 preservation path

The V1 -> IR V2 path remains available where all V1-only abstractions erase safely before runtime representation.

Implemented candidate:

- modules/imports/export erased after deterministic link;
- behaviors expanded in semantic order;
- pure functions inlined call-by-value;
- bounded `for` unrolled;
- nested locals alpha-renamed;
- short-circuit `and/or` compiled to forward CFG rather than eager V0.2 logical instructions;
- primitive custom capabilities emitted as typed IR contracts;
- `Int -> Rat` event coercion normalized explicitly;
- any non-erasable algebraic value use fails closed instead of tunneling through Text/JSON/host objects;
- lowering receipt V1 binds linked V1 semantic hash to the resulting IR V2 hash.

## IR V3 algebraic runtime

IR V3 preserves the acyclic finite machine model of IR V2 and adds immutable algebraic values without heap references, reflection or runtime code generation.

### Runtime value surface

Implemented candidate:

- primitive V0.2 value encodings retained;
- nominal record values;
- payload-free enums;
- `Option<T>`;
- `Result<T,E>`;
- recursively closed type table;
- maximum algebraic-value nesting budget;
- type-directed canonical encode/decode;
- redundant nominal type witness validation in algebraic JSON values.

### Algebraic ISA

Implemented candidate opcodes:

```text
MAKE_RECORD
LOAD_FIELD
MAKE_VARIANT
TEST_VARIANT
LOAD_VARIANT_PAYLOAD
```

They compose with the existing acyclic stack/local/state/capability/event machine. There are still no backward jumps, recursion, reflection, threads or hidden host references.

### Verification

Implemented candidate:

- strict JSON duplicate-key rejection;
- exact IR envelope/profile/source-hash validation;
- closed/sorted type table validation;
- typed state/capability/event validation;
- typed CFG abstract interpretation;
- stack merge equality;
- definite local initialization;
- algebraic opcode stack effects;
- canonical `semantic_hash` and `debug_hash` validation;
- V2 -> V3 verified lift preserving the certified primitive model.

## Multi-runtime implementation

### Python

Implemented candidate runtime, validator, type/value codec, V1->V3 lowerer, V2->V3 lift, conformance runner, checkpoint V2 and lowering receipt V2.

The Python product surface additionally contains:

- `PythonProgramArtifactV1`: immutable validated canonical IR V3 deployment artifact;
- `PythonCapabilityContractV1`: exact capability ABI summary derived from validated IR;
- `PythonRuntimeHostV1`: runtime-only least-authority host with no source compilation entry point;
- `build_python_program_v1` / `build_python_program_v1_paths`: explicit build-time source-to-IR V3 helpers;
- missing capability rejection before execution;
- unused capability rejection by default;
- callable validation before authority reaches the runtime;
- exact Runtime Checkpoint V2 capture/restore through the same V3 runtime semantics;
- public versioned root-package exports without changing the certified V0.2 unversioned aliases.

The runtime host accepts only precompiled validated IR V3. Source compilation stays a build/tooling concern and cannot be requested through the runtime host.

`RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py` implements a clean-commit Python product gate. It runs the Python/frontend closure, builds two wheels from independent `git archive HEAD` trees with fixed build epoch, requires identical wheel bytes, installs the wheel offline in a fresh venv, verifies installed console scripts/descriptor, compiles explicit IR V3 outside the checkout, executes the installed runtime host, captures/restores a checkpoint and requires continuation after restore. The final receipt binds commit, tree and wheel SHA-256 while still declaring `CERTIFY_FULL=NO` and `LANGUAGE_STABLE=NO`.

Capability callback implementations remain trusted embedding code. TEV instruction/event budgets constrain TEV execution, not arbitrary Python code supplied by the embedding application. Untrusted callbacks require process/container isolation at the application boundary.

### JavaScript

Implemented additive ES2022 V3 modules for:

- exact BigInt/Rational primitives;
- V3 type table and algebraic codec;
- typed CFG validation;
- V3 program validation;
- V3 runtime;
- canonical conformance receipt;
- Runtime Checkpoint V2 capture/parse/restore;
- package exports and TypeScript declarations.

The certified V0.2 JS runtime remains separate.

### C#

Implemented `TevScript.Core.V3` as a separate deterministic `net8.0` assembly whose source set is explicit and whose normal runtime surface is dependency-free.

Hardening includes:

- no reflection in V3 runtime/conformance/checkpoint paths;
- strict duplicate-key JSON reader;
- closed object-tree JSON writer for AOT receipt generation rather than general serializer metadata;
- host-independent SHA-256 implementation for canonical identity;
- explicit separation from the V0.2 `netstandard2.1` assembly;
- signed-update consumers bind the existing managed ES256 verifier through `TevScript.Update` without coupling the V3 runtime assembly to it.

## Runtime Checkpoint V2

Checkpoint V2 is additive and does not reinterpret `TEV_SCRIPT_RUNTIME_CHECKPOINT_V1`.

It binds:

```text
program_id
ir_schema
IR semantic_hash
source_schema
source_semantic_hash
exact entity set
exact state set
each state type
canonical algebraic value
```

Restore is allowed only against the exact target IR/source identity. A similar program or compatible-looking schema is insufficient.

Implemented gates cover:

- Python capture/restore;
- JavaScript capture/restore;
- C# capture/restore;
- Python/JS/C# checkpoint byte lock;
- process restart continuation;
- tampered program/source/state/type/value rejection;
- WASI process-to-process checkpoint transport.

## Browser-WASM V3

A dedicated AOT browser gate consumes the same portable IR V3 fixture and conformance scenario used by host runtimes.

The browser must return through an authenticated loopback HTTP witness:

- the exact conformance `receipt_hash` computed by the host oracle;
- the exact Runtime Checkpoint V2 hash computed by the host oracle.

A browser startup smoke is not sufficient for V3 parity.

## WASI V3

The WASI gate is designed as two separate Wasmtime processes:

1. `fresh`: execute/validate and write Runtime Checkpoint V2;
2. `restore`: start a fresh process, parse/restore the checkpoint and continue.

The gate compares receipt/checkpoint identity against the Python host oracle and verifies the checkpoint produced by WASI through the Python parser as a cross-implementation counterfactual.

## Transactional hot swap V3

Implemented candidate:

- immutable snapshot before candidate construction;
- isolated candidate validation/runtime construction;
- exact program/entity continuity;
- state type and migrated-value validation under the candidate type table;
- capability ceiling over full ABI (`id + parameters + return_type + kind`), not only capability names;
- plans bound to runtime generation and source semantic hash;
- single authoritative commit;
- stale/foreign/consumed plan rejection;
- one-step runtime rollback.

This design rejects nominal descriptor drift even when a textual `type_id` is reused but the old value cannot normalize against the candidate descriptor.

## Signed update V3

V3 does not reinterpret the V0.2 update package. It introduces:

```text
TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2
TEV_SCRIPT_UPDATE_BODY_V2
TEV_SCRIPT_INSTALLED_UPDATE_V2
```

The signed body binds:

- channel id;
- program id;
- monotonic epoch/sequence;
- `from_ir_semantic_hash`;
- target IR semantic hash;
- target source semantic hash;
- target IR canonical SHA-256;
- complete embedded canonical IR V3.

Security/continuity model:

- signature verification precedes authoritative mutation;
- transition authorization is exact `from -> target`;
- replay/epoch rollback/invalid epoch advance fail closed;
- durable-store failure rolls the runtime commit back;
- installed-package loading re-verifies package integrity/signature but does not pretend to reapply the historical transition;
- restart state is recovered separately through an exact target Runtime Checkpoint V2;
- fixture signing reuses the existing Gate-5C test P-256 key only inside an ephemeral fixture tool;
- the runtime gate verifies with the independent existing managed ES256 implementation.

Implemented campaigns exist for:

- desktop/host signed update;
- Browser-WASM signed update AOT witness;
- WASI signed update fresh process -> durable installed record/checkpoint -> separate restore process.

## Full precertify V5

`RUN_TEV_SCRIPT_V1_PRECERTIFY.py` now requires, from one clean immutable checkout:

1. V1 Python frontend/static/IR gates;
2. C# assembly/surface isolation guard;
3. Python/JavaScript/C# IR V3 receipt byte lock;
4. Python/JavaScript/C# Runtime Checkpoint V2 byte lock + restart;
5. Browser-WASM V3 AOT receipt/checkpoint parity;
6. WASI V3 receipt/checkpoint parity + fresh/restore continuation;
7. signed-update V3 host campaign;
8. signed-update V3 Browser-WASM campaign;
9. signed-update V3 WASI fresh/restore campaign;
10. complete V0.2 portable regression including Browser-WASM and WASI;
11. clean worktree before and after;
12. identical HEAD/tree throughout validation.

The Python distribution/product admission is intentionally available as the separate `RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py` gate. It does not replace the cross-host language/runtime precertification campaign.

Any V1/V3 `SKIPPED_*` is a pre-certification failure.

A successful pre-certify deliberately still emits:

```text
V1_PRECERTIFY=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

because technical validation and release/stable admission are separate governance operations.

## Verificación actual de esta sesión

The current branch has moved materially beyond earlier locally executed V3 ancestors. This ChatGPT execution environment cannot materialize and execute the exact GitHub checkout with the full local toolchain required for the repository's certification campaigns.

Therefore the current exact-HEAD status is deliberately:

```text
CODE_AND_GATES=PUBLISHED_CANDIDATE
CURRENT_HEAD_PYTHON_PRODUCTION_GATE=NOT_EXECUTED_HERE
CURRENT_HEAD_FULL_PRECERTIFY=NOT_EXECUTED_HERE
CURRENT_HEAD_CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Do not reinterpret implementation presence, static inspection or a previously passing ancestor as a fresh dynamic PASS for the current HEAD.

## Active falsifiable hypotheses

### H1 — source/path determinism

Permuting source input order or relocating source files must not change linked V1 bytes or target IR semantic identity.

### H2 — call-by-value preservation

Inlining a pure function argument containing an observation must invoke that observation exactly once.

### H3 — short-circuit preservation

An observation in an unselected `and/or` branch must never execute after lowering.

### H4 — composition-order preservation

Behavior fragment order follows explicit dependency/use order and is observable; reversing a semantically relevant `use` order must change linked identity.

### H5 — algebraic cross-host identity

Python, JavaScript, C#, Browser-WASM and WASI must produce the same canonical observable result for the same IR/scenario.

### H6 — checkpoint identity

Checkpoint V2 bytes/hash and restart continuation must agree across Python/JS/C#/WASI and reject target/source/type/value tampering.

### H7 — signed transition authority

A signed package for `from=A -> target=B` must never be applicable from C, even when channel/program/sequence are otherwise valid.

### H8 — capability ABI authority

Keeping a capability id while changing any parameter, return type or kind must be rejected unless the host ceiling explicitly authorizes that exact new ABI.

### H9 — update/store atomicity

A durable-store failure after runtime commit must restore the previous runtime before returning failure.

### H10 — V0.2 non-regression

No V1/V3 addition may alter the certified V0.2 semantic/runtime receipts.

### H11 — Python least authority

A Python production host must reject execution before startup when a required capability is missing and must reject surplus capability authority by default.

### H12 — Python wheel reproducibility

Two offline wheel builds from independent archives of the same exact commit, with the governed fixed build epoch, must produce the same filename and SHA-256 bytes.

## Tareas siguientes

1. Execute `RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py` on the exact current clean branch with Python 3.11+ and a locally available compatible setuptools build backend; fix any failure without weakening the gate.
2. Execute `RUN_TEV_SCRIPT_V1_PRECERTIFY.py` on the same exact current clean branch in the Windows development environment with Node, .NET, Chromium, Wasmtime and the .NET-required wasi-sdk available.
3. Fix every failure without weakening or skipping a gate.
4. Re-run from one exact clean commit/tree until the Python production gate and `V1_PRECERTIFY=PASS` both pass with zero skips.
5. Freeze the resulting evidence receipts and execute the separate read-only `CERTIFY_FULL` admission bound to that exact commit/tree.
6. Only after `CERTIFY_FULL` should a stable-admission commit be considered; that promoted commit must itself re-run the Python production gate, PRECERTIFY and CERTIFY_FULL rather than inheriting certification from its parent.

## Production boundaries unchanged

Even a V1 language/runtime `CERTIFY_FULL` would not by itself close production signing-key provisioning/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN deployment, physical Unity Input System/Animator providers, evolutionary self-assembly or decentralized peer-to-peer consensus/trust. Those are deployment/system-security surfaces, not missing language semantics.

For Python specifically, TEV execution budgets do not sandbox arbitrary embedding callbacks. If capability implementations are untrusted, failure-prone or tenant supplied, the embedding application must enforce process/container, OS-resource and external I/O controls outside the TEV runtime.
