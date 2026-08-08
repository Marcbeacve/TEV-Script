# TEV Script

TEV Script is a bounded, statically typed, deterministic reactive language with explicit host-capability boundaries.

The language is not defined by Python, JavaScript, C#, Unity, Browser-WASM or WASI. Those are replaceable implementations/targets that are conformant only when they reproduce the canonical TEV semantics and receipts.

TEV Script currently has two important layers in this repository:

```text
V0.2
    certified bounded language/runtime oracle
    TEV_SCRIPT_PROGRAM_IR_V2

V1 candidate
    modules + pure functions + records/enums + Option/Result
    behavior composition + bounded for + exhaustive match
    deterministic linked semantic program
    TEV_SCRIPT_PROGRAM_IR_V2 when V1 abstractions are losslessly erasable
    TEV_SCRIPT_PROGRAM_IR_V3 for full algebraic runtime semantics
```

**V1 is an implementation candidate, not yet a stable release.** The repository intentionally keeps technical implementation, host-specific certification, global certification and stable-release admission as separate states.

---

## Architecture

### V0.2 certified path

```text
.tevs V0.2 source
    -> exact V0.2 frontend
    -> TEV_SCRIPT_PROGRAM_IR_V2
    -> conforming runtime
```

The certified V0.2 language-completeness oracle is:

```text
COMMIT=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
TREE=4d97cc4c50096325c6ccb1f36edf22afebea19fc
```

V1 work does not reinterpret that historical certification.

### V1 source-semantic path

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

`TEV_SCRIPT_LINKED_PROGRAM_V1` is the canonical source-semantic authority. Runtime backends do not independently reinterpret imports, visibility or source naming.

---

## V1 language surface

V1 adds a substantial programming model while preserving boundedness and deterministic execution.

### Source organization

```text
script root
module
import
export/private module declarations
```

Module identity comes from the declared module id, not a filesystem path.

### Values

Primitive portable values remain:

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
record
enum
Option<T>
Result<T,E>
```

Records/enums are nominal. `Option`/`Result` are built-in closed algebraic type families. `Unit` is capability-return-only and is not a storable value.

### Computation

```text
fn                       pure user function
let                      immutable lexical binding
if / else                deterministic branch
for i in A .. B          statically bounded half-open integer iteration
match                    exhaustive enum/Option/Result matching
```

There is no recursion or unbounded loop in V1.0.

### Reactive state

```text
entity
state
on event(...)
emit event(...)
return
```

State is the explicit persistent mutable surface. Events are deterministic local event-machine messages, not threads.

### Reuse/composition

```text
behavior
use
```

Behaviors are compile-time deterministic composition units, not classes, base classes or runtime trait objects.

### Host authority

```tevs
capability world.temperature(Vec2) -> Rat observation;
capability storage.deposit(Resource) -> Unit effect;
```

Capabilities are typed ports. They make external observations/effects visible in the language contract instead of granting ambient host-object access.

---

## What V1 deliberately does not add

V1.0 intentionally excludes:

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

These are not hidden implementation gaps. Each would enlarge the semantic and verification surface and therefore requires a separate language revision.

---

# Quick start

## Python package

From the repository root:

```powershell
python -m pip install -e .
```

Two command surfaces are deliberately kept separate:

```text
tev-script       V0.2 certified CLI
tev-script-v1    V1 implementation-candidate CLI
```

The V1 work does not silently replace the V0.2 command.

---

## V1: check a program

```powershell
tev-script-v1 check .\examples\v1\Calculator.tevs
```

`check` performs the complete source-semantic pipeline and reports:

```text
program_id
linked_semantic_hash
static_semantic_hash
whether IR V2 is losslessly available
IR V2 blocker count
default runtime IR
```

---

## V1: compile with automatic target selection

```powershell
tev-script-v1 compile `
  .\examples\v1\Calculator.tevs `
  --target auto `
  -o .\Calculator.ir.json
```

`auto` is semantic, not heuristic:

```text
V1 runtime surface is provably erasable to V0.2 values/opcodes
    -> TEV_SCRIPT_PROGRAM_IR_V2

otherwise
    -> TEV_SCRIPT_PROGRAM_IR_V3
```

A programmer may also force a target:

```powershell
tev-script-v1 compile source.tevs --target irv2 -o program.json
tev-script-v1 compile source.tevs --target irv3 -o program.json
```

Forcing IR V2 on a V1 program requiring runtime records/enums/Option/Result fails closed rather than creating a lossy encoding.

---

## V1: link a multi-file program

The source set is explicit and finite:

```powershell
tev-script-v1 check `
  .\examples\v1\ecosystem\main.tevs `
  .\examples\v1\ecosystem\model.tevs `
  .\examples\v1\ecosystem\rules.tevs `
  .\examples\v1\ecosystem\storage.tevs
```

To emit canonical source semantics:

```powershell
tev-script-v1 link `
  .\examples\v1\ecosystem\main.tevs `
  .\examples\v1\ecosystem\model.tevs `
  .\examples\v1\ecosystem\rules.tevs `
  .\examples\v1\ecosystem\storage.tevs `
  -o .\Ecosystem.linked.v1.json
```

Input source order and physical file relocation must not change canonical linked bytes when semantics are unchanged.

---

# V1 examples

The examples under `examples/v1/` are executable test assets, not illustrative pseudocode.

```text
Calculator.tevs
    enum + Result + exhaustive match + exact Rat arithmetic

ErasableToIrV2.tevs
    V1 fn + behaviors + bounded for, but runtime surface erases to IR V2

AlgebraicCapability.tevs
    record + enum + Option/Result + algebraic capability ABI -> IR V3

ecosystem/
    complete multi-module domain/rules/capability/root decomposition
```

See:

```text
examples/v1/README.md
```

for commands and learning order.

---

# IR V3

IR V3 extends the bounded acyclic V0.2 runtime model without turning it into a general heap/object VM.

It adds a closed type table and immutable algebraic values.

## Algebraic instructions

```text
MAKE_RECORD
LOAD_FIELD
MAKE_VARIANT
TEST_VARIANT
LOAD_VARIANT_PAYLOAD
```

The rest of the machine remains explicitly typed and bounded:

```text
state
parameters
locals
stack
forward-only CFG
pure calls
capability calls
event emission
RETURN
```

No runtime reflection, host object reference or code generation is introduced.

---

## IR V3 verification

A V3 program is validated before execution for:

- strict JSON shape and duplicate keys;
- exact profile/boundary values;
- closed and sorted type table;
- nominal/constructed type references;
- state/capability/event ABI;
- canonical semantic/source hashes;
- typed stack flow;
- definite local initialization;
- CFG merge consistency;
- algebraic opcode stack effects;
- forward-only control flow.

---

# Runtime implementations

## Python

The Python reference contains:

```text
V1 frontend/linker/static semantics
canonical linked-program emitter
IR V2 and IR V3 lowering
IR V3 validator/type/value model
IR V3 runtime
checkpoint V2
conformance receipt runner
```

For deployment, V1 now has a separate Python production surface:

```text
PythonProgramArtifactV1
    validated canonical TEV_SCRIPT_PROGRAM_IR_V3 artifact

PythonRuntimeHostV1
    IR-only execution host
    exact capability preflight
    least-authority binding by default
    RuntimeCheckpointV2 capture/restore

build_python_program_v1 / build_python_program_v1_paths
    explicit build-time source -> IR V3 helpers
```

The production host does not accept source and does not compile at runtime. Physical authority enters only through explicit capability bindings; surplus authority is rejected by default.

Python also has two exact-commit product gates:

```text
RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
    reproducible-wheel + isolated-runtime admission

RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py
    read-only Python-host certificate authority over the production receipt
```

The Python certificate is intentionally host-specific: it may assert `PYTHON_CERTIFY_FULL=PASS` while global `CERTIFY_FULL=NO` and `LANGUAGE_STABLE=NO`. See `docs/V1_PYTHON_PRODUCTION.md`.

## JavaScript

The ES2022 V3 runtime provides exact `BigInt`/rational semantics, V3 type/value validation, typed CFG, runtime execution, conformance receipt and checkpoint V2 support.

The V0.2 JavaScript runtime remains separately usable.

## C#

The repository deliberately keeps two assemblies:

```text
TevScript.Core
    certified V0.2 runtime
    netstandard2.1

TevScript.Core.V3
    additive V1/IR V3 runtime candidate
    net8.0
```

Normal V3 runtime consumers do not depend on the signed-update cryptographic provider.

Signed-update gates additionally bind the existing managed ES256 verifier through `TevScript.Update`.

## Browser-WASM

The V3 Browser-WASM gate AOT-compiles the C# V3 runtime and must reproduce host-oracle conformance-receipt and checkpoint hashes through an authenticated loopback witness.

A page-load smoke is not treated as runtime parity. The managed gate reports its
result through an explicit `JSImport` witness; console interception remains
diagnostic only and is not certification authority. The portable V3 assembly
uses closed ASCII lexical predicates instead of a regular-expression runtime,
so identifier, hash and canonical-number admission is identical under native,
Browser-WASM AOT and WASI execution.

## WASI

The V3 WASI gate uses separate `fresh` and `restore` Wasmtime processes. The first writes a canonical checkpoint; the second starts from a new process, restores it and continues execution. Wasmtime is invoked with `-S http` solely to satisfy .NET WASI host linkage; this does not grant a TEV capability or semantic authority.

---

# Runtime Checkpoint V2

Checkpoint V2 binds exact runtime state to:

```text
program_id
IR schema
IR semantic_hash
source schema
source semantic_hash
exact entity set
exact state set
state type
canonical algebraic value
```

It is an exact-target restart mechanism, not a generic arbitrary-program migration format.

Python, JavaScript and C# implementations exist, with cross-runtime byte-lock gates. WASI additionally transports the checkpoint between separate processes.

---

# Governed updates V3

V3 does not reinterpret the historical V0.2 update package. It defines additive contracts:

```text
TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2
TEV_SCRIPT_UPDATE_BODY_V2
TEV_SCRIPT_INSTALLED_UPDATE_V2
```

A signed transition binds:

```text
channel
program
epoch + sequence
from_ir_semantic_hash
target_ir_semantic_hash
target_source_semantic_hash
target canonical IR SHA-256
target canonical IR
signature algorithm / key id / signature
```

This means an update authorizes the exact transition:

```text
A -> B
```

not merely “install B from any prior state”.

The transactional runtime layer validates a candidate in isolation, validates state migration and the full capability ABI ceiling, then performs one authoritative commit. If durable-store commit fails, runtime rollback is required.

Host, Browser-WASM and WASI signed-update gates are implemented as certification candidates.

---

# Determinism

The V1 model requires semantic identity to remain invariant under changes that are not program meaning, including:

```text
source path relocation
input source enumeration order
filesystem ordering
path separator
locale
timezone
host dictionary iteration order
```

Meaningful order remains meaningful, including:

```text
statement order
behavior use order
function argument order
record constructor expression order
event order
```

Exact integers and rationals are never delegated to host floating-point conventions.

---

# Documentation

Programmer-facing V1 documentation:

```text
docs/TEV_SCRIPT_V1_LANGUAGE_REFERENCE.md
    full language reference

docs/TEV_SCRIPT_V1_PROGRAMMING_MODEL.md
    TEV-native architecture, design patterns and data structures

docs/V1_PYTHON_PRODUCTION.md
    Python IR-only deployment boundary, least-authority host, production admission and host-specific certification

examples/v1/README.md
    executable learning path and CLI usage
```

Compiler/runtime architecture:

```text
docs/V1_COMPILER_RUNTIME_BOUNDARY_DECISION.md
docs/V1_IMPLEMENTATION_PLAN.md
```

Certification/governance:

```text
docs/V1_CERTIFICATION_PROTOCOL.md
PROJECT_STATE.md
CANONICAL_INDEX.json
spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json
```

Historical V0.2 validation remains documented under the existing V0.2 specs and `docs/VALIDATION.md`.

---

# Validation levels

TEV Script deliberately distinguishes implementation from host certification, global certification and stable release.

## Development closure

```powershell
python .\RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py
```

This covers the Python V1 source-semantic/lowering suite, V3 Python tests, V1 CLI/examples and selected V0.2 Python regressions.

## Python production admission

```powershell
python .\RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
```

This gate is bound to one exact clean commit. It validates governance and the Python closure, builds two wheels from independent `git archive HEAD` trees with an offline fixed build environment, requires identical wheel bytes and the portable `py3-none-any` tag, installs the wheel into a fresh venv, proves imports come from that venv, compiles deployed IR V3 outside the checkout, exercises the IR-only host, least-authority negative cases, a typed capability, checkpoint/restart continuation and a deterministic 10,000-event soak. Its receipt binds the exact commit/tree, Python/build-tool versions and wheel SHA-256.

A successful Python production admission deliberately means:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

It is a Python product/distribution admission, not yet a Python certificate and not a substitute for V1 cross-runtime certification.

## Python full certification

```powershell
python .\RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py
```

This read-only gate re-runs the production admission on the exact same clean commit, independently recomputes and verifies the production receipt hash, requires all wheel/install/runtime/authority/checkpoint/soak evidence, rechecks HEAD/tree and canonical/state immutability, and emits a certificate bound to the exact production receipt and wheel SHA-256.

A Python-host success means:

```text
PYTHON_CERTIFY_FULL=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

This permits Python to reach host-specific technical certification without waiting for Unity. It does not declare the global language/runtime matrix certified or authorize a stable package version.

## Full pre-certification

```powershell
python .\RUN_TEV_SCRIPT_V1_PRECERTIFY.py
```

`PRECERTIFY V5` requires, from one exact clean checkout:

1. governance consistency;
2. V1 frontend/static/lowering closure;
3. C# V0.2/V3 assembly and AOT surface guard;
4. Python/JavaScript/C# IR V3 receipt byte lock;
5. Python/JavaScript/C# checkpoint V2 byte lock + restart;
6. Browser-WASM V3 AOT receipt/checkpoint parity;
7. WASI V3 fresh/restore parity;
8. signed-update host campaign;
9. signed-update Browser-WASM campaign;
10. signed-update WASI fresh/restore campaign;
11. V0.2 complete portable regression;
12. clean and immutable Git HEAD/tree before/after.

Mandatory V1/V3 `SKIPPED_*` results are not accepted as a full precertification.

## Technical full certification

```powershell
python .\RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py
```

This gate is read-only. It re-runs pre-certify, validates the canonical pre-certify receipt and binds the global certificate to the exact Git commit/tree.

A global technical success means:

```text
CERTIFY_FULL=PASS
LANGUAGE_STABLE=NO
```

Stable release admission is intentionally a separate governance operation. If stable metadata changes the tree, the resulting commit must itself be re-run through the certificate scope being claimed; certification is not inherited transitively from its parent.

See `docs/V1_CERTIFICATION_PROTOCOL.md` and `docs/V1_PYTHON_PRODUCTION.md`.

---

# Current repository status

The current V1 branch contains the complete implementation/gate candidate described above, but this README does **not** claim that the exact current HEAD has completed Python production admission, Python host-specific certification or global pre-certification in this ChatGPT runtime.

The authoritative current status is `PROJECT_STATE.md`.

Until the exact clean commit passes the required admission sequence:

```text
CURRENT_HEAD_PYTHON_PRODUCTION_GATE=NOT_EXECUTED_HERE
CURRENT_HEAD_PYTHON_CERTIFY_FULL=NOT_EXECUTED_HERE
V1_CERTIFY_FULL=NO
V1_LANGUAGE_STABLE=NO
```

---

# Relationship with the existing TEV languages

```text
.tevs  bounded portable reactive behavior
.tev   governed causal actions
.tevg  finite multi-entity workflows
```

TEV Script does not create a second hidden causal kernel. Where a feature belongs to the governed causal/general layer, lowering/adaptation should target the existing TEV causal contracts rather than duplicating authority semantics inside `.tevs`.

---

# V0.2 historical validation

The original V0.2 portable campaign remains meaningful as a regression oracle.

Portable entry point:

```powershell
python .\RUN_PORTABLE_CONFORMANCE.py
```

Historical V0.2 source CLI:

```powershell
tev-script check .\examples\Player.tevs
tev-script compile .\examples\Player.tevs --output .\Player.ir.json
```

The V1 implementation is additive and is required to preserve those certified semantics while expanding the source model and runtime value system through explicit versioned boundaries.
