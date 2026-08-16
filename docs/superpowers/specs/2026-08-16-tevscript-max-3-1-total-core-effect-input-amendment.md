# TEVScript MAX 3.1 Total-Core — Effect Input Amendment

Date: 2026-08-16
Status: NORMATIVE AMENDMENT
Applies to: `TEVScript MAX 3.1 Total-Core`

## Problem

A V2 effects source is not sufficient by itself to construct a detached Program IR V4 Effects execution artifact. The source compiler closes state declarations, observation capability contracts and actions, but the V4 artifact additionally requires an execution-instance observation `scenario` and may receive an execution-instance `current_state`.

Treating that evidence as source text would collapse two distinct authorities:

```text
source semantics != observation/execution evidence
```

The existing V2 effects contract already preserves this distinction: changing `scenario` or `current_state` preserves the compiled source semantic hash while changing the detached Program IR V4 execution identity.

## Corrected Total-Core compilation API

The 3.1 compiler is therefore:

```python
compile_total_core_v31(
    process_source: str,
    *,
    unit_sources: Mapping[str, str],
    effect_inputs: Mapping[str, Mapping[str, Any]] = {},
    proof_admissions: Sequence[VerifiedProofAdmissionV1] = (),
) -> TotalCoreProgramV1
```

For an `effects` unit, its `effect_inputs[unit_id]` object has the closed field set:

```text
scenario       required mapping
current_state  optional mapping or null
```

Rules:

1. every declared `effects` unit requires exactly one `effect_inputs` entry;
2. `pure` and `recursive` units must not have `effect_inputs` entries;
3. undeclared `effect_inputs` entries are rejected;
4. the effect source is compiled only by existing V2 effects source authority;
5. `scenario` and `current_state` are passed only to the existing V4 effects builder;
6. no physical command grant or provider authority is introduced by Total-Core compilation;
7. V2 Effects R2 physical-command source is not silently reinterpreted as V4 Effects R1;
8. source paths and mapping enumeration order are nonsemantic.

## Identity correction

`source_semantic_hash` binds only source-semantic material:

```text
canonical 3.1 process model
+
ordered child tuples:
  unit_id
  declared profile
  child V2 semantic_hash
```

It does **not** bind effect scenario or current state.

The exact execution instance is nevertheless content-addressed because:

```text
effect scenario/current_state
        -> V4 program_ir_hash
        -> TotalCoreUnitV1.unit_hash
        -> TotalCoreProgramV1.program_hash
```

Therefore two executions with the same source but different observation evidence satisfy:

```text
same source_semantic_hash
!= program_hash
```

This amendment supersedes any earlier design text that included an effects execution `program_ir_hash` inside the 3.1 `source_semantic_hash`.

## Security consequence

Observation evidence remains explicit, external and replayable. Source code cannot manufacture a scenario merely by declaring an effects unit. Missing or extra effect evidence fails closed during Total-Core compilation.
