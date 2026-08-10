# TEV Script Semantic Residual V0

Status: **post-V1 experimental semantic authority; additive; no V1 reinterpretation; `LANGUAGE_STABLE=NO`**.

## 1. Ontology

Residual is not a third primitive. The semantic reduction remains:

- `SemanticFieldV0`: represented semantic content;
- Transformation/application relations: producers of new Fields.

A residual is a `SemanticFieldV0` with profile `TEV_SCRIPT_SEMANTIC_RESIDUAL_V0`. `Residualize` is a transformation family deriving that Field relative to an explicit judgment.

For context `Gamma`, laws `L`, state/subject `F`, transformation `T`, result `F'`, and judgment `J`:

`F' = Apply(Gamma, L, F, T)`

`R = Residualize(Gamma, L, F', J)`

The closure law is judgment-relative:

`Closed(R_J(F')) <=> no obstruction represented as relevant to J remains unresolved`.

Closure does not mean omniscience, equality with a complete world model, or absence of unrelated differences.

## 2. Residual versus delta

A field delta answers what changed between two Fields. A residual answers what still obstructs a named judgment. Therefore unrelated facts may change while a residual stays closed, and a Field may be unchanged while a proof/authority/resource residual remains open.

No universal scalar error is defined. Obstruction cardinality is descriptive, not a universal utility, severity, distance, or optimization metric.

## 3. Canonical residual Field

The exact V0 surface contains only:

- `tev.residual/11`
- `tev.residual.obstruction/9`

`tev.residual` binds:

1. residual profile;
2. `OPEN | CLOSED`;
3. residual domain;
4. judgment id;
5. judgment hash;
6. canonical judgment JSON;
7. source hash;
8. canonical source JSON;
9. centered-context hash;
10. law-context hash;
11. obstruction count.

A residual therefore remains interpretable from its own Field: the source is both present and content-addressed. Context and law changes are explicit comparison boundaries rather than hidden ambient inputs.

Each `tev.residual.obstruction` binds:

1. deterministic index;
2. obstruction hash;
3. namespaced obstruction kind;
4. subject;
5. canonical expected value;
6. canonical observed value;
7. canonical detail map;
8. optional evidence hash;
9. canonical dependency-reference list.

The obstruction hash commits to every semantic obstruction component except its row index. Rows are deduplicated and sorted by obstruction hash.

## 4. Fail-closed parsing

`parse_residual` rejects:

- extra declarations or hidden relations;
- incorrect profile/status;
- malformed hashes;
- non-canonical JSON payloads;
- source-hash or judgment-hash drift;
- obstruction-hash drift;
- non-canonical obstruction ordering;
- malformed dependency references;
- index/count mismatch;
- `CLOSED` with obstructions or `OPEN` without obstructions.

A malformed residual is not a weaker residual. It is not a residual Field.

## 5. Boundary identity

A comparison boundary is content-addressed from:

- residual domain;
- judgment hash;
- context hash;
- law hash.

Source identity is deliberately excluded from the comparison boundary because progress normally compares different successive sources under the same judgment/context/laws.

Changing judgment, context, or laws makes two residuals `INCOMPARABLE` unless a separate transformation explicitly proves a correspondence between the boundaries.

## 6. Obstruction identity and dependency frontier

Each obstruction is independently content-addressed. This makes it possible to distinguish:

- resolved obstructions;
- persistent obstructions;
- newly introduced obstructions.

`dependency_refs` are explicit routing/attention inputs. They may name immutable hashes or stable semantic resources/obligations. They do not grant authority and do not prescribe which planner, prover, observer, repairer, or agent must be invoked.

The core exposes filtering by kind, subject, and dependency reference without creating a new residual judgment. This avoids the unsafe inference that a filtered view being empty means the original residual is closed.

## 7. Progress algebra

For residuals on the same boundary, let `O(R)` be the finite set of obstruction hashes.

The safe refinement relation is:

`R1 <= R0  iff  O(R1) subseteq O(R0)`.

Strict reduction is proper subset. This relation makes no claim that one changed expected/observed value is numerically closer than another.

`residual_progress(before, after)` classifies:

- `CLOSED`: an open set becomes empty;
- `REDUCED`: the new obstruction set is a proper subset;
- `UNCHANGED`: obstruction identity is unchanged;
- `REGRESSED`: the prior set is a proper subset of the new set;
- `CHANGED`: some obstructions resolved while others were introduced;
- `INCOMPARABLE`: judgment/context/law boundary changed.

The progress record explicitly exposes resolved, persistent, and introduced obstruction hashes and is itself content-addressable as `TEV_SCRIPT_RESIDUAL_PROGRESS_V0` data. It is a DTO/view, not a third semantic primitive.

## 8. Join and product aggregation

Two distinct operations are required.

### Compatible join

`join_residuals` requires the same comparison boundary and flattens the union of child obstruction sets. It is suitable for multiple independent analyses of one judgment.

### Product aggregation

`aggregate_residuals` may combine different child judgments. An open child is represented as `aggregate.child_residual_open` and binds the child residual hash, child judgment hash, child boundary hash, and child obstruction count.

Aggregation therefore preserves child identity instead of pretending heterogeneous judgments share one obstruction algebra.

## 9. Generic Field requirement residual

`residualize_fields(observed, required, judgment_id, domain)` treats required body facts as judgment-relevant requirements.

- exact required fact present -> no obstruction;
- relation present with different arguments -> `semantic.value_mismatch`;
- relation absent -> `semantic.missing_fact`;
- unrelated observed facts -> irrelevant to closure.

This is one residualization transformation, not the definition of all possible judgments.

## 10. Operational adapter

Application outcomes are interpreted relative to their regime:

- `evaluate/project` close on `COMPLETED`;
- `prepare/replay` close on `PREPARED`;
- `commit` closes on `COMMITTED`.

Consequently a `PREPARED` commit result is not silently treated as committed success.

Open operational statuses are projected without rewriting the source Outcome Field, including `UNKNOWN_COMMIT`, `PARTIAL`, `LAW_VIOLATION`, rejection, suspension, budget exhaustion, and missing capability.

`UNKNOWN_COMMIT` remains a reconciliation obstruction, not a Boolean failure.

## 11. Proof and epistemic adapters

The residual profile can represent:

- pending proof obligations;
- proof scope mismatch;
- inactive/revoked proof evidence;
- insufficient proof method;
- untrusted verifier;
- countermodels;
- missing knowledge.

Independent proof defects remain separate obstruction atoms. They are not collapsed into one generic `proof_failed` bit.

## 12. Composition, abstraction, model, refinement

Exact or relation-scoped divergence can be residualized without changing the original Fields.

Typical domains include:

- composition diamond mismatch;
- abstraction non-commutation or judgment loss;
- model prediction/observation mismatch;
- refinement obligations not discharged.

Relation-scoped divergence may close even when the complete Fields differ, because closure is always relative to the requested judgment.

## 13. Authority, resource, safety, liveness, causal layers

Thin adapters map domain-specific open obligations into the same profile:

- `authority.missing`;
- `resource.deficit`;
- `safety.violation`;
- `liveness.pending`;
- `causal.hazard`;
- `refinement.failure`;
- `epistemic.missing_knowledge`.

These names are extensible stable ids, not a closed ontology. The residual core does not import or know any specific planner/agent implementation.

## 14. Routing semantics

Residual is a routing signal, not routing authority.

A consumer may use domain, kind, subject, dependencies, evidence and progress classification to select a next transformation. Examples include observation for missing knowledge, proof search for proof obligations, reconciliation for unknown commit, or model revision for persistent model mismatch.

No such policy is embedded in V0. Safety, authority, cost, desirability, and human-review policy remain explicit external judgments.

## 15. Reducibility and irreducibility

`OPEN` does not imply reducible. A residual may expose an obstruction for which:

- no known transformation exists;
- required authority cannot be obtained;
- the judgment is false;
- the problem lies beyond a finite proof boundary;
- a physical resource is permanently unavailable.

Residual V0 records open structure. It does not promise convergence.

## 16. CUOFC correspondence boundary

CUOFC supplies an independent finite mathematical fragment:

`R_J = (Required intersect Relevant_J) - Satisfied`.

Its finite obstruction-set order uses subset refinement; product composition uses set union. TEV enriches each obstruction with kind, subject, expected/observed values, evidence and dependencies while preserving the finite set-level closure/refinement laws under the explicit encoding.

The correspondence is research-only. CUOFC has no runtime, language, ABI, truth, certification, release, or promotion authority over TEV Script.

The dependency direction is prohibited:

`TEV residual core -> CUOFC` = forbidden.

Research correspondence may depend on both sides:

`research correspondence -> TEV residual + CUOFC mathematics` = allowed.

## 17. V1 isolation

Residual V0 adds:

- no `.tevs` keyword;
- no V1 grammar change;
- no IR V2/V3 opcode;
- no runtime ABI change;
- no C#/JS/Unity semantic reinterpretation;
- no stable-language promotion.

The feature remains post-V1 additive semantic research until separately admitted.

## 18. Required falsification properties

The focal campaign must falsify at least:

- Field/Transformation reduction preservation;
- null residual closure;
- judgment relevance scoping;
- deterministic obstruction identity and ordering;
- source/judgment/context/law binding;
- fail-closed tamper detection;
- compatible join boundary rejection;
- progress classification and incomparability;
- dependency-frontier querying;
- mode-sensitive operational closure;
- proof/countermodel preservation;
- cross-layer adapter compatibility;
- absence of CUOFC/IA/planner/agent runtime imports.

No `LANGUAGE_STABLE=YES` claim follows from this campaign.
