# TEVScript MAX V3 IR V5 Semantic Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD. Every code task begins with an observed RED test.

**Goal:** Implement the first Program IR V5 profile and a deterministic runtime for continuation-linked bounded quanta.

**Architecture:** `program_ir_v5_semantic.py` owns canonical program/instruction/checkpoint artifacts and validation. `runtime_v5_semantic.py` executes one bounded quantum by delegating Field deltas to `omega_semantic_basis_v1` and epoch/continuation identity to the existing `omega_kernel_v1` Omega0 authority.

**Tech Stack:** Python stdlib, TEV canonical hash, MAX semantic basis, existing Omega0 epoch/continuation contracts.

## Global Constraints

- V2 and Omega0 implementation remain unchanged.
- Every quantum executes at most `quantum_step_limit` instructions.
- Cyclic global control flow is allowed only because suspension is mandatory at the step boundary.
- Proof-open transformations are rejected by this executable profile.
- Checkpoints are exact-program/exact-continuation only.

### Task 1 — RED/GREEN IR V5 program validation

Tests first for canonical program hash, closed transformation table, PC targets, duplicate transformations, proof-open transformation rejection and tamper detection. Implement:

```text
SemanticInstructionV1
SemanticProcessProgramV1
semantic_instruction_*
semantic_process_program
validate_semantic_process_program
```

### Task 2 — RED/GREEN checkpoint validation

Test initial checkpoint, later checkpoint exact state/continuation binding, program mismatch and tamper. Implement `ProcessCheckpointV1`, `initial_process_checkpoint`, `validate_process_checkpoint`, `process_state_hash`.

### Task 3 — RED/GREEN bounded quantum runtime

Test:

```text
apply + halt                 -> HALTED
jump cycle step_limit=3      -> SUSPENDED after exactly 3 steps
resume next epoch            -> continuation link valid
branch_fact                  -> deterministic branch
wrong transformation input   -> fail closed
```

Implement `QuantumResultV1` and `run_semantic_quantum`.

### Task 4 — Open-trace invariant

Run multiple epochs over a cyclic process and assert each epoch uses exactly the finite declared budget while `verify_continuation_link` holds for adjacent receipts. No runtime call may execute an unbounded loop.

### Task 5 — Regression

Run the semantic basis, primitive-basis probe, type/effect and IR V5 focal suites together. Later global certification must add this frontier before any stable/publication claim.