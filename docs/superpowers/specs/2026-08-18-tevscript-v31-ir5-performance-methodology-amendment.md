# TEVScript 3.1 IR5 Execution Plan — Performance Methodology Amendment

Date: 2026-08-18
Status: DESIGN AMENDMENT / CORRECTS PERFORMANCE METHODOLOGY
Parent spec: `docs/superpowers/specs/2026-08-18-tevscript-v31-ir5-execution-plan-design.md`

## 1. Reason for amendment

The parent design correctly preserves canonical checkpoint/result validation in Phase A, but its first performance-gate table incorrectly required large **end-to-end** speedups for `branch_fact` while the boundary validators still perform work proportional to program/Field size.

The reference call path is structurally:

```text
run_total_core_quantum
  -> validate_total_core_program
  -> validate_total_core_checkpoint
       -> validate_total_core_program
       -> total_core_checkpoint
            -> validate_total_core_program
            -> validate_semantic_field
            -> canonical checkpoint reconstruction/hash
  -> execute instruction loop
  -> total_core_checkpoint
       -> validation/reconstruction
  -> _build_quantum_result
       -> validate_total_core_program
       -> validate_semantic_field
       -> validate_total_core_checkpoint
       -> canonical result reconstruction/hash
```

The prepared Phase A path intentionally retains the same canonical boundary/evidence semantics. Therefore changing the branch instruction itself from:

```python
any(fact.fact_hash == needle for fact in field.facts)
```

to:

```python
needle in fact_hashes
```

changes the instruction lookup from O(number_of_facts) to average O(1), but cannot by itself guarantee a 4x end-to-end quantum speedup while O(number_of_facts) validation/canonicalization remains outside the hot loop.

This is a methodology error, not an implementation failure. The gate must distinguish the cost layer being measured.

## 2. Two-layer benchmark model

All performance certification is split into two non-substitutable layers.

### Layer A — algorithmic hot-path gate

Measures only the operation that Phase A is authorized to change. Preparation and external boundary validation occur before the timed region.

For branch membership the benchmark compares:

```text
reference predicate = linear scan of canonical field facts
prepared predicate  = hash-set membership over a prebuilt runtime-only index
```

Required field cardinalities:

```text
10
100
1_000
10_000
```

This layer proves the intended complexity change independently of checkpoint/evidence cost.

### Layer B — canonical end-to-end quantum gate

Measures the public/reference quantum call and prepared quantum call including all currently retained Phase A boundary validation and evidence construction.

This layer answers a different question: how much latency does Phase A save **without weakening the canonical boundary**?

Layer A PASS can never be used as evidence that Layer B passed, and vice versa.

## 3. Corrected Layer A promotion gates

For `branch_fact`:

```text
BRANCH_INDEX_IDENTITY_ALL_CARDINALITIES=PASS
BRANCH_PREPARED_LOOKUP_10K_VS_REFERENCE_SPEEDUP >= 10.0
BRANCH_PREPARED_SCALING_10K_OVER_10            <= 2.0
BRANCH_REFERENCE_SCALING_10K_OVER_10           >= 20.0
```

The scaling ratios compare median lookup time at the stated cardinalities in the same fresh process.

These gates validate the algorithmic claim:

```text
reference membership grows with field cardinality
prepared membership remains approximately flat
```

No canonical hash/result claim is inferred from the microbenchmark; canonical identity is covered by the differential runtime suite.

## 4. Corrected Layer B Phase A gates

Phase A end-to-end gates become conservative because boundary/evidence work is intentionally retained:

```text
SEMANTIC_IDENTITY_ALL_CASES=PASS
jump_10k.speedup                 >= 1.02
apply_plain.speedup               >= 1.02
apply_proof_admitted.speedup      >= 1.05
mixed_total_core.speedup          >= 1.05

branch_fact_10.p95_ratio          <= 1.05
branch_fact_100.p95_ratio         <= 1.05
branch_fact_1k.p95_ratio          <= 1.05
branch_fact_10k.p95_ratio         <= 1.05

invoke_v4_pure.p95_ratio          <= 1.05
invoke_v4_recursive.p95_ratio     <= 1.05
invoke_v4_effects.p95_ratio       <= 1.05

GEOMEAN_PHASE_A_E2E_SPEEDUP        >= 1.05
```

These thresholds are not a declaration that 5% is the final performance ceiling. They are a **non-regression/promotion gate for the limited Phase A trust change**.

## 5. Phase B decision gate

The benchmark must profile the canonical end-to-end mixed workload and attribute time to:

```text
prepared hot instruction execution
checkpoint/program/field validation
canonical continuation/checkpoint/result construction and hashing
V4 child execution when present
other
```

Define:

```text
boundary_evidence_share =
  (validation + canonical evidence construction time)
  / total prepared end-to-end quantum time
```

Decision:

```text
boundary_evidence_share < 0.20
    -> Phase B remains YAGNI.

boundary_evidence_share >= 0.20
    -> Phase B becomes REQUIRED before this optimization project may claim
       final 10/10 performance closure.
```

Phase B still requires its own design amendment before changing trusted constructors or external validation behavior.

## 6. Final 10/10 criterion

The optimization project may be called `10/10` only when all of the following are true:

```text
exact reference/prepared canonical identity = PASS
1,000-seed differential fuzz              = PASS
all five instruction kinds                 = PASS
proof admission boundary                   = PASS
resume/continuation identity                = PASS
stale/tampered plan negatives               = PASS
JS canonical parity non-regression          = PASS
full repository regression                  = PASS
zero skip                                   = PASS
Layer A algorithmic gates                   = PASS
Layer B Phase A gates                       = PASS
```

and additionally either:

```text
boundary_evidence_share < 20%
```

or:

```text
Phase B designed + implemented + differentially verified + benchmarked = PASS
```

This prevents a local hot-loop win from being mislabeled as complete runtime optimization while preserving the rule that performance work cannot weaken canonical authority merely to obtain a benchmark number.

## 7. Superseded parent-spec text

This amendment supersedes only the performance thresholds and interpretation in parent sections 13-14. All parent invariants, correctness gates, complexity gates, fuzz requirements, JS parity requirements and Phase B authority restrictions remain in force.