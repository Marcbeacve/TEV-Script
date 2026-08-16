# TEVScript MAX 3.0.0 — Epistemic and Effect Type Design

Date: 2026-08-16
Status: IMPLEMENTATION CANDIDATE
Parent semantic basis: `Field + Transformation + Apply`

## Goal

Add compile/runtime-checkable epistemic and effect distinctions without adding new primitive semantic families. Every type/effect descriptor lowers to ordinary MAX Field facts; effect authority remains owned by Omega0 grants and resources.

## Epistemic qualifiers

The closed V3 qualifier set is:

```text
Observed<T>
Inferred<T>
Predicted<T>
Hypothesis<T>
Verified<T>
```

These qualifiers are intentionally not arranged as an implicit subtyping ladder. They describe provenance classes, not value quality. Therefore cross-qualifier assignment is never implicit.

`EpistemicTypeV1` binds:

```text
base_type
qualifier
type_hash
```

Rules:

- exact same base type + qualifier may assign implicitly;
- different base types never assign implicitly;
- different qualifiers never assign implicitly;
- promotion to `Observed<T>` requires explicit observation evidence;
- promotion to `Predicted<T>` requires explicit model/projection evidence;
- promotion to `Verified<T>` requires at least one explicit proof/verifier witness;
- `Inferred<T>` requires an explicit Transformation identity;
- `Hypothesis<T>` requires explicit provenance evidence;
- a missing proof for `Verified<T>` yields `PROOF_REQUIRED`, never PASS;
- missing observation/model/provenance evidence yields REJECT because it cannot be manufactured by the type checker.

A refinement receipt binds source/target type hashes, the exact Transformation hash and the evidence hashes used.

## Effect rows

`EffectRowV1` is a type-level projection of effects, not an authority grant. It contains sorted unique effect IDs and required capability IDs. Its hash may be bound by compiler/IR artifacts.

An actual row is substitutable for an allowed row iff:

```text
actual.effects     subset_of allowed.effects
actual.capabilities subset_of allowed.capabilities
```

No effect row may claim that a capability is granted. Runtime authority remains the separate Omega `AuthorityGrantV1` boundary.

## Lowering

The layer proves it is derived by lowering every descriptor/receipt to normal Field facts:

```text
tev.type.epistemic
tev.type.effect_row
tev.type.epistemic_refinement
```

No new Field or Transformation representation is introduced.

## Definition of Done

```text
CLOSED_EPISTEMIC_QUALIFIERS=PASS
NO_IMPLICIT_EPISTEMIC_ESCALATION=PASS
OBSERVED_REQUIRES_OBSERVATION=PASS
PREDICTED_REQUIRES_MODEL=PASS
VERIFIED_REQUIRES_PROOF=PASS
MISSING_PROOF_IS_PROOF_REQUIRED=PASS
EFFECT_ROW_CANONICAL=PASS
EFFECT_SUBSET_SUBSTITUTION=PASS
EFFECT_ROW_GRANTS_NO_AUTHORITY=PASS
ALL_TYPE_EFFECT_OBJECTS_LOWER_TO_FIELD=PASS
TAMPER_NEGATIVES=PASS
V2_AND_OMEGA0_AUTHORITY_UNCHANGED=PASS
LANGUAGE_STABLE=NO
PROMOTION_AUTHORITY=FALSE
```
