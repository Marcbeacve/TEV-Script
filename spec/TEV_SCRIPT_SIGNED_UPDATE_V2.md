# TEV Script signed update V2 — IR V3

Status: **normative V1 / signed-update V2 candidate**.

This contract extends the certified V0.2 update model for IR V3 without reinterpreting `TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V1`.

## 1. Separation of authorities

Signed-update V2 separates three operations that MUST NOT be conflated:

1. **live transition authority** — a signed package authorizes exactly one IR semantic identity to transition to one target IR semantic identity;
2. **installed target authority** — durable state may identify one previously verified signed target package as installed;
3. **runtime state continuity** — persisted TEV state is restored only from `TEV_SCRIPT_RUNTIME_CHECKPOINT_V2` bound to the exact target program.

Loading an installed target after process restart is not a replay of the package's live transition. A restart first verifies the durable installed package, selects its exact target IR, constructs that target runtime, and then restores a checkpoint V2 belonging to that target if persistent state is required.

## 2. Package envelope

Canonical package:

```json
{
  "schema":"TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2",
  "body":{
    "schema":"TEV_SCRIPT_UPDATE_BODY_V2",
    "channel_id":"stable.channel",
    "program_id":"Root",
    "epoch":1,
    "sequence":1,
    "from_ir_semantic_hash":"...",
    "target_ir_semantic_hash":"...",
    "target_source_semantic_hash":"...",
    "ir_sha256":"...",
    "ir":{}
  },
  "signature":{
    "algorithm":"ES256",
    "key_id":"test-key",
    "value":"..."
  }
}
```

The complete package MUST be canonical JSON. The signed bytes are the UTF-8 bytes of canonical JSON for `body` only.

## 3. Exact transition binding

`from_ir_semantic_hash` is mandatory and is compared to the currently active runtime semantic hash during `Prepare`.

Therefore a valid signature over `A -> B` cannot authorize:

- `C -> B`;
- `A -> C`;
- any target whose embedded canonical IR bytes differ;
- the same target after its semantic identity changes.

A package with identical `from_ir_semantic_hash` and `target_ir_semantic_hash` is rejected as a no-op update.

## 4. Target binding

The body binds the target at four independent levels:

- `program_id` equals embedded IR `program_id`;
- `target_ir_semantic_hash` equals embedded IR `semantic_hash`;
- `target_source_semantic_hash` equals embedded IR `source_semantic_hash`;
- `ir_sha256` equals SHA-256 of the complete canonical embedded IR artifact.

The embedded IR is fully validated as `TEV_SCRIPT_PROGRAM_IR_V3` before it can enter a swap plan.

## 5. Transactional runtime swap

Preparation is non-authoritative. It MUST:

1. parse and validate the candidate IR;
2. require equal `program_id`;
3. require the exact same entity identity set;
4. require every pre-existing state to remain present with the exact same canonical type id;
5. validate every migrated value against the candidate type table;
6. validate requested capability contracts against the host capability ceiling;
7. construct and restore an isolated candidate runtime;
8. bind the resulting plan to current runtime `generation` and source semantic hash.

Commit performs one authoritative runtime replacement. A stale, foreign or consumed plan is rejected.

The host retains the previous runtime for one rollback operation. A durable-store failure after runtime commit MUST attempt rollback. If both durable commit and rollback fail, the authority fails closed with a compound failure rather than claiming success.

## 6. Capability ceiling

IR V3 capability authority is based on the complete ABI, not only capability id.

The ceiling entry is:

```text
(capability_id, parameter type vector, return type, kind)
```

A candidate using the same id with different parameters, return type or observation/effect kind is an authority escalation and is rejected.

This is required because V3 signatures may contain nominal records, enums, `Option<T>` and `Result<T,E>`.

## 7. Durable monotonicity

Installed update state uses `TEV_SCRIPT_INSTALLED_UPDATE_V2` and records:

```text
channel_id
epoch
sequence
package_sha256
package_json
```

Rules inherited from the V0.2 update model:

- the first package is `epoch=1, sequence=1`;
- within an epoch, sequence strictly increases;
- epoch never decreases;
- epoch may advance by exactly one;
- a new epoch begins at sequence 1.

The durable record embeds the complete canonical package and verifies that channel/epoch/sequence/package hash agree with it.

## 8. Installed-target restart

`TryLoadInstalledPackage` validates durable integrity and re-verifies the package signature. It returns the verified installed target package but does **not** call `PrepareSwap` and does not mutate the current runtime.

A restart flow is therefore:

```text
load installed record
-> parse package
-> reverify signature
-> validate target IR
-> construct runtime directly from installed target IR
-> optionally parse checkpoint V2
-> restore checkpoint exact against that target
-> continue execution
```

This avoids weakening `from_ir_semantic_hash` merely to support restart.

## 9. Signature verification

The runtime update authority is parameterized by a verifier exposing:

```text
key_id
algorithm_id
Verify(signed_body_bytes, signature_bytes)
```

Both key id and algorithm must equal the package signature metadata before verification. Signature bytes use canonical Base64 at the package boundary.

`ES256` is the intended portable certified profile for the current gates, using the repository's managed P-256 verifier through an adapter. The signed-update V2 core does not embed a crypto provider or network trust store.

## 10. Negative boundary

At minimum, conformance MUST reject:

- noncanonical package JSON;
- duplicate JSON keys;
- malformed/noncanonical Base64;
- unknown key or algorithm;
- invalid signature;
- wrong channel;
- wrong `from_ir_semantic_hash`;
- embedded IR hash mismatch;
- target semantic/source hash mismatch;
- program id mismatch;
- no-op transition;
- stale runtime swap plan;
- foreign/consumed plan;
- removed entity;
- removed state;
- changed state type;
- migrated value invalid under the target type table;
- capability id outside ceiling;
- capability ABI change under an allowed id;
- replayed/non-monotonic epoch or sequence;
- durable store changed after prepare;
- durable store write failure without successful runtime rollback.

## 11. Compatibility

V0.2 update schemas, classes, gates and historical receipts remain unchanged. IR V3 signed-update V2 is additive and lives in the isolated `TevScript.Core.V3` runtime assembly.
