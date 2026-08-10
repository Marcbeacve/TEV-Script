# TEV Script Semantic Apply Calculus V0

Status: **post-V1 experimental, additive, non-normative for TEV Script V1**.

This document records the smallest executable semantic calculus currently supported by falsification campaigns over TEV Script. It does not change V1 source syntax, IR V3, reference runtime semantics, ABI V1, stable admission, or the Causal Reaction Model.

## 1. Design objective

TEV Script should become general in what it can represent and reason about while remaining explicit and governed where computation crosses observation, authority, resources, irreversible knowledge, or the external world.

The surface language may grow substantially. The trusted semantic core should not grow proportionally.

The current central judgment is written schematically as:

```text
Î“, L âŠ¢ F ==[T,H]=> Î©
```

where:

- `F` is a canonical semantic Field;
- `T` is a transformation/rule description;
- `Î“` is the centered context: identity, view, knowledge, authority, frame and policy;
- `L` is the law/assumption context;
- `H` is an interpretation regime/handler;
- `Î©` is an Outcome Field carrying status, result state, effect profile and evidence.

A one-sort encoding in which rule descriptions are Fields is allowed, but is not treated as a deep minimality theorem. What matters is the application relation and its laws.

## 2. Canonical Fields

A Field is a finite, canonical, self-describing relational configuration. Relation declarations are encoded as semantic facts, and field identity is SHA-256 over canonical semantic content.

Live entity identity is not content identity. An `EntityId` remains stable while Field snapshots change. Content addressing is intended for immutable artifacts such as programs, IR, schemas, models, contracts, evidence bundles, receipts and snapshots.

A Field that *claims* to be evidence is not therefore authoritative evidence. Evidence authority depends on verifier identity, proof/attestation, scope, provenance and trust stratum.

## 3. Transformation descriptions

Transformation descriptions may themselves be encoded as Fields. A transformation declares intended operations and an indexed effect profile; it does not receive host authority by declaration.

Surface roles such as `observe`, `infer`, `project`, `act`, `verify` and `goal` need not be ontological primitive sorts. They may elaborate to transformation/effect/application patterns.

## 4. Indexed effect-domain algebra

Effects form one indexed family:

```text
Effect(domain, resource(args...), mode, laws, commitment)
```

Domains include, but are not limited to:

```text
state
external
knowledge
authority
cost
time
security
random
choice
event
```

Domain labels do not imply universal laws. Each deployment or semantic domain supplies explicit rules for aliasing, commutativity, temporal read semantics, idempotence, retry safety, reservation, consumption, reversibility, compensation and durability.

`observation` and `action` are overlapping derived roles. A destructive observation such as `queue.pop()` may both acquire knowledge and consume an external resource.

## 5. Resource identity

Capability ids are not resource ids. Resource terms may depend on concrete arguments:

```text
file.write(path, bytes) -> external:file(path)/write
db.update(table,key,v) -> external:row(table,key)/write
```

Therefore two invocations of one capability may be independent after realization even when the static capability id is identical.

Unknown aliasing fails closed.

## 6. Commitment profile

Atomicity is not a scalar. Each effect domain carries a commitment profile with independent dimensions including:

```text
stage:
  untouched | reserved | applied | confirmed | unknown

recoverability:
  reversible | compensable | irreversible | unknown

durability:
  volatile | durable | unknown

epistemic exposure:
  none | acquired | disclosed
```

A reaction may simultaneously be state-reversible, externally partial, epistemically irreversible and cost-consuming.

## 7. Application regimes

The same transformation/effect description may be interpreted by different handlers.

### Evaluate

Pure/internal evaluation. No ambient physical effects.

### Project

Runs against an explicit Model Field. It must not mutate actual external resources. Missing model operations reject rather than falling through to the host.

### Prepare

May acquire real observations, reservations or authority leases and may therefore cross explicitly recorded epistemic/cost/resource frontiers. Physical actuation is represented as intents unless the law specifically declares an acquisition operation unavoidable during preparation.

### Replay

Substitutes recorded observations/transcripts and checks semantic identity and resulting evidence.

### Commit

Consumes a Prepared Outcome and attempts external realization. It preserves `UNKNOWN_COMMIT`, `PARTIAL`, `LAW_VIOLATION` and related statuses rather than inventing success/failure.

Grouping syntax never implies transaction scope. Atomic/transaction boundaries must be explicit.

## 8. Outcome Fields

An Outcome is a Field, not a Bool. Relevant statuses include:

```text
COMPLETED
PREPARED
COMMITTED
REJECTED
ABSTAINED
DEFERRED
SUSPENDED
BUDGET_EXCEEDED
CAPABILITY_UNAVAILABLE
PARTIAL
UNKNOWN_COMMIT
LAW_VIOLATION
```

`UNKNOWN_COMMIT` is a composition barrier. Subsequent action requires reconciliation with newly observed reality.

## 9. Epistemic evidence

Evidence records positive and negative support separately. The focal finite aggregation distinguishes:

```text
NEITHER
TRUE_ONLY
FALSE_ONLY
BOTH
```

This is sufficient to preserve contradiction without overwrite or classical explosion by storage semantics. It is **not** a claim that TEV Script already has a complete paraconsistent logic.

Evidence carries:

```text
source
event_time
knowledge_time
provenance dependencies
status
unknown reason
security label where applicable
```

Invalidating one evidence source invalidates dependent conclusions transitively without erasing history.

Belief-revision policy remains a separate proof/design obligation.

## 10. Center

A Center is a derived semantic profile, not merely a visual projection. It combines at least:

```text
identity
view
knowledge
authority
frame
policy
```

Observation authority and disclosure authority are distinct. Authority attenuation/delegation is monotone: ordinary delegation can reduce scope but cannot amplify it.

## 11. Decision/admission dimensions

The calculus keeps separate:

```text
Possible
Authorized
Safe
ResourcesAvailable
Desirable
```

Admissibility depends on the first four. Desirability/utility is a selection concern and cannot override hard safety or authority constraints.

Abstention, escalation and human review are ordinary semantic outcomes/transformations, not hidden runtime callbacks.

## 12. Projection and causal claims

A projected result binds:

```text
model hash
assumptions
result
fidelity/evidence metadata
```

`Observed<T>` and `Predicted<T>` are not interchangeable.

Temporal precedence is not a causal claim. Causal receipts require an explicit causal criterion and an intervention/counterfactual model. General actual causality remains an open formal boundary.

## 13. Trace and distribution

A Reaction remains a finite local causal closure. Global behavior lives at Trace/Episode level.

Distributed traces retain a partial happens-before order. Concurrent events need not receive a fictitious causal total order. A canonical serialization/publication order may exist independently for reproducibility.

Bounded-response and finite-ranking progress witnesses are supported. General fairness/infinite-trace liveness remains a proof obligation.

## 14. General computation without hidden divergence

The language architecture may support:

```text
finite structural iteration
well-founded recursion with decreasing measures
open computation as bounded resumable quanta
```

Each operational quantum terminates. Long-running/open computations return explicit continuations and statuses such as `SUSPENDED` rather than hiding divergence inside one reaction.

Trace-level computational universality is a hypothesis requiring formal proof before any Turing-completeness claim.

## 15. Abstraction and questions

An abstraction is adequate relative to judgments. For a concrete transition `F -> F'` and abstraction `Î±`, an abstract transition should preserve the requested judgment via a commuting/soundness condition.

A Question may be represented as the minimum epistemic refinement required to make a decision/judgment constant over all remaining possible Fields.

Attention can therefore be derived from judgment dependencies rather than being a primitive semantic machine.

The coarsest adequate abstraction need not be unique in general.

## 16. Self-reference

Programs, models, contracts, proofs and receipts may all be represented as semantic artifacts. This is **stratified semantic homoiconicity**, not unrestricted self-rewrite.

A candidate may not certify a change to the verifier that authorizes that same candidate. Modification requires a verifier/trust stratum strictly above the modified subject, plus strong evidence appropriate to the scope.

## 17. Law justification

A law hash identifies a claim, not truth.

Claims used for strong scheduling, transaction, timing, security or resource conclusions require justification such as:

```text
proved
attested
exhaustively checked over a declared finite scope
```

Sampled empirical evidence remains `PROOF_REQUIRED` for universal claims. Falsifying evidence rejects the law claim.

## 18. Surface-language consequence

This calculus intentionally does **not** prescribe V2 syntax. It supports a surface where ordinary pure code remains ordinary, while operational constructs such as `observe`, `project`, `act`, `require`, protocols and resumable processes elaborate into the common semantic calculus.

The intended relation is:

```text
simple surface syntax
        ->
deep explicit semantics
```

not a verbose metatheory notation for every arithmetic function.

## 19. Open proof obligations

The following are intentionally not claimed closed:

- complete paraconsistent inference;
- belief revision policy;
- general fairness;
- infinite-trace liveness;
- general actual causality;
- trace-level computational universality;
- full protocol/session composition with resources/authority;
- hard-real-time soundness across hosts;
- complete distributed consistency semantics.

## 20. Promotion boundary

V0 is research evidence only until its schemas, reference implementation, falsification campaign, IR V3 embedding and cross-branch compatibility all pass from exact repository identities. It does not claim `LANGUAGE_STABLE=YES`.
