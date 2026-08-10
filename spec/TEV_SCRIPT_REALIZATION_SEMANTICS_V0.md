# TEV Script Realization Semantics V0

Status: **experimental post-V1 architecture contract**.

This document does not alter the admitted TEV Script V1.0.0 source semantics, linked-program identity, IR V2/V3 semantics, runtime ABI, or the historical `v1.0.0` release identity.

## 1. Purpose

TEV Script currently separates source semantics from runtime implementations. Realization Semantics V0 generalizes that boundary so a semantic Transformation may have multiple independently identified physical/software realizations without making any realization the semantic authority.

The architectural target is not:

```text
TEV -> one compiler -> one machine
```

but:

```text
Transformation semantics
        |
        v
Realization problem
        |
        +-- admissibility constraints
        +-- evidence policy
        +-- approximation policy
        +-- resource policy
        +-- available machine/substrate descriptions
        |
        v
candidate realizations
        |
        v
verify / validate / measure
        |
        v
admitted realization(s)
        |
        v
selection / execution / observation
```

Compilation, reuse, specialization, interpretation, JIT/AOT lowering, GPU kernels, distributed placement and future hardware synthesis are strategies for producing a Realization. They are not separate semantic foundations.

## 2. Primitive model

Realization V0 introduces **no new primitive**.

```text
Field
Transformation
```

remain the architectural primitive families.

A Machine, ResourceVector, Evidence record, ApproximationContract, RealizationProblem, RealizationCandidate, admission decision, resource observation and RealizationReceipt are all representable as Fields.

Operations such as:

```text
CanRealize
AdmitRealization
ComposeResourceCost
ParetoFront
ObserveRealizationCost
```

are Transformations over those Fields.

`Realization` is therefore a semantic profile of Field data, not a third primitive beside Field and Transformation.

## 3. Semantic identity versus realization identity

The central invariant is:

```text
Transformation semantic identity != Realization identity
```

A Transformation semantic hash identifies **what relation/computation is required**.

A Realization hash identifies one candidate way to realize that Transformation under a machine/substrate description, artifacts, assumptions, evidence and resource predictions.

Therefore all of the following may realize the same Transformation:

```text
Python reference execution
JavaScript runtime
C# runtime
WASM artifact
x86-64 native binary
ARM64 native binary
GPU kernel
FPGA circuit
cluster plan
```

without changing the Transformation semantic hash.

Changing machine, code layout, compiler version, optimizer, scheduling policy or measured cost MUST NOT silently change Transformation semantic identity.

## 4. Correctness precedes optimization

Realization selection is two-stage:

```text
1. admissibility
2. optimization / selection
```

A candidate R may be considered for cost optimization only if it first satisfies the applicable semantic/evidence/resource policy.

Formally:

```text
Admissible(R, T, C, P)
```

is evaluated before:

```text
argmin Cost(R, C)
```

or Pareto selection.

A cheaper incorrect realization is never preferable to a correct one.

Cost policy MUST NOT upgrade semantic evidence, relax an approximation contract, invent missing machine capabilities or hide a failed proof obligation.

## 5. Semantic relations

A candidate Realization explicitly declares one semantic relation to the requested Transformation.

V0 relations are:

```text
EXACT_EQUIVALENT
REFINEMENT
APPROXIMATION
SIMULATION
PROJECTION
```

Their meanings are intentionally distinct.

### EXACT_EQUIVALENT

The candidate claims equality of the governed observable semantics inside the declared scope.

This is the preferred relation for ordinary compilation and runtime replacement.

### REFINEMENT

The candidate is at least as constrained/defined as the source relation under an explicit refinement contract.

Refinement does not imply byte identity, implementation identity or unrestricted behavioral equality outside the certified scope.

### APPROXIMATION

The candidate may differ from exact semantics only according to an explicit ApproximationContract.

Approximation MUST NOT be silently promoted to exact equivalence.

### SIMULATION

The realization establishes a simulation relation sufficient for the declared use but not full observable equivalence.

### PROJECTION

The realization computes a governed projection/model view and does not claim execution of the full source semantics.

Policies decide which relations are acceptable for a given RealizationProblem.

## 6. Approximation contract

Every `APPROXIMATION` realization requires an explicit approximation contract.

At minimum the contract binds:

```text
metric identity
domain identity
error upper bound
guarantee kind
optional confidence lower bound
```

Guarantee kinds are distinct, for example:

```text
DETERMINISTIC_BOUND
PROBABILISTIC_BOUND
EMPIRICAL_BOUND
```

A probabilistic/empirical guarantee is not a proof of a deterministic bound.

An exact/refinement realization MUST NOT carry a non-empty approximation contract as if it were semantically irrelevant.

## 7. Evidence is not a scalar rank

Evidence is represented independently from semantics and cost.

V0 evidence methods include:

```text
PROOF
EXHAUSTIVE
TRANSLATION_VALIDATION
DIFFERENTIAL_TEST
STATISTICAL_VALIDATION
EMPIRICAL_OBSERVATION
ATTESTATION
ASSUMPTION
```

These methods are not forced into one total ordering.

A policy can require, for example:

```text
TRANSLATION_VALIDATION by verifier H
```

without asserting that this method is globally stronger or weaker than all other methods.

Evidence binds:

```text
claim hash
scope hash
method
verifier identity
witness identity
assumption identities
coverage/profile data
status
```

Evidence status is explicit and may be:

```text
ACTIVE
REVOKED
FALSIFIED
```

A revoked/falsified witness cannot remain an active admission witness.

Existing TEV proof-boundary witnesses may be projected into the general realization-evidence representation; they remain their own typed authority and are not redefined by R0.

## 8. Claims and circularity avoidance

Evidence does not attest the whole candidate object including itself.

A RealizationCandidate has a separate **semantic claim hash** built from the candidate realization payload, requested Transformation, Machine identity, semantic relation, approximation contract and assumptions, but excluding evidence references.

Evidence items target this semantic claim hash.

This avoids the circular definition:

```text
candidate hash -> evidence hash -> candidate hash
```

The final candidate hash may include evidence references after the claim is independently defined.

## 9. MachineField

A machine/substrate is described as a Field, not as a vendor conditional in TEV semantic code.

A MachineField may describe:

```text
operation semantic capabilities
numeric models
memory/address spaces
parallelism capabilities
communication capabilities
synchronization/atomicity properties
artifact/executable formats
capacity/resource declarations
additional canonical properties
```

The core asks:

```text
CanRealize(T, MachineField)?
```

rather than:

```text
if NVIDIA ...
if x86 ...
```

Vendor/product-specific adapters MAY produce MachineFields but vendor names are not TEV semantic primitives.

Each machine operation capability binds a stable operation id to a semantic operation hash. A candidate may require operation semantic hashes; admission fails closed when the target machine does not advertise them.

## 10. Resource algebra

Runtime `EffectAtomV0` already models committed/external resource effects. Realization resources solve a different problem: prediction, bounds, observations and composition of implementation cost.

The two surfaces may be related but MUST NOT be conflated.

R0 ResourceVector quantities are non-negative exact rational bounds over named dimensions.

Each ResourceDimension declares composition laws for at least:

```text
SEQUENTIAL
PARALLEL
```

Supported base aggregation laws are deliberately small:

```text
SUM
MAX
```

Examples:

```text
latency:
  sequential = SUM
  parallel   = MAX

energy:
  sequential = SUM
  parallel   = SUM

peak_memory (one possible profile):
  sequential = MAX
  parallel   = SUM
```

More sophisticated reliability/bandwidth/temporal algebras require their own declared laws instead of being approximated by an unjustified scalar formula.

Unknown upper bounds remain unknown. They MUST NOT be converted to zero or a guessed finite value.

## 11. Resource predictions versus observations

Predicted and observed resources are different Fields.

A candidate may carry:

```text
predicted_resource_vector
```

while execution later produces:

```text
ResourceObservation(
    realization_hash,
    execution_context_hash,
    observed_resource_vector
)
```

Observations may train/update a future CostModel, but measured latency/energy/memory changes do not modify Transformation semantic identity.

The same realization may have different observations under different machines, workloads, placements or contention contexts.

## 12. Resource policy

A RealizationPolicy may define hard ceilings such as:

```text
latency <= L
memory <= M
energy <= E
money <= C
```

A known upper bound exceeding a hard ceiling is a semantic admission rejection under that policy.

A missing/unknown upper bound for a required hard ceiling is not silently accepted. It produces a proof/measurement/resource-information obligation.

Soft optimization preferences belong to later selection/planning and are not hard admissibility constraints.

## 13. RealizationProblem

A RealizationProblem binds:

```text
requested Transformation semantic hash
execution/context hash
admission policy hash
available MachineField hashes
optional required artifacts/capabilities
```

The problem asks for admissible realization candidates. It does not prescribe one algorithm for finding them.

Search may use:

```text
lookup
reuse
compilation
specialization
composition
rewriting/e-graphs
superoptimization
program synthesis
hardware synthesis
remote discovery
```

without changing the problem identity.

## 14. RealizationCandidate

A candidate binds:

```text
requested Transformation semantic hash
realization kind
machine hash
artifact hashes
required machine-operation semantic hashes
semantic relation
optional approximation contract
assumption hashes
predicted resource vector
evidence references
provenance identities
```

Examples of `realization kind` are descriptive stable ids rather than a closed semantic enum:

```text
tev.realization.interpreter
tev.realization.wasm
tev.realization.native
tev.realization.gpu
tev.realization.fpga
tev.realization.distributed
```

Future kinds may be introduced without changing the primitive model.

## 15. Admission policy

Admission is a pure semantic Transformation over canonical Fields.

At minimum admission checks:

1. requested Transformation hash matches the candidate;
2. candidate Machine hash matches the supplied MachineField;
3. required operation semantic hashes are available;
4. semantic relation is allowed;
5. approximation contract is structurally valid and within policy;
6. candidate assumptions are accepted by policy;
7. required evidence exists, is active and targets the exact semantic claim;
8. required verifier identities/methods/scopes satisfy evidence policy;
9. hard resource ceilings are not exceeded;
10. unknown required resource bounds remain explicit obligations.

Admission returns one of:

```text
PASS
PROOF_REQUIRED
REJECT
```

`PASS` means the candidate is admissible under the supplied policy and known evidence. It does not mean globally optimal.

## 16. Realization Residual

Every non-closed admission decision can be represented as a structured Residual Field.

Typical obstruction kinds include:

```text
realization.transformation_mismatch
machine.identity_mismatch
machine.operation_missing
relation.not_allowed
approximation.contract_missing
approximation.metric_mismatch
approximation.bound_exceeded
assumption.not_accepted
evidence.required
evidence.claim_mismatch
evidence.method_unaccepted
evidence.verifier_untrusted
evidence.inactive
resource.bound_unknown
resource.ceiling_exceeded
```

A candidate may therefore be iteratively improved by reducing its Residual:

```text
candidate R0 -> residual open
specialize     -> residual smaller
collect proof  -> residual smaller
choose machine -> residual closed
```

Residual remains a Field produced by a diagnostic/admission Transformation, not a new primitive.

## 17. Pareto selection

Optimization is not required to collapse all resource dimensions to one scalar.

Given admitted candidates, R0 supports deterministic Pareto-front extraction over selected resource dimensions.

Candidate A dominates B only when A is no worse in every selected known upper-bound dimension and strictly better in at least one.

Unknown required values make candidates incomparable rather than magically cheap.

Policy-specific weighted utility, monetary conversion, learned preferences and scheduling are future planner concerns.

## 18. Semantic memoization

For pure Transformations, result memoization SHOULD be keyed by semantic identity rather than realization identity:

```text
H(
  transformation_semantic_hash,
  canonical_input_hash,
  semantic_environment_hash
)
```

This permits exact CPU/GPU/WASM realizations of the same Transformation to share semantically valid cached results when all governing assumptions match.

A cache hit is a realization strategy; it does not alter the Transformation.

## 19. Specialization and partial evaluation

A specialized realization MUST preserve provenance:

```text
parent_transformation_hash
specialization_bindings_hash
specialized_transformation_hash or refinement relation
realization hash
validation evidence
```

Partial evaluation may improve cost but cannot erase the semantic relation connecting the specialized artifact to its source Transformation.

## 20. Adaptive realization

Future adaptive replacement is governed by the same admission model.

A running system MUST NOT replace R1 with R2 merely because a profiler predicts R2 is cheaper.

The transition requires:

```text
candidate R2
  -> semantic/evidence admission
  -> state/ABI compatibility admission
  -> transactional replacement
  -> observation
  -> rollback evidence where applicable
```

The existing TEV causal prepare/commit/abort model is the intended architectural substrate for such replacement.

## 21. Placement and heterogeneity

A Realization may be composite.

For example:

```text
T
|- T1 -> CPU
|- T2 -> GPU
|- T3 -> remote node
`- T4 -> FPGA
```

The composite realization must bind communication/memory-transfer operations and their resource/effect assumptions. Moving data is not treated as free.

Placement is a realization concern, not part of the source Transformation semantic identity unless location itself is semantically observable in the Transformation specification.

## 22. Fault tolerance

Replication/redundancy may be a realization strategy when policy requires stronger reliability.

For example:

```text
R = vote(R1, R2, R3)
```

is admissible only if the composition relation and failure assumptions are explicit.

R0 does not define a universal reliability algebra because independent/correlated failures require different laws.

## 23. Backend synthesis

The Realization boundary intentionally permits future backend synthesis.

Given:

```text
Transformation semantics
MachineField
admission/evidence policy
```

an engine may synthesize a lowering/backend candidate rather than invoke a handwritten backend.

The synthesized backend or machine program remains a candidate Realization and requires the same validation/evidence boundary as handwritten output.

No synthesized compiler may become its own sole authority.

## 24. Self-hosting and reflection

Self-hosting is not an R0 requirement.

A future TEV-written compiler/realizer is a strong sufficiency test, but the Realization abstraction must work before self-hosting exists.

Reflection is stratified. A candidate may inspect/request optimization of its own semantic/artifact Fields, but it cannot rewrite the verifier/policy that authorizes the same transition within the same authority stratum.

## 25. Source syntax is a view

R0 does not require `.tevs` text to remain the unique long-term semantic authority.

The architecture permits a future canonical semantic object graph with multiple views:

```text
TEV Script text
agent-generated semantic IR
proof view
causal view
performance view
hardware view
```

However V1 source programs continue to embed through the admitted V1 frontend/link/IR path. R0 cannot reinterpret V1 source semantics.

## 26. Undecidability and bounded claims

Realization search is not assumed complete.

The architecture explicitly permits outcomes including:

```text
PASS
REJECT
PROOF_REQUIRED
UNKNOWN
TIMEOUT
RESOURCE_EXHAUSTED
UNDECIDABLE_IN_THIS_SYSTEM
```

No component may claim that TEV can always:

```text
find the optimal program
prove arbitrary equivalence
decide termination in general
solve undecidable semantic properties
```

The ability to preserve `UNKNOWN` or an explicit Residual is a required correctness property.

## 27. Trusted computing base

The target TCB is:

```text
canonical semantic contracts
canonical hashing/value model
small realization/verifier contracts
admission policy semantics
trusted proof/verifier boundaries chosen by policy
```

Compilers, optimizers, synthesis engines, profilers and cost models should be replaceable proposal mechanisms whenever independent validation can re-establish the required claim.

## 28. Relationship to V1 runtimes

R0 first wraps existing executions as realizations; it does not replace them.

The current pipeline:

```text
TEV_SCRIPT_LINKED_PROGRAM_V1
  -> IR V2/V3
  -> Python / JS / C# / Browser-WASM / WASI
```

becomes the first Realization corpus.

This allows the Realization semantics itself to be tested using already-certified host diversity before any native CPU/GPU backend is introduced.

## 29. R0 success criteria

R0 is considered focal-closed only when one exact Git identity demonstrates:

1. MachineField has content-addressed canonical identity.
2. ResourceVector composition preserves exact rational bounds and unknowns fail closed.
3. Evidence items bind exact claims/scopes/verifiers and revoked/falsified evidence cannot admit a candidate.
4. Exact and approximate relations cannot be confused.
5. Approximation requires an explicit contract.
6. RealizationCandidate semantic claim hash is independent of its evidence references.
7. Machine-operation mismatch produces REJECT/Residual.
8. Missing required evidence produces PROOF_REQUIRED/Residual.
9. Hard resource-ceiling violations produce REJECT/Residual.
10. Unknown hard resource bounds remain obligations.
11. PASS candidates alone are eligible for Pareto extraction.
12. Cost/resource changes do not alter Transformation semantic identity.
13. Existing V1/post-V1 semantic tests remain untouched during focal development.
14. No vendor/ISA/GPU-specific concept becomes a primitive dependency of the semantic core.
15. No new authority dependency on CUOFC, TEVProver or IA-TEV is introduced.

Long repository-wide certification remains a separate final phase.

## 30. Immediate roadmap after R0

```text
R0  realization semantics
R1  existing hosts represented as governed Realizations
R2  translation-validation boundary
R3  machine-independent lowered IR + native CPU
R4  equivalence/specialization optimization algebra
R5  cost-model learning and planner
R6  heterogeneous CPU/GPU realization
R7  distributed placement/fault tolerance
R8  realization/backend synthesis
R9  hardware/FPGA realization
R10 adaptive safe replacement
R11 autonomous Transformation synthesis
R12 canonical semantic substrate with multiple human/agent views
```

The ordering is intentional: TEV defines what a valid Realization means before committing the architecture to x86, GPU, FPGA or any other substrate.