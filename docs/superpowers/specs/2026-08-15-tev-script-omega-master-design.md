# TEV-Script Ω — Master Design

Date: 2026-08-15

## Objective

Maximize usable computational power while minimizing trusted authority.

The target is not a large all-purpose core. The target is a small semantic kernel plus verifiable extensions:

```text
TEV-Script Ω = K + P + C + R + E
```

where:

- `K` = minimal semantic kernel;
- `P` = proofs/certificates and translation-validation evidence;
- `C` = capability/authority algebra;
- `R` = compositional resource algebra;
- `E` = epochs/continuations for open-ended computation.

Everything else—ADTs, protocols, network, GPU, AI, databases, Unity, distributed compute, package systems, native compilation—is compiled or projected onto those five foundations.

The stable TEV-Script V2.0.0 release remains immutable authority:

```text
BASE_COMMIT=2bdb047dcad41f9d112219bd65925c25668c02e0
BASE_TREE=aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8
LANGUAGE_VERSION=2.0.0
STABLE_ADMISSION_RECEIPT_SHA256=4235895f6229e168ff315c41624c23c205692046b74e030f6fd3fc8ca40adfe6
```

Ω is a new research/evolution track and must never silently redefine V2 stable artifacts or inherit V2 stable admission for new semantics.

## Pareto objective

TEV-Script Ω optimizes expressivity subject to hard constraints:

```text
maximize expressivity
subject to:
  closed semantics
  explicit authority
  reproducible execution
  statically/explicitly accountable resources
  minimal trusted computing base
```

The design accepts that expressivity, decidability, performance, portability, security, and TCB size compete. No single “maximum feature set” is the target.

## Approaches considered

### A. Grow the language core until it resembles Rust/C++

Rejected. This increases the TCB, makes formal reasoning harder, and turns external systems into ambient semantics.

### B. Keep V2 fixed and put every feature in trusted host code

Rejected. It preserves a small core but moves too much semantic authority into providers and host runtimes, making verification weak.

### C. Minimal kernel + typed/proved extensions — selected

Keep a small kernel of values, types, total functions, transitions, effects, authority, resources, and proof objects. Compile richer syntax/features into this kernel and validate each lowering with small verifiers.

## K — Minimal semantic kernel

The trusted semantic kernel contains only constructs necessary to express and check deterministic bounded transitions:

```text
values
types
total functions
closed control
state transitions
effect algebra
authority algebra
resource algebra
proof/certificate objects
canonical identity
```

The kernel does not contain HTTP, GPU, databases, filesystems, processes, threads, AI models, Unity, distributed clusters, or arbitrary FFI.

### Kernel invariants

- deterministic given explicit inputs/transcripts;
- exact integer/rational semantics until explicit host conversion;
- no ambient I/O;
- no runtime source compilation;
- no arbitrary executable pointers;
- no unrestricted reflection;
- no unbounded execution construct;
- malformed/missing authority, resources, proofs, or hashes fail closed.

## Decidable refinement layer

The core type system remains decidable. Refinements are limited to a closed, mechanically decidable logic with optional explicit proof objects for stronger claims.

Examples:

```text
Int{0 <= value < 256}
List<Byte,N>{length <= N}
FileHandle<Root=R,Mode=Read,MaxBytes=1048576>
```

Policy:

```text
decidable core typing
+ optional explicit proof objects
+ external provers as untrusted assistants
```

Type checking must not become arbitrary theorem proving.

## C — Capability / authority algebra

Capabilities become first-class authority objects with explicit algebraic operations:

```text
grant
attenuate
delegate
consume
revoke
compose
```

Authority objects have identity, scope, lifetime, resource budget, and duplication policy.

### Linear / affine grants

Certain grants are linear or affine:

```text
Grant<FileReplace>
  -> commit
  -> ConsumedGrant<FileReplace>
```

A linear grant cannot be duplicated:

```text
G != G tensor G
```

This directly represents use-once permissions, exclusive resources, ownership, locks, transfers, revocation tokens, and consumable budgets.

### Effect signatures

Function signatures expose causal effects:

```text
A -{E}-> B
```

Examples:

```text
normalize : Text ->{} Text
inspect   : Path ->{observe:file.read} Result
publish   : Artifact ->{observe:network,command:file.replace} Receipt
```

Compile-time rule:

```text
Effects(function) subseteq Authority(caller)
```

Effects are algebraic values, not hidden host calls.

## Session/protocol types

Capabilities that represent temporal protocols may carry state-machine/session types.

Example:

```text
Connect -> Send<Request> -> Receive<Response> -> Close
```

Illegal temporal transitions fail at compile/admission time where statically decidable, or at the smallest runtime protocol kernel otherwise.

This applies to APIs, databases, distributed protocols, hardware, robotics, and long-lived agent/provider sessions.

## Nondeterminism rule

Nondeterminism is never implicit semantics.

External uncertainty is converted into explicit content-addressed observation evidence:

```text
world
  -> observation
  -> transcript/evidence
  -> deterministic kernel computation
```

Therefore:

```text
Program + Transcript -> Result
```

is deterministic even if the external world was not.

Clock values, random bytes, network arrivals, sensor readings, user input, LLM outputs, and filesystem observations all follow this rule.

## R — Resource algebra

Every admitted computation carries a compositional resource vector:

```text
R(P) = <cpu,memory,stack,io,network,gpu,tasks,storage,effects,communication>
```

Composition laws are explicit and conservative.

Examples:

```text
R(A ; B) = R(A) + R(B)
R(select(A,B)) <= max(R(A),R(B))
R(parallel(A,B)) = componentwise_composition(A,B,policy)
```

A resource component may be static, proof-bounded, provider-bounded, or explicitly unknown/unavailable. Unknown is never silently converted to zero.

Authority grants may carry resource budgets and consumption semantics.

## General total computation

Ω generalizes termination without accepting arbitrary recursion.

Termination hierarchy:

```text
structural recursion
integer measure
lexicographic measure
multiset order
well-founded relation + explicit proof
```

Every recursive call must have a checkable decrease witness. Unproven recursion is rejected.

User ADTs and exhaustive pattern matching are required projections because they enable clean structural algorithms, compiler IRs, protocol states, symbolic expressions, and proof terms.

Higher-order source constructs are admitted only when build-time closure conversion and defunctionalization eliminate them into closed first-order runtime artifacts.

## P — Proof/certificate system

Proof objects are data consumed by small verifier kernels.

Core certificates include:

```text
type closure
termination
resource bounds
effect/authority compatibility
source -> IR translation
IR -> optimized IR translation
optimized IR -> WASM/native translation
canonical artifact identity
```

External provers, theorem provers, superoptimizers, ML systems, and AI may generate candidates/proofs but never become admission authority.

Rule:

```text
AIProposal -> TEVVerifier -> PASS/FAIL
```

## Translation validation

Instead of trusting a permanently perfect compiler, every important transformation may emit a witness:

```text
Compiler(Source) = IR
Validator(Source, IR, proof) = PASS
```

Repeat for:

```text
Source -> IR
IR -> optimized IR
optimized IR -> WASM
WASM -> native
```

The compiler/optimizer may be large and fallible. The validator remains small and trusted.

## Optimizations are proposals, not authority

Any optimizer—including TEVProver, superoptimizers, PGO, ML, or LLM-generated rewrites—may propose optimized artifacts.

Admission requires:

```text
Semantics(original) = Semantics(candidate)
```

through proof or translation validation.

## Canonical model + canonical binary IR

The semantic model has at least two encodings:

```text
canonical JSON   -> audit/debug/interchange
canonical binary -> execution/cache/network
```

Both decode to the same canonical semantic object and therefore the same semantic identity.

Encoding bytes may differ; semantic identity must not.

## Deep content addressing

Content addressing applies below whole programs:

```text
types
functions
proofs
modules
constants
task results
capability contracts
optimized IR blocks
native blocks
```

This enables a computational flyweight model: a validated content-addressed function/proof/block is stored once and referenced by many programs.

## Perfect incremental invalidation target

The build graph is content-addressed. A change invalidates only transitive semantic dependents.

The same invalidation graph applies to:

```text
source fragments
IR
proofs
tests
optimized IR
native code
receipts
```

No unchanged semantic node is rebuilt merely because an unrelated file changed.

## E — Epoch / continuation algebra

Open-ended computation is an unbounded sequence of bounded admitted epochs.

Each epoch produces a continuation receipt:

```text
Ci = Hash(
  program_i,
  state_i,
  observations_i,
  effects_i,
  resources_i,
  previous_continuation
)
```

The next epoch must consume the exact previous continuation.

An epoch result contains:

```text
result
new durable state
observation receipts
effect receipts
resource consumption
next continuation
```

This yields infinite-duration systems composed of finite proofs, without `while true` or unbounded individual execution.

For IA-TEV this is the preferred long-running cognition/execution mechanism.

## Durable checkpoints

Checkpoint artifacts bind:

```text
program/IR hash
continuation hash
durable state
capability state
observation transcripts
pending intents
ledger head
resource counters
epoch identity
```

Restart, migration, or failover must preserve those identities exactly.

## Verifiable distribution

Pure/content-addressed tasks may execute on any worker:

```text
task hash + input hashes + budget
  -> worker
  -> output + receipt
  -> verifier/join
```

Physical scheduling order has no semantic authority. Deterministic joins reconstruct kernel semantics from task receipts.

The same semantic program may execute on one CPU, many cores, remote machines, GPUs, or edge workers if the corresponding backend passes translation/runtime validation.

## Diverse bootstrap / self-hosting

Self-hosting is not considered closed merely because the compiler compiles itself.

The strong target is diverse bootstrap:

```text
bootstrap A (Python)
bootstrap B (Rust)
       -> compile same TEV compiler source
       -> identical canonical IR
```

Later use diverse double compilation / equivalent techniques to reduce trusting-trust risk.

## Relationship between TEVScript_max and Ω

`TEVScript_max` is retained as a useful catalogue of desirable capabilities. Ω is the stronger architecture rule:

```text
max features       -> rejected as governing objective
max capability
with minimum TCB   -> selected objective
```

ADTs, termination generalization, proof-carrying IR, runtimes, capability providers, checkpoints, distribution, AOT, and self-hosting remain goals, but they are implemented as projections/extensions over `K/P/C/R/E` whenever possible.

## Implementation decomposition

The work is split into independently certifiable projects:

### Ω0 — Kernel Contract Extraction

Define the smallest explicit semantic interfaces for `K/P/C/R/E` without changing V2 behavior. Build canonical objects and validators that can encode existing V2 executions as Ω-compatible witnesses.

### Ω1 — Authority + Resource Algebra

Add capability identity/lifetime/linearity, grant/attenuate/delegate/consume/revoke, explicit effect sets, and resource vectors with conservative composition.

### Ω2 — Epoch / Continuation Runtime

Add continuation receipts and checkpoint/replay semantics. This provides the earliest direct power gain for IA-TEV because long-running behavior becomes a verified sequence of bounded transitions.

### Ω3 — Total Core Projection

Add user ADTs, exhaustive matching, structural/lexicographic/multiset/well-founded termination, and higher-order defunctionalization as syntax/compiler projections onto the kernel.

### Ω4 — Proof / Translation Validation

Add proof-carrying artifacts and validators for Source->IR and optimization transformations. External provers remain assistants.

### Ω5 — Canonical Binary + Deep CAS + Incremental Build

Add binary encoding of the same semantic model, deep content-addressed nodes, cache reuse, and exact dependency invalidation.

### Ω6 — Universal Capability + Session Providers

Add governed capability families (network, database, process, GPU, clock, randomness, sensors, Unity, model inference, storage) as typed providers, not kernel instructions.

### Ω7 — Independent Runtime / WASM / Native / Distribution

Add an independent runtime (Rust preferred), WASM/native translation validation, and distributed execution parity.

### Ω8 — Self-hosting + Diverse Bootstrap

Move compiler components into TEV-Script and prove cross-bootstrap equivalence.

## First implementation target — Ω0

Ω0 must be additive and V2-compatible. It does not change the V2 grammar.

It introduces canonical data models/validators for:

```text
KernelComputationIdentity
ProofEnvelope
AuthorityGrant
AuthorityUse
ResourceVector
EffectSet
ObservationEvidence
EpochIdentity
ContinuationReceipt
```

Existing V2 Program IR/effects/receipts are projected into these objects through adapters. This gives IA-TEV a stable future-facing execution contract before new syntax is added.

### Ω0 trust boundary

Ω0 validators may trust only:

- canonical hash implementation;
- closed schema/shape validators;
- exact V2 artifact identities supplied by existing V2 validators;
- small algebraic rules encoded in Ω0.

They must not trust arbitrary provider code, AI outputs, compiler assertions, or mutable global state.

### Ω0 Definition of Done

```text
V2_MAIN_UNCHANGED=PASS
V2_REGRESSION=PASS
KERNEL_IDENTITY=PASS
PROOF_ENVELOPE=PASS
AUTHORITY_GRANT_MODEL=PASS
RESOURCE_VECTOR_MODEL=PASS
EFFECT_SET_MODEL=PASS
OBSERVATION_EVIDENCE=PASS
CONTINUATION_RECEIPT=PASS
TAMPER_NEGATIVES=PASS
DETERMINISTIC_REPLAY_BINDING=PASS
PROMOTION_AUTHORITY=FALSE
```

No Ω0 artifact may claim a new stable language version.

## IA-TEV consequence

The intended eventual boundary is:

```text
IA-TEV proposes
  code / plans / proofs / optimizations / capabilities / next epoch
        |
        v
TEV-Script Ω validators
        |
     PASS/FAIL
        |
        v
bounded execution + receipts + continuation
```

IA-TEV gains open-ended operational power without becoming part of the trusted verification boundary.
