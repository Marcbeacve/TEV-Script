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

### T1. Repeatable V2 technical certification

The existing V2 certifier is historically pinned to the original V2 implementation base `284ec3ec...`. That one-shot binding must remain valid for historical receipts.

Extend `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py` without invalidating the legacy path:

- Default invocation preserves the historical pinned-base behavior and `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1` semantics.
- Add an explicit `--expected-base <40-hex-sha>` mode for future technical-parent certification.
- In current-base mode, require `origin/main == expected_base`, require `expected_base` to be an ancestor of `HEAD`, require an `agent/` branch, require a clean worktree, and bind the exact commit/tree/base.
- Current-base mode emits a new `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2` receipt validated by a new schema. The V1 receipt schema remains immutable.
- Both modes run the same V2 authority, schemas/contracts, CLI, source/static, Program IR V4, filesystem-safety, governed-regression, full-regression, and V1 non-regression evidence.
- Both modes must emit `LANGUAGE_STABLE=NO`.

This creates a reusable technical certification authority without rewriting historical evidence.

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

The descriptor must expose stable-admission authority even while the claim is false:

- stable admission gate path;
- stable admission receipt schema;
- technical-parent certificate requirement;
- release-diff confinement requirement;
- artifact byte-identity requirement;
- current technical certification claim;
- current language-stable claim.

### T3. Descriptor/schema authority

Generalize `schemas/tev-script-v2-descriptor.schema.json` so it accepts exactly two coherent release profiles:

- candidate: stable false, no technical-parent binding, no stable claim;
- stable: `STABLE_2_0_0`, stable true, exact technical-parent commit and certificate hash present, current V2 technical claim true, current V2 language-stable claim true.

Do not weaken semantic/security fields. Program IR, filesystem invariants, command inventory, capability boundaries, and runtime-source restrictions remain identical across profiles.

Add the new current-base technical receipt schema as additive authority; preserve the existing receipt schema unchanged.

### T4. V2 stable governance validator

Add `tools/validate_v2_stable_governance.py`.

It validates only release/governance state and must fail closed unless all of the following hold:

- release profile is `stable`;
- release status is `STABLE_2_0_0`;
- canonical V2 target is unique and stable;
- descriptor and descriptor schema agree with stable state;
- feature matrix declares stable admission and its required promotion gates;
- technical-parent commit/hash are valid and exposed consistently;
- Python project version is `2.0.0`, dependencies remain empty, and V2 CLI entry points remain present;
- README, CHANGELOG, and PROJECT_STATE contain the stable-admission identity/witness tokens;
- no JavaScript/C#/Unity V2 stability is implied unless separately proven.

### T5. V2 stable admission gate

Add `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` plus a stable-admission receipt schema.

The gate consumes:

```text
--technical-parent-certificate <external path>
--artifact-out-dir <external empty directory>
```

It must:

1. require clean worktree before and after;
2. bind exact `HEAD`, tree, branch, and technical parent;
3. validate the external technical-parent certificate hash and schema;
4. require the certificate commit/tree to equal the declared technical parent;
5. require the technical parent to be an ancestor of the stable candidate;
6. enforce the exact release-only diff whitelist;
7. run V2 stable governance;
8. run V2 technical certification in current-base/stable-head mode while requiring that technical certification itself still reports `LANGUAGE_STABLE=NO`;
9. run V1 non-regression certification;
10. build exactly one Python wheel, verify filename/version/hash against the certification receipt, and keep artifacts outside the repository;
11. verify descriptor self-hash and canonical release metadata consistency;
12. verify HEAD/tree unchanged after all gates;
13. emit a self-hashed `TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1`;
14. emit `CERTIFY_FULL=PASS`, `STABLE_ADMISSION=PASS`, and only then `LANGUAGE_STABLE=YES`.

No stable tag, release, push, PR, or merge is performed by the gate.

### T6. Phase-T tests

Add governed tests for:

- historical V1 receipt compatibility;
- current-base technical-certification identity binding;
- base drift rejection;
- dirty-worktree rejection;
- descriptor candidate/stable profile schema discrimination;
- candidate profile cannot claim stable;
- stable profile cannot omit parent certificate identity;
- stable-admission release diff rejects every non-whitelisted path;
- technical gate cannot self-promote;
- stable gate rejects missing/mismatched parent certificate;
- artifact directory must be external and empty;
- stable gate verifies exact wheel byte identity;
- stable gate leaves repository identity unchanged;
- negative control proving a technical implementation change cannot be hidden in an S release.

Phase T must pass full repository regression with zero skips and fresh V1/V2 certification before it can become technical parent `P`.

## Phase S — release-only stable identity

Phase S begins only after Phase T has been independently certified and canonically merged. Let:

```text
P=<exact merged Phase-T technical parent>
P_CERT=<exact TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2 hash>
```

Create a new `agent/` branch from `P`.

### Closed release path set

Exactly these seven paths may differ from `P`:

```text
CANONICAL_INDEX.json
CHANGELOG.md
PROJECT_STATE.md
README.md
pyproject.toml
spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json
tev_script/release_metadata_v2.py
```

No parser, compiler, IR, runtime, filesystem, schema, certifier, validator, or test file may change in Phase S.

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

`CANONICAL_INDEX.json` and the V2 feature matrix must expose the stable V2 target and stable-admission gate. The Python distribution version becomes `2.0.0`; existing V1 compatibility surfaces remain present. README, CHANGELOG, and PROJECT_STATE record the exact technical parent and the fact that the stable claim is pending gate execution until `STABLE_ADMISSION=PASS`.

JavaScript, C#, and Unity package/version claims are not promoted to V2 merely because Python V2 becomes stable. Cross-runtime V2 stability requires separate evidence if later desired.

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
            +--> V1 non-regression
            +--> Python wheel build/hash
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

Every identity, schema, hash, path-set, artifact, or gate mismatch fails closed with exit code non-zero and the terminal witnesses:

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
V2_TECHNICAL_PARENT_CERTIFICATE      PASS
V2_RELEASE_DIFF_CONFINEMENT          PASS
V2_STABLE_GOVERNANCE                 PASS
V2_TECHNICAL_RECERTIFICATION         PASS
V1_NON_REGRESSION                     PASS
PYTHON_2_0_0_WHEEL_BYTE_IDENTITY     PASS
DESCRIPTOR_INDEX_MATRIX_CONSISTENCY  PASS
WORKTREE_CLEAN_BEFORE_AFTER          PASS
HEAD_TREE_UNCHANGED                  PASS
STABLE_ADMISSION                     PASS
LANGUAGE_STABLE                      YES
```

Publication and merge of Phase T and Phase S remain separate governed actions requiring explicit authorization. A stable tag/release is a further action and is not implied by Stable Admission or merge.
