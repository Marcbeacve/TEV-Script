# TEV Script V1 certification protocol

Status: **candidate governance authority**.

This protocol separates four states that must never be conflated:

1. implementation exists;
2. pre-certification evidence passes;
3. the exact commit is technically certified;
4. a stable release is admitted.

The separation is intentional. Editing metadata to say `stable=true` is not evidence that the edited commit is the one that passed the runtime and portability campaign.

## 1. Historical V0.2 oracle

V1 certification is anchored to the certified V0.2 language-completeness oracle:

```text
6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
```

A V1 candidate must contain that commit in its ancestry and must preserve the V0.2 portable regression campaign.

## 2. Stage A — implementation candidate

An implementation candidate may contain complete source/runtime functionality and conformance gates, but it must still report:

```text
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Code presence, test files, documentation, prior branch evidence or a passing ancestor do not promote the current commit.

## 3. Stage B — `V1_PRECERTIFY`

Authority:

```text
RUN_TEV_SCRIPT_V1_PRECERTIFY.py
```

The gate runs from one exact clean checkout and requires all of the following without V1/V3 skips:

- reference V1 frontend/static/lowering closure;
- V0.2 Python regression inside the closure gate;
- C# V0.2/V3 assembly-isolation and reflection/AOT surface guard;
- Python/JavaScript/C# IR V3 canonical receipt byte lock;
- Python/JavaScript/C# Runtime Checkpoint V2 byte lock and restart continuation;
- Browser-WASM AOT IR V3 receipt/checkpoint parity;
- WASI IR V3 fresh-process/checkpoint/restore-process parity;
- signed-update V3 host campaign;
- signed-update V3 Browser-WASM campaign;
- signed-update V3 WASI fresh/restore campaign;
- complete portable V0.2 regression including browser-WASM and WASI witnesses;
- clean worktree before and after;
- identical commit and tree before and after validation.

A successful run emits one canonical JSON receipt:

```text
TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V5
```

and its SHA-256.

`V1_PRECERTIFY=PASS` still means:

```text
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

because pre-certification is an evidence-producing test campaign, not the final admission step.

## 4. Stage C — technical `CERTIFY_FULL`

Authority:

```text
RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py
```

`CERTIFY_FULL` is deliberately read-only. It does not edit version metadata, create tags, merge branches or publish releases.

The gate:

1. requires a clean worktree;
2. records exact `HEAD`, tree and branch;
3. runs `RUN_TEV_SCRIPT_V1_PRECERTIFY.py` as a child process;
4. requires exactly one successful pre-certify receipt and receipt SHA-256;
5. parses that receipt rather than trusting terminal prose;
6. verifies that the embedded commit/tree/branch equal the current checkout;
7. verifies that every mandatory V1/V3 evidence field is `PASS` or its exact stronger PASS token;
8. verifies `certify_full=false` and `language_stable=false` in the pre-certify evidence, proving the child did not self-promote;
9. re-checks the repository remains clean and the exact commit/tree are unchanged after all validation;
10. emits a new technical certificate bound to that exact commit/tree and the exact pre-certify receipt hash.

The technical certificate schema is:

```text
TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V1
```

A successful technical admission emits:

```text
CERTIFY_FULL=PASS
LANGUAGE_STABLE=NO
```

This is not contradictory: `CERTIFY_FULL` certifies the language/runtime candidate at one immutable Git identity; stable release admission is a separate publication/governance decision.

## 5. Stage D — stable-release admission

Stable admission is intentionally not performed by `CERTIFY_FULL`.

A release/promotion commit may change repository-facing version metadata such as `descriptor.json`, `CANONICAL_INDEX.json` or release documentation. Because that produces a **different tree/commit**, it cannot inherit the parent's technical certificate blindly.

The safe promotion sequence is:

```text
candidate commit C
  -> PRECERTIFY(C)=PASS
  -> CERTIFY_FULL(C)=PASS
  -> create narrowly scoped stable-admission commit S
  -> PRECERTIFY(S)=PASS
  -> CERTIFY_FULL(S)=PASS
  -> only then tag/publish S as stable
```

If promotion metadata would alter a semantically hashed artifact, the resulting semantic identities must be recomputed through their normal canonical pipelines rather than patched manually.

## 6. No transitive certification

These do **not** imply certification of another commit:

- a parent commit passed;
- a sibling branch passed;
- the diff is documentation-only;
- the diff is a version-string-only change;
- the generated IR is visually identical;
- all tests passed before the final commit was created.

Every certified Git commit/tree must be the identity observed by the gate itself.

## 7. No skipped mandatory target

For V1 full certification, a missing Node, .NET, Chromium, Wasmtime, .NET WASI pack or required wasi-sdk is a failed admission environment, not a successful partial certification.

Individual development gates may report `SKIPPED_*` when a tool is unavailable. `PRECERTIFY` and `CERTIFY_FULL` must reject those skips.

## 8. Production-security boundary

Language/runtime `CERTIFY_FULL` does not certify:

- production signing-key custody/rotation;
- hostile rollback-resistant monotonic storage;
- public WAN/TLS/DNS/CDN deployment;
- external package registries;
- physical Unity input/animation providers;
- decentralized consensus/trust;
- unrestricted self-modifying or evolutionary code.

Those are distinct system/deployment assurance surfaces.
