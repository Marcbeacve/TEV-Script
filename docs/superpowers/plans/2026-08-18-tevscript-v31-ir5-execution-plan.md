# TEVScript 3.1 IR5 Execution Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a derived, non-authoritative prepared execution path for TEVScript 3.1 Total-Core that preserves exact canonical outputs while removing repeated hot-path lookup and membership work.

**Architecture:** `TotalCoreProgramV1` and `run_total_core_quantum()` remain the semantic authority/oracle. A new `runtime_v5_total_optimized.py` validates the canonical program at preparation time, pre-resolves instructions/tables/proof-open Apply data into an immutable `TotalCoreExecutionPlanV1`, then executes quanta through `run_prepared_total_core_quantum()` while preserving external checkpoint validation and canonical result/evidence constructors.

**Tech Stack:** Python 3.11+, stdlib only, `unittest`, existing TEVScript canonical builders/runtime, independent JavaScript Total-Core witness for non-regression.

**Spec:** `docs/superpowers/specs/2026-08-18-tevscript-v31-ir5-execution-plan-design.md`

## Global Constraints

- Language semantics remain exactly `3.1.0`.
- Program IR remains exactly `TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1`.
- No canonical schema changes.
- No source syntax changes.
- `run_total_core_quantum()` remains unchanged as the reference oracle during Phase A.
- `TotalCoreExecutionPlanV1` is private runtime data: no schema, canonical hash, signature, serialization, or semantic authority.
- Full canonical program validation occurs at plan preparation.
- Every external checkpoint entering optimized execution remains fail-closed validated before execution.
- Canonical field, receipt, continuation, checkpoint and quantum-result construction semantics remain unchanged in Phase A.
- No runtime dependency additions.
- No publication, tag, stable admission or merge is authorized by this plan.

---

### Task 1: Prepared program representation

**Files:**
- Create: `tev_script/runtime_v5_total_optimized.py`
- Create: `tests/test_runtime_v5_total_optimized.py`

**Interfaces:**
- Consumes: `TotalCoreProgramV1`, `TotalCoreInstructionV1`, `TotalCoreUnitV1`, `VerifiedProofAdmissionV1`, `validate_total_core_program`.
- Produces:
  - `PreparedTotalCoreInstructionV1`
  - `PreparedProofApplyV1`
  - `TotalCoreExecutionPlanV1`
  - `prepare_total_core_execution_plan(program: TotalCoreProgramV1) -> TotalCoreExecutionPlanV1`

- [ ] **Step 1: Write the failing preparation test**

Add a minimal halt-only program and assert that preparation binds exact program identity and private opcode data:

```python
from tev_script.omega_semantic_basis_v1 import semantic_field
from tev_script.program_ir_v5_total import TotalCoreInstructionV1, TotalCoreProgramV1
from tev_script.runtime_v5_total_optimized import (
    _OP_HALT,
    prepare_total_core_execution_plan,
)

AUTHORITY = "a" * 64
SOURCE = "b" * 64


def _halt_program() -> TotalCoreProgramV1:
    return TotalCoreProgramV1.build(
        program_id="OptimizedHalt",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((), profile="actual"),
        transformations=(),
        v4_units=(),
        proof_admissions=(),
        instructions=(TotalCoreInstructionV1.halt(),),
        entry_pc=0,
        quantum_step_limit=1,
        authority_hash=AUTHORITY,
    )


def test_prepare_plan_binds_exact_validated_program() -> None:
    program = _halt_program()
    plan = prepare_total_core_execution_plan(program)
    assert plan.program is program
    assert plan.program_hash == program.program_hash
    assert plan.authority_hash == program.authority_hash
    assert plan.entry_pc == 0
    assert plan.quantum_step_limit == 1
    assert len(plan.instructions) == 1
    assert plan.instructions[0].opcode == _OP_HALT
```

- [ ] **Step 2: Run RED**

Run:

```bash
python -m pytest tests/test_runtime_v5_total_optimized.py::test_prepare_plan_binds_exact_validated_program -q
```

Expected: FAIL because `tev_script.runtime_v5_total_optimized` does not exist.

- [ ] **Step 3: Implement the minimal immutable plan**

Create private opcodes and frozen/slotted dataclasses. `prepare_total_core_execution_plan()` must call `validate_total_core_program(program)` once, build transformation/unit/proof indexes once, and pre-resolve each canonical instruction into `PreparedTotalCoreInstructionV1` without changing canonical objects.

Required shape:

```python
_OP_APPLY = 1
_OP_BRANCH_FACT = 2
_OP_JUMP = 3
_OP_HALT = 4
_OP_INVOKE_V4 = 5

@dataclass(frozen=True, slots=True)
class PreparedTotalCoreInstructionV1:
    opcode: int
    transformation: Any | None = None
    unit: TotalCoreUnitV1 | None = None
    fact_hash: str | None = None
    next_pc: int | None = None
    present_pc: int | None = None
    absent_pc: int | None = None
    target_pc: int | None = None
    result_relation: str | None = None

@dataclass(frozen=True, slots=True)
class PreparedProofApplyV1:
    proof_use_hash: str
    execution_local_transformation: Any

@dataclass(frozen=True, slots=True)
class TotalCoreExecutionPlanV1:
    program: TotalCoreProgramV1
    program_hash: str
    authority_hash: str
    entry_pc: int
    quantum_step_limit: int
    instructions: tuple[PreparedTotalCoreInstructionV1, ...]
    transformations_by_hash: Mapping[str, Any]
    units_by_hash: Mapping[str, TotalCoreUnitV1]
    proof_admissions_by_requirement: Mapping[str, VerifiedProofAdmissionV1]
    prepared_proof_applies: Mapping[str, PreparedProofApplyV1]
```

Use `MappingProxyType` for derived maps so callers cannot mutate the plan tables.

- [ ] **Step 4: Run GREEN and existing IR5 tests**

```bash
python -m pytest tests/test_runtime_v5_total_optimized.py::test_prepare_plan_binds_exact_validated_program -q
python -m pytest tests/test_program_ir_v5_total.py tests/test_runtime_v5_total.py tests/test_runtime_v5_total_proof.py -q
```

Expected: PASS.

- [ ] **Step 5: Add structural negative tests**

Use `dataclasses.replace()` to construct a plan with a mismatched `program_hash` and assert the later prepared executor rejects it with a dedicated deterministic diagnostic. Do not add an executor implementation yet; this test stays RED until Task 2.

- [ ] **Step 6: Commit**

```bash
git add tev_script/runtime_v5_total_optimized.py tests/test_runtime_v5_total_optimized.py
git commit -m "feat: add IR5 Total-Core execution plan"
```

---

### Task 2: Prepared control-flow runtime and O(1) fact membership

**Files:**
- Modify: `tev_script/runtime_v5_total_optimized.py`
- Modify: `tests/test_runtime_v5_total_optimized.py`

**Interfaces:**
- Consumes: `TotalCoreExecutionPlanV1`, `TotalCoreCheckpointV1`, existing canonical checkpoint/result helpers.
- Produces: `run_prepared_total_core_quantum(plan, checkpoint, *, task_strategy=None) -> TotalCoreQuantumResultV1`.

- [ ] **Step 1: Write RED tests for halt and jump identity**

For a halt-only program and a `jump(0)` program, compare the exact result object from the reference and prepared paths:

```python
reference = run_total_core_quantum(program, checkpoint)
prepared = run_prepared_total_core_quantum(
    prepare_total_core_execution_plan(program), checkpoint
)
assert prepared == reference
```

The jump program must use a finite `quantum_step_limit=3` and assert `SUSPENDED`, `steps_used == 3`, and exact continuation/checkpoint equality.

- [ ] **Step 2: Verify RED**

Expected: FAIL because `run_prepared_total_core_quantum` is not implemented.

- [ ] **Step 3: Implement minimal halt/jump executor**

At entry:

1. verify the plan's stored `program_hash` and `authority_hash` match `plan.program`;
2. validate the external checkpoint against `plan.program`;
3. reject halted checkpoint resume identically to the reference runtime;
4. derive epoch and evidence inputs using the same canonical helpers as the reference runtime;
5. execute `_OP_JUMP` and `_OP_HALT` with numeric dispatch;
6. construct the continuation, next checkpoint and quantum result using existing reference semantics.

No `apply`, `branch_fact`, or `invoke_v4` support yet.

- [ ] **Step 4: Run GREEN**

Run the two new tests plus existing IR5 runtime tests.

- [ ] **Step 5: Write RED branch tests across field cardinalities**

Build semantically valid fields containing 0, 1, 10, 100, 1,000 and 10,000 distinct facts. For each cardinality, create one `branch_fact` whose searched hash is present and one whose searched hash is absent. Assert prepared result equals reference result exactly.

- [ ] **Step 6: Implement runtime-only fact index**

At quantum entry:

```python
fact_hashes = {fact.fact_hash for fact in checkpoint.field.facts}
```

For `_OP_BRANCH_FACT` use:

```python
pc = instruction.present_pc if instruction.fact_hash in fact_hashes else instruction.absent_pc
```

Never use the set to construct canonical fields or hashes.

- [ ] **Step 7: Add an invariant helper used only by tests**

Expose a private function:

```python
def _fact_hash_index(field: SemanticFieldV1) -> set[str]:
    return {fact.fact_hash for fact in field.facts}
```

Tests assert equality with recomputation after every mutation class in later tasks.

- [ ] **Step 8: Commit**

```bash
git add tev_script/runtime_v5_total_optimized.py tests/test_runtime_v5_total_optimized.py
git commit -m "feat: add prepared IR5 control flow"
```

---

### Task 3: Plain and proof-admitted Apply fast path

**Files:**
- Modify: `tev_script/runtime_v5_total_optimized.py`
- Modify: `tests/test_runtime_v5_total_optimized.py`

**Interfaces:**
- Consumes: canonical `FieldTransformationV1`, `apply_field_transformation`, exact proof admissions from the prepared plan.
- Produces: exact reference-equivalent Apply receipts and proof-use evidence without per-Apply proof-index reconstruction.

- [ ] **Step 1: Write RED plain Apply differential test**

Build a transformation that adds one fact and removes another. Execute reference and prepared paths from the same checkpoint. Assert the complete `TotalCoreQuantumResultV1` objects are equal and `_fact_hash_index(prepared.field)` equals recomputation from `prepared.field.facts`.

- [ ] **Step 2: Implement plain Apply**

For `_OP_APPLY` with no proof requirements, call `apply_field_transformation(field, prepared.transformation)` directly. Preserve reference diagnostic behavior and ordered evidence accumulation. After PASS, update the runtime-only fact set from canonical transformation remove/add identities.

- [ ] **Step 3: Write RED proof-admitted Apply test**

Reuse the exact proof fixture pattern from `tests/test_runtime_v5_total_proof.py`: one requirement, one VERIFIED admission bound to the program authority, one proof-open transformation. Assert exact reference/prepared result equality.

- [ ] **Step 4: Prepare proof Apply once**

During `prepare_total_core_execution_plan()`:

1. use the already-built `proof_admissions_by_requirement` mapping;
2. select admissions in exact transformation requirement order;
3. compute the same `proof_use_hash` body as `_apply_total_core_transformation()`;
4. construct the same proof-cleared execution-local field transformation;
5. store it in `prepared_proof_applies[transformation_hash]`.

The prepared executor must not rebuild the proof-admission map or proof-cleared transformation per Apply.

- [ ] **Step 5: Add repeated-execution identity test**

Where transformation preconditions permit, execute multiple independent checkpoints/quanta through the same plan and prove each result equals the reference path. This establishes that plan data is immutable/reusable.

- [ ] **Step 6: Run focused regression**

```bash
python -m pytest tests/test_runtime_v5_total_optimized.py tests/test_runtime_v5_total.py tests/test_runtime_v5_total_proof.py tests/test_omega_semantic_basis_v1.py -q
```

- [ ] **Step 7: Commit**

```bash
git add tev_script/runtime_v5_total_optimized.py tests/test_runtime_v5_total_optimized.py
git commit -m "feat: prepare IR5 apply execution"
```

---

### Task 4: Prepared V4 invocation and bridge parity

**Files:**
- Modify: `tev_script/runtime_v5_total_optimized.py`
- Modify: `tests/test_runtime_v5_total_optimized.py`

**Interfaces:**
- Consumes: exact pre-resolved `TotalCoreUnitV1`, reference `_run_v4_unit`/bridge semantics or equivalent canonical calls.
- Produces: byte/hash-identical bridge facts, child receipts, Apply receipts and continuation evidence for pure, recursive and effects units.

- [ ] **Step 1: Write three RED differential tests**

Reuse fixture construction semantics from `tests/test_runtime_v5_total.py` for:

- pure child (`add1(4)`);
- recursive child (`factorial(5)`);
- effects child (`sensor.read`).

For each case:

```python
assert run_prepared_total_core_quantum(plan, checkpoint) == run_total_core_quantum(program, checkpoint)
```

- [ ] **Step 2: Implement `_OP_INVOKE_V4` using direct unit reference**

Dispatch by `prepared.unit.profile` to the existing V4 runtime. Preserve the same bridge payload, bridge transformation identity, Apply receipt, child receipt hash, observation/effect evidence, `v4_evaluation_steps`, and next PC.

Do not optimize V4 internals in this task.

- [ ] **Step 3: Update fact membership after bridge Apply**

After canonical bridge Apply PASS, add exactly the resulting bridge fact hash to the runtime set. Add an invariant assertion in tests that the set equals the canonical field recomputation.

- [ ] **Step 4: Add mixed multi-quantum differential test**

Construct a program containing branch, plain Apply, proof Apply, invoke_v4, jump and halt across at least two quanta. Execute reference and prepared paths until halt or a fixed finite number of quanta; compare every quantum result pair exactly.

- [ ] **Step 5: Commit**

```bash
git add tev_script/runtime_v5_total_optimized.py tests/test_runtime_v5_total_optimized.py
git commit -m "feat: prepare IR5 V4 invocation"
```

---

### Task 5: Deterministic differential fuzz and JS parity non-regression

**Files:**
- Create: `tools/run_v31_total_core_optimized_differential_fuzz.py`
- Modify: `tests/test_runtime_v5_total_optimized.py`
- Verify unchanged: `tests/test_runtime_v5_total_js_parity.py`
- Verify unchanged: `runtime_js_v31/runtime_v5_total.mjs`

**Interfaces:**
- Consumes: canonical builders and both Python execution paths.
- Produces: deterministic mismatch-free campaign summary.

- [ ] **Step 1: Add seeded valid-program generator**

Generate bounded valid programs with:

```text
seeds = 1000
instruction_count = 1..128
field_fact_count = 0..512
instruction kinds represented across campaign = all five
proof-open Apply represented = yes
V4 profiles represented = pure, recursive, effects
```

Ensure generated control flow cannot index outside canonical program bounds; rely on `TotalCoreProgramV1.build()` as the canonical validator.

- [ ] **Step 2: Differential oracle**

For every executable seed/quantum:

```python
reference = run_total_core_quantum(program, checkpoint)
prepared = run_prepared_total_core_quantum(plan, checkpoint)
if reference != prepared:
    raise AssertionError(seed, program.program_hash, reference, prepared)
```

Any mismatch is immediate failure; never average or skip it.

- [ ] **Step 3: Invalid boundary negatives**

For deterministic selected seeds, pair a valid plan with a checkpoint from another program and assert fail-closed rejection. Also test halted checkpoint resume rejection and a dataclass-replaced stale plan hash.

- [ ] **Step 4: Run existing JS parity suite unchanged**

```bash
python -m pytest tests/test_runtime_v5_total_js_parity.py -q
```

The optimized Python plan must introduce no new canonical artifact understood by JS.

- [ ] **Step 5: Commit**

```bash
git add tools/run_v31_total_core_optimized_differential_fuzz.py tests/test_runtime_v5_total_optimized.py
git commit -m "test: fuzz IR5 prepared runtime parity"
```

---

### Task 6: Performance harness and promotion gate

**Files:**
- Create: `tools/benchmark_v31_total_core_performance.py`
- Create: `RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE.py`
- Modify only after all gates pass: `tev_script/__init__.py`

**Interfaces:**
- Consumes: reference and prepared runtimes.
- Produces: machine-local performance receipt and optional public API promotion.

- [ ] **Step 1: Implement benchmark cases**

Required cases:

```text
jump_10k
branch_fact_10
branch_fact_100
branch_fact_1k
branch_fact_10k
apply_plain
apply_proof_admitted
invoke_v4_pure
invoke_v4_recursive
invoke_v4_effects
mixed_total_core
```

Record median, p95, preparation cost and exact semantic-identity PASS before reporting speedup.

- [ ] **Step 2: Add structural instrumentation tests**

Using test-only patching/counters, prove:

```text
PLAN_PROGRAM_VALIDATION_COUNT_PER_PREPARE = 1
TRANSFORMATION_INDEX_BUILD_COUNT_PER_PLAN = 1
UNIT_INDEX_BUILD_COUNT_PER_PLAN = 1
PROOF_ADMISSION_INDEX_BUILD_COUNT_PER_PLAN = 1
PER_QUANTUM_TRANSFORMATION_INDEX_REBUILD = 0
PER_QUANTUM_UNIT_INDEX_REBUILD = 0
PER_APPLY_PROOF_INDEX_REBUILD = 0
```

Do not make production correctness depend on counters.

- [ ] **Step 3: Run three fresh-process benchmark campaigns**

Promotion thresholds from the spec:

```text
jump_10k.speedup                 >= 1.10
branch_fact_1k.speedup            >= 2.00
branch_fact_10k.speedup           >= 4.00
apply_plain.speedup               >= 1.10
apply_proof_admitted.speedup      >= 1.20
mixed_total_core.speedup          >= 1.20
invoke_v4_pure.p95_ratio          <= 1.05
invoke_v4_recursive.p95_ratio     <= 1.05
invoke_v4_effects.p95_ratio       <= 1.05
GEOMEAN_WARM_SPEEDUP               >= 1.25
```

All semantic identity gates must pass in each run.

- [ ] **Step 4: Measure evidence share**

Profile `mixed_total_core` after Phase A. If evidence/boundary construction is <20% of optimized end-to-end quantum time, Phase B remains explicitly out of scope. If >=20%, stop and create the separate spec amendment required by the design before changing trusted constructors.

- [ ] **Step 5: Full repository regression**

Run the existing repository regression/certification command appropriate for the current 3.1 platform candidate. Required result: no new failures and zero skips relative to the certified baseline.

- [ ] **Step 6: Public API promotion only if every gate passes**

Add to `tev_script.__init__` only:

```python
from .runtime_v5_total_optimized import (
    TotalCoreExecutionPlanV1,
    prepare_total_core_execution_plan,
    run_prepared_total_core_quantum,
)
```

and corresponding `__all__` entries. Do not change `run_total_core_quantum` default behavior.

- [ ] **Step 7: Commit**

```bash
git add tools/benchmark_v31_total_core_performance.py RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE.py tev_script/__init__.py
git commit -m "perf: certify IR5 prepared runtime"
```

---

## Final verification before completion

Run, in this order:

```bash
python -m pytest tests/test_runtime_v5_total_optimized.py -q
python tools/run_v31_total_core_optimized_differential_fuzz.py
python -m pytest tests/test_runtime_v5_total_js_parity.py -q
python -m pytest tests/test_program_ir_v5_total.py tests/test_runtime_v5_total.py tests/test_runtime_v5_total_proof.py -q
python RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE.py
python RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py
```

Completion requires:

```text
REFERENCE_PREPARED_EXACT_IDENTITY=PASS
DIFFERENTIAL_FUZZ_1000=PASS
V31_TOTAL_CORE_JS_PARITY_NONREGRESSION=PASS
PERFORMANCE_PROMOTION=PASS
FULL_REPOSITORY_REGRESSION=PASS
ZERO_SKIP=PASS
```

Do not merge, tag, publish or perform Stable Admission from this plan.