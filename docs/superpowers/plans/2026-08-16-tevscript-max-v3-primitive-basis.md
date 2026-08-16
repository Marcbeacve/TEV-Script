# TEVScript MAX V3 Primitive Basis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and certify the additive TEVScript MAX `3.0.0` primitive semantic basis `Field + Transformation + Apply` on the existing Ω branch without changing V2 or Omega0 authority.

**Architecture:** `omega_semantic_basis_v1.py` is a small canonical kernel containing finite Fields, concrete Field-delta Transformations, Apply receipts and literal sequential composition. `tevprober_max_basis_v1.py` independently checks finite observational minimality against over-refined and insufficient alternatives. A dedicated certifier seals the exact additive frontier and runs basis tests plus Omega0/V2 non-regression when a full repository executor is available.

**Tech Stack:** Python 3.11+ stdlib, existing `tev_script.canonical`, existing `tev_script.diagnostics`, existing Ω0 contracts by hash binding only, `unittest`, canonical SHA-256. No new dependency. No GitHub Actions.

## Global Constraints

- Work only on existing branch `agent/tev-script-omega-kernel-v1`.
- Stable V2 base remains `2bdb047dcad41f9d112219bd65925c25668c02e0`.
- V2 language identity remains `2.0.0`; MAX candidate identity is `3.0.0`.
- Do not modify V2 grammar, Program IR V4, V2 runtime, V2 feature matrix, V2 release metadata, V2 Stable Admission or the root V2 canonical authority.
- Do not modify Omega0 implementation while closing this basis; consume its hashes/contracts additively.
- Every operational quantum remains finite.
- Missing/malformed proof, authority, resource or hash evidence never becomes PASS.
- `Residual`, `Goal`, `Policy`, `Discovery`, `Realization` and related domain constructs are derived library concepts, not primitive kernel families.
- No stable, publication or merge authority is granted by this phase.

---

### Task 1: RED — Field canonicalization contract

**Files:**
- Create: `tests/test_omega_semantic_basis_v1.py`
- Later create: `tev_script/omega_semantic_basis_v1.py`

**Interfaces:**
- `field_fact(relation: str, arguments: Sequence[object]) -> FieldFactV1`
- `semantic_field(facts: Sequence[FieldFactV1], *, profile: str = "actual") -> SemanticFieldV1`
- `validate_semantic_field(value: object) -> SemanticFieldV1`

- [ ] Write tests asserting input order is nonsemantic, duplicate facts reject, unstable relation ids reject, and tampered `field_hash` rejects.
- [ ] Run `python -m unittest -v tests.test_omega_semantic_basis_v1.OmegaFieldTests`; require RED because module does not yet exist.
- [ ] Implement only the Field contract.
- [ ] Re-run the exact test; require PASS.
- [ ] Commit tests + implementation.

### Task 2: RED — Transformation contract

**Interfaces:**
- `field_transformation(...) -> FieldTransformationV1`
- `validate_field_transformation(value: object) -> FieldTransformationV1`

Exact constructor parameters:

```python
field_transformation(
    *,
    transformation_id: str,
    remove_fact_hashes: Sequence[str] = (),
    add_facts: Sequence[FieldFactV1] = (),
    required_before_hash: str | None = None,
    effect_set_hash: str,
    resource_vector_hash: str,
    proof_requirement_hashes: Sequence[str] = (),
) -> FieldTransformationV1
```

- [ ] Add RED tests for deterministic ordering/hash, duplicate removal rejection, add/remove collision rejection, malformed hash rejection and before pin representation.
- [ ] Run only new Transformation tests and observe RED.
- [ ] Implement minimal closed contract.
- [ ] Run all semantic-basis tests; require PASS.
- [ ] Commit.

### Task 3: RED — Apply calculus

**Interfaces:**
- `apply_field_transformation(before: SemanticFieldV1, transformation: FieldTransformationV1) -> tuple[SemanticFieldV1, ApplyReceiptV1]`
- `validate_apply_receipt(value: object) -> ApplyReceiptV1`

Rules:

```text
required_before_hash mismatch -> deterministic diagnostic
remove target missing         -> deterministic diagnostic
collision                     -> construction diagnostic
proof requirements empty      -> PASS
proof requirements non-empty  -> PROOF_REQUIRED
```

The candidate after Field is canonical in both PASS and PROOF_REQUIRED; the receipt preserves the unresolved proof hashes.

- [ ] Add RED positive and negative tests.
- [ ] Observe RED.
- [ ] Implement Apply.
- [ ] Require PASS.
- [ ] Commit.

### Task 4: RED — Literal sequential composition

**Interfaces:**
- `apply_sequence(before: SemanticFieldV1, transformations: Sequence[FieldTransformationV1]) -> tuple[SemanticFieldV1, tuple[ApplyReceiptV1, ...]]`

- [ ] Add tests proving literal replay order is preserved and that a second transformation may pin the exact first result.
- [ ] Add negative test showing reversed order fails when pins/removals make order semantic.
- [ ] Implement only sequential replay; do not add commutativity assumptions.
- [ ] Require PASS.
- [ ] Commit.

### Task 5: RED — TEVProber primitive-basis minimality gate

**Files:**
- Create: `tests/test_tevprober_max_basis_v1.py`
- Create: `tools/tevprober_max_basis_v1.py`

**Interfaces:**
- `evaluate_basis() -> dict[str, object]`
- `verify_basis_report(report: Mapping[str, object]) -> bool`

Finite witness model:

```text
world states:        door.closed, door.open
transformations:     open, close
observations:        resulting state under each admitted transformation
minimal encoding:    Field state + Transformation identity
over-refined:        minimal + unrelated primitive policy tag
insufficient:        Field state only, transformation identity erased
```

Required report:

```text
status = PASS
minimal.sufficient = true
minimal.minimal = true
overrefined.sufficient = true
overrefined.minimal = false
overrefined.overrefined = true
insufficient.sufficient = false
insufficient.counterexample != null
kernel_tcb_expanded_bool = false
promotion_authority_bool = false
```

- [ ] Write RED tests for exact report and tamper rejection.
- [ ] Observe RED.
- [ ] Implement finite exhaustive comparison and self-hashed report.
- [ ] Require PASS.
- [ ] Commit.

### Task 6: Primitive-basis technical certifier

**Files:**
- Create: `tests/test_max_v3_basis_certify.py`
- Create: `tools/tevprober_max_v3_basis_frontier.py`
- Create: `schemas/tev-script-max-v3-basis-certify-receipt.schema.json`
- Create: `RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY.py`

The frontier is exactly:

```text
RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY.py
docs/superpowers/plans/2026-08-16-tevscript-max-v3-primitive-basis.md
docs/superpowers/specs/2026-08-16-tevscript-max-v3-primitive-basis-design.md
schemas/tev-script-max-v3-basis-certify-receipt.schema.json
tests/test_max_v3_basis_certify.py
tests/test_omega_semantic_basis_v1.py
tests/test_tevprober_max_basis_v1.py
tev_script/omega_semantic_basis_v1.py
tools/tevprober_max_basis_v1.py
tools/tevprober_max_v3_basis_frontier.py
```

Certifier requirements:

```text
exact branch identity
exact clean HEAD/tree
exact frontier relative to Omega0 head 35046a16...
V2 governed files unchanged from stable base
Omega0 files unchanged from Omega0 head
basis unittest PASS, zero skips
TEVProber basis PASS
full repository tests PASS when full executor is available
LANGUAGE_STABLE=NO
PROMOTION_AUTHORITY=FALSE
```

The receipt is create-once outside the repository and self-hashed.

### Task 7: Validation and handoff

- [ ] Run basis focal tests.
- [ ] Run Omega0 tests unchanged.
- [ ] Run V2 authority validation.
- [ ] Run full repository test suite.
- [ ] Run `RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY.py` against a clean exact checkout and external receipt path.
- [ ] Verify receipt independently.
- [ ] Only after all above PASS, update the V3 roadmap status; do not claim stable language or publication.

## Next plans after this gate

After primitive-basis certification, continue on the same branch with independently certifiable plans:

1. V3 epistemic/effect type refinements.
2. IR V5 Field/Transformation/Apply profile.
3. V3 process/continuation source surface reusing Ω0 epoch contracts.
4. Derived semantic stdlib ported selectively from `realization-semantics-r0` / R10.
5. Total Core projection (ADTs, generalized termination, defunctionalization).
6. Proof-carrying IR and translation validation.
7. Independent runtime/WASM/native parity.
8. V3 tooling/package/stdlib closure.
9. V3 Stable Admission, release artifact byte lock, draft PR, merge/tag/publication only after exact admission.