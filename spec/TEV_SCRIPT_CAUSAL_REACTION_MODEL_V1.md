# TEV Script Causal Reaction Model V1

Status: **post-V1 experimental, additive, non-normative for TEV Script V1 source semantics**.

This specification defines a general causal layer over already validated `TEV_SCRIPT_PROGRAM_IR_V3`. It does **not** add source keywords, reinterpret TEV Script V1, replace `ScriptRuntimeV3`, or claim `LANGUAGE_STABLE=YES`.

## 1. Purpose

TEV Script V1 already gives bounded deterministic execution, explicit typed capabilities, canonical semantic identity, event-chain budgets, exact checkpoints and governed program updates. The causal layer extracts the more general structure latent in those mechanisms:

`trigger -> bounded reaction -> observations/state/effects/events -> evidence`.

The reaction, rather than one handler or statement, becomes the unit of contracts, authority, preparation, scheduling and admission.

## 2. Four post-V1 objects

### 2.1 Capability Law Catalog

A deployment-specific content-addressed authority describing resources touched by capabilities and the laws the host guarantees. It is separate from the program semantic hash.

It can describe resource regions/aliases; `read`, `write`, `consume`, `reserve`; observation temporal semantics (`snapshot`, `stable`, `sequence_sensitive`, `unknown`); immediate or `prepare_commit_abort` effects; explicitly certified commuting pairs; commit-total-after-prepare; durable recovery; and finite authority/lease capacity.

Unknown deployment facts fail closed. `complete=true` is required before distinct external resource ids prove non-aliasing. A capability-law `kind` must agree exactly with the IR V3 capability kind; a kind mismatch is a failed law binding, never an alternate interpretation of the program.

### 2.2 Reaction Contract

An implementation-independent content-addressed ceiling on one externally triggered reaction. It may exist before an implementation. It bounds state reads/writes, observations/effects, emitted events, resources, reachable handlers, instruction ceiling and required atomicity.

A protocol view constrains canonical typed-state edges `(before,event,after)`. Typestate is therefore a contract view rather than a VM primitive.

Proof obligations are content-addressed references. The reference kernel does not pretend to prove arbitrary theorem domains: unresolved obligations produce `PROOF_REQUIRED`, never `PASS`.

### 2.3 Prepared Reaction

A concrete reaction evaluated against an exact before-checkpoint and observation transcript, with physical effects represented as intents only where deployment laws prove staging preserves V1-observable semantics.

It binds program/source semantic hashes, contract/law/refinement/footprint hashes, trigger arguments, exact before/after `RuntimeCheckpointV2`, observations, effect intents, emitted events, atomicity and preparation evidence. Identical inputs produce identical prepared-reaction hashes; changed observations change identity.

### 2.4 Refinement Receipt

Binds candidate program/footprint to contract and deployment laws. `PASS` means all structural and runtime-checkable requirements supplied to the reference verifier passed. `REJECT` records concrete escalation/violation. `PROOF_REQUIRED` records unresolved semantic proof obligations.

## 3. Reaction footprint

For an external trigger, analysis closes over handlers reached through emitted events within the same entity. The closure remains bounded by IR V3 `maximum_event_chain`.

The footprint records state read/write sets, observation/effect sets, emitted events, capability occurrences, reachable handler count, conservative instruction ceiling, and whether the reachable event graph is cyclic.

## 4. Internal independence

Two reactions are internally non-interfering only if:

`W1 ∩ (R2 ∪ W2) = ∅` and `W2 ∩ (R1 ∪ W1) = ∅`, with state resource identity including entity id.

## 5. External resource independence

Capability ids are not resource ids. Distinct capabilities may alias one physical/logical resource. Deployment laws supply that relation.

Same-resource `read/read` is not automatically reorderable: sequence-sensitive observations can change results under reordering. Read/read is accepted only under `snapshot`/`stable` laws or an explicit symmetric commuting law. Missing laws and unknown aliases fail closed.

## 6. Deterministic concurrency

The layer adds no `thread`, `async`, `await`, mutex or implicit scheduler semantics. A host may physically prepare reactions concurrently only after independence is proved; publication remains canonically ordered. Concurrency is an optimization of commuting causal work, not a source-language ordering rule.

## 7. Preparability and the staging hazard

Effect staging is not universally semantics-preserving. Example:

`effect world.set(1); seen = observation world.read()`.

Direct V1 may observe `1`; delaying the effect may observe `0`. The reference proof detects effect occurrences that may precede later observations through the reachable event graph, then requires resource-law evidence that staging commutes. Same/unknown interfering resources reject. Disjoint resources are accepted only under a complete catalog.

## 8. Canonical state authority

Preparation snapshots and publication use `TEV_SCRIPT_RUNTIME_CHECKPOINT_V2`. Native host object copying is not semantic authority and is not a supported substitute, especially for algebraic values with host-internal representation details.

## 9. Preparation

1. Derive footprint and check structural refinement.
2. Prove preparability against deployment laws.
3. Capture exact before-checkpoint.
4. Restore a checkpoint-bound shadow runtime.
5. Execute real observations through transcript wrappers.
6. Replace effects with canonical intent collectors.
7. Run the existing bounded V1 reaction closure on the shadow runtime.
8. Capture after-checkpoint/emitted events.
9. Check dynamic protocol and atomicity requirements.
10. Hash the Prepared Reaction.

Failure during shadow execution never mutates original runtime state.

## 10. Atomicity classes

- `interleaved`: direct V1, no causal preparation claim.
- `state_atomic`: no external effects; state publishes as one causal result.
- `state_atomic_external_partial_possible`: state is withheld on effect failure but the external world may already be partial.
- `transactional`: all effects support prepare/commit/abort and claim total commit after successful prepare.
- `durable_transactional`: transactional plus deployment-certified durable crash recovery.

The kernel never upgrades beyond deployment evidence.

## 11. Commit

The Prepared Reaction recomputes and validates its embedded before/after checkpoint hashes, and its runtime bundle fixes the prepared-reaction hash against later mutation. The current checkpoint hash must still match the Prepared Reaction before hash. Immediate effect intents execute in reaction order; failure leaves state unpublished and is conservatively classified external-partial. Transactional effects prepare all, abort prepared intents on prepare failure, commit after all prepare operations succeed, and publish state only after all commits succeed. A failed commit that contradicts a `commit_total_after_prepare` law is surfaced as `LAW_VIOLATION`.

## 12. Reaction-level least authority

Reaction footprints permit authority leases narrower than the program-wide capability set. Resource capacity plus `consume`/`reserve` can model one-shot/linear authority without imposing linear types on every TEV value. Batch admission counts reaction-level reservations against declared finite authority capacity; pairwise independence alone is not used to hide a capacity overflow.

## 13. Refinement and AI synthesis

A candidate refines a contract only when every read/write/observation/effect/event/resource and budget stays within its ceiling. Extra authority is an escalation. A planner, optimizer, human or AI may propose a candidate; none may enlarge the contract by generation alone.

The language therefore needs no imperative `AI` or `goal` keyword. Goals/postconditions belong to contracts; synthesis is replaceable.

## 14. Protocol/typestate

Protocol edges are exact canonical typed values. An absent edge rejects before commit. This captures state-dependent operation legality without a second runtime type machine.

## 15. Meta-transitions

Existing signed transactional update, prepared migration, commit/rollback and checkpoints share the same high-level Prepare/Verify/Commit form. Program update is therefore a meta-transition under the same causal architecture, without changing the established signed-update protocol.

## 16. Three identities

Strong claims bind separately to:

1. program semantic hash — what the program means;
2. contract hash — what is allowed;
3. deployment-law hash — what the host/world guarantees.

Deployment physics must not contaminate portable program semantic identity.

## 17. Conservatism

Fail closed on incomplete required law catalogs, missing capability laws, unknown aliasing, sequence-sensitive reordering, unsafe effect→observation staging, contract ceiling escalation, insufficient atomicity, absent protocol edges, stale before-state, or unresolved proof obligations.

## 18. Non-goals

No unbounded computation, implicit concurrency, async/await semantics, reflection, runtime source compilation, host-native references, ambient authority, distributed consensus, magical reversal of irreversible physical effects, automatic truth of deployment laws, unrestricted self-modification, or reinterpretation of V1 semantics.

## 19. Promotion boundary

This layer remains post-V1 experimental until schemas, positive/negative campaigns, preparation/commit behavior, exact clean identity and existing V1 certification all pass. Promotion is separate from V1 Stable Admission.

## 20. Reference campaign

The governed reference campaign entry point is `tests/run_causal_reaction_campaign.py`, deliberately kept inside the manifest-authorized `tests` source root.
