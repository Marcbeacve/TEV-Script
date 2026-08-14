# TEV Script V2 Final Review Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three actionable final-review defects, recertify one new exact V2 identity, and promote only that identity.

**Architecture:** Preserve the approved V2 design and add fail-closed admission at the two missing trust boundaries: Windows `UNICODE_STRING` construction and external `file.read` evidence validation. Close the certification inventory by deriving V2 test ownership from imports of governed V2 implementation modules, while retaining the explicit test list as execution authority.

**Tech Stack:** Python 3.14, `unittest`, Windows NT handle-relative filesystem APIs, JSON authority matrix, Git/GitHub CLI.

## Global Constraints

- Do not merge or mark the PR Ready until every new negative, the full 1,155-test regression, `CERTIFY_V1`, and `CERTIFY_V2` pass on a clean committed identity.
- Keep filesystem operations handle-relative and fail closed; do not add path-based fallbacks.
- Admit at most 1 MiB of `file.read` UTF-8 content and one overflow witness byte.
- Keep V1 certification as regression evidence; it cannot substitute for `CERTIFY_V2`.
- Publish only a final exact commit/tree/changed-path identity; never publish an intermediate repair commit.

---

### Task 1: Reject unrepresentable Windows relative names

**Files:**
- Modify: `tev_script/scoped_filesystem_v2.py`
- Test: `tests/test_scoped_filesystem_v2.py`

**Interfaces:**
- Consumes: one validated relative path component as `str`.
- Produces: an exact UTF-16LE byte length that fits both `UNICODE_STRING.Length` and `MaximumLength`, or `TEVS_SCOPED_FS_PATH` before `_NtCreateFile` can run.

- [ ] **Step 1: Write the failing boundary test**

Add a test that accepts 32,766 ASCII code points, rejects 32,767 because the NUL-inclusive maximum would exceed `USHORT`, and on Windows patches `_NtCreateFile` to prove an oversized direct `_win_open_relative` call never reaches the kernel wrapper.

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest -v tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_windows_unicode_name_lengths_fail_closed_before_ntcreatefile`

Expected before the fix: failure because the length wraps or `_NtCreateFile` is invoked.

- [ ] **Step 3: Implement the minimal validation**

Add a platform-independent helper that computes `len(name.encode("utf-16-le"))`, rejects when `encoded_length + 2 > 0xffff`, call it from the shared relative-path parser and again immediately before constructing `_WinUnicodeString`.

- [ ] **Step 4: Run the focused filesystem tests**

Run: `python -m unittest -v tests.test_scoped_filesystem_v2`

Expected: PASS with zero skips on the certification host.

### Task 2: Enforce 1 MiB while validating external evidence

**Files:**
- Modify: `tev_script/file_observation_acquisition_v2.py`
- Test: `tests/test_file_observation_acquisition_v2.py`

**Interfaces:**
- Consumes: an untrusted `return`, `byte_count`, and content hash from acquisition evidence.
- Produces: validated UTF-8 bytes no larger than `MAX_FILE_READ_BYTES_V2`, or `TEVS_FILE_READ_EVIDENCE_CONTENT` before accepting the witness.

- [ ] **Step 1: Write the failing forged-evidence test**

Acquire a valid one-byte witness, replace its return with 1,048,577 ASCII bytes, recompute the inner and outer hashes independently, and assert semantic validation rejects it with `TEVS_FILE_READ_EVIDENCE_CONTENT`.

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest -v tests.test_file_observation_acquisition_v2.FileObservationAcquisitionV2Tests.test_external_oversize_evidence_is_rejected_even_with_consistent_hashes`

Expected before the fix: failure because validation accepts the forged oversized witness.

- [ ] **Step 3: Implement bounded UTF-8 admission**

Validate `byte_count` as a non-boolean integer in `[0, 1048576]`, reject an obviously oversized code-point count before encoding, and encode into a bounded buffer so no more than 1 MiB plus one witness byte is retained before rejection.

- [ ] **Step 4: Run the focused observation tests**

Run: `python -m unittest -v tests.test_file_observation_acquisition_v2`

Expected: PASS.

### Task 3: Close the governed V2 test inventory

**Files:**
- Modify: `tools/validate_v2_authority.py`
- Modify: `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- Test: `tests/test_v2_authority.py`
- Test: `tests/test_v2_certify_full.py`

**Interfaces:**
- Consumes: explicit governed implementation and test path lists plus the repository test tree.
- Produces: failure when a test imports a governed V2 implementation module but is absent from the governed test list.

- [ ] **Step 1: Write failing inventory tests**

Add a temporary-root behavioral test proving the authority validator rejects an unlisted test that imports `tev_script.ir_v4_effect_commands`; also require `v2_test_modules()` to include `tests.test_effect_command_artifacts_v4`.

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest -v tests.test_v2_authority tests.test_v2_certify_full`

Expected before the fix: failure for the missing closure validator/module.

- [ ] **Step 3: Implement inventory closure**

Parse test imports with `ast`, compare them with modules derived from governed implementation paths, reject unlisted owners, and add `tests/test_effect_command_artifacts_v4.py` to the explicit test inventory.

- [ ] **Step 4: Run authority and certifier tests**

Run: `python -m unittest -v tests.test_v2_authority tests.test_v2_certify_full tests.test_effect_command_artifacts_v4`

Expected: PASS.

### Task 4: Recreate exact certification and promotion evidence

**Files:**
- Produce externally: new V1/V2 receipts and Python artifacts outside the repository.
- Modify remotely only after all local gates pass: branch and PR #12.

**Interfaces:**
- Consumes: the final clean committed repair identity.
- Produces: new commit/tree/path count, V1/V2 receipt hashes, independent review verdict, exact remote branch, Ready PR, merge commit, and post-merge main tree verification.

- [ ] **Step 1: Run focused security and authority gates**

Run the three changed test modules, `tools/validate_v2_filesystem_safety.py`, and `tools/validate_v2_authority.py`; require zero skips and every mandatory PASS witness.

- [ ] **Step 2: Run the full regression**

Run: `python -m unittest discover -s tests -p "test*.py"`

Expected: all tests PASS, zero skips.

- [ ] **Step 3: Commit and certify the exact identity**

Commit all reviewed repairs, then run V1 global certification, V1 Python certification, and `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py` with external outputs. Require `CERTIFY_V1=PASS`, `PYTHON_CERTIFY_FULL=PASS`, `CERTIFY_V2=PASS`, and a clean worktree.

- [ ] **Step 4: Review and publish exactly once**

Obtain a fresh independent review of the new base-to-head range. Push the exact branch, verify remote base/head/tree/path count, update the PR evidence, mark Ready, and merge with `--merge --match-head-commit <new-head>`.

- [ ] **Step 5: Verify post-merge state**

Require PR merged, remote `main` at the returned merge commit, merge tree equal to the certified candidate tree, both merge parents exact, and the final full regression PASS on that tree.
