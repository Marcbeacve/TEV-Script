# TEV Script V1 examples

These examples are executable test assets for the V1 implementation candidate. They are not pseudocode copies of the documentation: `tests/test_v1_examples.py` and `tests/test_v1_cli_full.py` compile and/or execute them through the real V1 pipeline.

## Install the local reference package

From the repository root:

```powershell
python -m pip install -e .
```

The package exposes two intentionally separate commands:

```text
tev-script       certified V0.2 CLI
tev-script-v1    V1 implementation-candidate CLI
```

Keeping the commands separate prevents V1 work from silently changing V0.2 command semantics before stable admission.

You can also invoke V1 without installation:

```powershell
python -m tev_script.cli_v1 ...
```

---

## V1 CLI model

A V1 compilation receives an explicit finite source set:

```text
one script root
+ every module needed by that root
```

The CLI does not scan directories or resolve packages from the network.

### Check/link/type-check

```powershell
tev-script-v1 check .\examples\v1\Calculator.tevs
```

`check` performs:

```text
parse
link
name resolution
type analysis
purity/effect/event analysis
constant validation
behavior composition
linked-program canonicalization
IR V2 boundary analysis
```

The result reports:

```text
program_id
linked_semantic_hash
static_semantic_hash
ir_v2_lowerable
ir_v2_blocker_count
default_target_ir
```

### Emit canonical linked semantics

```powershell
tev-script-v1 link `
  .\examples\v1\Calculator.tevs `
  -o .\Calculator.linked.v1.json
```

This writes:

```text
TEV_SCRIPT_LINKED_PROGRAM_V1
```

That artifact is the semantic boundary between source compilation and runtime targets.

### Inspect whether IR V2 is lossless

```powershell
tev-script-v1 boundary .\examples\v1\ErasableToIrV2.tevs
```

Exit code:

```text
0   lossless IR V2 lowering available
3   IR V3 required
2   source/link/type diagnostic
```

The nonzero `3` result is not an invalid V1 program. It means the program uses a runtime value/operation that cannot be represented losslessly by IR V2.

### Compile with automatic target selection

```powershell
tev-script-v1 compile `
  .\examples\v1\Calculator.tevs `
  --target auto `
  -o .\Calculator.ir.json
```

Selection rule:

```text
IR V2 boundary lowerable = true
    -> TEV_SCRIPT_PROGRAM_IR_V2

otherwise
    -> TEV_SCRIPT_PROGRAM_IR_V3
```

There is no heuristic based on file names or syntax tokens. Selection is made after linked/static semantics.

### Force one target

```powershell
tev-script-v1 compile `
  .\examples\v1\ErasableToIrV2.tevs `
  --target irv2 `
  -o .\erasable.v2.json
```

```powershell
tev-script-v1 compile `
  .\examples\v1\ErasableToIrV2.tevs `
  --target irv3 `
  -o .\erasable.v3.json
```

Forcing IR V2 on a program that requires algebraic runtime values fails closed and does not create a lossy output file.

Legacy explicit aliases remain available:

```text
lower-irv2
lower-irv3
```

---

# Example 1 — Calculator

File:

```text
examples/v1/Calculator.tevs
```

Concepts:

```text
enum Operation
CalcError enum
Result<Rat, CalcError>
exact Rat arithmetic
exhaustive match
state mutation
explicit divide-by-zero domain failure
```

The calculator models a domain error as:

```text
Err(CalcError::DivisionByZero)
```

rather than relying on a host exception as normal application control flow.

Because `Operation` and `Result` are live runtime values, the default target is IR V3.

Try:

```powershell
tev-script-v1 check .\examples\v1\Calculator.tevs
tev-script-v1 compile .\examples\v1\Calculator.tevs --target auto -o .\Calculator.ir.json
```

---

# Example 2 — V1 abstractions erased to IR V2

File:

```text
examples/v1/ErasableToIrV2.tevs
```

Concepts:

```text
pure user function
behavior dependency
behavior state
bounded for
exact Rat state
```

Although the source uses several V1 features, the runtime state remains entirely within the V0.2 primitive/vector value model.

Therefore:

```text
modules/behavior/function/for semantics
    -> validated expansion/inlining/unrolling
    -> certified TEV_SCRIPT_PROGRAM_IR_V2 machine
```

Try:

```powershell
tev-script-v1 boundary .\examples\v1\ErasableToIrV2.tevs
tev-script-v1 compile .\examples\v1\ErasableToIrV2.tevs --target auto -o .\Erasable.ir.json
```

This example demonstrates an important TEV Script design property: **source-language expressiveness and runtime-VM complexity do not have to increase together** when abstractions can be proven erasable.

---

# Example 3 — Algebraic capability boundary

File:

```text
examples/v1/AlgebraicCapability.tevs
```

Concepts:

```text
record Sample
enum SensorError
Result<Sample, SensorError>
Option<Sample>
algebraic observation capability
algebraic effect payload
nested exhaustive match
```

The host boundary is typed:

```tevs
capability sensor.read() -> Result<Sample, SensorError> observation;
capability storage.accept(Sample) -> Unit effect;
```

This program cannot be losslessly represented in IR V2 because records and sum types survive at runtime and cross capability boundaries.

Try:

```powershell
tev-script-v1 boundary .\examples\v1\AlgebraicCapability.tevs
```

The command should report `lowerable=false` and exit with code `3`.

Then:

```powershell
tev-script-v1 compile `
  .\examples\v1\AlgebraicCapability.tevs `
  --target auto `
  -o .\AlgebraicCapability.ir.json
```

The result must use:

```text
TEV_SCRIPT_PROGRAM_IR_V3
```

---

# Example 4 — Multi-module ecosystem

Files:

```text
examples/v1/ecosystem/main.tevs
examples/v1/ecosystem/model.tevs
examples/v1/ecosystem/rules.tevs
examples/v1/ecosystem/storage.tevs
```

The program deliberately separates:

```text
ecosystem.model
    domain records/enums

ecosystem.rules
    pure computation

ecosystem.storage
    host capability ports

Ecosystem root
    persistent entity + behavior composition
```

Check the complete finite source set:

```powershell
tev-script-v1 check `
  .\examples\v1\ecosystem\main.tevs `
  .\examples\v1\ecosystem\model.tevs `
  .\examples\v1\ecosystem\rules.tevs `
  .\examples\v1\ecosystem\storage.tevs
```

Compile:

```powershell
tev-script-v1 compile `
  .\examples\v1\ecosystem\main.tevs `
  .\examples\v1\ecosystem\model.tevs `
  .\examples\v1\ecosystem\rules.tevs `
  .\examples\v1\ecosystem\storage.tevs `
  --target auto `
  -o .\Ecosystem.ir.json
```

The test suite analyzes the same four files in forward and reverse input order and requires identical canonical linked-program bytes and hash.

This proves that command-line source ordering is build input presentation, not semantic module order.

---

# Suggested learning order

For learning the language rather than only running the gates:

```text
1. Calculator.tevs
   enum + Result + match + state

2. ErasableToIrV2.tevs
   fn + behavior + bounded for + lowering boundary

3. AlgebraicCapability.tevs
   records + Option/Result + typed host authority

4. ecosystem/
   modules + exports/imports + pure domain layer + capability layer
```

Then read:

```text
docs/TEV_SCRIPT_V1_LANGUAGE_REFERENCE.md
docs/TEV_SCRIPT_V1_PROGRAMMING_MODEL.md
```

For implementation/certification architecture:

```text
docs/V1_COMPILER_RUNTIME_BOUNDARY_DECISION.md
docs/V1_CERTIFICATION_PROTOCOL.md
```

---

# Development validation

Run the V1 Python/front-end closure:

```powershell
python .\RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py
```

The example tests are discovered under the normal `test_v1_*.py` V1 suite.

Full pre-certification requires additional installed targets/tools and is intentionally broader:

```powershell
python .\RUN_TEV_SCRIPT_V1_PRECERTIFY.py
```

That campaign requires the Python, Node, C#, Browser-WASM, WASI, checkpoint and signed-update gates with no mandatory V1/V3 skips.

The current repository is still an implementation candidate until one exact clean commit passes the required admission sequence.
