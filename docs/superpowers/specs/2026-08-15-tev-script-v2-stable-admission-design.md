# TEV Script V2 Stable Admission — Design

Date: 2026-08-15

## Status and objective

TEV Script V2 is canonically merged on `main` at:

```text
MAIN=fef64edf903610b87a1dc959ef7cbf7ab9f5400f
MAIN_TREE=2cb038689c881822e3248fbb4cd9b46b888e2b9f
CERTIFIED_CANDIDATE=1ef5f5edffade0d2388a281f6a2b1c9b8f9dc4d4
CERTIFIED_CANDIDATE_TREE=2cb038689c881822e3248fbb4cd9b46b888e2b9f
V2_RECEIPT_HASH=c826ee732977a38bf015985a3f08f845a985b751d80b0d71bc0dcb17ed6aa6b5
```

The merge preserves the certified candidate tree exactly. V2 nevertheless remains non-stable by authority: `CANONICAL_INDEX.json`, the V2 feature matrix, descriptor, and descriptor schema still encode a candidate/non-stable state, and no V2 stable-admission gate exists.

The objective is to make `LANGUAGE_STABLE=YES` derivable only from a separate, fail-closed Stable Admission procedure. Merge, technical certification, or a manual metadata edit must never imply stability by themselves.

## Governing invariant

The V1 architecture is the reference pattern:

```text
technical certification != stable admission
```

A stable claim is valid only when a release-only identity `S` is admitted relative to an independently technically certified parent `P`.

Therefore:

```text
CERTIFY_V2=PASS          -> LANGUAGE_STABLE=NO
STABLE_ADMISSION_V2=PASS -> LANGUAGE_STABLE=YES
```

The stable gate must never be introduced or modified in the same release-only diff whose stability it judges.

Language version and distribution version are distinct authorities. V2 language stability is `2.0.0`; the existing Python reference distribution remains `1.0.0` during this admission because V1 stable non-regression currently binds that package version. A future package-version transition is a separate technical/release project and must not be smuggled into V2 Stable Admission.

## Approaches considered

### A. Direct stable release from current `main`

Add `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` and stable metadata in one branch from `fef64edf...`.

Rejected. This makes the judge part of the judged release diff. It violates the V1 invariant that runtime/compiler/gate changes require a newly technically certified parent before stable admission.

### B. Two-stage bootstrap, then release-only admission — selected

1. **T — Stable-tooling technical phase.** Add stable-admission machinery while all V2 stable claims remain false. Freshly certify this exact tooling tree against the current canonical `main`; merge it only after technical review/certification. The resulting canonical commit is `P`.
2. **S — Stable release phase.** Branch from `P` and modify only a closed release-metadata path set. Run the already-existing stable gate from `P`. Only this gate may emit `LANGUAGE_STABLE=YES`.

This preserves non-circular authority and mirrors V1 while adapting it to V2's Python-centered public surface.

### C. External/tag-only stable admission

Keep repository authority unchanged and treat an external receipt or tag as the stable claim.

Rejected. The repository's canonical index, descriptor, schemas, and feature matrix would continue to contradict the tag. Stable state must be internally inspectable and independently verifiable.

## Phase T — stable-admission tooling technical parent

Phase T starts from exact canonical parent:

```text
P0=fef64edf903610b87a1dc959ef7cbf7ab9f5400f
```

Phase T is **not** a stable release. Every observable stable claim remains false.

### T1. Repeatable/profile-aware V2 technical certification

The existing V2 certifier is historically pinned to the original V2 implementation base `284ec3ec...`, and the current authority validator hard-codes the candidate profile. Those historical semantics must remain valid by default.

Extend `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py` and `tools/validate_v2_authority.py` additively:

- Default invocation preserves the historical candidate/pinned-base behavior and `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1` semantics.
- Add `--profile candidate|stable`, defaulting to `candidate`.
- Add explicit `--expected-base <40-hex-sha>` current-base mode.
- In current-base mode, require `origin/main == expected_base`, require `expected_base` to be an ancestor of `HEAD`, require an `agent/` branch, require a clean worktree, and bind exact commit/tree/base.
- Current-base mode emits `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2` validated by a new additive schema. It includes `admission_profile`; its base SHA is exact but not globally hard-coded. The V1 receipt schema remains immutable.
- Candidate profile requires candidate/non-stable index, feature matrix, release metadata, descriptor, and schema state.
- Stable profile requires stable-shaped index, feature matrix, release metadata, descriptor, and schema state, but the technical certifier still emits `LANGUAGE_STABLE=NO`.
- Both profiles run the same semantic/security evidence: V2 normative authority, schemas/contracts, CLI, source/static, Program IR V4, filesystem safety, governed regression, full regression, and V1 stable non-regression.

Phase T itself is certified with:

```text
RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py \
  --profile candidate \
  --expected-base fef64edf903610b87a1dc959ef7cbf7ab9f5400f \
  --receipt-out <external-path>
```

This creates reusable technical certification without rewriting historical evidence.

### T2. Release metadata indirection

Add `tev_script/release_metadata_v2.py` as release-only state, initially in candidate mode:

```text
RELEASE_PROFILE=candidate
RELEASE_STATUS=IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED
STABLE=false
CURRENT_V2_CERTIFY_FULL_CLAIM=false
CURRENT_V2_LANGUAGE_STABLE_CLAIM=false
TECHNICAL_PARENT_COMMIT=""
TECHNICAL_PARENT_CERTIFICATE_SHA256=""
STABLE_LANGUAGE_VERSION=2.0.0
```

`descriptor_v2.py` must read release state from this module rather than hard-code candidate/stable values. In Phase T this refactor must be behavior-preserving: descriptor output remains non-stable.

The descriptor exposes stable-admission authority even while the claim is false:

- stable admission gate path;
- stable admission receipt schema;
- technical-parent certificate requirement;
- release-diff confinement requirement;
- artifact byte-identity requirement;
- current technical certification claim;
- current language-stable claim.

The historical `certified_base_sha=284ec3ec...` remains an initial-V2 lineage datum; it is not reused as the future stable technical-parent identity.

### T3. Descriptor/schema authority

Generalize `schemas/tev-script-v2-descriptor.schema.json` so it accepts exactly two coherent release profiles:

- candidate: stable false, no technical-parent binding, no stable claim;
- stable: `STABLE_2_0_0`, stable true, exact technical-parent commit and certificate hash present, current V2 technical claim true, current V2 language-stable claim true.

Do not weaken semantic/security fields. Program IR, filesystem invariants, command inventory, capability boundaries, and runtime-source restrictions remain identical across profiles.

Add the current-base V2 technical receipt schema and the V2 stable-admission receipt schema as additive authority. Preserve the historical V2 receipt schema unchanged.

### T4. V2 stable governance validator

Add `tools/validate_v2_stable_governance.py`.

It validates only release/governance state and fails closed unless all of the following hold:

- release profile is `stable`;
- release status is `STABLE_2_0_0`;
- canonical V2 target is unique and stable;
- descriptor and descriptor schema agree with stable state;
- feature matrix declares stable admission and its required promotion gates;
- technical-parent commit/hash are valid and exposed consistently;
- Python project version remains `1.0.0`, dependencies remain empty, and V2 CLI entry points remain present;
- README, CHANGELOG, and PROJECT_STATE contain stable-admission identity/witness tokens;
- no JavaScript/C#/Unity V2 stability is implied unless separately proven.

The `1.0.0` Python package-version check is deliberate: it preserves the already-stable V1 package contract while admitting V2 as a language. Language V2 and package-version evolution are decoupled.

### T5. V2 Python artifact certification

Add `RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py` as a technical packaging gate. It supports candidate/stable profiles but never emits a stable-language claim.

It must:

- require a clean exact Git identity;
- build artifacts outside the repository;
- produce exactly one wheel;
- require distribution name `tev-script-portable-reference` and package version `1.0.0`;
- verify V2 console entry points `tev-script-v2` and `tev-script-v2-describe` exist in wheel metadata;
- verify the installed/imported wheel exposes the V2 descriptor and CLI from the wheel, not from the checkout;
- verify descriptor self-hash and language version `2.0.0`;
- record exact wheel filename/hash and technical Git identity in a self-hashed external receipt;
- emit `PYTHON_V2_CERTIFY_FULL=PASS` and `LANGUAGE_STABLE=NO` only on success.

This proves that the existing 1.0.0 reference distribution physically carries the admitted V2 surface without falsely claiming a package 2.0 release.

### T6. V2 stable admission gate

Add `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` plus `TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1` schema.

The gate consumes:

```text
--technical-parent-certificate <external path>
--artifact-out-dir <external empty directory>
```

It must:

1. require clean worktree before and after;
2. bind exact `HEAD`, tree, branch, and technical parent;
3. validate external technical-parent certificate hash and `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2` schema;
4. require the certificate profile to be `candidate` and its commit/tree to equal the declared technical parent;
5. require the technical parent to be an ancestor of the stable candidate;
6. enforce the exact release-only diff whitelist;
7. run V2 stable governance;
8. run V2 technical certification with `--profile stable --expected-base P`, requiring that it still emits `LANGUAGE_STABLE=NO`;
9. run V1 stable non-regression certification;
10. run V2 Python artifact certification with stable profile and verify exact wheel byte identity;
11. verify descriptor self-hash and canonical release metadata consistency;
12. verify HEAD/tree unchanged after all gates;
13. emit a self-hashed `TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1` outside the repository;
14. emit `CERTIFY_FULL=PASS`, `STABLE_ADMISSION=PASS`, and only then `LANGUAGE_STABLE=YES`.

No tag, release, push, PR, or merge is performed by the gate.

### T7. Phase-T tests

Add governed tests for:

- historical V2 receipt V1 compatibility;
- current-base technical-certification identity binding;
- candidate/stable profile discrimination;
- base drift rejection;
- dirty-worktree rejection;
- descriptor candidate/stable profile schema discrimination;
- candidate profile cannot claim stable;
- stable profile cannot omit parent certificate identity;
- stable-admission release diff rejects every non-whitelisted path;
- technical gates cannot self-promote;
- stable gate rejects missing/mismatched parent certificate;
- artifact directory must be external and empty;
- V2 wheel gate proves entry points and imports originate from the wheel;
- stable gate verifies exact wheel byte identity;
- stable gate leaves repository identity unchanged;
- negative control proving a technical implementation change cannot be hidden in an S release.

Phase T must pass full repository regression with zero skips and fresh V1/V2 technical certification before it can become technical parent `P`.

## Phase S — release-only stable identity

Phase S begins only after Phase T has been independently certified and canonically merged. Let:

```text
P=<exact merged Phase-T technical parent>
P_CERT=<exact TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2 hash>
```

Create a new `agent/` branch from `P`.

### Closed release path set

Exactly these six paths may differ from `P`:

```text
CANONICAL_INDEX.json
CHANGELOG.md
PROJECT_STATE.md
README.md
spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json
tev_script/release_metadata_v2.py
```

`pyproject.toml` is intentionally excluded. No parser, compiler, IR, runtime, filesystem, schema, certifier, validator, test, or package-version file may change in Phase S.

### Required S state

`tev_script/release_metadata_v2.py` becomes:

```text
RELEASE_PROFILE=stable
RELEASE_STATUS=STABLE_2_0_0
STABLE=true
CURRENT_V2_CERTIFY_FULL_CLAIM=true
CURRENT_V2_LANGUAGE_STABLE_CLAIM=true
TECHNICAL_PARENT_COMMIT=P
TECHNICAL_PARENT_CERTIFICATE_SHA256=P_CERT
STABLE_LANGUAGE_VERSION=2.0.0
```

`CANONICAL_INDEX.json` and the V2 feature matrix expose the stable V2 target and stable-admission gate. README, CHANGELOG, and PROJECT_STATE record the exact technical parent and state that the stable-shaped source claim remains pending until `STABLE_ADMISSION=PASS`.

The Python distribution remains version `1.0.0` and is certified byte-for-byte as carrying the V2 stable public surface. Existing V1 compatibility/stability remains intact. JavaScript, C#, and Unity package/version claims are not promoted to V2 merely because the V2 language becomes stable; cross-runtime V2 stability requires separate evidence.

## Stable admission data flow

```text
P technical tree
  + external P technical receipt
            |
            v
S release-only tree
            |
            +--> release diff confinement
            +--> stable governance
            +--> V2 technical recertification -> LANGUAGE_STABLE=NO
            +--> V1 stable non-regression
            +--> V2 Python wheel certification -> LANGUAGE_STABLE=NO
            +--> descriptor/index/matrix consistency
            +--> clean HEAD/tree invariant
            |
            v
TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1
            |
            v
LANGUAGE_STABLE=YES
```

## Error handling

Every identity, schema, hash, path-set, artifact, or gate mismatch fails closed with exit code non-zero and terminal witnesses:

```text
STABLE_ADMISSION=FAIL
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

No failure path mutates repository source. External artifacts may be discarded and regenerated.

If Phase T or S discovers a required parser/runtime/security change, abort Stable Admission. That change belongs to a new technical branch, requires fresh technical certification, and produces a new technical parent before another S attempt.

## Success criteria

Phase T is complete only when the stable-admission machinery is technically certified while V2 remains non-stable.

Phase S is admitted only when:

```text
V2_TECHNICAL_PARENT_CERTIFICATE       PASS
V2_RELEASE_DIFF_CONFINEMENT           PASS
V2_STABLE_GOVERNANCE                  PASS
V2_TECHNICAL_RECERTIFICATION          PASS
V1_STABLE_NON_REGRESSION              PASS
V2_PYTHON_WHEEL_BYTE_IDENTITY         PASS
V2_LANGUAGE_VERSION_2_0_0             PASS
PYTHON_PACKAGE_VERSION_1_0_0          PASS
DESCRIPTOR_INDEX_MATRIX_CONSISTENCY   PASS
WORKTREE_CLEAN_BEFORE_AFTER           PASS
HEAD_TREE_UNCHANGED                   PASS
STABLE_ADMISSION                      PASS
LANGUAGE_STABLE                       YES
```

Publication and merge of Phase T and Phase S remain separate governed actions requiring explicit authorization. A stable tag/release is a further action and is not implied by Stable Admission or merge.
