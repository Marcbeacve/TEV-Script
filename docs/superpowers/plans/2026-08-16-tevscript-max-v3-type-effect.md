# TEVScript MAX V3 Epistemic and Effect Typing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD task-by-task. No production code without an observed RED test first.

**Goal:** Add derived epistemic qualifiers and effect rows to MAX V3 while lowering every new object to the existing Field basis.

**Architecture:** One focused module `tev_script/omega_type_effect_v1.py` owns canonical descriptors, explicit epistemic refinement judgments, effect-row subset checking and Field lowering. It imports the semantic basis but creates no new semantic primitive family and grants no capability authority.

**Tech Stack:** Python stdlib + existing TEV canonical hash/diagnostics + `omega_semantic_basis_v1`.

## Global Constraints

- Same branch: `agent/tev-script-omega-kernel-v1`.
- V2 and Omega0 files remain byte-identical.
- Language identity is candidate `3.0.0`; stable/promotion remain false.
- Qualifiers are provenance categories, not an implicit quality order.
- Effect rows are type-level requirements, never authority grants.

### Task 1 — RED/GREEN epistemic type identity

Create `tests/test_omega_type_effect_v1.py` first. Test closed qualifiers, canonical hashes, exact-only implicit assignment and tamper rejection. Observe missing-module RED, then implement `EpistemicTypeV1`, `epistemic_type`, `can_implicitly_assign_epistemic`, `validate_epistemic_type`.

### Task 2 — RED/GREEN explicit epistemic refinement

Add tests for:

```text
Observed target without observation evidence -> REJECT
Predicted target without model evidence       -> REJECT
Verified target without proof                 -> PROOF_REQUIRED
Verified target with proof                    -> PASS
Inferred target with Transformation           -> PASS
Hypothesis target with provenance              -> PASS
```

Implement `EpistemicRefinementReceiptV1` and `refine_epistemic_type`.

### Task 3 — RED/GREEN effect rows

Add tests for canonical order/dedup rejection, actual-subset-of-allowed substitution and non-authority flag. Implement `EffectRowV1`, `effect_row`, `effect_row_substitutable`, validation.

### Task 4 — RED/GREEN Field lowering

Add tests proving epistemic types, effect rows and refinement receipts lower only to `FieldFactV1` / `SemanticFieldV1` using relations `tev.type.epistemic`, `tev.type.effect_row`, `tev.type.epistemic_refinement`. Implement lowering helpers.

### Task 5 — Validation

Run the full new focal tests plus primitive-basis tests. The later global V3 certifier must include this frontier before stable/publication claims.