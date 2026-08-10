# TEV Script Post-V1 Causal / Semantic Integration V0

Status: experimental post-V1 integration contract. This document does not alter the admitted V1.0.0 language semantics or the `v1.0.0` release identity.

## 1. Purpose

This integration closes the architectural gap between two previously independent post-V1 lines:

- Causal Reaction V1: footprint analysis, deployment laws, preparability, structural/prepared refinement, prepare/commit/abort and commit results.
- Semantic Calculus / Residual V0: Fields, application/evidence semantics, proof/frontier closure, provider-neutral semantic authority and structured Residuals.

The integration is additive. Neither subsystem becomes the authority of the other.

## 2. Primitive model

No new primitive is introduced.

```text
Field
Transformation
```

Causal contracts, deployment-law catalogs, reaction footprints, refinement receipts, prepared reactions, preparability results and commit results are representable as Semantic Fields.

Transformations that evaluate preparability, refinement and commit outcomes may produce Residual Fields describing the exact judgment-relevant obstruction that remains.

Residual is therefore not a third primitive.

## 3. Bridge direction

The bridge is intentionally one-directional:

```text
Causal DTO / receipt / result
          |
          v
semantic_causal_bridge_v0
          |
          +--> Semantic Field
          |
          +--> Residual Field
```

The causal modules do not import Semantic Calculus modules.

Semantic Calculus core modules do not import causal modules.

Only `semantic_causal_bridge_v0.py` imports both sides.

This prevents circular semantic authority and keeps Causal Reaction independently testable.

## 4. Artifact Fields

The bridge uses the declarations:

```text
tev.causal.artifact / 4
tev.causal.binding  / 3
```

The root artifact fact binds:

```text
bridge profile
artifact kind
content identity hash
canonical artifact JSON
```

Bindings preserve important cross-artifact identities such as:

- contract hash;
- deployment law-catalog hash;
- program/source semantic hashes;
- footprint hash;
- refinement receipt hash;
- prepared reaction hash;
- before/after checkpoint hashes;
- entity / trigger;
- atomicity;
- commit status.

The source causal object remains the typed DTO/receipt. The Semantic Field is the canonical bridge representation used for composition with other semantic Fields.

## 5. Preparability Residual

A `PreparabilityResultV1(preparable=True)` closes the preparability judgment only when it contains no reasons and no hazards.

A non-preparable result yields structured obstructions:

```text
causal.preparability_reason
causal.staging_hazard
causal.not_preparable
```

A contradictory successful result containing unresolved reasons/hazards is rejected fail-closed rather than normalized silently.

## 6. Refinement Residual

A `RefinementReceiptV1` maps as follows:

```text
PASS
  -> CLOSED residual

PROOF_REQUIRED
  -> proof.required obstruction(s)

REJECT
  -> refinement.failure obstruction(s)
```

The residual binds receipt, contract, program, footprint and law-catalog identities.

A PASS receipt containing failures or pending obligations is inconsistent and rejected fail-closed.

A PROOF_REQUIRED receipt containing structural failures is also rejected as inconsistent.

## 7. Commit Residual

A `CommitResultV1` maps as follows:

```text
COMMITTED
  -> CLOSED

ABORTED
  -> operational.application_aborted

EXTERNAL_PARTIAL
  -> operational.partial_commit

LAW_VIOLATION
  -> operational.law_violation
```

The bridge does not rewrite causal commit semantics. It only gives the causal result an exact semantic/residual representation.

Contradictory flags, for example `COMMITTED` with `state_committed=false`, are rejected fail-closed.

## 8. Authority boundary

The bridge must not depend on:

- TEVProver;
- CUOFC runtime authority;
- IA-TEV;
- agent/planner routing policy;
- host deployment policy.

CUOFC correspondence remains research-only and non-normative.

IA-TEV may consume the bridge and Residual API, but IA-TEV is not part of TEV Script semantic authority.

## 9. Integration success criteria

The post-V1 integration candidate is eligible for promotion only when all of the following hold on one exact Git identity:

1. Causal Reaction campaign PASS.
2. Semantic Calculus campaign PASS.
3. Frontier Closure campaign PASS.
4. Semantic Authority Decoupling PASS.
5. CUOFC correspondence campaign PASS as non-normative research.
6. Residual campaign PASS.
7. Causal/Semantic bridge tests PASS.
8. No circular causal/semantic imports.
9. Full repository unit regression PASS with zero unexpected skips.
10. Global technical certification PASS on the integrated tree.
11. Python technical certification PASS on the integrated tree.
12. The admitted V1.0.0 tag/commit remains unchanged.

Promotion of the post-V1 candidate advances `main`; it does not move or reinterpret the `v1.0.0` tag.
