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
V1 Python reproducible-wheel production admission:     CERTIFIED PROFILE AVAILABLE
V1 Python host-specific full certification:            PASS ON 5d2bd345... ONLY
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
V0.2 Browser-WASM/WASI global regression witnesses:    GATE IMPLEMENTED
V1 global PRECERTIFY V6 historical campaign:           PASS ON 49826a24... ONLY
V1 global CERTIFY_FULL V1 historical campaign:         PASS ON 49826a24... ONLY
V1 global technical candidate:                         CERTIFIED

Stage-D release metadata boundary:                     IMPLEMENTED CANDIDATE
Stage-D candidate/stable descriptor profiles:          IMPLEMENTED CANDIDATE
Stage-D PRECERTIFY V7 profiled:                         IMPLEMENTED CANDIDATE
Stage-D CERTIFY_FULL V2 profiled:                       IMPLEMENTED CANDIDATE
Stage-D Python production V2 profiled:                  IMPLEMENTED CANDIDATE
Stage-D Python certify V2 profiled:                     IMPLEMENTED CANDIDATE
Stage-D stable governance:                              IMPLEMENTED CANDIDATE
Stage-D exact parent-certificate binding:               IMPLEMENTED CANDIDATE
Stage-D release-diff confinement:                       IMPLEMENTED CANDIDATE
Stage-D exact artifact byte identity:                   IMPLEMENTED CANDIDATE
Stage-D stable-admission authority:                     IMPLEMENTED CANDIDATE
Stage-D authority regression campaign:                 IMPLEMENTED CANDIDATE

Python certified reference commit:                     5d2bd345b2bd0c852d95fbf2795566722186a67f
Python certified reference tree:                       059a6de31e977c3866ab7baa8e0ae39aa4c63842
Python certified wheel SHA256:                         1fa49b926e68d203e3528cc42ffb68cf0d179b98bb7cedc4a95f6b3102f18e05
Python certificate receipt SHA256:                     e59738a5d5631723449e3a4e8ff94a99df73081be0fd005d5191bbfd2186a0eb
PYTHON_CERTIFY_FULL(reference 5d2bd345...):             PASS

GLOBAL_TECHNICAL_CERTIFIED_COMMIT=49826a24c178c19f8868d968c51ddd89f02f0d93
GLOBAL_TECHNICAL_CERTIFIED_TREE=2255746adc3250fcdb1a0f41967911777fe990f2
GLOBAL_TECHNICAL_CERTIFICATE_SHA256=00e6325ad00abaea6a58112f7aa7130d1ba8e3b7feab61d120a81bb4ed887b1c
CERTIFY_FULL(reference 49826a24...)=PASS
LANGUAGE_STABLE(reference 49826a24...)=NO

CURRENT_STAGE=P_STABLE_ADMISSION_TOOLING
CURRENT_HEAD_CERTIFY_FULL=NO
STABLE_ADMISSION=NOT_REQUESTED
LANGUAGE_STABLE=NO
```

The global technical certificate above is identity-bound to `49826a24c178c19f8868d968c51ddd89f02f0d93`. That commit/tree is frozen Stage-C authority and is not modified by Stage D. The current branch adds the mechanism needed to admit a future stable release; it does **not** inherit the Stage-C certificate and it does not yet authorize `LANGUAGE_STABLE=YES`.

## Autoridad V0.2 preservada

The certified V0.2 language-completeness oracle remains:

```text
COMMIT=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
PARENT=6a33404eb9712b5fae30367d1beb189d8e42f170
TEV_SCRIPT_LANGUAGE_COMPLETE=PASS_CERTIFIED_LOCAL
```

V1 does not reinterpret those receipts. The root `descriptor.json` remains the historical V0.2 descriptor. The C# V0.2 assembly remains `TevScript.Core` targeting `netstandard2.1`; V3 is compiled as the additive `TevScript.Core.V3` assembly. Normal V3 runtime consumers reference only `TevScript.Core.V3`. Signed-update gates additionally reference the already existing `TevScript.Update` assembly solely to reuse the managed ES256 verifier authority; the V3 runtime itself does not depend on that cryptographic provider.

## Rama de trabajo actual

```text
BRANCH=agent/tev-script-v1-stable-admission-v1
BASE_CERTIFIED_V0_2=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
GLOBAL_CERTIFIED_REFERENCE=49826a24c178c19f8868d968c51ddd89f02f0d93
GLOBAL_CERTIFIED_REFERENCE_RECEIPT_SHA256=00e6325ad00abaea6a58112f7aa7130d1ba8e3b7feab61d120a81bb4ed887b1c
PYTHON_CERTIFIED_REFERENCE=5d2bd345b2bd0c852d95fbf2795566722186a67f
RELEASE_PROFILE=candidate
STABLE_RELEASE=NO
CURRENT_HEAD_CERTIFY_FULL=NO
STABLE_ADMISSION=NOT_REQUESTED
LANGUAGE_STABLE=NO
```

This branch is P: stable-admission tooling. It was created from the exact globally certified C commit but is a new Git identity. P must itself pass candidate-profile `CERTIFY_FULL V2` before it can become technical parent authority for a release-shaped S commit. No merge, PR, tag or stable publication follows merely from implementation presence.

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

The linked-program module normalizer consumes the actual `UnitIndexV1.kind` contract. The erroneous `unit_kind` consumer was removed rather than hidden behind a compatibility alias, and `tests/test_v1_linked_program_unit_kind_regression.py` locks that field contract with a real multi-module program.

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

V1 compilation remains split into semantic and runtime layers:

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
- V2 -> V3 verified lift preserving the certified primitive model;
- canonical integer lexical hardening includes explicit `-0` rejection;
- shared Python/JavaScript/C# IR-V3 negative corpus includes a negative-zero mutation.

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

`RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py` now has candidate/stable profiles while preserving the same runtime evidence. V2 receipts bind `admission_profile`, exact commit/tree, package version, reproducible wheel and full runtime witnesses. Stable profile additionally requires zero-skip frontend evidence and can export the already-certified wheel bytes to an external empty directory.

`RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py` V2 re-runs the matching production profile, independently verifies its receipt/hash, requires both reentrant and concurrent `TEVS_PYTHON_V1_HOST_BUSY` authority guards, and may export the same verified wheel. It always retains `global_certify_full=false` and `language_stable=false`; Python certification cannot self-promote the language.

The exact historical Python host/product profile remains dynamically certified on commit `5d2bd345b2bd0c852d95fbf2795566722186a67f`. That certificate is preserved as reference evidence but is not transitive to P or S.

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

The certified V0.2 JS runtime remains separate. Stage D does not change JS runtime semantics; a future S may change only `javascript/package.json` to version `1.0.0`, after which stable admission runs `npm test` and hashes the exact `npm pack` bytes.

### C#

Implemented `TevScript.Core.V3` as a separate deterministic `net8.0` assembly whose source set is explicit and whose normal runtime surface is dependency-free.

Hardening includes:

- no reflection in V3 runtime/conformance/checkpoint paths;
- strict duplicate-key JSON reader;
- closed object-tree JSON writer for AOT receipt generation rather than general serializer metadata;
- host-independent SHA-256 implementation for canonical identity;
- closed ASCII lexical predicates for AOT-portable identifiers/hashes/canonical integers;
- explicit `-0` rejection in the canonical integer helper;
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

A browser startup smoke is not sufficient for V3 parity. Managed code reports through explicit `JSImport`; console output remains diagnostic only and cannot authorize PASS.

## WASI V3

The WASI gate uses two separate Wasmtime processes:

1. `fresh`: execute/validate and write Runtime Checkpoint V2;
2. `restore`: start a fresh process, parse/restore the checkpoint and continue.

The gate compares receipt/checkpoint identity against the Python host oracle and verifies the checkpoint produced by WASI through the Python parser as a cross-implementation counterfactual. Host `-S http` remains linkage-only; governed regressions prohibit TEV Core V3/WASI gates from acquiring network authority through `System.Net`, `HttpClient` or sockets.

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

## Global certification profiles and Stage D

`RUN_TEV_SCRIPT_V1_PRECERTIFY.py` V7 accepts `--profile candidate|stable`, candidate by default. The dynamic campaign remains identical across profiles: zero-skip frontend, C# surface, Python/JS/C# byte locks, checkpoint restart, Browser-WASM, WASI, signed updates, independent V0.2 Browser/WASI witnesses, V0.2 portable regression, certification-time `jsonschema`, and immutable HEAD/tree. Only governance/release metadata expectations differ. Its receipt binds `admission_profile`, `certify_full=false`, `language_stable=false`.

`RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py` V2 accepts the same profiles. It validates profile-specific authority metadata, re-runs PRECERTIFY V7 with the same profile and emits a technical certificate with `certify_full=true`, `language_stable=false`. `--receipt-out` can persist the exact canonical certificate outside the repository; this is how P becomes verifiable parent authority for S.

`RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` is the only authority permitted to emit `LANGUAGE_STABLE=YES`. It requires:

1. a stable-shaped S with governed release metadata;
2. exact external candidate-profile `CERTIFY_FULL V2` receipt for technical parent P;
3. recomputed parent receipt SHA equal to S's embedded parent-certificate SHA;
4. parent commit/tree equality and ancestry;
5. P..S changed paths confined to the explicit release whitelist;
6. stable governance;
7. full global `CERTIFY_FULL --profile stable` on S;
8. full Python `PYTHON_CERTIFY_FULL --profile stable` on S;
9. exact exported Python wheel bytes;
10. `npm test` and exact `npm pack` bytes;
11. immutable S HEAD/tree throughout;
12. canonical `TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_V1` binding all identities/hashes.

Only a complete stable admission terminates:

```text
CERTIFY_FULL=PASS
STABLE_ADMISSION=PASS
LANGUAGE_STABLE=YES
```

Every subordinate technical gate continues to emit `LANGUAGE_STABLE=NO`.

## Verificación actual de esta sesión

Stage C is no longer pending. The exact global candidate C was dynamically certified by one clean campaign supplied by the operator:

```text
COMMIT=49826a24c178c19f8868d968c51ddd89f02f0d93
TREE=2255746adc3250fcdb1a0f41967911777fe990f2
V1_PRECERTIFY=PASS
CERTIFY_FULL=PASS
V1_CERTIFY_FULL_RECEIPT_SHA256=00e6325ad00abaea6a58112f7aa7130d1ba8e3b7feab61d120a81bb4ed887b1c
LANGUAGE_STABLE=NO
```

The current branch is a descendant P containing Stage-D tooling. It has changed certification/governance code and therefore **cannot inherit** C's certificate. Current exact-HEAD status remains deliberately:

```text
CODE_AND_GATES=STAGE_D_TOOLING_CANDIDATE
RELEASE_PROFILE=candidate
CURRENT_HEAD_CERTIFY_FULL=NO
STABLE_ADMISSION=NOT_REQUESTED
LANGUAGE_STABLE=NO
```

P must pass one candidate-profile global `CERTIFY_FULL V2` and persist that exact receipt externally before S is created.

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

### H13 — Python certification identity

A Python full certificate is valid only if the independently recomputed production receipt hash, embedded receipt hash, external receipt hash, certificate HEAD/tree and wheel identity all agree exactly and the repository remains unchanged throughout certification.

### H14 — global zero-skip evidence

Global PRECERTIFY must fail if any V1, IR V3 or selected V0.2 Python regression unittest is skipped, regardless of test-runner stdout/stderr formatting.

### H15 — global schema evidence

Global PRECERTIFY must fail when certification-time `jsonschema` is unavailable or when the V0.2 portable campaign does not emit exact `JSON_SCHEMA_VALIDATION=PASS`; this requirement must not become a runtime dependency of the Python wheel.

### H16 — canonical integer cross-host rejection

The shared IR V3 negative corpus must force Python, JavaScript and C# to reject `-0` as a non-canonical semantic integer.

### H17 — unique stable authority

No PRECERTIFY, global CERTIFY_FULL or Python certificate may emit `LANGUAGE_STABLE=YES`. Only a successful exact `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` may do so.

### H18 — parent-certificate binding

Stable admission must reject S if the supplied P receipt bytes, receipt hash, candidate profile, parent commit or parent tree differ from S's declared technical parent authority.

### H19 — release-diff confinement

Any P..S modification outside release metadata/documentation/distribution paths must make stable admission fail, even when the changed runtime happens to pass tests.

### H20 — exact publication bytes

The Python wheel and JavaScript tarball bound in the stable receipt must be the exact externally materialized bytes intended for publication; a later rebuild is not automatically equivalent.

## Tareas siguientes

1. Finish static audit of P and confirm governance/frontend tests contain no stable-profile skip or accidental self-promotion path.
2. Synchronize the exact final P branch to one clean isolated Windows checkout; do not alter the WIP checkout merely for certification.
3. Run **one** candidate-profile P campaign with receipt export:

```text
python RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile candidate --receipt-out <external/P.certify-full-v2.json>
```

4. Require `CERTIFY_FULL=PASS`, `LANGUAGE_STABLE=NO`, exact P HEAD/tree and externally recomputed P receipt SHA.
5. Only after P passes, create S from that exact P identity. S may change only the release whitelist: `CANONICAL_INDEX.json`, `CHANGELOG.md`, `PROJECT_STATE.md`, `README.md`, `javascript/package.json`, `pyproject.toml`, `spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json`, `tev_script/release_metadata_v1.py`.
6. S sets release profile/status/parent certificate, Python/JS `1.0.0`, stable target/matrix claims and release documentation. No parser/linker/runtime/gate change is permitted in S.
7. Execute once on exact S:

```text
python RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py --technical-parent-certificate <P receipt> --artifact-out-dir <external empty release dir>
```

8. Require exact stable receipt, global stable-profile recertification, Python stable-profile recertification, JS test/pack and artifact SHA equality.
9. Only after `STABLE_ADMISSION=PASS` and explicit operator authorization may main be fast-forwarded/tagged/published. Prefer `v1.0.0` pointing exactly at S and publish only the certified artifact bytes.
10. Do not merge, tag, publish or mark stable before that explicit authorization.

## Production boundaries unchanged

Even a successful stable admission would not by itself close production signing-key provisioning/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN deployment, physical Unity Input System/Animator providers, evolutionary self-assembly or decentralized peer-to-peer consensus/trust. Those are deployment/system-security surfaces, not missing language semantics.

For Python specifically, TEV execution budgets do not sandbox arbitrary embedding callbacks. If capability implementations are untrusted, failure-prone or tenant supplied, the embedding application must enforce process/container, OS-resource and external I/O controls outside the TEV runtime.
