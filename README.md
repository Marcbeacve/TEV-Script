# TEV Script

TEV Script is a bounded, statically typed, deterministic reactive language with explicit host-capability boundaries.

The language is not defined by Python, JavaScript, C#, Unity, Browser-WASM or WASI. Those are replaceable implementations/targets that are conformant only when they reproduce the canonical TEV semantics, canonical artifacts and governed receipts.

## Release status

This branch contains the **V1.0.0 stable-shaped release candidate S4**.

```text
LANGUAGE_VERSION=1.0.0
RELEASE_PROFILE=stable
RELEASE_STATUS=STABLE_1_0_0
STABLE_ADMISSION=REQUESTED
LANGUAGE_STABLE_CLAIM=REQUESTED
```

The claim above is not yet publication authority. Only `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` may make it authoritative for this exact Git identity. Until that gate emits `STABLE_ADMISSION=PASS`, no tag, main promotion, package publication or stable artifact substitution is authorized by the repository metadata alone.

The exact technically certified parent is P6:

```text
P_BRANCH=agent/tev-script-v1-stable-finalization-p6
P_COMMIT=9c79d43a082e8c609d4b85d2cadd5b462f488252
P_TREE=a242425c98945eda90a7b45e4ef11394ef423bd4
P_CERTIFY_FULL_V2_RECEIPT_SHA256=6c5b8e1ab243d4ccd2108c816c83542c6e3fec1b2a69efc0c09e4a85327c0e07
P_CERTIFY_FULL_V2_RECEIPT_FILE_SHA256=c8a8b6bd307431dc32db17a10640a2890ce6316e6eaebacf0b2dcfa6420d702a
P_PYTHON_CERTIFY_FULL_RECEIPT_SHA256=271d3fbdf6d1e9284b8fede03823fbff1c98ba3fab81a0e2dd1602420a5437c8
P_PYTHON_WHEEL_SHA256=9116ea8f80cc89b26cbff0581108935f905d260f430ef0cf719e0166475b4944
```

P6 passed candidate-profile global `CERTIFY_FULL`, Python `PYTHON_CERTIFY_FULL`, exact HEAD/TREE stability and clean-worktree checks on Windows. Its Python certification ran with Python 3.14.6 and explicit certification tooling (`jsonschema 4.26.0`, `setuptools 82.0.1`) while the TEV Python package itself kept zero runtime dependencies.

---

# Architecture

TEV Script keeps the certified V0.2 oracle and the V1 language/runtime profile separate and additive.

```text
V0.2
    certified bounded language/runtime oracle
    TEV_SCRIPT_PROGRAM_IR_V2

V1.0.0
    modules + imports + visibility
    pure functions
    records + enums + Option/Result
    exhaustive match
    statically bounded for
    behavior composition
    typed observation/effect capabilities
    deterministic multi-file linking
    TEV_SCRIPT_LINKED_PROGRAM_V1
        ├── losslessly erasable -> TEV_SCRIPT_PROGRAM_IR_V2
        └── full algebraic      -> TEV_SCRIPT_PROGRAM_IR_V3
```

Historical V0.2 language-completeness authority remains:

```text
COMMIT=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
```

The root `descriptor.json` remains the V0.2 descriptor. V1 introspection is versioned separately through `TEV_SCRIPT_DESCRIPTOR_V3` and `tev-script-v1-describe`.

## V2 implementation candidate

This branch also contains the additive TEV Script `2.0.0` implementation candidate.
V2 is governed independently by:

```text
spec/TEV_SCRIPT_V2_LANGUAGE.md
spec/TEV_SCRIPT_PROGRAM_IR_V4.md
spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md
spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json
schemas/tev-script-v2-*.schema.json
schemas/tev-script-program-ir-v4.schema.json
```

Its public interfaces are `python -m tev_script.cli_v2`, `tev-script-v2`,
`python -m tev_script.describe_v2`, and `tev-script-v2-describe`. The `descriptor`
command reports the same self-hashed candidate contract. V2 certification is
performed only by `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py`; a V1 certificate is retained
as regression evidence but is not V2 authority.

The V2 filesystem boundary pins an opened root directory identity, performs
no-follow handle-relative traversal, rejects an oversized `file.read` after consuming
at most the 1 MiB budget plus one witness byte, and linearizes `file.replace` with a
same-directory atomic rename. Unsupported secure primitives fail closed. None of
these candidate materials authorizes publication or merge.

## Canonical source-semantic path

```text
one V1 script root + zero or more V1 modules
    ↓
lexer / parser
    ↓
deterministic import linker
    ↓
name + visibility resolution
    ↓
nominal / constructed type analysis
    ↓
purity + capability-effect + event analysis
    ↓
constant evaluation
    ↓
behavior composition
    ↓
TEV_SCRIPT_LINKED_PROGRAM_V1
    ├── losslessly erasable profile ──→ TEV_SCRIPT_PROGRAM_IR_V2
    └── full algebraic profile ───────→ TEV_SCRIPT_PROGRAM_IR_V3
```

`TEV_SCRIPT_LINKED_PROGRAM_V1` is the canonical source-semantic authority. Runtime targets do not independently reinterpret imports, visibility or source naming.

---

# V1.0.0 language surface

## Source organization

```text
script root
module
import
export/private module declarations
```

Module identity comes from the declared module id, not from filesystem location. Source enumeration order and path relocation are non-semantic.

## Values

Primitive portable values:

```text
Bool
Int
Rat
Text
Vec2
Vec3
Unit
```

V1 adds nominal/constructed algebraic values:

```text
record
enum
Option<T>
Result<T,E>
```

Records and enums are nominal. `Option` and `Result` are built-in closed algebraic type families. `Unit` is capability-return-only and is not a storable state value.

## Computation

```text
fn                       pure user function
let                      immutable lexical binding
if / else                deterministic branch
for i in A .. B          statically bounded half-open integer iteration
match                    exhaustive enum/Option/Result matching
```

There is no recursion or unbounded loop in V1.0.0.

## Reactive state

```text
entity
state
on event(...)
emit event(...)
return
```

State is the explicit persistent mutable surface. Events are deterministic local event-machine messages, not implicit threads.

## Reuse and composition

```text
behavior
use
```

Behaviors are compile-time deterministic composition units, not classes, base classes or runtime trait objects.

## Host authority

```tevs
capability world.temperature(Vec2) -> Rat observation;
capability storage.deposit(Resource) -> Unit effect;
```

Capabilities are typed ports. External observation/effect authority is explicit instead of ambient host-object access.

---

# Deliberate V1.0.0 boundaries

V1.0.0 intentionally excludes:

```text
unbounded loops
recursion
async/await
threads / implicit concurrency
classes / inheritance
reflection
runtime code generation
runtime source compilation
user-defined generics
general user List/Map/Set containers
host-native object references
exceptions as normal language control flow
package-registry/network import resolution
wildcard imports
implicit re-export
```

These are governed language boundaries, not hidden implementation gaps.

---

# Quick start

Install the Python reference package from this source tree:

```powershell
python -m pip install .
```

The stable-shaped distributions are versioned `1.0.0`, while the historical V0.2 command remains preserved:

```text
tev-script       historical/certified V0.2 CLI
tev-script-v1    V1.0.0 CLI
```

Check a V1 program:

```powershell
tev-script-v1 check .\examples\v1\Calculator.tevs
```

Compile with automatic target selection:

```powershell
tev-script-v1 compile `
  .\examples\v1\Calculator.tevs `
  --target auto `
  -o .\Calculator.ir.json
```

Automatic target selection is semantic:

```text
V1 runtime surface is provably erasable to V0.2 values/opcodes
    -> TEV_SCRIPT_PROGRAM_IR_V2
otherwise
    -> TEV_SCRIPT_PROGRAM_IR_V3
```

Forcing IR V2 on a program that needs runtime algebraic values fails closed.

Multi-file linking uses an explicit finite source set:

```powershell
tev-script-v1 link `
  .\examples\v1\ecosystem\main.tevs `
  .\examples\v1\ecosystem\model.tevs `
  .\examples\v1\ecosystem\rules.tevs `
  .\examples\v1\ecosystem\storage.tevs `
  -o .\Ecosystem.linked.v1.json
```

---

# IR V3

IR V3 extends the bounded acyclic V0.2 machine with a closed type table and immutable algebraic values without introducing a general heap/object VM.

Algebraic instructions:

```text
MAKE_RECORD
LOAD_FIELD
MAKE_VARIANT
TEST_VARIANT
LOAD_VARIANT_PAYLOAD
```

The runtime remains explicitly typed and bounded:

```text
state
parameters
locals
stack
forward-only CFG
capability calls
event emission
RETURN
```

Validation covers strict JSON, closed/sorted type tables, nominal identities, capability/event ABI, canonical hashes, typed stack flow, definite locals, CFG merge consistency, algebraic opcode effects and forward-only control flow.

---

# Runtime implementations

## Python

The Python reference provides the V1 frontend/linker/static semantics, linked-program emitter, IR V2/V3 lowering, V3 validation/runtime, conformance receipts and Runtime Checkpoint V2.

Production deployment is deliberately split:

```text
build_python_program_v1 / build_python_program_v1_paths
    explicit build-time source -> canonical IR V3

PythonProgramArtifactV1
    validated canonical IR V3 deployment artifact

PythonRuntimeHostV1
    IR-only runtime host
    exact capability preflight
    least-authority binding by default
    serialized non-reentrant access
    RuntimeCheckpointV2 capture/restore
```

The Python project has **zero runtime dependencies**. For reproducible certified packaging, the repository contains an in-tree PEP 517 backend at `tools/tev_script_build_backend.py`:

```text
[build-system]
requires = []
build-backend = "tev_script_build_backend"
backend-path = ["tools"]
```

The backend uses only the Python standard library, packages the tracked `tev_script/*.py` module surface, creates canonical wheel metadata/entry points/RECORD content and fixes ZIP timestamps through `SOURCE_DATE_EPOCH`. Build-system regression requires two offline `pip wheel --no-build-isolation` builds to be byte-identical and tagged `py3-none-any`.

The stable-profile Python gate additionally requires a `1.0.0` package, zero frontend skips, isolated wheel installation, exact installed-module origin, least-authority rejection cases, reentrant/concurrent host-busy rejection, typed capability execution, checkpoint continuation and a deterministic 10,000-event soak.

`jsonschema` is certification tooling for the governed V0.2 Draft 2020-12 schema campaign; it is not a runtime dependency of the TEV Python package.

## JavaScript

`@tev-script/runtime` is versioned `1.0.0` in this release-shaped commit. The ES2022 runtime provides exact BigInt/rational semantics, V3 algebraic values, typed CFG validation, execution, conformance receipts and checkpoint V2 support. `STABLE_ADMISSION` runs `npm test`, `npm pack`, validates pack metadata/integrity and binds the exact tarball SHA-256.

## C# / Browser-WASM / WASI

`TevScript.Core` remains the V0.2 `netstandard2.1` runtime. `TevScript.Core.V3` is the additive deterministic V1/IR V3 `net8.0` assembly.

Global certification includes Python/JavaScript/C# canonical byte locks, Browser-WASM AOT receipt/checkpoint parity through managed-to-browser witness authority, and WASI fresh/restore process parity. Governed tests prohibit unintended network authority in the TEV V3 runtime/gates.

---

# Checkpoint and governed update model

Runtime Checkpoint V2 binds exact state to program id, IR/source semantic hashes, exact entity/state/type sets and canonical algebraic values. It is an exact-target restart mechanism, not arbitrary migration.

The V1 signed-update surface uses:

```text
TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2
TEV_SCRIPT_UPDATE_BODY_V2
TEV_SCRIPT_INSTALLED_UPDATE_V2
```

Updates authorize an exact transition `A -> B`, bind target IR/source identities and canonical IR bytes, validate candidate state/capability continuity and require rollback if durable-store commit fails.

---

# Certification and Stable Admission

TEV Script distinguishes implementation, technical certification, stable admission and publication.

## Technical certification

Candidate and stable profiles run the same mandatory semantic/cross-host campaign. The profile changes governance/release expectations only.

```powershell
python .\RUN_TEV_SCRIPT_V1_PRECERTIFY.py --profile stable
python .\RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile stable
```

Even a stable-profile technical certificate must end with:

```text
CERTIFY_FULL=PASS
LANGUAGE_STABLE=NO
```

because technical certification is not the release authority.

## Stable Admission

The only stable authority is:

```powershell
python .\RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py `
  --technical-parent-certificate <P6.certify-full-v2.json> `
  --artifact-out-dir <external-empty-release-dir>
```

It requires all of the following on this exact S4 commit:

1. stable release metadata and descriptor claims;
2. exact canonical `CERTIFY_FULL V2` receipt for P6;
3. recomputed P6 receipt SHA-256 equal to the certificate SHA embedded in S4;
4. exact P6 commit/tree and ancestry;
5. `P6..S4` changed-path set equal to the eight governed release files;
6. stable governance and `1.0.0` Python/JavaScript versions;
7. full global stable-profile `CERTIFY_FULL` on S4;
8. full Python stable-profile certification on S4;
9. exact externally exported Python wheel bytes;
10. JavaScript tests plus exact `npm pack` bytes and integrity metadata;
11. immutable S4 HEAD/tree throughout;
12. a canonical `TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_V1` binding all identities and artifact hashes.

Only this gate may terminate:

```text
CERTIFY_FULL=PASS
STABLE_ADMISSION=PASS
LANGUAGE_STABLE=YES
```

Until then, `stable=true` is a governed request awaiting admission.

---

# Publication identity

After `STABLE_ADMISSION(S4)=PASS`, the release identity is exactly S4. Preferred publication flow:

```text
fast-forward main -> exact S4 SHA
tag v1.0.0 -> exactly S4
publish the exact wheel/tarball bytes produced by Stable Admission
```

A squash, rebase or merge commit creates a different identity and cannot inherit S4's stable receipt.

No certification gate performs merge, tag or publication automatically.

---

# Documentation

Primary V1 references:

```text
docs/TEV_SCRIPT_V1_LANGUAGE_REFERENCE.md
docs/TEV_SCRIPT_V1_PROGRAMMING_MODEL.md
docs/V1_COMPILER_RUNTIME_BOUNDARY_DECISION.md
docs/V1_PROJECT_MANIFEST.md
docs/V1_LSP.md
docs/V1_PYTHON_PRODUCTION.md
docs/V1_CERTIFICATION_PROTOCOL.md
PROJECT_STATE.md
CANONICAL_INDEX.json
spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json
```

The examples under `examples/v1/` are executable test assets and learning material.

---

# Production-security boundary

Even `STABLE_ADMISSION=PASS` does not certify unrelated deployment/security surfaces such as production signing-key custody/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN operation, external registry operational security, physical Unity input/animation providers, decentralized consensus/trust or unrestricted self-modifying/evolutionary code.

Python capability implementations remain trusted embedding code. TEV instruction/event budgets do not sandbox arbitrary Python callbacks; untrusted callbacks require external process/container and resource isolation.

---

## TEV Script V2 stable-admission request

```text
V2_STABLE_ADMISSION=REQUESTED
V2_LANGUAGE_VERSION=2.0.0
V2_PYTHON_PACKAGE_VERSION=1.0.0
V2_TECHNICAL_PARENT_COMMIT=64d31f9c726ab82719a152bf551dc524abe82373
V2_TECHNICAL_PARENT_CERTIFICATE_SHA256=49ccf5f6e5c4bf9962ccc6823ecade5f61f616787d3f7c5f0b596b51d4ff1bc7
```

This is the release-only Phase S source shape. It is bound to the exact independently recertified technical parent above. The source claim remains pending until `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` emits `STABLE_ADMISSION=PASS`. No tag, package publication, or main promotion is implied by this metadata alone.

---

## TEVScript MAX 3.0.0 stable-admission request

```text
V3_STABLE_ADMISSION=REQUESTED
V3_LANGUAGE_VERSION=3.0.0
V3_TECHNICAL_PARENT_COMMIT=e858097c6610df6d11c58b90728cfb94f5785388
V3_TECHNICAL_PARENT_TREE=eb6ff8a052cd0db81be5e7949f6073012888034b
V3_TECHNICAL_RECEIPT_HASH=e2c9ba26f5ef891229c0796703f6b3e2adf71980491901f7b1832b55e3a46b4d
V3_TECHNICAL_RECEIPT_FILE_SHA256=4c3e5199ddbabab697520d8fa95fa6d4566876512e7e6c162da0b2ffcd1382f8
V3_TECHNICAL_V3_TEST_COUNT=94
V3_TECHNICAL_FULL_TEST_COUNT=1335
V3_TECHNICAL_SKIPPED_TESTS=0
V3_TECHNICAL_WHEEL_SHA256=0cb9828c634f3d9dce3b4b8ef2b6a90a548373a141c59fec22569b34cc7fbbc9
V3_PUBLICATION_AUTHORITY=NO_UNTIL_STABLE_ADMISSION
V3_MERGE_AUTHORITY=NO
```

The certified technical parent completed V3 focal and full-repository
regression with zero skips. This release-shaped commit changes only the
governed V3 stable-request whitelist and binds the exact external technical
certificate.

stable=true in the V3 release metadata is a Stable Admission request, not
publication authority. Only RUN_TEV_SCRIPT_V3_STABLE_ADMISSION.py may emit
V3_STABLE_ADMISSION=PASS and V3_LANGUAGE_STABLE=YES for the exact release
commit and exact final wheel. The Stable Admission receipt never grants merge
authority.
