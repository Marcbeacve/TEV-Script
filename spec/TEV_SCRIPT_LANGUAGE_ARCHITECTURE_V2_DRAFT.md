# TEV Script Language Architecture V2 â€” Research Draft

Status: **architecture draft only**. This document does not create V2 syntax or reinterpret V1.

## Identity

Target identity:

> TEV Script is a general semantic programming language: general in what it can compute, represent and reason about; strict and explicit when operations acquire knowledge, consume authority/resources, project counterfactuals or commit effects to an external world.

V1 remains the bounded deterministic foundation and compatibility profile.

## Layering

```text
TEVScript surface
  |
  +-- pure computational core
  +-- state/entity/relation model
  +-- epistemic/operational surface
  +-- contracts/protocols/goals
  |
Typed + effect elaboration
  |
TEV Semantic IR
  |
Semantic Apply Calculus
  |
effect handlers: project / prepare / replay / test / commit
  |
Capability ABI
  |
hosts/adapters
```

## Pure computational core

Architectural targets include:

- `let`, constants and ordinary block functions;
- records, enums and algebraic values;
- parametric generics with coherence;
- traits/protocol constraints without ambient reflection;
- deterministic collection semantics;
- `Array<T,N>`, bounded `Vec/Map/Set/Queue` profiles;
- finite iteration;
- well-founded recursion using explicit decreasing measures;
- resumable/fuelled open processes;
- exact numeric semantics independent of hosts;
- deterministic pseudo-random streams with explicit identity.

Unbounded memory, wall-clock time, entropy and external I/O are effect/resource concerns, not ambient primitives.

## Operational layer

Surface distinctions may include:

- `observe`: explicitly acquires information;
- `infer`: derives information without claiming observation;
- `project`: evaluates against an explicit Model Field and never commits real host effects;
- `act`: expresses an intended intervention;
- `require`/`invariant`: semantic verification boundaries;
- `process`/`await`: ergonomic syntax for explicit continuations/events rather than opaque host tasks.

These surface forms should elaborate to the Semantic Apply Calculus rather than define independent runtimes.

## Types and effects

The type/effect architecture should be able to represent distinctions such as:

```text
Observed<T>
Inferred<T>
Predicted<T>
Hypothesis<T>
Verified<T>
```

without allowing implicit epistemic escalation.

Effect summaries are indexed by domains and concrete resource terms. They drive safety, authority admission, replayability, scheduling and optimization.

## State and identity

Entity identity is stable and separate from Field content identity. The semantic model distinguishes actual, observed, belief, projected, candidate/prepared, committed, historical and derived profiles without forcing all of them to be visible in everyday source syntax.

## Relations

First-class relational modeling is an architectural target. Properties that genuinely belong to relations should not be forced into one arbitrary object's fields.

## Goals and policies

Goals, hard constraints, policies and utilities remain separate:

- hard constraints are not soft utility weights;
- admissibility is separate from desirability;
- planners are replaceable algorithms;
- AI/LLM/human proposal mechanisms are consumers/providers, not magic language primitives.

## Capabilities and authority

Capability declarations describe typed external operations. Authority is separately granted by deployment context. Observation, disclosure, declassification, delegation and actuation authorities remain distinct.

Packages cannot obtain ambient host authority merely by being imported.

## Packages and ABI

The future package/build architecture should provide immutable dependency identities, lockfiles, effect/capability manifests, targets and host requirements. Installing a package must not execute arbitrary OS scripts.

Runtime ABI V2 must freeze canonical values, collections, effect requests, continuation/outcome representation, capability requests/responses, receipt/evidence identity and failure semantics.

## Tooling

Target tooling includes:

```text
tev new
tev add
tev check
tev fmt
tev test
tev run
tev build
tev explain
tev trace
tev replay
tev inspect
tev diff
tev verify
tev adapter
tev package
```

`explain` and semantic diff should derive their claims from semantic IR/evidence, never from ungrounded narrative generation.

## Trusted computing base

The semantic TCB must remain small. Parser/compiler/optimizer implementations should be replaceable where certificates, semantic identities and conformance allow a smaller verifier to re-establish relevant properties.

Self-modification is stratified: application/model/policy code may be proposed for change under higher verification strata; candidates cannot rewrite the authority that validates the same transition.

## V1 embedding criterion

V2 architecture is acceptable only if valid V1 programs embed into the new semantic model while preserving V1 observable semantics, exact numeric behavior, capability boundaries, canonical identities and conformance receipts where the embedding claims equivalence.

No V2 feature may silently reinterpret a V1 program.
