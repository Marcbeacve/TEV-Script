# TEV Script V1 certification protocol

Status: **candidate governance authority**.

This protocol separates states that must never be conflated:

1. implementation exists;
2. a host/product-specific admission or certificate may pass for a bounded scope;
3. global pre-certification evidence passes;
4. the exact commit is globally technically certified;
5. a stable release is admitted.

The separation is intentional. Editing metadata to say `stable=true` is not evidence that the edited commit is the one that passed the runtime, distribution or portability campaign.

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

## 3. Host-specific certification profiles

A host may require product/distribution evidence that is meaningful for that host but is not part of the language's cross-runtime semantic matrix. Such a profile may be certified independently only when all of the following hold:

- the scope is explicit and narrower than global V1 certification;
- the gate binds itself to an exact clean commit/tree;
- the evidence is canonical and content-addressed;
- the host-specific certificate does not emit global `CERTIFY_FULL=PASS`;
- the host-specific certificate does not emit `LANGUAGE_STABLE=YES`;
- no certificate is inherited across a changed commit or artifact.

### 3.1 Python production admission

Authority:

```text
RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
```

This gate verifies the Python distribution/embedding boundary on one exact clean commit. Its mandatory scope includes the current Python/frontend/IR V3 closure, V0.2 Python regression, governance, zero runtime dependencies, two independent offline wheel builds, byte-identical reproducible `py3-none-any` wheel output, isolated wheel installation, installed-module origin, explicit deployed IR V3 compilation, IR-only runtime execution, least-authority capability preflight, serialized/non-reentrant host access with fail-closed `TEVS_PYTHON_V1_HOST_BUSY`, typed capability execution, Runtime Checkpoint V2 continuation and a deterministic 10,000-event soak.

The canonical Python product contract requires:

```text
python_production_surface.serialized_host_access=true
```

A capability-driven attempt to reenter the same active host must be rejected and must not mutate TEV state. The host does not turn Python thread scheduling into an implicit TEV ordering rule.

It emits:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V1
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Production admission is evidence generation, not yet a Python certificate.

### 3.2 Python host `PYTHON_CERTIFY_FULL`

Authority:

```text
RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py
```

This gate is read-only with respect to tracked repository content. It captures its own exact HEAD/tree, verifies `serialized_host_access=true`, re-runs Python production admission, parses the canonical production receipt rather than trusting terminal prose, independently recomputes the receipt hash, requires the embedded hash and external hash to agree, validates every mandatory Python product witness including `reentrant_access_rejected=PASS`, rechecks repository/canonical/state immutability and emits a certificate bound to the exact production receipt and wheel SHA-256.

The Python certificate schema is:

```text
TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V1
```

Its certified scope explicitly includes:

```text
V1_PYTHON_SERIALIZED_HOST_ACCESS_GUARD
```

A successful Python-host admission emits:

```text
PYTHON_CERTIFY_FULL=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

The certificate itself records:

```text
python_certify_full=true
global_certify_full=false
language_stable=false
stable_release_authorized=false
```

This permits the Python host/product profile to reach technical certification without waiting for Unity or the full multi-runtime V1 campaign. It does **not** redefine `CERTIFY_FULL` and cannot authorize a stable V1 release by itself.

## 4. Stage B — global `V1_PRECERTIFY`

Authority:

```text
RUN_TEV_SCRIPT_V1_PRECERTIFY.py
```

The gate runs from one exact clean checkout and requires all of the following without V1/V3 skips:

- reference V1 frontend/static/lowering closure;
- V0.2 Python regression inside the closure gate;
- C# V0.2/V3 assembly-isolation and reflection/AOT surface guard;
- regex-free closed ASCII lexical admission in the portable C# V3 assembly;
- Python/JavaScript/C# IR V3 canonical receipt byte lock;
- Python/JavaScript/C# Runtime Checkpoint V2 byte lock and restart continuation;
- Browser-WASM AOT IR V3 receipt/checkpoint parity;
- explicit managed-to-JavaScript Browser-WASM witness authority (console output is diagnostic only);
- WASI IR V3 fresh-process/checkpoint/restore-process parity;
- signed-update V3 host campaign;
- signed-update V3 Browser-WASM campaign;
- signed-update V3 WASI fresh/restore campaign;
- complete portable V0.2 Python/JavaScript regression;
- independent V0.2 Browser-WASM AOT and WASI/Wasmtime dynamic witnesses from
  `tools/validate_v0_2_portable_hosts.py`;
- explicit classification of optional `jsonschema` validation as either PASS
  or `OPTIONAL_DEPENDENCY_UNAVAILABLE`;
- clean worktree before and after;
- identical commit and tree before and after validation.

A successful run emits one canonical JSON receipt:

```text
TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V6
```

and its SHA-256.

`V1_PRECERTIFY=PASS` still means:

```text
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

because pre-certification is an evidence-producing test campaign, not the final global admission step.

## 5. Stage C — global technical `CERTIFY_FULL`

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

The global technical certificate schema is:

```text
TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V1
```

A successful global technical admission emits:

```text
CERTIFY_FULL=PASS
LANGUAGE_STABLE=NO
```

This is not contradictory: `CERTIFY_FULL` certifies the language/runtime candidate at one immutable Git identity; stable release admission is a separate publication/governance decision.

## 6. Stage D — stable-release admission

Stable admission is intentionally not performed by either Python `PYTHON_CERTIFY_FULL` or global `CERTIFY_FULL`.

A release/promotion commit may change repository-facing version metadata such as package version, `descriptor.json`, `CANONICAL_INDEX.json` or release documentation. Because that produces a **different tree/commit**, it cannot inherit the parent's technical certificate blindly.

For a Python-only product release, the minimum safe host-specific promotion sequence is:

```text
candidate commit C
  -> PYTHON_PRODUCTION(C)=PASS_CANDIDATE
  -> PYTHON_CERTIFY_FULL(C)=PASS
  -> create narrowly scoped Python stable-admission/version commit S
  -> PYTHON_PRODUCTION(S)=PASS_CANDIDATE
  -> PYTHON_CERTIFY_FULL(S)=PASS
  -> only then perform the separately authorized Python release/tag/publication step
```

For a globally certified V1 release, the global sequence remains:

```text
candidate commit C
  -> PRECERTIFY(C)=PASS
  -> CERTIFY_FULL(C)=PASS
  -> create narrowly scoped stable-admission commit S
  -> PRECERTIFY(S)=PASS
  -> CERTIFY_FULL(S)=PASS
  -> only then tag/publish S as globally stable
```

If the globally stable release also publishes the Python distribution, its Python product certificate should be re-run on S as well rather than inferred from the global semantic certificate.

If promotion metadata would alter a semantically hashed artifact, the resulting semantic identities must be recomputed through their normal canonical pipelines rather than patched manually.

## 7. No transitive certification

These do **not** imply certification of another commit:

- a parent commit passed;
- a sibling branch passed;
- the diff is documentation-only;
- the diff is a version-string-only change;
- the generated IR is visually identical;
- all tests passed before the final commit was created;
- the wheel filename is unchanged;
- global `CERTIFY_FULL` passed on another tree;
- Python `PYTHON_CERTIFY_FULL` passed on another tree.

Every certified Git commit/tree and host artifact must be the identity observed by the relevant gate itself.

## 8. No skipped mandatory target

For global V1 full certification, a missing Node, .NET, Chromium, Wasmtime, .NET WASI pack or required wasi-sdk is a failed admission environment, not a successful partial certification.

For Python full certification, a missing/incompatible local Python 3.11+, pip or setuptools build environment, a non-reproducible wheel, a failed isolated install or any mandatory runtime/authority/serialization/checkpoint/soak witness is likewise a failed host admission.

Individual development gates may report `SKIPPED_*` when a tool is unavailable. Python production/certification and global `PRECERTIFY`/`CERTIFY_FULL` must reject skips in their mandatory scope.

## 9. Production-security boundary

Neither Python `PYTHON_CERTIFY_FULL` nor global language/runtime `CERTIFY_FULL` certifies:

- arbitrary Python host callbacks as safe or resource-bounded;
- deterministic scheduling between multiple independent Python host instances unless the application makes that ordering explicit;
- production signing-key custody/rotation;
- hostile rollback-resistant monotonic storage;
- public WAN/TLS/DNS/CDN deployment;
- external package registries;
- physical Unity input/animation providers;
- decentralized consensus/trust;
- unrestricted self-modifying or evolutionary code.

Those are distinct system/deployment assurance surfaces. Untrusted Python capability implementations require isolation/resource controls outside the TEV runtime.
