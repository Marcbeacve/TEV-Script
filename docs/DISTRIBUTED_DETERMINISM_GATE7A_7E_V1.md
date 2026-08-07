# Distributed Determinism Gate 7A→7E V1

## Scope

This batch closes the distributed-determinism frontier after certified Gate-6D.

- Gate-7A: deterministic replay.
- Gate-7B: cross-host lockstep.
- Gate-7C: first-divergence localization.
- Gate-7D: canonical checkpoint + restart continuation.
- Gate-7E: signed-update lockstep.

The campaign uses the same TEV Core across native .NET, Python, JavaScript,
browser-wasm and WASI/Wasmtime.

## Gate-7A — deterministic replay

The governed `distributed.lockstep.v1` episode is executed repeatedly.
Python, JavaScript and C# each run the same episode 64 times. Every runtime must
produce byte-identical canonical receipts across its own reruns.

## Gate-7B — cross-host lockstep

The complete canonical conformance receipt is compared byte-for-byte across:

- Python
- JavaScript
- C#/.NET
- C# browser-wasm AOT in a real Chromium process
- C# WASI in Wasmtime

No host-specific tolerance is permitted.

## Gate-7C — first divergence

A counterfactual changes exactly invocation 7 while keeping the same
`scenario_id`. Prefix receipts are produced for every invocation. The detector
must prove:

- prefixes 1→6 are byte-identical,
- the first input divergence is invocation 7,
- the first receipt divergence is invocation 7.

The chosen episode may later reconverge to the same final state; this is
intentional and demonstrates why terminal-state comparison alone is
insufficient.

## Gate-7D — canonical checkpoint

Gate-7 introduces `TEV_SCRIPT_RUNTIME_CHECKPOINT_V1` as a portable exact-state
checkpoint.

A checkpoint contains:

- exact `program_id`,
- exact `semantic_hash`,
- the complete entity set,
- the complete typed state set.

Restore fails closed if program identity, semantic identity, entity set, state
set or state type differs.

The uninterrupted continuation receipt must be byte-identical to continuation
from the checkpoint after:

- a real Chromium process restart, and
- a second Wasmtime process.

The C# Core file and Unity Core mirror are byte-identical.

## Gate-7E — signed-update lockstep

The same signed Gate-5/6 update package and the same
`TevScriptUpdateAuthority` are executed on native .NET, browser-wasm and WASI.
The resulting signed-update lockstep receipt must be byte-identical and binds:

- package SHA-256,
- epoch / sequence,
- runtime generation,
- active semantic hash,
- exact final checkpoint,
- replay rejection.

## Boundaries

This batch does not claim:

- production signing-key provisioning / rotation,
- hostile rollback-resistant durable storage,
- public WAN/TLS/DNS/CDN transport,
- stable release.

Those are production-hardening boundaries after semantic determinism.
