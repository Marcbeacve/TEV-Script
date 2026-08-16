# TEVScript MAX V3 Derived Semantic Stdlib Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD; each production feature begins with an observed failing test.

**Goal:** Implement Residual, decision/admission/selection/resolution and discovery/realization closure as derived views over MAX Field/Transformation.

**Architecture:** One focused module `tev_script/semantic_stdlib_v1.py` owns canonical DTO views and Field lowering/parsing. It imports only canonical hashing, diagnostics and the MAX semantic basis. It neither imports historical `semantic_*_v0` modules nor grants host authority.

## Constraints

- Same existing Omega branch.
- No V2/Omega0 file mutation.
- No hidden candidate/hash/backend tie-breakers.
- `PROOF_REQUIRED` never upgrades to PASS.
- All canonical authority is Field/Transformation.

### Task 1 — Residual RED/GREEN

Write tests for CLOSED iff no obstructions, canonical order, exact parse/tamper, and progress `CLOSED/REDUCED/UNCHANGED/REGRESSED/CHANGED/INCOMPARABLE` under exact boundary identity. Then implement `ResidualObstructionV1`, `ResidualViewV1`, `residual_field`, `parse_residual`, `compare_residuals`.

### Task 2 — Decision RED/GREEN

Write tests for candidate/admission facts, selected implies PASS, open candidate -> INDETERMINATE, all rejected -> NO_ADMISSIBLE_REALIZATION, unique best admitted -> SELECTED, equal best distinct candidates -> INDETERMINATE. Implement `DecisionCandidateV1`, `AdmissionV1`, `DecisionResultV1`, `decision_field`, `resolve_candidates`.

### Task 3 — Discovery/realization RED/GREEN

Write tests proving exact transformation application produces a closure residual; exact recovered theory -> CLOSED; mismatched recovered theory -> OPEN with exact obstruction. Implement `closure_residual`, `discovery_realization_field`.

### Task 4 — Lowering/non-authority

Assert every stdlib product is a `SemanticFieldV1` and contains no authority-grant primitive. Run all new MAX focal suites together.