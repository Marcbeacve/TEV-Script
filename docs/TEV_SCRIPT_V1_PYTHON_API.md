# TEV Script V1 — Python Integration API

Status: programmer-facing guide for the V1 implementation candidate.

This guide describes the additive V1 Python integration model. The historical unversioned V0.2 API remains available and is not silently rebound to V1.

---

## 1. Two API generations coexist intentionally

V0.2 keeps familiar unversioned names:

```python
import tev_script

tev_script.compile_path(...)
tev_script.ScriptRuntime(...)
tev_script.run_conformance(...)
```

V1 uses explicit versioned names:

```python
tev_script.analyze_v1_paths(...)
tev_script.compile_v1_paths_auto(...)
tev_script.compile_v1_paths_to_ir_v2(...)
tev_script.compile_v1_paths_to_ir_v3(...)
tev_script.ScriptRuntimeV3(...)
```

This prevents an import upgrade from silently changing certified V0.2 behavior.

---

# Part I — Source analysis and compilation

## 2. Analyze source without choosing a runtime target

```python
from tev_script import analyze_v1_paths

analysis = analyze_v1_paths([
    "main.tevs",
    "model.tevs",
    "rules.tevs",
])
```

The returned `V1AnalysisBundle` contains four important layers:

```text
analysis.plan
    deterministic source/link graph

analysis.semantics
    resolved static semantics

analysis.linked_program
    canonical TEV_SCRIPT_LINKED_PROGRAM_V1

analysis.ir_v2_boundary
    proof/result describing whether runtime semantics can erase to IR V2
```

Useful identities:

```python
analysis.semantics.semantic_hash
analysis.linked_program.semantic_hash
```

`linked_program.semantic_hash` is the source-semantic identity consumed by runtime-target lowering.

---

## 3. Compile with automatic runtime target selection

```python
from tev_script import compile_v1_paths_auto

compiled = compile_v1_paths_auto(["program.tevs"])

print(compiled.target_ir)
print(compiled.target.ir["semantic_hash"])
```

The selection rule is exact:

```text
analysis.ir_v2_boundary.lowerable == True
    -> TEV_SCRIPT_PROGRAM_IR_V2

otherwise
    -> TEV_SCRIPT_PROGRAM_IR_V3
```

There is no syntax-token heuristic.

A source program may use V1-only abstractions such as functions, behaviors and bounded `for` and still target IR V2 when all runtime-visible values/operations remain representable by the certified V0.2 machine.

---

## 4. Force IR V2

```python
from tev_script import compile_v1_paths_to_ir_v2

compiled = compile_v1_paths_to_ir_v2(["program.tevs"])
```

This is appropriate when an integration deliberately requires the smaller certified V2 runtime profile.

If the linked V1 program contains a runtime-visible construct that cannot be represented losslessly, compilation fails closed. It does not encode records or variants into strings/opaque host objects.

---

## 5. Force IR V3

```python
from tev_script import compile_v1_paths_to_ir_v3

compiled = compile_v1_paths_to_ir_v3(["program.tevs"])
```

IR V3 is the complete V1 runtime profile for:

```text
records
enums
Option<T>
Result<T,E>
field loads
variant tests/payload extraction
algebraic capability/event values
```

Important identities:

```python
linked_hash = compiled.analysis.linked_program.semantic_hash
ir_hash = compiled.target.ir["semantic_hash"]
```

These hashes should not be conflated.

---

# Part II — Project manifests

## 6. Load an explicit reproducible project

```python
from tev_script import load_v1_project

project = load_v1_project("tevscript.project.json")

print(project.default_target)
print(project.manifest_hash)
print(project.project_input_hash)
print(project.source_paths)
```

`TEV_SCRIPT_PROJECT_V1` is build metadata, not language semantics.

It has two build identities:

```text
manifest_hash
    normalized build recipe

project_input_hash
    build recipe + exact bytes/hash of every source
```

Neither replaces:

```text
linked_program.semantic_hash
```

which is the canonical program meaning.

---

## 7. Detect source drift during a governed build

```python
from tev_script import verify_v1_project_inputs

project = load_v1_project("tevscript.project.json")

# ... perform analysis ...

verify_v1_project_inputs(project)
```

If the manifest or source bytes changed after loading, verification fails instead of letting a build receipt describe a different input snapshot.

A portable input witness is available as:

```python
witness = project.input_witness()
```

---

# Part III — Lowering evidence

## 8. Build an IR V2 lowering receipt

```python
from tev_script import (
    compile_v1_paths_to_ir_v2,
    build_ir_v2_lowering_receipt,
    verify_ir_v2_lowering_receipt,
)

compiled = compile_v1_paths_to_ir_v2(["program.tevs"])
receipt = build_ir_v2_lowering_receipt(
    compiled.analysis.linked_program,
    compiled.target,
)

verify_ir_v2_lowering_receipt(
    receipt.receipt,
    compiled.analysis.linked_program,
    compiled.target,
)
```

Receipt schema:

```text
TEV_SCRIPT_LOWERING_RECEIPT_V1
```

It proves the V1→IR V2 erasable profile rather than merely recording two unrelated hashes.

---

## 9. Build an IR V3 lowering receipt

```python
from tev_script import (
    compile_v1_paths_to_ir_v3,
    build_ir_v3_lowering_receipt,
    verify_ir_v3_lowering_receipt,
)

compiled = compile_v1_paths_to_ir_v3(["program.tevs"])
receipt = build_ir_v3_lowering_receipt(
    compiled.analysis.linked_program,
    compiled.target,
)

verify_ir_v3_lowering_receipt(
    receipt.receipt,
    compiled.analysis.linked_program,
    compiled.target,
)
```

Receipt schema:

```text
TEV_SCRIPT_LOWERING_RECEIPT_V2
```

The full V3 receipt binds preservation of algebraic runtime values, the closed type table and the target semantic hash to the linked V1 source semantics.

---

# Part IV — IR V3 validation and values

## 10. Validate V3 IR before runtime use

```python
from tev_script import validate_program_ir_v3

validate_program_ir_v3(
    compiled.target.ir,
    expected_source_semantic_hash=(
        compiled.analysis.linked_program.semantic_hash
    ),
)
```

Validation checks more than JSON shape:

```text
closed type table
type references
state/capability/event ABI
canonical hashes
stack flow
definite local initialization
CFG merges
algebraic opcode contracts
forward-only control flow
```

---

## 11. Construct algebraic values

The V3 runtime exposes nominal host-side value types:

```python
from tev_script import RecordValueV3, VariantValueV3
```

Record example:

```python
from fractions import Fraction
from tev_script import RecordValueV3

sample = RecordValueV3(
    "sensors.Sample",
    (
        ("confidence", Fraction(9, 10)),
        ("value", Fraction(21, 1)),
    ),
)
```

Variant examples:

```python
from tev_script import VariantValueV3

none = VariantValueV3("Option<Int>", "None")
some = VariantValueV3("Option<Int>", "Some", 42)
```

Do not substitute arbitrary host dictionaries/objects for runtime state values. The codec/type table is the authority at boundaries.

---

## 12. Encode/decode canonical values

```python
from tev_script import (
    build_type_table_v3,
    encode_v3_value,
    decode_v3_value,
)

table = build_type_table_v3(compiled.target.ir)
encoded = encode_v3_value(
    "Option<Int>",
    some,
    table,
    context="example",
)
round_trip = decode_v3_value(
    "Option<Int>",
    encoded,
    table,
    context="example",
)
```

This codec is used to keep capability/event/checkpoint values independent from Python object-layout conventions.

---

# Part V — Execute IR V3

## 13. Create a runtime

```python
from tev_script import ScriptRuntimeV3

runtime = ScriptRuntimeV3(
    compiled.target.ir,
    expected_source_semantic_hash=(
        compiled.analysis.linked_program.semantic_hash
    ),
)
```

Invoke an event:

```python
runtime.invoke("Calculator", "calculate", operation, value)
```

Read state:

```python
state = runtime.state("Calculator")
```

The returned state contains TEV semantic values, not native mutable object references.

---

## 14. Bind capabilities

Capability providers are supplied by the host when constructing the runtime.

Conceptually:

```python
runtime = ScriptRuntimeV3(
    ir,
    {
        "world.read": read_world,
        "storage.write": write_storage,
    },
    expected_source_semantic_hash=source_hash,
)
```

A provider is an adapter boundary. Incoming/outgoing values are validated against the capability signature/type table.

Example observation returning a record can return canonical encoded TEV data or the corresponding V3 value representation accepted by the runtime codec.

The TEV program itself never receives the Python function/object identity.

---

# Part VI — Conformance receipts

## 15. Run a portable V3 conformance scenario

```python
import json
from tev_script import run_ir_v3_conformance

scenario = json.loads(
    open("conformance/ir-v3-portable.scenario.json", encoding="utf-8").read()
)

bundle = run_ir_v3_conformance(
    compiled.target.ir,
    scenario,
)

print(bundle.receipt_hash)
print(bundle.canonical_json)
```

The receipt captures more than final state:

```text
scenario hash
program/source semantic hashes
initial state hash
per-step state hashes
emitted typed events
capability-call transcript
final canonical state/hash
receipt hash
```

Python, JavaScript and C# conformance gates compare the canonical receipt bytes, not merely approximate observables.

---

# Part VII — Checkpoints

## 16. RuntimeCheckpointV2

`RuntimeCheckpointV2` is exported as the exact-target restart representation for IR V3 values.

Its contract binds checkpoint state to:

```text
program id
IR schema/hash
source schema/hash
exact entity set
exact state set
state type
canonical algebraic value
```

It should be used for restart/continuation of the exact target program, not as an arbitrary migration format between unrelated IRs.

For complete capture/parse/restore examples, see:

```text
tests/test_runtime_checkpoint_v2.py
tests/test_ir_v3_checkpoint_cross_runtime.py
```

The same canonical checkpoint bytes are used by Python, JavaScript and C# gates; WASI additionally transports them across separate processes.

---

# Part VIII — Identity model

## 17. Do not collapse the hashes

A governed V1 build may have all of these identities:

```text
project.manifest_hash
project.project_input_hash
analysis.semantics.semantic_hash
analysis.linked_program.semantic_hash
target.ir["semantic_hash"]
lowering_receipt.receipt_hash
conformance_receipt.receipt_hash
checkpoint.checkpoint_hash
signed_update.package_sha256
```

They answer different questions.

### Build configuration

```text
manifest_hash
```

Which normalized build recipe was selected?

### Exact source inputs

```text
project_input_hash
```

Which files/bytes were fed to the compiler?

### Source semantics

```text
linked_semantic_hash
```

What TEV program meaning did those sources produce?

### Runtime target semantics

```text
IR semantic_hash
```

Which concrete machine program executes?

### Transformation evidence

```text
lowering receipt hash
```

Which source-semantic→runtime-target transformation was verified?

### Execution evidence

```text
conformance receipt hash
```

Which scenario execution trace/state did a runtime reproduce?

### Restart evidence

```text
checkpoint hash
```

Which exact runtime state can be resumed?

Keeping these identities distinct is a core part of the TEV Script governance model.

---

# Part IX — Recommended integration pipeline

## 18. Development build

```text
load project / explicit paths
    -> analyze_v1_*
    -> inspect lowering boundary
    -> compile auto/V2/V3
    -> validate target
    -> build lowering receipt
```

## 19. Runtime test

```text
validated IR
    -> ScriptRuntimeV3
    -> deterministic capability adapters
    -> invoke scenario
    -> canonical conformance receipt
```

## 20. Production/governed artifact flow

Use the CLI `build`/`compile --receipt` path or reproduce the same ordering in integration code:

```text
exact source inputs
    -> canonical linked semantics
    -> target IR
    -> lowering receipt
    -> evidence-safe artifact commit
```

The CLI's artifact commit policy is:

```text
EVIDENCE_SAFE_RECEIPT_LAST_V1
```

The receipt is installed after the IR so receipt presence acts as the final commit witness. Normal I/O exceptions roll back previous IR/receipt entries. The implementation deliberately does not claim two-path hardware atomicity across crashes/filesystems.

---

# Part X — Stability boundary

## 21. Candidate status

Even though these APIs are implemented and tested, current V1 APIs remain an implementation-candidate surface until exact clean-commit admission succeeds.

Therefore integrations should currently treat versioned V1 names as the stable *shape being tested*, not as a released compatibility promise.

The unversioned V0.2 surface remains separate specifically so experimentation and certification of V1 cannot silently mutate existing consumers.
