# [ESTADO ACTUAL DEL PROYECTO]

## Estado canónico actual

```text
PUBLISHED_PACKAGE_VERSION=3.1.0
PUBLISHED_LANGUAGE_VERSION=3.1.0
PUBLISHED_PROFILE=total_core
PUBLISHED_TAG=v3.1.0
PUBLISHED_COMMIT=c20718ddb2223ba0bfd05ff59006ca31e2966b0b
PUBLISHED_TREE=812b140c5e6fb7232ef379773d9c37e8f3459f4c
PUBLISHED_STABLE_ADMISSION=PASS

PLATFORM_CANDIDATE_PACKAGE_VERSION=3.1.1
PLATFORM_CANDIDATE_LANGUAGE_VERSION=3.1.0
PLATFORM_CANDIDATE_PROFILE=total_core
PLATFORM_CANDIDATE_BRANCH=agent/tevscript-platform-completion-v1
MERGE_AUTHORITY=FALSE
PUBLICATION_AUTHORITY=FALSE
TAG_AUTHORITY=FALSE
```

`3.1.1` is a platform/tooling completion patch over unchanged Total-Core language semantics `3.1.0`. The published `v3.1.0` package/tag remains immutable predecessor authority.

## Progreso del cierre de plataforma

```text
Canonical package/language/profile version domains:    IMPLEMENTED
Public __version__ / CLI version binding:               IMPLEMENTED
Normative 3.1 platform integration:                     IMPLEMENTED
Content-addressed normative authority set:              IMPLEMENTED
Explicit Language/IR/Runtime/ABI/checkpoint matrix:     IMPLEMENTED
Root-bound authority/entrypoint validation:             IMPLEMENTED
Current generic Total-Core CLI:                         IMPLEMENTED
Current Total-Core LSP:                                 IMPLEMENTED
Semantic-area conformance manifest:                     IMPLEMENTED
Deterministic Total-Core differential fuzzing:          IMPLEMENTED
Direct Total-Core constitutional witnesses:             IMPLEMENTED
Clean-source reproducible wheel gate:                   IMPLEMENTED
SBOM + provenance + conformance/environment binding:    IMPLEMENTED
Full repository zero-skip regression gate:              IMPLEMENTED
Release/regression exact source identity binding:       IMPLEMENTED
Sealed receipt verifiers:                               IMPLEMENTED
Completion/full-regression receipt V2 schemas:          IMPLEMENTED
PyPI Markdown long-description metadata:                IMPLEMENTED
Nine-gate aggregate completion authority:               IMPLEMENTED

FULL_REPOSITORY_REGRESSION_IN_CONNECTOR_ENVIRONMENT:     NOT EXECUTED
PLATFORM_COMPLETION_CERTIFICATION:                       PENDING CLEAN CHECKOUT
```

The connector/container used for implementation cannot materialize the complete GitHub checkout because its local network path cannot resolve GitHub. Focused and synthetic TDD was used to build and falsify individual platform organs; those checks are development evidence only and are not promoted to full-repository certification.

## Completion authority

The exact aggregate gate order is:

```text
VERSION_IDENTITY
NORMATIVE_SPEC
VERSION_MATRIX
TOOLING_3X
CONFORMANCE
DIFFERENTIAL_FUZZ
SEMANTIC_INVARIANTS
REPRODUCIBLE_RELEASE
FULL_REGRESSION
```

Only nine simultaneous PASS values on one exact clean commit/tree may emit:

```text
PLATFORM_COMPLETION=PASS
```

`FULL_REGRESSION` requires a non-empty pytest suite, zero failures, zero errors and zero skips; it binds JUnit bytes, HEAD/tree and worktree cleanliness before/after execution. Its source identity must equal the source identity from `REPRODUCIBLE_RELEASE`. The aggregate and full-regression receipts are both sealed, externally verifiable V2 receipts.

A FAIL blocks completion. A HOLD remains HOLD. The completion receipt never grants merge, tag, release or stable-promotion authority.

Authoritative execution from a complete clean checkout:

```powershell
python .\RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py `
  --receipt .\TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT.json
```

## Current architecture

```text
.tevs 3.1 Total-Core project
        ↓
current generic CLI / current Total-Core LSP
        ↓
compile_total_core_v31
        ↓
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
        ↓
validated V4 child units + Field / Transformation / Apply
        ↓
bounded quantum execution
        ↓
content-addressed checkpoint / continuation / receipts
        ↓
Python reference runtime ⇄ independent JavaScript witness
```

Production runtimes execute validated canonical IR/artifacts only. Source declarations never grant physical authority; effects cross explicit capabilities/providers. Exact `Int`/`Rat`, bounded execution, canonical identity, replay and cross-runtime equivalence remain constitutional properties.

## Current documentation / authority map

```text
README.md
docs/STATUS.md
docs/TEV_SCRIPT_3_1_PLATFORM_COMPLETION.md
spec/TEV_SCRIPT_3_1_PLATFORM.md
spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json
spec/TEV_SCRIPT_VERSIONING.md
spec/TEV_SCRIPT_VERSION_MATRIX.json
conformance/v31-platform-manifest.json
schemas/tev-script-platform-full-regression-v2.schema.json
schemas/tev-script-platform-completion-receipt-v2.schema.json
RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py
```

---

# Historical V1/S4 project-state snapshot — preserved

The material below is retained as historical release-line evidence. It is not the current project state.

## Progreso histórico

```text
V0.2 exact source grammar / static semantics:          PASS CERTIFIED LOCAL
V0.2 source -> IR V2 closure:                          PASS CERTIFIED LOCAL
V0.2 Python / JavaScript / C# conformance:             PASS CERTIFIED LOCAL
V0.2 Unity Editor / PlayMode / Mono / IL2CPP:          PASS CERTIFIED LOCAL
V0.2 Browser-WASM / WASI / distributed determinism:    PASS CERTIFIED LOCAL
V0.2 language completeness:                            PASS CERTIFIED LOCAL

V1 lexical / grammar / semantic contract:              CLOSED
V1 deterministic multi-file linker:                    IMPLEMENTED
V1 nominal + constructed type system:                  IMPLEMENTED
V1 scopes / purity / effects / events:                 IMPLEMENTED
V1 constants / behaviors / bounded control flow:       IMPLEMENTED
V1 canonical linked semantic program:                  IMPLEMENTED
V1 erasable source semantics -> IR V2:                 IMPLEMENTED
V1 full algebraic source semantics -> IR V3:           IMPLEMENTED
IR V3 closed type table / codec / validator / CFG:     IMPLEMENTED
IR V3 Python / JavaScript / C# runtimes:               IMPLEMENTED
Runtime Checkpoint V2 cross-runtime:                   IMPLEMENTED
Browser-WASM AOT / WASI fresh-restore:                 IMPLEMENTED
Transactional hot swap / signed update V2/V3:          IMPLEMENTED
Python hermetic in-tree wheel backend:                 IMPLEMENTED + P6 CERTIFIED

Technical parent P6:                                   PASS CERTIFIED LOCAL
P6 Global CERTIFY_FULL candidate profile:              PASS
P6 Python CERTIFY_FULL candidate profile:              PASS
P6 worktree / HEAD / TREE stability:                   PASS

Stage-D release-shaped S4 metadata:                    PREPARED
Stage-D stable admission on S4:                        REQUESTED / NOT YET EXECUTED
Python package version in S4:                          1.0.0
JavaScript package version in S4:                      1.0.0
V1 language version:                                   1.0.0

V2 source language / static semantics:                 NORMATIVE CANDIDATE AUTHORITY
Program IR V4 schemas / contracts:                     IMPLEMENTED
V2 CLI + self-hashed descriptor:                       IMPLEMENTED
V2 filesystem handle-relative safety:                  IMPLEMENTED
V2 file.read 1 MiB pre-admission:                      IMPLEMENTED
V2 TOCTOU race negatives / fail-closed coverage:       IMPLEMENTED
V2 independent CERTIFY_FULL gate:                      IMPLEMENTED
V2 publication / PR / merge authority:                 NOT GRANTED
```

V2 has its own feature matrix, schemas, conformance vectors, filesystem-safety gate,
and exact-identity certification receipt. The V1 gates remain mandatory regression
evidence, but they cannot substitute for `CERTIFY_V2`. Certification receipts are
written outside the repository so certification cannot mutate the identity it
attests.

## Verificación / autoridades exactas históricas

### V0.2 oracle preservado

```text
BASE_CERTIFIED_V0_2=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
BASE_CERTIFIED_V0_2_TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
```

The root `descriptor.json` remains historical V0.2 authority. V1 does not overwrite or reinterpret it.

### Technical parent P6

P6 is the exact technical parent for this stable-shaped release. It was certified from a clean Windows checkout after closing the historical `bdist_wheel` environmental dependency with an in-tree, stdlib-only PEP 517 wheel backend.

```text
TECHNICAL_PARENT_BRANCH=agent/tev-script-v1-stable-finalization-p6
TECHNICAL_PARENT_COMMIT=9c79d43a082e8c609d4b85d2cadd5b462f488252
TECHNICAL_PARENT_TREE=a242425c98945eda90a7b45e4ef11394ef423bd4
TECHNICAL_PARENT_CERTIFICATE_SCHEMA=TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2
TECHNICAL_PARENT_CERTIFICATE_SHA256=6c5b8e1ab243d4ccd2108c816c83542c6e3fec1b2a69efc0c09e4a85327c0e07
TECHNICAL_PARENT_CERTIFICATE_FILE_SHA256=c8a8b6bd307431dc32db17a10640a2890ce6316e6eaebacf0b2dcfa6420d702a
TECHNICAL_PARENT_PROFILE=candidate
TECHNICAL_PARENT_CERTIFY_FULL=PASS
TECHNICAL_PARENT_LANGUAGE_STABLE=NO
```

The canonical certificate SHA above is the SHA-256 of the canonical JSON receipt bytes. It is the authority embedded into this S commit. The physical receipt-file SHA is recorded separately and is not substituted for the canonical certificate identity.

### P6 Python product certificate

```text
P6_PYTHON_CERTIFY_FULL_RECEIPT_SHA256=271d3fbdf6d1e9284b8fede03823fbff1c98ba3fab81a0e2dd1602420a5437c8
P6_PYTHON_PRODUCTION_RECEIPT_SHA256=3bce21be43f5092a2d95d9b76482e32da99764e8c38b113b87eec315cc970594
P6_PYTHON_WHEEL=tev_script_portable_reference-0.2.0-py3-none-any.whl
P6_PYTHON_WHEEL_SHA256=9116ea8f80cc89b26cbff0581108935f905d260f430ef0cf719e0166475b4944
P6_PYTHON_VERSION=3.14.6
P6_CERTIFICATION_JSONSCHEMA_VERSION=4.26.0
P6_CERTIFICATION_SETUPTOOLS_VERSION=82.0.1
```

These are candidate-profile P6 identities. They are evidence for the parent, not publication artifacts for V1.0.0. Stable Admission will rebuild and re-certify the exact S4 `1.0.0` wheel and JavaScript tarball and bind their bytes into the stable-admission receipt.

## Rama / release shape histórica

```text
BRANCH=agent/tev-script-v1-stable-release-1-0-0-v4
CURRENT_STAGE=S_STABLE_RELEASE_SHAPE
RELEASE_PROFILE=stable
RELEASE_STATUS=STABLE_1_0_0
LANGUAGE_VERSION=1.0.0
PYTHON_PACKAGE_VERSION=1.0.0
JAVASCRIPT_PACKAGE_VERSION=1.0.0
STABLE_ADMISSION=REQUESTED
LANGUAGE_STABLE_CLAIM=REQUESTED
CERTIFY_FULL_CLAIM=REQUESTED
TAG_CREATED=NO
MERGED_TO_MAIN=NO
PUBLISHED=NO
```

The `stable=true` metadata is deliberately a claim awaiting admission. It does not itself establish `LANGUAGE_STABLE=YES`. Only a successful exact Stable Admission receipt for this S identity can authorize that conclusion.

## S4 release-diff confinement histórico

S4 must differ from P6 in exactly these eight paths and no others:

```text
CANONICAL_INDEX.json
CHANGELOG.md
PROJECT_STATE.md
README.md
javascript/package.json
pyproject.toml
spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json
tev_script/release_metadata_v1.py
```

No parser, linker, static semantic, compiler, IR, runtime, C#, Browser-WASM, WASI, signed-update implementation, test, build backend, or certification-gate change is permitted in S4. Any technical failure requiring such a change invalidates S4 and requires a new technically certified parent.

## Log de cambios histórico

1. The historical V1 technical base was integrated to `main` without claiming language stability.
2. The old release-shaped S2 remained bound to an obsolete technical parent and was not reused.
3. The P4 attempt exposed that `PYTHONNOUSERSITE=1` made ambient Setuptools unavailable; P4 was rejected rather than weakening isolation.
4. P6 replaced ambient wheel-building authority with `tools/tev_script_build_backend.py`, an in-tree stdlib-only deterministic PEP 517 backend.
5. P6 build-system regression verified two offline `pip wheel --no-build-isolation` builds are byte-identical and `py3-none-any`.
6. P6 PRECERTIFY exposed `jsonschema` as explicit certification tooling rather than runtime dependency. Certification was rerun inside a frozen certification venv while keeping TEV runtime dependencies at zero.
7. Exact P6 passed global and Python candidate-profile certification with stable HEAD/TREE and a clean worktree.
8. S4 changes only governed release metadata/documentation/version paths and binds the exact P6 canonical certificate SHA.

## Canonical V1 source/runtime boundary histórico

```text
V1 source set
   -> exact lexical/parser contract
   -> deterministic multi-file linker
   -> static semantics
   -> TEV_SCRIPT_LINKED_PROGRAM_V1
        |-> losslessly erasable -> TEV_SCRIPT_PROGRAM_IR_V2
        |-> full algebraic      -> TEV_SCRIPT_PROGRAM_IR_V3
```

Key V1.0.0 language surface:

- modules, imports and explicit export/private visibility;
- nominal records and enums;
- built-in `Option<T>` and `Result<T,E>`;
- pure user functions with acyclic bounded call graphs;
- immutable lexical `let` bindings;
- exhaustive algebraic `match`;
- statically bounded half-open integer `for`;
- deterministic behavior composition;
- typed observation/effect capabilities;
- explicit entity state/events;
- exact `Int` and `Rat` semantics;
- no recursion, unbounded loops, reflection, dynamic code, hidden host objects or implicit concurrency.

## Runtime / portability model histórico

IR V3 keeps the finite acyclic machine model and adds closed immutable algebraic values through a canonical type table. Runtime implementations are Python, JavaScript and C#; global certification also covers Browser-WASM AOT, WASI fresh/restore, checkpoint parity and governed signed updates.

The Python distribution uses an in-tree PEP 517 backend whose build requirements are empty. The backend is packaging authority only; it does not participate in TEV language semantics or runtime execution. Python project runtime dependencies remain exactly zero.

## Hipótesis falsables históricas

### H1 — exact parent binding
Stable Admission must reject any mismatch in P6 certificate bytes, canonical receipt SHA, commit or tree.

### H2 — exact release diff
Any missing required release path or any ninth changed path in `P6..S4` must fail Stable Admission.

### H3 — stable-profile non-self-promotion
`PRECERTIFY`, global `CERTIFY_FULL` and Python `CERTIFY_FULL` may pass on S4 but must continue to emit `LANGUAGE_STABLE=NO`.

### H4 — deterministic distribution
Independent S4 Python wheel builds from the exact source must produce byte-identical `py3-none-any` artifacts.

### H5 — isolated installed execution
The admitted S4 wheel must install into a fresh environment without runtime dependencies and execute the governed CLI/runtime/checkpoint/authority campaign from the installed package.

### H6 — cross-host identity
Python, JavaScript, C#, Browser-WASM and WASI must preserve governed canonical bytes, receipts and checkpoint identities.

### H7 — exact publication bytes
A later rebuild must not silently replace the Python wheel or JavaScript tarball whose hashes were admitted by Stable Admission.

### H8 — V0.2 non-regression
No V1 release operation may alter or reinterpret the certified V0.2 semantic/runtime oracle.

## Tareas históricas

1. Materialize a clean checkout of exact S4.
2. Preserve the exact canonical P6 receipt file generated during certification.
3. Use a certification Python environment that provides the explicitly required Draft 2020-12 `jsonschema` tooling; this tooling is not a TEV runtime dependency.
4. Create a fresh empty external artifact directory.
5. Execute:

```text
python RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py --technical-parent-certificate <P6 canonical receipt file> --artifact-out-dir <external empty release dir>
```

6. Require exact S4 HEAD/tree stability, exact eight-path confinement, `CERTIFY_FULL=PASS`, `STABLE_ADMISSION=PASS`, `LANGUAGE_STABLE=YES` and a canonical stable-admission receipt SHA-256.
7. Preserve the exact admitted Python wheel, JavaScript tarball and stable receipt bytes.
8. Only after successful Stable Admission may the operator separately authorize fast-forward of `main`, creation of tag `v1.0.0` exactly at S4 and publication of those exact artifacts.

## Production boundaries unchanged

A successful language/runtime stable admission does not certify unrelated deployment/security surfaces such as signing-key custody/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN operation, external registry security, physical Unity providers, decentralized consensus/trust or unrestricted self-modifying code.

Python capability implementations remain trusted embedding code. Untrusted callbacks require process/container, OS-resource and I/O controls outside the TEV runtime.

---

## TEV Script V2 stable-admission request histórico

```text
V2_STABLE_ADMISSION=REQUESTED
V2_LANGUAGE_VERSION=2.0.0
V2_PYTHON_PACKAGE_VERSION=1.0.0
V2_TECHNICAL_PARENT_COMMIT=64d31f9c726ab82719a152bf551dc524abe82373
V2_TECHNICAL_PARENT_CERTIFICATE_SHA256=49ccf5f6e5c4bf9962ccc6823ecade5f61f616787d3f7c5f0b596b51d4ff1bc7
```

This is the historical release-only Phase S source shape. It is retained as predecessor evidence and is not current platform state.
