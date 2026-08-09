# TEV Script V1 certification protocol

Status: **candidate governance authority with governed stable-admission path**.

This protocol separates five authorities that must never be conflated:

```text
implementation
    != host/product certification
    != global technical certification
    != stable admission
    != merge/tag/publication
```

Editing metadata to say `stable=true` is a claim, not evidence. Only an exact successful `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` receipt may authorize `LANGUAGE_STABLE=YES`.

## 1. Historical V0.2 oracle

V1 remains anchored to:

```text
6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5
```

Every V1 candidate/stable commit must contain that oracle in its ancestry and preserve the V0.2 regression surface. Root `descriptor.json` remains historical V0.2 authority; V1 introspection is `TEV_SCRIPT_DESCRIPTOR_V3`.

## 2. Candidate state

Implementation presence alone reports:

```text
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

A passing parent/sibling, documentation change, version change or metadata claim is not certification of the current Git identity.

## 3. Python product certification

Authorities:

```text
RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py
```

Profiles:

```text
--profile candidate   # default
--profile stable
```

Profiles change release/governance expectations only. Runtime semantics and evidence remain mandatory: least authority, serialized/non-reentrant host access, real concurrent-access rejection, typed capabilities, Runtime Checkpoint V2, isolated install, two byte-identical wheels and 10,000-event soak.

Production receipt:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V2
```

Python certificate:

```text
TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V2
PYTHON_CERTIFY_FULL=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Stable-profile Python certification does not authorize language stability. `--artifact-out-dir` exports the exact already-certified wheel bytes outside the repository; stable publication must use those bytes, not a later rebuild.

## 4. Global PRECERTIFY

Authority:

```text
RUN_TEV_SCRIPT_V1_PRECERTIFY.py
```

Profiles:

```text
--profile candidate   # default
--profile stable
```

Both profiles run the same dynamic campaign. Only profile-specific governance differs.

Mandatory scope includes:

- frontend/static/lowering with `--require-zero-skips`;
- explicit zero unittest skips;
- certification-time `jsonschema` and exact schema PASS;
- C# V0.2/V3 isolation/AOT surface;
- Python/JavaScript/C# IR V3 canonical byte lock;
- Runtime Checkpoint V2 cross-host byte lock/restart;
- Browser-WASM managed→JSImport→authenticated witness parity;
- WASI fresh/restore parity;
- signed-update host/Browser/WASI campaigns;
- independent V0.2 Browser-WASM/WASI witnesses;
- complete portable V0.2 regression;
- clean immutable HEAD/tree.

Receipt:

```text
TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V7
admission_profile = candidate | stable
certify_full = false
language_stable = false
```

Success always ends:

```text
V1_PRECERTIFY=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

## 5. Global technical CERTIFY_FULL

Authority:

```text
RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py
```

Profiles:

```text
--profile candidate   # default
--profile stable
```

The gate binds exact branch/HEAD/tree, validates profile-specific authority metadata, runs PRECERTIFY V7 with the same profile, recomputes its receipt hash, requires all mandatory evidence, rechecks repository identity and emits:

```text
TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2
admission_profile = candidate | stable
certify_full = true
language_stable = false
```

Terminal witness:

```text
CERTIFY_FULL=PASS
LANGUAGE_STABLE=NO
```

`--receipt-out <external-path>` persists those exact canonical receipt bytes outside the repository. This is required when a technically certified Stage-D tooling commit P becomes parent authority for stable S.

## 6. Stage D — stable-release admission

Authority:

```text
RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py
```

Receipt:

```text
TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_V1
```

### 6.1 Required C → P → S chain

```text
C = already globally certified language/runtime candidate
P = Stage-D tooling commit; release_profile=candidate
S = release-shaped 1.0.0 commit
```

Required sequence:

```text
C
  -> build Stage-D tooling P
  -> CERTIFY_FULL(P --profile candidate)=PASS
  -> persist exact P technical receipt outside repository
  -> create S directly from exact P
  -> S changes exactly the governed release path set
  -> STABLE_ADMISSION(S)=PASS
  -> only then may exactly S be tagged/published
```

P matters because the mechanism capable of stable admission must itself be technically certified before it becomes authority.

### 6.2 Exact parent-certificate binding

S records:

```text
TECHNICAL_PARENT_COMMIT=<P>
TECHNICAL_PARENT_CERTIFICATE_SHA256=<SHA-256 of exact P CERTIFY_FULL V2 receipt>
```

Stable admission requires:

```text
--technical-parent-certificate <exact external P receipt file>
```

It recomputes and verifies that receipt and requires:

- schema `TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2`;
- `admission_profile=candidate`;
- receipt commit exactly P;
- receipt tree exactly Git's tree for P;
- `certify_full=true`;
- `language_stable=false`;
- recomputed receipt SHA exactly equal to S's declared parent-certificate SHA;
- P is an ancestor of S.

A metadata hash without the matching verified receipt bytes is insufficient.

### 6.3 Exact release-diff path set

P..S must change **exactly these eight paths**:

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

This is equality, not merely a whitelist/subset rule:

```text
changed_paths(P..S) == required_release_paths
```

If any required path is missing, stable admission fails. If any extra path exists, stable admission fails.

Therefore S cannot change parser, linker, compiler, IR, Python/JavaScript/C# runtime, Browser-WASM/WASI product code, tests, schemas or certification gates. Such a change requires a new candidate P and fresh technical certification before another stable attempt.

### 6.4 Stable-shaped metadata

S must request:

```text
language_version = 1.0.0
release_profile = stable
release_status = STABLE_1_0_0
stable claim = true
Python package version = 1.0.0
JavaScript package version = 1.0.0
STABLE_ADMISSION=REQUESTED
LANGUAGE_STABLE_CLAIM=REQUESTED
```

`README.md` and `CHANGELOG.md` must explicitly contain `1.0.0` and `STABLE_ADMISSION`. Root V0.2 `descriptor.json` is not overwritten.

These remain unauthoritative claims until the exact stable-admission receipt passes.

### 6.5 Mandatory recertification of S

Stable admission runs on S itself:

```text
RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile stable
RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py --profile stable
npm test
npm pack --json
```

Thus S repeats global cross-runtime certification and Python distribution certification under stable metadata. Both child certificates must still report:

```text
LANGUAGE_STABLE=NO
```

If either child gate self-promotes, stable admission fails.

### 6.6 Exact publication artifacts

Stable admission requires an external empty artifact directory and emits/validates:

```text
python/<certified 1.0.0 wheel>
javascript/<certified 1.0.0 npm tarball>
tev-script-v1-stable-admission.receipt.json
```

Python wheel identity must match the Python certificate filename/SHA-256.

JavaScript package identity is independently bound by:

- `package.json` name/version;
- `npm pack --json` name/version;
- non-empty npm integrity;
- exact tarball filename;
- independently computed tarball SHA-256.

Publication must use these exact certified bytes. A rebuild is another artifact even if reproducibility is expected.

### 6.7 Unique stable authority

Only `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` may terminate:

```text
CERTIFY_FULL=PASS
STABLE_ADMISSION=PASS
LANGUAGE_STABLE=YES
```

All PRECERTIFY/global/Python subordinate gates must remain `LANGUAGE_STABLE=NO`.

## 7. No transitive certification

No transitive certification is allowed. These do not certify another identity:

- a parent/sibling passed;
- the diff is documentation/version-only;
- outputs look equivalent;
- wheel/package names are unchanged;
- artifacts were rebuilt from the same source;
- technical certification passed on another tree;
- stable metadata exists without stable-admission receipt.

Every certificate/admission is bound to the exact Git identity and exact artifacts observed by its own authority.

## 8. Merge/tag/publication identity

After `STABLE_ADMISSION(S)=PASS`, S is the release identity.

Preferred path:

```text
fast-forward main -> exactly S
tag v1.0.0 -> exactly S
publish exact stable-admission artifact bytes
```

A squash/rebase/merge commit M is a new identity. If publication must use M, M requires fresh stable admission before it can be represented as the certified stable release.

Certification gates do not themselves merge, tag or publish.

## 9. No skipped mandatory target

No skipped mandatory target is admitted. Missing Node, .NET, Chromium, Wasmtime, .NET WASI pack, wasi-sdk or certification-time `jsonschema` is an admission-environment failure, not partial success.

Global candidate/stable PRECERTIFY/CERTIFY_FULL and stable Python profile require explicit zero skips in their mandatory frontend scope.

## 10. Production-security boundary

Even `STABLE_ADMISSION=PASS` does not certify unrelated deployment/security domains, including production signing-key custody/rotation, hostile rollback-resistant monotonic storage, public WAN/TLS/DNS/CDN deployment, arbitrary host callback sandboxing, external registry operational security, physical Unity input/animation providers, decentralized consensus/trust or unrestricted evolutionary/self-modifying code.
