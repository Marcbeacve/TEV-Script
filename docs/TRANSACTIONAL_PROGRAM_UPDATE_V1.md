# Transactional Program Update V1

Gate-5A introduces a portable transactional supervisor for replacing a complete
`TEV_SCRIPT_PROGRAM_IR_V2` at runtime.

This is **not** a network update system and is **not** a signature authority.
Those are later gates.

## Authority model

The existing `TevScriptRuntime` remains a fixed-program runtime. It is not
mutated in place.

`TevScriptRuntimeHost` owns one active runtime and performs:

```text
candidate JSON
    |
    v
strict TevScriptProgram.Parse
    |
    v
program/entity/state compatibility
    |
    v
explicit capability ceiling
    |
    v
construct isolated candidate runtime
    |
    v
restore compatible snapshot
    |
    v
TevScriptRuntimeSwapPlan
    |
    +-- reject -> active runtime unchanged
    |
    `-- Commit -> single active-reference swap
```

The previous runtime object is retained for one explicit rollback.

## Gate-5A compatibility contract

Required:

- identical `program_id`;
- identical entity identity set;
- every existing state remains present;
- every existing state keeps the exact same TEV type;
- candidate capability declarations stay inside the host-provided capability
  ceiling.

Allowed:

- handler/instruction changes allowed by IR V2;
- different semantic hash;
- new states, initialized from the candidate program;
- changes to initial values of existing states (the live snapshot wins).

Not yet included:

- network transport;
- package signatures;
- anti-replay / monotonic release counters;
- persistent crash recovery;
- arbitrary state-schema migrations;
- entity addition/removal;
- WASM/browser transport;
- app-store policy claims.

## Atomicity

Preparation never changes the active runtime.

Commit validates plan ownership and generation, then performs one authoritative
reference replacement while holding the host lock. Plans prepared against an
older generation fail closed.

Rollback restores the exact previous runtime object rather than reconstructing
it from serialized data.
