# TEVScript MAX 3.0.0 — Derived Semantic Standard Library

Date: 2026-08-16
Status: IMPLEMENTATION CANDIDATE

## Goal

Recover the useful post-V1 semantic vocabulary from the historical realization branches without reviving a second semantic kernel. Every stdlib object is a typed view over ordinary MAX `SemanticFieldV1` facts and, when it changes state, an ordinary `FieldTransformationV1`.

## Modules in the first closure

### Residual

`ResidualObstructionV1` and `ResidualViewV1` represent what still blocks a named judgment. Canonical authority is a Field containing:

```text
tev.std.residual
tev.std.residual.obstruction
```

A residual is `CLOSED` iff its obstruction set is empty. Progress between residuals is derived by set comparison of obstruction hashes under the exact same boundary hash.

### Goal / policy / candidate / admission / resolution

Canonical facts:

```text
tev.std.goal
tev.std.policy
tev.std.candidate
tev.std.admission
tev.std.selection
tev.std.resolution
```

Constitutive rules:

```text
Selected -> Candidate + Admission(PASS)
PROOF_REQUIRED is never PASS
REJECT is never selected
NO_ADMISSIBLE only if every registered candidate is conclusively REJECT
any open candidate prevents NO_ADMISSIBLE and yields INDETERMINATE
multiple equally-ranked distinct admitted candidates yield INDETERMINATE
```

A policy may rank admitted candidates only after admissibility. Ranking data is explicit and content-addressed; candidate identifiers/hashes are never hidden tie-breakers.

### Discovery / realization

The first V3 stdlib does not install planners or search algorithms into the kernel. It represents:

```text
Discovery = explicit Transformation + evidence that maps observed Field -> theory Field
Realization = explicit Transformation + evidence that maps theory Field -> candidate/world Field
```

A discovery/realization closure judgment compares exact Fields and emits a Residual. Zero residual is relative to the bound comparison, never a universal inverse theorem.

## Lowering and authority

All records lower to Field facts. Physical execution remains outside the stdlib and still requires Omega authority/effect/resource evidence. The stdlib cannot grant authority, verify its own proof obligations or upgrade `PROOF_REQUIRED`.

## Compatibility

Historical `semantic_*_v0.py` implementations in `realization-semantics-r0` and R10 are research/source references only. MAX V3 owns new V1 contracts and does not import those modules at runtime.

## Definition of Done

```text
RESIDUAL_CLOSED_IFF_EMPTY=PASS
RESIDUAL_PROGRESS_EXACT_BOUNDARY=PASS
SELECTED_IMPLIES_ADMITTED=PASS
OPEN_CANDIDATE_IMPLIES_INDETERMINATE=PASS
NO_ADMISSIBLE_REQUIRES_CLOSED_REJECTION=PASS
TIE_HAS_NO_HIDDEN_HASH_TIEBREAKER=PASS
DISCOVERY_REALIZATION_ARE_DERIVED=PASS
ZERO_RESIDUAL_BOUND_RELATIVE=PASS
ALL_OBJECTS_LOWER_TO_FIELD=PASS
NO_AUTHORITY_AMPLIFICATION=PASS
TAMPER_NEGATIVES=PASS
```
