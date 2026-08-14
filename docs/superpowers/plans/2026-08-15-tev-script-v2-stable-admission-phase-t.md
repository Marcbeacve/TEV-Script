# TEV Script V2 Stable Admission Phase T Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and technically certify the reusable V2 Stable Admission machinery while every V2 stable-language claim remains false.

**Architecture:** Phase T is a technical bootstrap from exact canonical base `fef64edf903610b87a1dc959ef7cbf7ab9f5400f`. It introduces release metadata indirection, profile-aware V2 technical certification, V2 artifact certification, stable governance, and the stable-admission gate; only a later release-only Phase S may use those already-certified tools to emit `LANGUAGE_STABLE=YES`.

**Tech Stack:** Python 3.11+ standard library, `unittest`, JSON Schema Draft 2020-12, Git exact identities, canonical SHA-256 receipts, existing deterministic PEP 517 backend and V1 stable certification gates.

## Global Constraints

- Work only on `agent/tev-script-v2-stable-admission-v1`; `main` stays untouched.
- Phase-T technical base is exactly `fef64edf903610b87a1dc959ef7cbf7ab9f5400f` with tree `2cb038689c881822e3248fbb4cd9b46b888e2b9f`.
- Do not create a PR, merge, tag, release, or claim stable promotion during Phase T.
- Every Phase-T observable V2 stable claim remains false; all technical gates must emit `LANGUAGE_STABLE=NO`.
- Preserve the historical `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1` path and pinned base `284ec3ec8c41681825ec1a8421f7ee2a1b012d68` for default legacy invocation.
- New repeatable technical certification uses `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2` and an explicit exact `--expected-base`.
- V2 language version is `2.0.0`; Python reference distribution version remains exactly `1.0.0` in this project.
- `pyproject.toml` must not change in Phase T or later Phase S for V2 stability.
- Python runtime dependencies remain exactly empty.
- V1 stable certification remains mandatory non-regression evidence.
- No parser, compiler, Program IR V4, filesystem-safety implementation, or language semantic change is authorized unless a failing gate demonstrates a real technical defect; such a defect invalidates the stable-admission track and requires a separately recertified technical parent.
- External receipts/artifacts must be outside the repository and source certification must leave HEAD/tree unchanged.

---

## File map

**Create:**
- `tev_script/release_metadata_v2.py` — V2 release/profile state only.
- `tools/v2_certification_support.py` — shared Git identity, external-output, hashing, and marker helpers for V2 gates.
- `schemas/tev-script-v2-certify-full-receipt-v2.schema.json` — current-base technical receipt.
- `RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py` — V2 wheel/public-surface technical certification.
- `schemas/tev-script-v2-python-certify-full-receipt.schema.json` — V2 Python certification receipt.
- `tools/validate_v2_stable_governance.py` — stable-shaped release-governance validator.
- `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` — sole V2 `LANGUAGE_STABLE=YES` authority.
- `schemas/tev-script-v2-stable-admission-receipt.schema.json` — stable-admission receipt.
- `tests/test_v2_release_metadata.py`
- `tests/test_v2_python_certify_full.py`
- `tests/test_v2_stable_governance.py`
- `tests/test_v2_stable_admission.py`

**Modify:**
- `tev_script/descriptor_v2.py`
- `schemas/tev-script-v2-descriptor.schema.json`
- `tools/validate_v2_authority.py`
- `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py`
- `tests/test_v2_descriptor.py`
- `tests/test_v2_schemas.py`
- `tests/test_v2_authority.py`
- `tests/test_v2_certify_full.py`
- `CANONICAL_INDEX.json`
- `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- `PROJECT_STATE.md`
- `README.md`

No other implementation file belongs to Phase T.

---

### Task 1: Add V2 release metadata as a separate authority

**Files:**
- Create: `tev_script/release_metadata_v2.py`
- Create: `tests/test_v2_release_metadata.py`

**Interfaces:**
- Produces constants `RELEASE_PROFILE`, `RELEASE_STATUS`, `STABLE`, `CURRENT_V2_CERTIFY_FULL_CLAIM`, `CURRENT_V2_LANGUAGE_STABLE_CLAIM`, `TECHNICAL_PARENT_COMMIT`, `TECHNICAL_PARENT_CERTIFICATE_SHA256`, `STABLE_LANGUAGE_VERSION`.
- Produces `validate_release_metadata() -> None`.

- [ ] **Step 1: Write candidate/stable invariant tests**

```python
import tev_script.release_metadata_v2 as metadata

self.assertEqual(metadata.RELEASE_PROFILE, "candidate")
self.assertEqual(metadata.RELEASE_STATUS, "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED")
self.assertIs(metadata.STABLE, False)
self.assertFalse(metadata.CURRENT_V2_CERTIFY_FULL_CLAIM)
self.assertFalse(metadata.CURRENT_V2_LANGUAGE_STABLE_CLAIM)
self.assertEqual(metadata.TECHNICAL_PARENT_COMMIT, "")
self.assertEqual(metadata.TECHNICAL_PARENT_CERTIFICATE_SHA256, "")
self.assertEqual(metadata.STABLE_LANGUAGE_VERSION, "2.0.0")
metadata.validate_release_metadata()
```

Also patch module globals to construct invalid candidate claims and invalid stable parent/hash shapes; assert stable error codes begin `TEVS_V2_RELEASE_METADATA_`.

- [ ] **Step 2: Run RED**

Run: `python -m unittest -v tests.test_v2_release_metadata`

Expected: import failure because `tev_script.release_metadata_v2` does not exist.

- [ ] **Step 3: Implement the exact candidate metadata**

```python
RELEASE_PROFILE = "candidate"
RELEASE_STATUS = "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED"
STABLE = False
CURRENT_V2_CERTIFY_FULL_CLAIM = False
CURRENT_V2_LANGUAGE_STABLE_CLAIM = False
TECHNICAL_PARENT_COMMIT = ""
TECHNICAL_PARENT_CERTIFICATE_SHA256 = ""
STABLE_LANGUAGE_VERSION = "2.0.0"
```

`validate_release_metadata()` accepts exactly candidate state above or stable state `STABLE_2_0_0` with both claims true, a 40-hex technical parent, and a 64-hex certificate SHA. Reject every mixed state.

- [ ] **Step 4: Run GREEN**

Run: `python -m unittest -v tests.test_v2_release_metadata`

Expected: PASS, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tev_script/release_metadata_v2.py tests/test_v2_release_metadata.py
git commit -m "feat: separate V2 release metadata"
```

### Task 2: Make the V2 descriptor release-profile aware without changing semantics

**Files:**
- Modify: `tev_script/descriptor_v2.py`
- Modify: `schemas/tev-script-v2-descriptor.schema.json`
- Modify: `tests/test_v2_descriptor.py`
- Modify: `tests/test_v2_schemas.py`

**Interfaces:**
- Consumes Task 1 release metadata.
- Keeps `V2_CERTIFIED_BASE_SHA` as historical V2 lineage.
- Produces descriptor fields `release_profile`, technical-parent bindings, current claims, and `stable_release_surface`.

- [ ] **Step 1: Write failing candidate descriptor assertions**

Require the current descriptor to expose:

```python
self.assertEqual(descriptor["release_profile"], "candidate")
self.assertEqual(descriptor["release_status"], "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED")
self.assertIs(descriptor["stable"], False)
self.assertEqual(descriptor["certification"]["technical_parent_commit"], "")
self.assertEqual(descriptor["certification"]["technical_parent_certificate_sha256"], "")
self.assertIs(descriptor["certification"]["current_v2_certify_full_claim"], False)
self.assertIs(descriptor["certification"]["current_v2_language_stable_claim"], False)
self.assertEqual(descriptor["stable_release_surface"]["admission_gate"], "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py")
self.assertIs(descriptor["stable_release_surface"]["stable_claim"], False)
```

- [ ] **Step 2: Write schema discrimination tests**

Build a stable-shaped descriptor by patching `descriptor_v2` release metadata values to `stable`, `STABLE_2_0_0`, both claims true, parent=`"1" * 40`, certificate=`"2" * 64`; recompute `descriptor_hash`; assert schema accepts it. Assert schema rejects candidate `stable=true`, stable profile with empty parent, and any security-boundary drift.

- [ ] **Step 3: Run RED**

Run: `python -m unittest -v tests.test_v2_descriptor tests.test_v2_schemas`

Expected: failures for missing release-profile/stable-surface fields.

- [ ] **Step 4: Refactor descriptor to read release metadata**

Keep semantic/security fields byte-equivalent. Add only release/governance data. The certification block must name:

```text
historical_receipt_schema = TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1
current_receipt_schema    = TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2
python_certify_full_gate  = RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py
stable_admission_gate     = RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py
```

`stable_release_surface` binds `release_metadata_v2.py`, stable governance, admission gate, stable receipt schema, exact-parent-certificate requirement, exact release-diff requirement, artifact-byte identity, and `stable_claim=STABLE`.

- [ ] **Step 5: Generalize descriptor schema with exact coherent branches**

Use JSON Schema `allOf` with one `oneOf` discriminator: candidate branch requires candidate status, false claims, and empty parent bindings; stable branch requires `STABLE_2_0_0`, true claims, 40/64 lowercase hex parent bindings. Do not relax command cardinality, filesystem invariants, runtime-source restriction, or Program IR schemas.

- [ ] **Step 6: Run GREEN**

Run: `python -m unittest -v tests.test_v2_release_metadata tests.test_v2_descriptor tests.test_v2_schemas`

Expected: PASS, zero skips.

- [ ] **Step 7: Commit**

```powershell
git add tev_script/descriptor_v2.py schemas/tev-script-v2-descriptor.schema.json tests/test_v2_descriptor.py tests/test_v2_schemas.py
git commit -m "feat: model V2 release profiles"
```

### Task 3: Make V2 authority validation profile-aware

**Files:**
- Modify: `tools/validate_v2_authority.py`
- Modify: `tests/test_v2_authority.py`

**Interfaces:**
- Produces `validate_v2_authority(profile: str = "candidate") -> dict[str, int]`.
- CLI accepts `--profile candidate|stable`, default `candidate`.

- [ ] **Step 1: Write profile tests**

Candidate test must keep current index/matrix/descriptor non-stable. Add pure helper tests that pass synthetic stable matrix/target/release metadata and require `STABLE_2_0_0`, `stable=true`, exact technical-parent bindings, and no publication/merge claim.

- [ ] **Step 2: Write a negative mixed-profile test**

Stable matrix + candidate descriptor, or candidate matrix + stable release metadata, must raise `V2AuthorityFailure` before semantic fixtures execute.

- [ ] **Step 3: Run RED**

Run: `python -m unittest -v tests.test_v2_authority`

Expected: new profile tests fail because validator is candidate-hard-coded.

- [ ] **Step 4: Split release-state checks from semantic checks**

Implement focused helpers:

```python
def _expected_release_state(profile: str) -> tuple[str, bool]: ...
def _require_release_authority(profile: str, matrix: Mapping[str, Any], target: Mapping[str, Any]) -> None: ...
def validate_v2_authority(profile: str = "candidate") -> dict[str, int]: ...
```

The existing grammar, IR, CLI, filesystem schema, and conformance checks remain shared and unchanged.

- [ ] **Step 5: Add CLI profile argument and stable witness**

Both profiles still print `TEV_SCRIPT_V2_AUTHORITY=PASS`; add `TEV_SCRIPT_V2_AUTHORITY_PROFILE=<profile>` so callers bind which governance branch was checked.

- [ ] **Step 6: Run GREEN**

Run: `python -m unittest -v tests.test_v2_authority tests.test_v2_descriptor tests.test_v2_schemas`

Expected: PASS, zero skips.

- [ ] **Step 7: Commit**

```powershell
git add tools/validate_v2_authority.py tests/test_v2_authority.py
git commit -m "feat: validate V2 authority by release profile"
```

### Task 4: Add repeatable current-base V2 technical certification

**Files:**
- Create: `tools/v2_certification_support.py`
- Create: `schemas/tev-script-v2-certify-full-receipt-v2.schema.json`
- Modify: `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py`
- Modify: `tests/test_v2_certify_full.py`
- Modify: `tests/test_v2_schemas.py`

**Interfaces:**
- `tools.v2_certification_support.GitIdentity(branch, commit_sha, tree_sha, base_sha)`.
- `collect_git_identity(root: Path, expected_base: str) -> GitIdentity`.
- `require_external_file(root: Path, path: Path) -> Path` and `require_external_empty_dir(root: Path, path: Path) -> Path`.
- V2 cert CLI adds `--profile` and `--expected-base` while preserving default historical behavior.

- [ ] **Step 1: Write failing current-base identity tests**

```python
identity = gate.collect_git_identity(ROOT, expected_base="3" * 40)
self.assertEqual(identity.base_sha, "3" * 40)
```

Mock `origin/main`; require exact equality and ancestor check. Reject uppercase/invalid SHA, base drift, dirty tree, detached/non-`agent/` branch.

- [ ] **Step 2: Write historical compatibility test**

Call `build_receipt_v1(...)` with historical base and validate against the unchanged `schemas/tev-script-v2-certify-full-receipt.schema.json`. Assert its field set remains exactly V1 and has no admission-profile/stable claim.

- [ ] **Step 3: Write V2 receipt schema test**

New receipt must contain:

```text
schema=TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2
admission_profile=candidate|stable
repository
commit_sha
tree_sha
base_sha
branch
dirty=false
python_version
gates
v2_test_count
v2_skipped_tests=0
v1_receipt_sha256
certify_full=true
language_stable=false
receipt_hash
```

- [ ] **Step 4: Run RED**

Run: `python -m unittest -v tests.test_v2_certify_full tests.test_v2_schemas`

Expected: failures for missing current-base mode/schema.

- [ ] **Step 5: Extract only shared certification mechanics**

Move Git identity/external path/hash/marker mechanics into `tools/v2_certification_support.py`; do not move semantic gate orchestration there. Keep `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py` as the readable orchestration boundary.

- [ ] **Step 6: Preserve default legacy mode**

With no `--expected-base`, require candidate profile, use historical `V2_CERTIFIED_BASE_SHA`, produce V1 receipt, and preserve existing witnesses.

- [ ] **Step 7: Implement current-base mode**

With `--expected-base`, validate exact 40-hex SHA, call authority with the chosen profile, build V2 receipt, validate new schema, and always print `LANGUAGE_STABLE=NO`.

- [ ] **Step 8: Run GREEN**

Run: `python -m unittest -v tests.test_v2_certify_full tests.test_v2_authority tests.test_v2_schemas`

Expected: PASS, zero skips.

- [ ] **Step 9: Commit**

```powershell
git add tools/v2_certification_support.py schemas/tev-script-v2-certify-full-receipt-v2.schema.json RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py tests/test_v2_certify_full.py tests/test_v2_schemas.py
git commit -m "feat: add repeatable V2 technical certification"
```

### Task 5: Certify that the existing Python 1.0.0 wheel physically carries V2

**Files:**
- Create: `RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py`
- Create: `schemas/tev-script-v2-python-certify-full-receipt.schema.json`
- Create: `tests/test_v2_python_certify_full.py`
- Modify: `tests/test_v2_schemas.py`

**Interfaces:**
- CLI: `--profile candidate|stable`, `--expected-base <sha>`, `--artifact-out-dir <external-empty-dir>`, optional `--receipt-out <external-file>`.
- Produces `TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL_RECEIPT_V1` and `PYTHON_V2_CERTIFY_FULL=PASS`; never stable-language authority.

- [ ] **Step 1: Write RED tests for artifact path, metadata, and wheel-origin proof**

Require external empty artifact dir. Reject repository paths. Require exactly one wheel named `tev_script_portable_reference-1.0.0-py3-none-any.whl`. Require entry points:

```text
tev-script-v2 = tev_script.cli_v2:main
tev-script-v2-describe = tev_script.describe_v2:main
```

- [ ] **Step 2: Write installed-origin smoke contract**

The isolated interpreter must execute code equivalent to:

```python
from pathlib import Path
import json, sys, tev_script
from tev_script.descriptor_v2 import v2_descriptor
module = Path(tev_script.__file__).resolve()
if not module.is_relative_to(Path(sys.prefix).resolve()):
    raise SystemExit("module_not_from_venv")
d = v2_descriptor()
assert d["language_version"] == "2.0.0"
assert d["release_profile"] == EXPECTED_PROFILE
print(d["descriptor_hash"])
```

- [ ] **Step 3: Run RED**

Run: `python -m unittest -v tests.test_v2_python_certify_full`

Expected: import failure because the gate does not exist.

- [ ] **Step 4: Reuse V1 production as the wheel builder, not as V2 authority**

Invoke `RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py --profile stable --artifact-out-dir <subdir>` and require `PYTHON_CERTIFY_FULL=PASS` plus `LANGUAGE_STABLE=NO`. Parse its canonical receipt, then independently inspect/install the exported wheel for V2-specific evidence.

- [ ] **Step 5: Validate V2 wheel evidence**

Check package name/version, wheel SHA, `entry_points.txt`, isolated module origin, descriptor self-hash, V2 language version, requested V2 release profile, and both V2 console scripts. Record the upstream V1 Python receipt SHA in the V2 receipt.

- [ ] **Step 6: Emit a self-hashed external receipt**

Receipt fields include exact Git identity/base, profile, package name/version, wheel filename/hash, V1 Python receipt hash, V2 descriptor hash, entry-point PASS, installed-origin PASS, `python_v2_certify_full=true`, `language_stable=false`, and canonical `receipt_hash`.

- [ ] **Step 7: Run GREEN**

Run: `python -m unittest -v tests.test_v2_python_certify_full tests.test_v2_schemas`

Expected: PASS, zero skips.

- [ ] **Step 8: Commit**

```powershell
git add RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py schemas/tev-script-v2-python-certify-full-receipt.schema.json tests/test_v2_python_certify_full.py tests/test_v2_schemas.py
git commit -m "feat: certify V2 Python artifact surface"
```

### Task 6: Add stable governance and the sole stable-admission authority

**Files:**
- Create: `tools/validate_v2_stable_governance.py`
- Create: `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py`
- Create: `schemas/tev-script-v2-stable-admission-receipt.schema.json`
- Create: `tests/test_v2_stable_governance.py`
- Create: `tests/test_v2_stable_admission.py`
- Modify: `tests/test_v2_schemas.py`

**Interfaces:**
- Stable governance validates a stable-shaped repository but never emits `LANGUAGE_STABLE=YES`.
- Stable admission is the only V2 Python source file allowed to contain `print("LANGUAGE_STABLE=YES")`.
- Exact Phase-S release path set:

```python
REQUIRED_RELEASE_PATHS = {
    "CANONICAL_INDEX.json",
    "CHANGELOG.md",
    "PROJECT_STATE.md",
    "README.md",
    "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
    "tev_script/release_metadata_v2.py",
}
ALLOWED_RELEASE_PATHS = frozenset(REQUIRED_RELEASE_PATHS)
```

- [ ] **Step 1: Write authority-source tests**

AST/read-source test must prove only `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` emits `LANGUAGE_STABLE=YES`; V2 technical cert, V2 Python cert, stable governance, and authority validator must not.

- [ ] **Step 2: Write exact release-diff tests**

Unit-test `validate_release_diff(parent, head)` with mocked Git output. Missing one required path, adding `tev_script/scoped_filesystem_v2.py`, changing a schema/gate/test, or changing `pyproject.toml` must fail.

- [ ] **Step 3: Write parent-certificate binding tests**

`load_parent_certificate` requires V2 receipt V2 schema, `admission_profile=candidate`, exact commit/tree, `certify_full=true`, `language_stable=false`, and canonical receipt hash equal to release metadata `TECHNICAL_PARENT_CERTIFICATE_SHA256`.

- [ ] **Step 4: Write stable-governance synthetic tests**

Stable state must require `STABLE_2_0_0`, `stable=true`, descriptor/index/matrix agreement, valid technical parent/hash, V2 stable gate bindings, Python distribution `1.0.0`, empty dependencies, V2 entry points, and stable-admission tokens in README/CHANGELOG/PROJECT_STATE. Candidate state must be rejected by this validator.

- [ ] **Step 5: Run RED**

Run:

```powershell
python -m unittest -v tests.test_v2_stable_governance tests.test_v2_stable_admission
```

Expected: import failures for the new validator/gate.

- [ ] **Step 6: Implement stable governance**

Follow the V1 pattern but assert only V2-language stability. Explicitly require Python package version `1.0.0`; do not claim JavaScript/C#/Unity V2 stability. Validate descriptor self-hash and all stable-release-surface bindings.

- [ ] **Step 7: Implement stable admission orchestration**

Order is fixed:

```text
clean identity
-> release_metadata_v2 stable validation
-> exact external parent certificate
-> exact six-path diff
-> validate_v2_stable_governance.py
-> RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --profile stable --expected-base <P>
-> require CERTIFY_V2=PASS + LANGUAGE_STABLE=NO
-> RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile stable
-> require CERTIFY_FULL=PASS + LANGUAGE_STABLE=NO
-> RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py --profile stable --expected-base <P>
-> require PYTHON_V2_CERTIFY_FULL=PASS + LANGUAGE_STABLE=NO
-> exact wheel byte identity
-> descriptor/index/matrix consistency
-> clean HEAD/tree unchanged
-> self-hashed stable receipt
-> STABLE_ADMISSION=PASS
-> LANGUAGE_STABLE=YES
```

Every failure prints `STABLE_ADMISSION=FAIL`, `CERTIFY_FULL=NO`, `LANGUAGE_STABLE=NO` and exits non-zero.

- [ ] **Step 8: Run GREEN**

Run: `python -m unittest -v tests.test_v2_stable_governance tests.test_v2_stable_admission tests.test_v2_schemas`

Expected: PASS, zero skips. Do not run the real stable gate on Phase-T candidate metadata.

- [ ] **Step 9: Commit**

```powershell
git add tools/validate_v2_stable_governance.py RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py schemas/tev-script-v2-stable-admission-receipt.schema.json tests/test_v2_stable_governance.py tests/test_v2_stable_admission.py tests/test_v2_schemas.py
git commit -m "feat: add V2 stable-admission authority"
```

### Task 7: Wire the new tooling into candidate authority and close governed inventory

**Files:**
- Modify: `CANONICAL_INDEX.json`
- Modify: `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- Modify: `tools/validate_v2_authority.py`
- Modify: `tests/test_v2_authority.py`
- Modify: `tests/test_v2_schemas.py`
- Modify: `PROJECT_STATE.md`
- Modify: `README.md`

**Interfaces:**
- Phase T remains candidate/non-stable.
- Candidate authority now advertises certified stable-admission tooling without claiming that Stable Admission has occurred.

- [ ] **Step 1: Write failing inventory tests**

Require the V2 target/matrix to list `release_metadata_v2`, current-base receipt schema, V2 Python cert gate/schema, stable governance, stable-admission gate/schema, and all four new test modules. `stable=false`, candidate status, publication=false, merge=false must remain exact.

- [ ] **Step 2: Require stable-release surface but false claim**

Canonical target must include:

```json
"stable_release_surface": {
  "release_metadata": "tev_script/release_metadata_v2.py",
  "governance": "tools/validate_v2_stable_governance.py",
  "admission_gate": "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py",
  "receipt_schema": "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1",
  "exact_parent_certificate_required": true,
  "release_diff_whitelist_required": true,
  "artifact_byte_identity_required": true,
  "stable_claim": false
}
```

- [ ] **Step 3: Run RED**

Run: `python -m unittest -v tests.test_v2_authority tests.test_v2_descriptor tests.test_v2_schemas`

Expected: inventory/surface failures.

- [ ] **Step 4: Update candidate canonical index and feature matrix**

Add tooling paths to governed groups. Add Phase-T promotion witnesses:

```text
CURRENT_BASE_CERTIFICATION_SUPPORTED
V2_PYTHON_ARTIFACT_CERTIFICATION_SUPPORTED
STABLE_ADMISSION_TOOLING_PRESENT
STABLE_ADMISSION_TOOLING_TECHNICALLY_CERTIFIED_REQUIRED
```

Do not add `STABLE_ADMISSION_PASS` or set `stable=true`.

- [ ] **Step 5: Update project state/docs only for Phase-T truth**

README/PROJECT_STATE must state: stable-admission tooling is being technically certified; V2 remains canonical but non-stable; Python package remains 1.0.0; Phase S does not exist yet; no tag/release/merge authority is implied.

- [ ] **Step 6: Run governed zero-skip suite**

Run:

```powershell
python -m unittest -v tests.test_v2_release_metadata tests.test_v2_descriptor tests.test_v2_schemas tests.test_v2_authority tests.test_v2_certify_full tests.test_v2_python_certify_full tests.test_v2_stable_governance tests.test_v2_stable_admission
```

Expected: PASS, zero skips.

- [ ] **Step 7: Commit**

```powershell
git add CANONICAL_INDEX.json spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json tools/validate_v2_authority.py tests/test_v2_authority.py tests/test_v2_schemas.py PROJECT_STATE.md README.md
git commit -m "docs: bind V2 stable tooling authority"
```

### Task 8: Full Phase-T regression, independent review, certification, and freeze

**Files:**
- Modify source only if fresh verification exposes a real defect; return to the owning task's RED/GREEN cycle.
- Produce receipts/wheel only in an external temporary directory.

**Interfaces:**
- Consumes every committed Phase-T task.
- Produces exact clean Phase-T candidate HEAD/tree and three independent evidence chains: V1 stable non-regression, V2 current-base technical receipt V2, V2 Python artifact receipt.

- [ ] **Step 1: Verify plan/spec and source whitespace**

```powershell
rg -n "T[B]D|T[O]DO|implement[ ]later|fill[ ]in[ ]details" docs/superpowers/specs/2026-08-15-tev-script-v2-stable-admission-design.md docs/superpowers/plans/2026-08-15-tev-script-v2-stable-admission-phase-t.md
git diff fef64edf903610b87a1dc959ef7cbf7ab9f5400f HEAD --check
```

Expected: `rg` exit 1/no matches; `git diff --check` exit 0.

- [ ] **Step 2: Run full regression**

Run: `python -m unittest discover -s tests -p "test*.py" -v`

Expected: zero failures/errors. Any skip is investigated; no V2 governed/stable-tooling test may skip.

- [ ] **Step 3: Run fresh V1 stable non-regression**

```powershell
python RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile stable --receipt-out C:/Users/benav/AppData/Local/Temp/tev-script-v2-stable-t/v1.json
```

Expected: `CERTIFY_FULL=PASS`, `LANGUAGE_STABLE=NO`.

- [ ] **Step 4: Run fresh V2 current-base technical certification**

```powershell
python RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --profile candidate --expected-base fef64edf903610b87a1dc959ef7cbf7ab9f5400f --receipt-out C:/Users/benav/AppData/Local/Temp/tev-script-v2-stable-t/v2.json
```

Expected: filesystem/TOCTOU/1MiB/authority/regression/V1 witnesses PASS, `CERTIFY_V2=PASS`, `LANGUAGE_STABLE=NO`.

- [ ] **Step 5: Run fresh V2 Python artifact certification**

```powershell
python RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py --profile candidate --expected-base fef64edf903610b87a1dc959ef7cbf7ab9f5400f --artifact-out-dir C:/Users/benav/AppData/Local/Temp/tev-script-v2-stable-t/python --receipt-out C:/Users/benav/AppData/Local/Temp/tev-script-v2-stable-t/python.json
```

Expected: exact 1.0.0 wheel, V2 entry points/import origin/descriptor PASS, `PYTHON_V2_CERTIFY_FULL=PASS`, `LANGUAGE_STABLE=NO`.

- [ ] **Step 6: Verify the real stable gate is impossible on Phase T**

Run stable governance only:

```powershell
python tools/validate_v2_stable_governance.py
```

Expected: non-zero because Phase T release profile is candidate. This is a required negative witness, not a blocker.

- [ ] **Step 7: Independent whole-branch code review**

Review `fef64edf...HEAD` specifically for circular authority, mutable-base TOCTOU, receipt substitution, artifact-origin confusion, V1 regression damage, accidental package-version change, hidden stable self-promotion, and release-diff bypass. Any actionable finding returns to its owning task and invalidates prior receipts.

- [ ] **Step 8: Re-run Steps 2–6 after the final code-review fix, if any**

Expected: fresh evidence only; never reuse receipts from a superseded tree.

- [ ] **Step 9: Freeze exact Phase-T identity**

```powershell
git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}
git merge-base --is-ancestor fef64edf903610b87a1dc959ef7cbf7ab9f5400f HEAD
git diff --name-only fef64edf903610b87a1dc959ef7cbf7ab9f5400f HEAD | Measure-Object
git ls-remote origin refs/heads/main
```

Expected: clean status; stable HEAD/tree; ancestry exit 0; exact changed-path count recorded; remote `main` still `fef64edf...` unless a separately reported external change occurred.

- [ ] **Step 10: Stop before publication**

Report Phase-T commit/tree/path count plus V1 receipt hash, V2 receipt V2 hash/file hash, V2 Python receipt hash/file hash, wheel SHA-256, full-regression count, review result, and `LANGUAGE_STABLE=NO`. Do not create PR or merge without new explicit authorization.
