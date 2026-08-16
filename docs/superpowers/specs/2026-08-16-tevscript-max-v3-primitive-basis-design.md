# TEVScript MAX 3.0.0 — Primitive Basis Design

Date: 2026-08-16
Status: DESIGN APPROVED / IMPLEMENTATION CANDIDATE
Base branch: `agent/tev-script-omega-kernel-v1`
Base Ω0 head before this design: `35046a16b2787438f03cffd0d376fbb68d63a5df`
Stable compatibility authority: TEV-Script `2.0.0` at `2bdb047dcad41f9d112219bd65925c25668c02e0`

## 1. Objective

TEVScript MAX is language version `3.0.0`. It preserves V2 as an immutable compatibility profile and extends the Ω line with the smallest semantic basis that can represent computation, evidence, state transition, long-running processes, authority and resource accounting without promoting domain conveniences into kernel authority.

The selected basis is:

```text
Semantic basis:       Field + Transformation
Operational action:   Apply
Open computation:     bounded quantum + continuation + resume
Discipline:           explicit effects + authority + resources + proofs
Derived library:      Residual / Goal / Policy / Law / Candidate /
                      Admission / Selection / Resolution /
                      Discovery / Realization / Planning / Hypothesis
```

`Apply` is an operational judgment over a Field and a Transformation. It is not a third semantic family.

## 2. Governing minimality criterion

A construct receives primitive semantic authority only if removing it causes an observable semantic distinction to become unrepresentable.

The V3 basis gate compares three finite models:

```text
MINIMAL
    Field + Transformation

OVERREFINED
    Field + Transformation + primitive domain tags
    (Residual/Goal/Policy/etc.)

INSUFFICIENT
    Field without transformation identity
```

Admission requires:

```text
MINIMAL.sufficient       = true
MINIMAL.minimal          = true
OVERREFINED.sufficient   = true
OVERREFINED.minimal      = false
OVERREFINED.overrefined  = true
INSUFFICIENT.sufficient  = false
INSUFFICIENT.counterexample != null
KERNEL_TCB_EXPANDED      = false
```

This is the TEVProver/TEVProber observational-minimality rule applied to the MAX language boundary.

## 3. Primitive family P0 — Field

A Field is an immutable finite content-addressed semantic carrier.

V3 concrete representation:

```text
FieldFactV1
    relation: stable relation id
    arguments: canonical finite values
    fact_hash: canonical hash(relation, arguments)

SemanticFieldV1
    schema
    profile
    facts: unique facts sorted by fact_hash
    field_hash
```

Rules:

1. relation IDs are stable ASCII identifiers using `[A-Za-z_][A-Za-z0-9_.:/-]*`;
2. arguments must be accepted by TEV canonical JSON;
3. duplicate fact hashes are rejected;
4. input ordering is nonsemantic; canonical Field order is `fact_hash` lexical order;
5. `field_hash` is computed from the complete canonical body without `field_hash`;
6. hash identity is an integrity/content identity, not a proof of truth;
7. host objects, callbacks, file handles, pointers and ambient references are not Field values.

A Field may denote program state, evidence, a theory, an observation, a proposal, a policy description, a goal description, a continuation descriptor, a receipt graph or any other finite denotable state.

## 4. Primitive family P1 — Transformation

A Transformation is a finite content-addressed semantic relation proposal over Fields.

The first executable V3 kernel fragment is an exact finite Field delta:

```text
FieldTransformationV1
    schema
    transformation_id
    required_before_hash: optional exact Field pin
    remove_fact_hashes: sorted unique hashes
    add_facts: sorted unique FieldFactV1 values
    effect_set_hash
    resource_vector_hash
    proof_requirement_hashes
    transformation_hash
```

The delta fragment is sufficient to represent every concrete finite state transition: any finite before/after pair can be represented by removing the facts absent from the target and adding the facts newly present in the target.

Rules:

1. a required before hash, when present, must match exactly;
2. every removal must exist in the before Field;
3. a transformation cannot remove and re-add the same fact hash in one delta;
4. additions may not duplicate facts that remain after removals;
5. effect/resource hashes are bindings to Ω evidence and do not themselves grant authority;
6. unresolved proof requirements prevent an admitted physical/verified promotion; the basis layer records them but never fabricates proof success;
7. transformation identity is independent of backend/provider identity.

Abstract or input-dependent rules are represented as Fields that generate/propose concrete Transformations under separately governed computation. The small Apply kernel therefore does not need arbitrary executable callbacks.

## 5. Apply calculus

`apply_field_transformation(before, transformation)` performs only the closed delta fragment.

Result:

```text
ApplyReceiptV1
    schema
    before_field_hash
    transformation_hash
    after_field_hash
    effect_set_hash
    resource_vector_hash
    proof_requirement_hashes
    status
    receipt_hash
```

Basis statuses are exactly:

```text
PASS
PROOF_REQUIRED
REJECT
```

Structural failure raises a deterministic TEV diagnostic and produces no after Field. A structurally valid delta with no proof requirements returns `PASS`. A structurally valid delta with unresolved proof requirements returns `PROOF_REQUIRED`; it may compute the candidate after Field but cannot be silently promoted to verified/committed status.

`REJECT` is reserved for explicit judgment adapters; malformed basis objects fail construction/validation rather than becoming ordinary domain data.

## 6. Composition

Composition is derived, not primitive.

A standard-library composition function may apply a finite sequence of Transformations and return the final Field plus the ordered Apply receipts. The kernel does not assume commutativity. Physical/effectful composition additionally requires the existing Ω authority/effect/resource boundaries.

Associativity claims beyond literal sequential replay are proof obligations, not syntax assumptions.

## 7. Process / continuation model

MAX preserves the hard invariant:

```text
EVERY_OPERATIONAL_QUANTUM_TERMINATES
```

Open-ended computation is:

```text
Q0 -> Continuation0
Continuation0 + Q1 -> Continuation1
Continuation1 + Q2 -> ...
```

Ω0 already defines content-addressed `EpochIdentityV1` and `ContinuationReceiptV1`. V3 reuses those contracts rather than creating a second continuation authority.

A V3 process is semantically a Field containing process state plus a Transformation that advances one bounded quantum. `resume` consumes the exact previous continuation identity. There is no `while true`, uncontracted recursion or opaque host task that bypasses the epoch boundary.

## 8. Epistemic and effect typing

V3 targets explicit qualifiers such as:

```text
Observed<T>
Inferred<T>
Predicted<T>
Hypothesis<T>
Verified<T>
```

These are type/effect refinements over values/evidence, not new semantic primitive families. No implicit escalation is permitted, e.g. `Predicted<T> -> Observed<T>` or `Observed<T> -> Verified<T>` requires an explicit admitted Transformation/proof.

Effect summaries remain explicit algebraic bindings. Authority remains deployment/grant state, separate from declaring or describing an effect.

## 9. Semantic standard library

The following MUST be implemented as derived constructions unless a future counterexample proves the basis insufficient:

```text
Residual
Goal
Policy
Law
Evidence aggregation
Hypothesis
Candidate
Admission
Selection
Resolution
Discovery
Realization
Planning
Experiment
Optimization strategy
```

The standard library may provide strong types and ergonomic source syntax, but semantic identity must lower to Field/Transformation/Apply plus Ω proof/effect/authority/resource evidence.

## 10. V2 compatibility

V2 remains independently executable and certifiable.

V3 rules:

1. no V2 source is silently interpreted as V3 source;
2. no V2 Program IR V4 artifact acquires V3 semantics merely because Ω can project it;
3. the existing `omega_v2_adapter_v1.py` remains an adapter, not V3 language authority;
4. V3 has its own language identity `3.0.0` and must receive its own Stable Admission before any stable/publication claim;
5. V2 governed files remain unchanged during the primitive-basis phase.

## 11. Planned IR boundary

The V3 executable semantic target is `TEV_SCRIPT_PROGRAM_IR_V5`.

IR V5 must eventually encode:

```text
closed Field values
closed Transformation values
Apply operations
proof/effect/resource/authority bindings
bounded process quantum
continuation input/output
canonical receipts
```

IR V5 is not part of the primitive-basis implementation task; the basis contract must be frozen first and then used as the semantic target for the V3 frontend/IR work.

## 12. Fail-closed requirements

Reject or hold on:

- malformed canonical values;
- duplicate or unstable facts;
- invalid or tampered hashes;
- missing remove targets;
- add/remove collisions;
- before-field pin mismatch;
- unresolved proof requirements being treated as PASS;
- authority/effect/resource bindings being treated as authority grants;
- implicit backend identity becoming semantic identity;
- domain constructs becoming primitive without a minimality counterexample;
- V2 governed-file mutation in this phase.

## 13. Primitive-basis Definition of Done

```text
V2_GOVERNED_FILES_UNCHANGED=PASS
FIELD_CANONICALIZATION=PASS
FIELD_TAMPER_NEGATIVES=PASS
TRANSFORMATION_CANONICALIZATION=PASS
DELTA_APPLY=PASS
BEFORE_PIN_NEGATIVE=PASS
REMOVE_MISSING_NEGATIVE=PASS
ADD_REMOVE_COLLISION_NEGATIVE=PASS
PROOF_REQUIRED_NOT_PASS=PASS
SEQUENTIAL_COMPOSITION=PASS
MINIMAL_BASIS_SUFFICIENT=PASS
OVERREFINEMENT_DETECTED=PASS
INSUFFICIENT_BASIS_COUNTEREXAMPLE=PASS
OMEGA0_NON_REGRESSION=PASS
PROMOTION_AUTHORITY=FALSE
LANGUAGE_STABLE=NO
```

This gate closes only the V3 semantic primitive basis. IR V5, frontend syntax, full semantic stdlib, independent runtimes and V3 Stable Admission remain subsequent independently certifiable closures on the same evolution branch.