# TEV Script V1 certification protocol

Status: **candidate governance authority with governed stable-admission path**.

This protocol separates states that must never be conflated:

1. implementation exists;
2. a host/product-specific admission or certificate may pass for a bounded scope;
3. global pre-certification evidence passes;
4. the exact commit is globally technically certified;
5. stable-admission tooling itself is technically certified;
6. a release-shaped exact commit passes stable admission;
7. only then may that exact commit be tagged/published as V1 stable.

Editing metadata to say `stable=true` is a claim, not evidence. The claim becomes authoritative only when `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` emits a matching content-addressed stable-admission receipt for that exact Git identity and exact release artifacts.

## 1. Historical V0.2 oracle

V1 certification is anchored to the certified V0.2 language-completeness oracle:

```text
6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
```

Every V1 candidate/stable commit must contain that oracle in its ancestry and preserve the V0.2 portable regression campaign. The historical root `descriptor.json` remains V0.2 authority; V1 release introspection is versioned separately through `TEV_SCRIPT_DESCRIPTOR_V3`.

## 2. Stage A — implementation candidate

An implementation candidate may contain complete source/runtime functionality and conformance gates, but it reports:

```text
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Code presence, documentation, a passing ancestor, a version string or `stable=true` metadata are not certification.

## 3. Host-specific Python certification

Authorities:

```text
RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py
```

Both gates accept:

```text
--profile candidate   # default
--profile stable
```

The profile changes release/governance expectations only. Runtime semantics, least-authority checks, serialized/non-reentrant host access, checkpoint continuation, typed capability execution, isolated wheel installation, reproducible wheel bytes and 10,000-event soak remain mandatory.

The production receipt schema is:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V2
```

and binds `admission_profile` plus exact commit/tree, build-tool identities, package version and wheel SHA-256.

Candidate production emits:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Stable-profile production emits:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_STABLE_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

`RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py` emits:

```text
TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V2
PYTHON_CERTIFY_FULL=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Even under `--profile stable`, Python certification does **not** authorize language stability. It certifies the exact Python distribution/host profile. The stable-admission gate is the only authority allowed to promote the release.

When `--artifact-out-dir` is supplied, Python production/certification copies the already-verified wheel bytes outside the repository. The exported wheel hash must equal the hash bound into the Python certificate; later stable publication must use those exact bytes rather than a new rebuild.

`jsonschema` remains a certification-tool dependency for global certification. It is not a Python runtime dependency and must not be added to the wheel merely to satisfy global gates.

## 4. Stage B — global `V1_PRECERTIFY`

Authority:

```text
RUN_TEV_SCRIPT_V1_PRECERTIFY.py
```

Profiles:

```text
--profile candidate   # default
--profile stable
```

The dynamic campaign is intentionally the same under both profiles. Only governance/release metadata expectations differ.

Mandatory scope includes:

- V1 frontend/static/lowering closure with `--require-zero-skips`;
- explicit zero-skip counters for V1, IR V3 and selected V0.2 Python regression suites;
- certification-time `jsonschema` and exact `JSON_SCHEMA_VALIDATION=PASS`;
- C# V0.2/V3 assembly isolation and reflection/AOT surface guard;
- Python/JavaScript/C# IR V3 canonical receipt byte lock;
- Python/JavaScript/C# Runtime Checkpoint V2 byte lock and restart continuation;
- Browser-WASM AOT receipt/checkpoint parity through explicit managed→JSImport→authenticated HTTP witness authority;
- WASI fresh/restore process parity;
- signed-update host, Browser-WASM and WASI campaigns;
- independent V0.2 Browser-WASM and WASI/Wasmtime dynamic witnesses;
- full portable V0.2 Python/JavaScript regression;
- clean immutable HEAD/tree throughout.

Receipt:

```text
TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V7
```

The receipt includes:

```text
admission_profile = candidate | stable
certify_full = false
language_stable = false
```

A successful precertify always ends:

```text
V1_PRECERTIFY=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

## 5. Stage C — global technical `CERTIFY_FULL`

Authority:

```text
RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py
```

Profiles:

```text
--profile candidate   # default
--profile stable
```

Candidate profile validates candidate metadata. Stable profile validates the release-shaped stable claim, but neither profile may self-promote the language.

`CERTIFY_FULL`:

1. requires a clean exact checkout;
2. binds branch/HEAD/tree;
3. validates profile-specific authority metadata;
4. runs PRECERTIFY V7 with the same profile;
5. recomputes and verifies the pre-certify receipt hash;
6. requires exact branch/commit/tree/profile equality;
7. requires every mandatory witness and zero-skip/schema evidence;
8. rechecks repository identity/authority-file hashes;
9. emits a new technical certificate.

Technical certificate schema:

```text
TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2
```

It contains:

```text
admission_profile = candidate | stable
certify_full = true
language_stable = false
```

and terminates:

```text
CERTIFY_FULL=PASS
LANGUAGE_STABLE=NO
```

`--receipt-out <external-path>` may write the exact canonical technical receipt outside the repository. This is used to bind the stable release to its certified technical parent.

## 6. Stage D — stable-release admission

Authority:

```text
RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py
```

Stable admission is a separate authority from PRECERTIFY, global `CERTIFY_FULL`, Python `PYTHON_CERTIFY_FULL`, tags and publication.

The stable-admission receipt schema is:

```text
TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_V1
```

### 6.1 Required two-identity sequence

Let:

```text
C = previously certified global candidate
P = stable-admission tooling commit/branch
S = release-shaped V1.0.0 commit
```

Required sequence:

```text
C
  -> create Stage-D tooling P (still release_profile=candidate)
  -> CERTIFY_FULL(P --profile candidate)=PASS
  -> persist P technical receipt outside repository
  -> create release-shaped S from P
  -> S changes only governed release/distribution metadata
  -> STABLE_ADMISSION(S)=PASS
  -> only then tag/publish exactly S
```

P is important: the mechanism capable of admitting a stable release must itself be technically certified before it is used as authority.

### 6.2 Exact parent certificate binding

S release metadata records:

```text
TECHNICAL_PARENT_COMMIT=<P>
TECHNICAL_PARENT_CERTIFICATE_SHA256=<sha256 of P CERTIFY_FULL V2 receipt>
```

Stable admission additionally requires:

```text
--technical-parent-certificate <exact P receipt file>
```

The gate recomputes that file's canonical receipt SHA-256 and verifies:

- schema `TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2`;
- `admission_profile=candidate`;
- receipt commit equals P;
- receipt tree equals Git's tree for P;
- `certify_full=true`;
- `language_stable=false`;
- recomputed receipt SHA equals S's embedded technical-parent certificate SHA.

A hash string in metadata without the corresponding verified receipt is insufficient.

### 6.3 Release-diff confinement

`STABLE_ADMISSION` compares P..S and rejects any changed path outside the explicit release whitelist.

Allowed release paths are intentionally limited to:

```text
CANONICAL_INDEX.json
CHANGELOG.md
PROJECT_STATE.md
README.md
javascript/package.json
pyproject.toml
spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json
tev_script/release_metadata_v1.py
```

Any compiler, parser, linker, runtime, IR, C#, Browser-WASM, WASI or certification-gate change means S is no longer a release-only commit. Such a change requires a new technical candidate P and fresh Stage-C certification before another stable attempt.

### 6.4 Stable-shaped S metadata

S must satisfy stable governance:

```text
language_version = 1.0.0
release_profile = stable
release_status = STABLE_1_0_0
stable claim = true
Python package version = 1.0.0
JavaScript package version = 1.0.0
```

The root V0.2 `descriptor.json` remains historical and is not overwritten. V1 introspection uses `TEV_SCRIPT_DESCRIPTOR_V3`, whose schema explicitly governs both candidate and stable profiles.

A stable claim in S remains unauthoritative until stable admission passes.

### 6.5 Mandatory recertification of S

Stable admission does not inherit P's semantic result. It runs on S itself:

```text
RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile stable
RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py --profile stable
npm test
npm pack
```

Therefore S repeats the full cross-runtime campaign and Python distribution certification under the stable metadata profile.

Both technical child certificates must still report:

```text
LANGUAGE_STABLE=NO
```

If either attempts to emit `LANGUAGE_STABLE=YES`, stable admission fails. This preserves one unique promotion authority.

### 6.6 Exact artifact identity

Stable admission requires an external empty artifact directory and exports:

```text
python/<certified 1.0.0 wheel>
javascript/<certified 1.0.0 npm tarball>
tev-script-v1-stable-admission.receipt.json
```

The stable receipt binds the exact wheel/tarball filenames and SHA-256 values. Publication must use these exact bytes. Rebuilding after certification and publishing the rebuild is not equivalent, even if reproducibility is expected.

### 6.7 Stable success witness

Only `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` may terminate with:

```text
CERTIFY_FULL=PASS
STABLE_ADMISSION=PASS
LANGUAGE_STABLE=YES
```

Every other V1 gate must continue to emit `LANGUAGE_STABLE=NO`.

## 7. No transitive certification

These do **not** certify another commit/artifact:

- parent/sibling branch passed;
- diff is documentation-only;
- diff is version-only;
- output looks identical;
- wheel filename is unchanged;
- artifact was rebuilt from the same source;
- `CERTIFY_FULL` passed on another tree;
- `PYTHON_CERTIFY_FULL` passed on another tree;
- a stable metadata claim exists without stable-admission receipt.

Every certificate/admission is bound to the exact Git identity and artifacts observed by its own authority.

## 8. Merge/tag/publication identity

After `STABLE_ADMISSION(S)=PASS`, the release identity is S.

Preferred publication path:

```text
fast-forward main -> S
tag v1.0.0 -> exactly S
publish exact certified artifacts from stable-admission output
```

A squash/rebase/merge commit M produces a new identity. If main must point to M instead of S, M requires a fresh stable admission before it may be tagged/published as the certified release.

No merge, tag or publication is performed by the certification gates themselves.

## 9. No skipped mandatory target

For global/stable V1 certification, missing Node, .NET, Chromium, Wasmtime, .NET WASI pack, required wasi-sdk or certification-time `jsonschema` is a failed admission environment, not a partial success.

All unittest suites included by the global frontend closure must report explicit skip count zero. Stable Python profile likewise requires the zero-skip frontend witness.

Individual development gates may report `SKIPPED_*` when tooling is unavailable. Global candidate/stable PRECERTIFY, CERTIFY_FULL and STABLE_ADMISSION reject skips in mandatory scope.

## 10. Production-security boundary

Even `STABLE_ADMISSION=PASS` does not certify unrelated deployment/security surfaces such as:

- arbitrary host callbacks as safe/resource-bounded;
- production signing-key custody/rotation;
- hostile rollback-resistant monotonic storage;
- public WAN/TLS/DNS/CDN deployment;
- external registry operational security;
- physical Unity input/animation providers;
- decentralized consensus/trust;
- unrestricted self-modifying/evolutionary code.

Those remain separate system/deployment assurance domains.
