# TEVScript 3.1 IR5 Total-Core Execution Plan — Design

Date: 2026-08-18
Status: APPROVED DESIGN / SPECIFICATION ONLY
Base branch: `main`
Base commit: `a0c3951a03403f871ff4a192f75f2c29437f5fdb`
Base tree: `cd256acb21266e5cfe842d6254d2ef12491ff3db`
Target language semantics: unchanged `3.1.0`
Target Program IR: unchanged `TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1`
Target package version: unchanged until a separate release decision

## 1. Objective

This change optimizes execution of the existing TEVScript 3.1 Total-Core runtime without changing language semantics, Program IR schemas, canonical hashes, proof rules, continuation semantics, or physical-effect authority.

The canonical relation is:

```text
TotalCoreProgramV1 (canonical semantic authority)
        |
        +--> run_total_core_quantum(...)             # existing reference oracle
        |
        +--> prepare_total_core_execution_plan(...)
                 |
                 v
           TotalCoreExecutionPlanV1                 # derived, disposable, non-authoritative
                 |
                 v
           run_prepared_total_core_quantum(...)
                 |
                 v
           byte/hash-identical canonical results
```

The optimization pattern is **validate canonical program -> derive a private execution plan once -> reuse that plan across quanta**. Phase A removes repeated static lookup, dispatch, membership and proof-preparation work from the hot instruction loop. Existing canonical checkpoint/result boundary validators remain authoritative in Phase A even if they internally revalidate canonical structures. Eliminating that remaining boundary cost requires the measured Phase B trigger in section 12.

This follows the already-proven architecture used by the optimized IR V3 runtime, but applies it to IR V5 Total-Core without making the private execution plan semantic authority.

The existing `tev_script/runtime_v5_total.py` remains the semantic execution oracle throughout development. Promotion is forbidden unless the optimized path reproduces its canonical outputs exactly.

## 2. Non-goals

This work does not:

- add source syntax;
- add an opcode to canonical Program IR V5;
- change `TotalCoreProgramV1`;
- change `TotalCoreInstructionV1`;
- change V4 child semantics;
- change proof-admission authority;
- change checkpoint, continuation, quantum-result, field, transformation or receipt schemas;
- make the execution plan serializable, signable or canonical;
- replace the independent JavaScript witness;
- optimize C#/Unity V3 runtimes as part of this change;
- weaken fail-closed validation at external trust boundaries;
- remove evidence generation or canonical hashing.

If a performance improvement requires any item above, it requires a separate design amendment.

## 3. Existing authority and observed cost centers

`TotalCoreProgramV1.build()` already closes static structural validity before execution. It validates and canonicalizes transformations, V4 units, proof admissions and instructions; rejects duplicate identities; proves PC targets are in range; proves `apply` references a known transformation; proves proof-open transformations have exact admissions; proves all proof admissions bind the program authority; and proves `invoke_v4` references a known unit.

Therefore the optimized runtime must not duplicate those static checks inside every instruction. It may derive resolved runtime structures only after one exact `validate_total_core_program()` call at plan preparation.

The current reference runtime performs useful but repeated work around and inside each quantum:

```text
validate_total_core_program(program)                        # boundary
validate_total_core_checkpoint(program, checkpoint)        # boundary
rebuild transformation_hash -> transformation dict         # hot-path setup
rebuild unit_hash -> unit dict                              # hot-path setup
string-dispatch every instruction                          # hot loop
linear scan of field.facts for branch_fact                 # hot loop
rebuild proof requirement -> admission dict per proof Apply # hot loop
rebuild proof-admitted execution-local transform per use    # hot loop
construct canonical result/checkpoint evidence             # boundary
revalidate canonical evidence during result construction   # boundary
```

Phase A targets the six hot-path items from table/index reconstruction through proof-open Apply preparation. Canonical entry/exit validation and evidence construction remain unchanged until profiling proves they are still material after Phase A.

## 4. Hard invariants

1. `TotalCoreProgramV1` remains the sole semantic authority for the program.
2. `TotalCoreExecutionPlanV1` is derived runtime data and has no schema, canonical hash, signature, release identity or wire representation.
3. A plan is valid for exactly one `program_hash` and one `authority_hash`.
4. Plan preparation performs full canonical program validation exactly once per plan construction.
5. Phase A may still invoke existing canonical validators at quantum entry/exit; no static program-table validation or reconstruction may occur inside the hot instruction loop.
6. Every external checkpoint entering optimized execution is validated against the canonical program before any instruction executes.
7. Every optimized quantum must produce a `TotalCoreQuantumResultV1` that compares equal to the reference oracle for the same canonical program, checkpoint and task strategy.
8. Equality includes field identity, PC, status, steps, V4 evaluation steps, apply receipt hashes, child receipt hashes, result hash, continuation, next checkpoint and quantum hash.
9. Optimization may never infer physical-effect authority from a V4 command plan or receipt.
10. Proof-open Apply remains usable only through exact VERIFIED admissions bound to the program authority.
11. A corrupted, stale or mismatched plan fails closed before execution.
12. No optimization may depend on Python object identity for semantic correctness.
13. JavaScript parity remains a release gate for canonical outputs even though JavaScript need not implement the same private execution-plan architecture.

## 5. New additive module

Create:

```text
tev_script/runtime_v5_total_optimized.py
```

The reference module remains:

```text
tev_script/runtime_v5_total.py
```

The optimized module may import public canonical types/functions and narrowly selected private helpers from the reference module only when those helpers are pure canonical constructors. It must not modify reference execution behavior during Phase A.

Primary additive API:

```python
def prepare_total_core_execution_plan(
    program: TotalCoreProgramV1,
) -> TotalCoreExecutionPlanV1:
    ...


def run_prepared_total_core_quantum(
    plan: TotalCoreExecutionPlanV1,
    checkpoint: TotalCoreCheckpointV1,
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> TotalCoreQuantumResultV1:
    ...
```

The initial implementation is not exported from `tev_script.__init__` until all promotion gates pass. Tests and benchmarks import the module explicitly.

## 6. `TotalCoreExecutionPlanV1`

The plan is an immutable `dataclass(frozen=True, slots=True)` containing at minimum:

```text
program                    exact validated TotalCoreProgramV1
program_hash               exact program.program_hash
authority_hash             exact program.authority_hash
entry_pc                    exact program.entry_pc
quantum_step_limit          exact program.quantum_step_limit
instructions                immutable tuple of prepared instructions
transformations_by_hash     immutable/private resolved mapping
units_by_hash               immutable/private resolved mapping
proof_admissions_by_requirement
prepared_proof_applies      transformation_hash -> prepared proof Apply data
```

The plan must not contain a second semantic copy of Program IR. Resolved tables are references to the exact canonical objects already contained in `program`.

The plan builder must reject any object that does not pass `validate_total_core_program()` and must assert that all derived table keys and prepared instruction references resolve exactly to the canonical validated program.

## 7. Prepared instructions

Canonical instruction kinds remain unchanged:

```text
apply
branch_fact
jump
halt
invoke_v4
```

The optimized plan replaces repeated string dispatch and hash-table resolution with private numeric opcodes and pre-resolved operands. Suggested private opcodes:

```text
_OP_APPLY       = 1
_OP_BRANCH_FACT = 2
_OP_JUMP        = 3
_OP_HALT        = 4
_OP_INVOKE_V4   = 5
```

A prepared instruction is private runtime data. It may use a compact immutable dataclass or tuple, but must retain enough data to execute without re-reading unresolved hashes from the canonical instruction on the hot path.

Required pre-resolution:

- `apply`: direct canonical transformation reference, prepared proof-use data if needed, and `next_pc`;
- `branch_fact`: exact `fact_hash`, `present_pc`, `absent_pc`;
- `jump`: exact `target_pc`;
- `halt`: opcode only;
- `invoke_v4`: direct canonical `TotalCoreUnitV1` reference, exact `result_relation`, and `next_pc`.

The prepared representation must be reproducibly derivable from the canonical program but is not itself canonical.

## 8. Fact membership index

The reference runtime evaluates `branch_fact` with a linear scan over `field.facts`. The optimized runtime maintains a runtime-only membership index:

```python
fact_hashes: set[str]
```

At quantum entry it is derived from the already-validated checkpoint field.

After a successful canonical field transformation, the index is updated only after the returned canonical field and PASS receipt exist. For a static `apply`, updates may use the exact canonical transformation's `remove_fact_hashes` and `add_facts`. For a V4 bridge fact, the exact newly generated bridge fact hash is added after the canonical bridge Apply passes.

The index is never used to construct canonical field ordering or field hashes. `SemanticFieldV1` remains the semantic source of truth.

Differential tests must periodically recompute:

```python
{fact.fact_hash for fact in field.facts}
```

and prove equality with the runtime index after every mutation class.

## 9. Proof-open Apply preparation

The canonical program builder already proves that every proof requirement referenced by an Apply has an exact admission and that all admissions bind `program.authority_hash`.

Plan preparation therefore builds once:

```text
requirement_hash -> VerifiedProofAdmissionV1
```

For every proof-open transformation, it also precomputes the exact static proof-use identity inputs:

```text
requirement_hashes
admission_hashes
proof_use_hash
execution-local proof-admitted transformation
```

The resulting execution-local transformation must be byte/hash-equivalent to the object the reference runtime would derive for the same program and transformation. It clears `proof_requirement_hashes` only after binding the exact admissions into `proof_use_hash`; all other canonical transformation fields remain identical.

No proof condition may be weakened merely because preparation has occurred.

## 10. V4 unit invocation

`invoke_v4` pre-resolves the exact canonical `TotalCoreUnitV1`. Child execution continues to delegate to the existing V4 runtime according to the unit profile:

```text
pure      -> run_program_ir_v4_pure
recursive -> run_program_ir_v4_recursive
effects   -> run_program_ir_v4_effects
```

This design does not optimize V4 internals. It only removes repeated V5 unit-hash resolution.

Bridge-fact construction remains canonical and must produce the exact same bridge fact, bridge transformation, Apply receipt and continuation evidence as the reference runtime.

## 11. Evidence boundary — Phase A

Phase A intentionally preserves the existing canonical boundary semantics for:

```text
TotalCoreCheckpointV1
ContinuationReceiptV1
TotalCoreQuantumResultV1
```

The optimized executor may collect hot-path data more efficiently, but it must feed the same ordered observation/effect/resource identities into the existing evidence semantics.

Existing public validators may therefore still perform canonical program/field/receipt reconstruction at quantum boundaries during Phase A. This cost is explicitly outside the Phase A hot-loop optimization contract.

Phase A is considered successful even if boundary evidence construction remains a noticeable fraction of total runtime, provided the promotion thresholds are met.

## 12. Conditional Phase B — trusted boundary/evidence constructors

Phase B is not automatically authorized by this design.

It may be proposed only if Phase A profiling shows that repeated boundary validation or canonical evidence reconstruction consumes at least **20% of optimized end-to-end quantum time** on the mixed benchmark workload.

If that threshold is met, a separate amendment must specify private trusted boundary/evidence constructors that:

- are reachable only after canonical program/checkpoint validation conditions are explicitly established;
- preserve public validators unchanged;
- preserve exact canonical bytes/hashes;
- cannot be called with externally unvalidated artifacts through public API;
- are independently differential-tested against the public reference constructors.

Without that measured trigger and amendment, Phase B is YAGNI and remains out of scope.

## 13. Benchmark harness

Create:

```text
tools/benchmark_v31_total_core_performance.py
```

The harness compares:

```text
reference = run_total_core_quantum
prepared  = run_prepared_total_core_quantum
```

It must benchmark both cold preparation and warm repeated execution, but promotion is based on warm execution because the execution plan is explicitly an amortized runtime structure.

Required workloads:

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

For membership scaling, branch workloads must use otherwise equivalent programs/fields whose only material change is fact cardinality.

Each benchmark records at minimum:

```text
case
iterations
warmup_iterations
reference_median_ns
prepared_median_ns
speedup
reference_p95_ns
prepared_p95_ns
p95_ratio
plan_prepare_median_ns
semantic_identity_pass
```

The harness must refuse to publish a performance PASS for a case whose canonical outputs differ.

## 14. Promotion performance gates

Performance numbers are relative to the same process, machine and benchmark invocation. Absolute wall-clock numbers are non-authoritative.

Required gates:

```text
SEMANTIC_IDENTITY_ALL_CASES=PASS

jump_10k.speedup                 >= 1.10
branch_fact_1k.speedup            >= 2.00
branch_fact_10k.speedup           >= 4.00
apply_plain.speedup               >= 1.10
apply_proof_admitted.speedup      >= 1.20
mixed_total_core.speedup          >= 1.20

invoke_v4_pure.p95_ratio          <= 1.05
invoke_v4_recursive.p95_ratio     <= 1.05
invoke_v4_effects.p95_ratio       <= 1.05

GEOMEAN_WARM_SPEEDUP              >= 1.25
```

`GEOMEAN_WARM_SPEEDUP` excludes cold plan construction and is computed over the listed warm workloads using positive median speedups.

A single benchmark run is not enough for certification. The promotion receipt must contain at least three independent benchmark runs in fresh Python processes, and the median of each run-level metric must satisfy the gate.

These thresholds may be changed only by an explicit spec amendment justified by measured results; they must not be silently relaxed to obtain PASS.

## 15. Complexity gates

In addition to timing, structural gates must prove:

```text
PLAN_PROGRAM_VALIDATION_COUNT_PER_PREPARE = 1
TRANSFORMATION_INDEX_BUILD_COUNT_PER_PLAN = 1
UNIT_INDEX_BUILD_COUNT_PER_PLAN = 1
PROOF_ADMISSION_INDEX_BUILD_COUNT_PER_PLAN = 1
PER_QUANTUM_TRANSFORMATION_INDEX_REBUILD = 0
PER_QUANTUM_UNIT_INDEX_REBUILD = 0
PER_APPLY_PROOF_INDEX_REBUILD = 0
PER_INSTRUCTION_STATIC_PROGRAM_VALIDATION = 0
BRANCH_FACT_MEMBERSHIP_ALGORITHM = O(1) average hash membership
```

Canonical boundary validators are excluded from `PER_INSTRUCTION_STATIC_PROGRAM_VALIDATION`; their measured cost is tracked separately for the Phase B trigger.

Tests may expose counters through a benchmark-only wrapper or monkeypatch instrumentation. Production semantics must not depend on counters.

## 16. Differential correctness campaign

Create:

```text
tests/test_runtime_v5_total_optimized.py
```

The differential suite must cover at minimum:

- halt-only quantum;
- jump loops ending by quantum suspension;
- branch present and absent;
- branch fields with 0, 1, 10, 100, 1,000 and 10,000 facts;
- plain Apply add/remove combinations;
- proof-admitted Apply;
- repeated proof-admitted Apply where allowed by transformation preconditions;
- pure V4 invocation;
- recursive V4 invocation;
- effects V4 invocation;
- mixed multi-quantum execution;
- resume from continuation-linked checkpoint;
- exact step-budget boundary;
- tampered checkpoint;
- checkpoint from a different program;
- halted checkpoint resume rejection;
- stale/mismatched execution plan rejection.

For every accepted case:

```python
reference_result == prepared_result
```

must hold exactly.

## 17. Differential fuzz

Add a deterministic fuzz campaign using seeded generators over valid bounded Total-Core programs assembled from the existing canonical builders.

Minimum promotion campaign:

```text
seeds                  >= 1,000
quanta per seed        >= 1 where execution remains valid
instruction count      1..128
field fact count       0..512
instruction kinds      all five kinds across campaign
proof-open apply        represented across campaign
V4 child profiles      all three represented across campaign
```

The fuzz oracle is the existing reference runtime. Any mismatch is an unconditional REJECT, not a benchmark failure that can be averaged away.

The generator must also run invalid checkpoint/program pair negatives to confirm fail-closed behavior.

## 18. JavaScript parity

The independent JavaScript Total-Core runtime remains a semantic witness, not an implementation-architecture mirror.

No JS execution plan is required by this design.

After the Python optimized path produces a canonical quantum result, existing Python/JS parity tests must continue proving byte/hash identity of the canonical artifacts. The Python plan must not introduce a new artifact that JavaScript needs to understand.

Required gate:

```text
V31_TOTAL_CORE_JS_PARITY_NONREGRESSION=PASS
```

## 19. Public API promotion

Before performance/correctness promotion, users continue to receive the existing API and behavior.

After all gates pass, a separate promotion commit may expose:

```python
TotalCoreExecutionPlanV1
prepare_total_core_execution_plan
run_prepared_total_core_quantum
```

through the 3.1 Python surface.

`run_total_core_quantum` remains available as the reference path. This design does not authorize silently replacing it with the optimized executor.

A later decision may choose an optimized default only after production evidence shows no regression; that decision is outside this spec.

## 20. Files expected in implementation

Phase A may create:

```text
tev_script/runtime_v5_total_optimized.py
tests/test_runtime_v5_total_optimized.py
tools/benchmark_v31_total_core_performance.py
```

It may minimally modify only if promotion requires it:

```text
tev_script/__init__.py
RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py
RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py
docs/TEV_SCRIPT_3_1_PLATFORM_COMPLETION.md
PROJECT_STATE.md
```

It must not modify Program IR V5 schemas or language/source semantics.

## 21. Required positive gates

```text
IR5_EXECUTION_PLAN_BUILD=PASS
IR5_PREPARED_INSTRUCTION_EQUIVALENCE=PASS
IR5_FACT_INDEX_EQUIVALENCE=PASS
IR5_PROOF_APPLY_EQUIVALENCE=PASS
IR5_V4_BRIDGE_EQUIVALENCE=PASS
IR5_CHECKPOINT_RESUME_EQUIVALENCE=PASS
IR5_DIFFERENTIAL_FUZZ=PASS
IR5_PERFORMANCE_PROMOTION=PASS
V31_TOTAL_CORE_JS_PARITY_NONREGRESSION=PASS
V31_TOTAL_CORE_REFERENCE_NONREGRESSION=PASS
FULL_REPOSITORY_REGRESSION=PASS
ZERO_SKIP=PASS
```

## 22. Required negatives

At minimum, optimized execution must reject:

- a plan whose `program_hash` does not equal its canonical program;
- a plan whose `authority_hash` does not equal its canonical program;
- a checkpoint for a different program;
- a tampered checkpoint hash;
- a halted checkpoint resume;
- an externally malformed canonical program during plan preparation;
- a stale plan reused after substituting a different canonical program object with a different hash;
- a corrupted prepared instruction reference detected by internal plan validation in tests;
- any proof-open execution whose prepared proof-use identity differs from the reference runtime;
- any V4 bridge result whose fact or receipt identity differs from the reference runtime.

## 23. Promotion policy

The optimized path is promoted only if all correctness, fuzz, parity, regression and performance gates pass together on the same candidate source tree.

Failure policy:

```text
semantic/hash mismatch        -> REJECT
fail-closed regression        -> REJECT
JS parity regression          -> REJECT
full regression failure       -> REJECT
performance gate miss         -> HOLD, not semantic REJECT
```

A performance HOLD leaves the optimized module experimental and leaves the reference runtime as the only promoted 3.1 path.

No tag, package publication, merge to `main`, release or Stable Admission authority is implied by this design document.

## 24. Acceptance theorem

The optimization is accepted only if, for every admitted canonical program `P`, admitted checkpoint `C`, and deterministic task strategy `S` used by the governed campaign:

```text
R_ref(P, C, S) = R_plan(Prepare(P), C, S)
```

where equality is exact `TotalCoreQuantumResultV1` equality, while the prepared path satisfies the declared structural and measured performance gates.

The semantic authority relation remains:

```text
Program IR V5 canonical artifact
            >
private execution plan
```

not the reverse.
