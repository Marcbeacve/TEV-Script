# Transactional Program Update V1

## Core model

`TevScriptRuntime` remains a fixed-program runtime. `TevScriptRuntimeHost`
owns replacement authority and prepares an isolated candidate runtime before
the active runtime reference may change.

The Gate-5A compatibility contract remains:

- identical `program_id`;
- identical entity identity set;
- every existing state remains present;
- every existing state keeps the exact TEV type;
- candidate capabilities remain within the explicit host ceiling;
- new states may be added and use candidate initial values.

`PrepareSwap` is non-authoritative. `Commit` performs the authoritative runtime
reference change. Reused/stale plans fail closed. `RollbackLastCommit` restores
the exact previous runtime object.

## Gate-5B AOT witness

Gate-5B does not change the Gate-5A implementation. It places the same
transactional host inside a Windows x64 IL2CPP/AOT Player.

The behavioral campaign is deliberately stronger than semantic-hash identity:

```text
Runtime A
health=100
damage(10) -> health=90

prepare/commit Runtime B
health migrates as 90
damage(10) -> health remains 90   # candidate behavior is active

rollback to exact Runtime A
health remains 90
damage(10) -> health=80           # previous behavior is restored
```

The same Player also verifies fail-closed state removal, capability escalation,
program-id drift, reused plans and stale plans.

Gate-5B requires IL2CPP/AOT artifact evidence:

- `GameAssembly.dll` present;
- exactly one `global-metadata.dat` under `il2cpp_data/Metadata`;
- `MonoBleedingEdge` absent.

No JIT, reflection, runtime source compilation, dynamic assembly loading,
network delivery or signature authority is introduced.

## Remaining update frontier

The next batch is:

```text
5C  signed update package and explicit key authority
5D  anti-replay / monotonic version or epoch
5E  remote transport with full-package activation
```

Transport is deliberately last: bytes received from the network must never
become authoritative before the package and replay contracts are independently
validated.
