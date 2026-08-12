# TEV Script Axiomatic Semantics V0

Status: **AXIOMATIC_CANDIDATE**  
Language identity: **unchanged (`1.0.0`)**  
System profile: **POST_V1_REALIZATION_SYSTEM_V0**  
Promotion authority: **none**

This document gives the smallest constitutive theory that the post-V1 TEV Script
system is required to realize. It is intentionally narrower than the implementation:
Python classes, receipts, plans, machines, evidence objects and realization records
may remain convenient DTOs, but their **semantic denotation** must project to one of
the two primitive families below.

The axioms are not a claim that the current implementation is already proved
complete. They define proof obligations. A failed Lean/Z3/TEVProver obligation is a
falsification or a `PROOF_REQUIRED` boundary, never something to waive by convention.

## 1. Primitive semantic families

### P0 — Field

A `Field` is a semantic state/carrier of facts, profiles, evidence, resources,
machines, regimes, receipts, traces, verdicts, programs or other denotable state.

`SemanticFieldV0` is the current canonical concrete Field representation. A Python
class does not become a third primitive merely because it has its own DTO shape.

### P1 — Transformation

A `Transformation` is a semantic relation capable of taking a Field to another
Field. Rules, evaluation, discovery, realization, admission, selection, resolution,
lowering and governed execution are transformations or compositions/projections of
transformations.

The current implementation materializes this family operationally through canonical
rules plus application/composition surfaces. V0 does **not** require a new
`SemanticTransformationV0` DTO; representation unification is a separate migration.

### Closure rule

Every semantic denotation introduced after this point MUST be expressible as:

1. a Field;
2. a Transformation; or
3. a non-semantic implementation witness/metadata object that denotes or binds one
   of the above.

A genuinely irreducible semantic object that cannot be represented this way is a
counterexample to V0 and requires revising the primitive basis.

## 2. Meta-logic boundary

Lean and Z3 are used as **meta-logics** for structural obligations. Their classical
logic MUST NOT be confused with TEV Script's object-level evidence logic.

Object-level evidence uses the four values:

`NEITHER`, `TRUE_ONLY`, `FALSE_ONLY`, `BOTH`.

`BOTH` is data saying that support and refutation coexist. It is not translated to a
meta-logical contradiction `P ∧ ¬P`; therefore classical explosion in the prover
does not license explosion inside TEV Script.

## 3. Mathematical axioms

### A0 — Semantic equivalence

`≈F` on Fields and `≈T` on Transformations are equivalence relations.

Exact canonical object equality is always sufficient for `≈F`; stronger behavioral
equivalence may be admitted by a separately scoped proof. Cryptographic hash equality
is an integrity witness, **not** an axiom of mathematical injectivity.

### A1 — Transformation action and congruence

There is an action relation:

`Step(T, before, after)`.

Equivalent Transformations have the same Step relation up to Field equivalence.
Replacing before/after by semantically equivalent Fields cannot change a valid
semantic step.

### A2 — Governed composition

For transformations `f` and `g`, composition is meaningful only under an explicit
`Composable(g,f)` judgment.

When composable:

`Step(g ∘ f, x, z) ↔ ∃y. Step(f,x,y) ∧ Step(g,y,z)`.

Nothing is asserted about the semantic value of `g ∘ f` outside the governed domain.
Physical effects, observations, missing laws and unresolved external serializability
may therefore return `REJECT` or `PROOF_REQUIRED`.

### A3 — Extensional transformation equivalence

If two transformations have the same Step relation for every Field pair, they are
semantically equivalent:

`(∀x y. Step(f,x,y) ↔ Step(g,x,y)) → f ≈T g`.

Together with A2, this yields **conditional associativity** wherever both
parenthesizations are governed/composable. It does not claim that arbitrary physical
effect programs commute.

### A4 — Four-valued evidence algebra

A truth status is the pair `(support, refute)`.

- negation swaps the pair;
- conjunction = `(s1 ∧ s2, r1 ∨ r2)`;
- disjunction = `(s1 ∨ s2, r1 ∧ r2)`.

The four states remain distinct. Contradictory evidence is representable and does not
erase either polarity.

### A5 — Residual soundness

Residual zero is meaningful only relative to an explicitly bound comparison. For a
discovery/realization cycle:

`Theory --realize--> World --discover--> Theory'`

a verified zero residual entails:

`Theory ≈F Theory'`.

The converse is not assumed unless the selected residual projection is proved
complete. Discovery and realization are therefore dual directions, not declared
global inverses.

### A6 — Admission precedes selection

For a selection problem Field `p` and candidate Field `c`:

`Selected(p,c) → Admitted(p,c)`.

Also:

`Selected(p,c) → ¬ProofRequired(p,c)`
`Selected(p,c) → ¬Rejected(p,c)`.

Unknown evidence or unresolved proof cannot be upgraded to a selection.

### A7 — Honest resolution

`NoAdmissible(p) ↔ ∀c. ¬Admitted(p,c)`.

`Indeterminate(p) → ∀c. ¬Selected(p,c)`.

If two semantically distinct admitted candidates are both best under the bound policy,
resolution is indeterminate rather than using name/hash/backend/input-order as a
semantic tie-break.

### A8 — Decision-state separation

The following are distinct constitutive outcomes:

- `PASS`
- `REJECT`
- `PROOF_REQUIRED`
- `SELECTED`
- `INDETERMINATE`
- `NO_ADMISSIBLE_REALIZATION`

No rule may identify `PROOF_REQUIRED` with `PASS`, `INDETERMINATE` with
`SELECTED`, or `NO_ADMISSIBLE_REALIZATION` with an implicit fallback.

## 4. Constitutive system invariants

These are architecture/policy invariants rather than free mathematical axioms. They
are checked by implementation/static gates and, where possible, by formal models.

### C0 — Semantic identity is not cost, evidence or backend identity

Cost/resource observations, proof evidence and backend labels may affect
admissibility, executability or ranking. They do not define semantic identity.

Required non-collapse witnesses include both:

- same semantics with different backend/cost metadata;
- different semantics with the same backend/cost metadata.

### C1 — Explicit effect boundary

No physical effect is implicit. Host effects cross explicit capabilities, and
semantic composition cannot silently promote a physical commit proof.

### C2 — Exact arithmetic boundary

Integer/rational arithmetic remains exact until an explicitly named host capability
performs conversion.

### C3 — Fail closed

Missing capability, exhausted budget, malformed IR, missing proof, hash mismatch,
unresolved observation, or unsupported theorem cannot become `PASS`.

### C4 — Proof scope binding

An external proof witness is useful only when its proof hash, verifier hash and scope
hash are bound and accepted by the configured verifier trust policy. A prover is a
verifier, not TEV Script semantic authority.

### C5 — Authority separation

TEV Script remains the semantic authority for TEV Script. IA-TEV is a consumer.
TEVProver and RepoTalk/Lean/Z3 may certify obligations but do not obtain semantic,
write, merge, release or truth authority merely by verifying them.

### C6 — Exact artifact binding

Post-V1 consumers bind the system API contract hash, the exact distribution artifact
SHA-256 and the canonical system integration receipt. Package version alone is not
system identity.

### C7 — Bounded reasoning honesty

Finite/exhaustive decision procedures may return `PASS` only inside their certified
bound. Exceeding the bound yields `PROOF_REQUIRED` or another explicit non-PASS
outcome.

### C8 — Hashes are bindings, not truth

Canonical hashes bind content and provenance. They are not evidence that a proposition
is true, and no theorem assumes collision-free hashing as a mathematical axiom.

## 5. Derived proof obligations

The machine-checkable V0 campaign must establish at least:

- **T0**: Field equivalence is an equivalence relation.
- **T1**: Transformation equivalence is an equivalence relation.
- **T2**: governed relational composition is conditionally associative.
- **T3**: `Selected → Admitted`.
- **T4**: `NoAdmissible → no Selected`.
- **T5**: distinct tied best candidates force `Indeterminate → no Selected`.
- **T6**: selected candidates cannot be `PROOF_REQUIRED` or `REJECT`.
- **T7**: zero-residual discovery/realization cycles are semantically closed.
- **T8**: four-valued negation is involutive; conjunction/disjunction are associative
  and commutative; De Morgan laws hold.
- **T9**: a non-trivial finite model exists.
- **T10**: semantic identity does not collapse to backend or cost metadata.
- **T11**: an intentionally weakened selection theory admits the forbidden state;
  this is the Z3 negative control proving that the safety axiom is doing work.
- **T12**: implementation correspondence finds the expected Field, rule/application,
  residual, paraconsistent, selection/resolution, proof-boundary and composition
  surfaces.
- **T13**: Lean source typechecks with no `sorry`/`admit`.
- **T14**: all Z3 theorem queries close as `unsat`; the model query is `sat`; the
  negative control rejects its intentionally false expected outcome.
- **T15**: TEVProver accepts only proof objects whose supported finite goal kinds and
  exact scope bindings match the obligation; unsupported goals remain blocked.

## 6. Formal engine allocation

### Lean

Lean proves the abstract typed consequences: equivalence machinery, conditional
associativity, fail-closed selection consequences, residual-zero closure and the
four-valued algebra. Laws are fields of a `Theory` structure; the formal source must
contain no global `axiom`, `sorry` or `admit`.

### Z3

Z3 checks the decidable/first-order fragment:

- selection safety;
- no-admissible and ambiguity consequences;
- non-collapse finite models;
- satisfiability/non-triviality;
- negative controls.

### TEVProver

TEVProver is used for content-addressed finite proof objects only where its installed
kernel declares the goal kind. V0 MUST NOT encode an unsupported higher-order theorem
as a fake TEVProver success. Lean/Z3 proof receipts may later be projected into
`ProofBoundaryWitnessV0` with exact `proof_hash`, `verifier_hash` and `scope_hash`.

### RepoTalk

RepoTalk is the governed execution lane for Lean/Z3. Verification must use the
fixed-command formal surface against an exact checkout HEAD. Direct ad-hoc solver
execution is not equivalent to the RepoTalk receipt.

## 7. Promotion rule

This candidate becomes system authority only after:

1. the static correspondence gate passes;
2. RepoTalk Lean passes with no admissions;
3. RepoTalk Z3 theorem/model/negative-control files pass their exact expected modes;
4. applicable TEVProver obligations are replayed through the installed proof port;
5. the resulting formal receipts are content-bound into the post-V1 system canonical
   index/integration receipt;
6. no historical V1 identity is rewritten.

Until then the correct status is `AXIOMATIC_CANDIDATE`, not `PROVED` or `STABLE`.
