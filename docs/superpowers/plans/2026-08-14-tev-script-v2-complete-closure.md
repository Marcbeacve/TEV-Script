# TEV Script V2 Complete Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a new exact TEV Script V2 candidate with handle-anchored filesystem safety, bounded file admission, complete normative authority, a public CLI, and an independent V2 certificate.

**Architecture:** A new `scoped_filesystem_v2` module owns platform directory handles and is the only physical file-access layer used by V2 providers. Versioned Markdown specifications, JSON Schemas, a descriptor module, and a strict `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py` gate establish V2 authority independently of V1 while preserving all V1 behavior.

**Tech Stack:** Python 3.11+ standard library, `ctypes` Win32 bindings, POSIX `dir_fd` operations, `unittest`, JSON Schema Draft 2020-12, Git-bound canonical SHA-256 receipts.

## Global Constraints

- Do not publish, create a pull request, merge, tag, release, or otherwise promote the branch.
- Preserve base ancestry at `284ec3ec8c41681825ec1a8421f7ee2a1b012d68`; a new candidate tree is expected.
- Keep Python package runtime dependencies empty and `requires-python = ">=3.11"`.
- Every physical effect crosses an explicit capability and fails closed on unsupported security primitives.
- Source grammar, static semantics, IR, value model, ABI, canonical hashing, and receipts are authority; runtimes are implementations.
- V2 certification must be independent of V1 certification and must bind exact clean HEAD/tree identities.
- Filesystem safety, TOCTOU closure, 1 MiB pre-admission, CLI V2, schemas/contracts, V1 certification, V2 certification, and full regression must all pass before freezing.

---

### Task 1: Commit the approved design and executable plan

**Files:**
- Create: `docs/superpowers/specs/2026-08-14-tev-script-v2-complete-closure-design.md`
- Create: `docs/superpowers/plans/2026-08-14-tev-script-v2-complete-closure.md`

**Interfaces:**
- Consumes: repository-owner authorization dated 2026-08-14.
- Produces: the threat model, authority model, required gates, and task sequence used by every later task.

- [ ] **Step 1: Verify the two documents exist and contain no placeholders**

Run:

```powershell
rg -n "T[B]D|T[O]DO|implement[ ]later|fill[ ]in[ ]details" docs/superpowers/specs/2026-08-14-tev-script-v2-complete-closure-design.md docs/superpowers/plans/2026-08-14-tev-script-v2-complete-closure.md
```

Expected: exit 1 with no matches.

- [ ] **Step 2: Verify documentation whitespace**

Run: `git diff --check`

Expected: exit 0.

- [ ] **Step 3: Commit**

```powershell
git add docs/superpowers/specs/2026-08-14-tev-script-v2-complete-closure-design.md docs/superpowers/plans/2026-08-14-tev-script-v2-complete-closure.md
git commit -m "docs: design complete V2 closure"
```

### Task 2: Add the handle-anchored filesystem primitive

**Files:**
- Create: `tev_script/scoped_filesystem_v2.py`
- Create: `tests/test_scoped_filesystem_v2.py`

**Interfaces:**
- Consumes: `TevScriptError` from `tev_script.diagnostics`.
- Produces: `ScopedFilesystemRootV2`, `ScopedFileReadV2`, `ScopedFileReplaceV2`, `open_scoped_root_v2`, `read_scoped_file_v2`, and `replace_scoped_file_v2`.

- [ ] **Step 1: Write failing root-identity and traversal tests**

Add tests that assert this contract:

```python
with open_scoped_root_v2(root) as scope:
    self.assertEqual(scope.canonical_root, canonical_host_path_v2(root))
    self.assertRegex(scope.scope_hash, r"^[0-9a-f]{64}$")
    with self.assertRaisesRegex(TevScriptError, "TEVS_SCOPED_FS_PATH"):
        read_scoped_file_v2(scope, "../outside.txt", maximum_bytes=1024)
```

Also replace the root directory after opening it and assert that the old scope never
reads from the replacement directory. Assert final symlinks/reparse points and parent
symlinks/junctions fail with `TEVS_SCOPED_FS_ESCAPE`.

- [ ] **Step 2: Run the focused tests and observe RED**

Run: `python -m unittest -v tests.test_scoped_filesystem_v2`

Expected: import failure because `tev_script.scoped_filesystem_v2` does not exist.

- [ ] **Step 3: Implement the immutable shared data model and strict path parser**

Implement these exact public shapes:

```python
@dataclass(frozen=True, slots=True)
class ScopedFileReadV2:
    canonical_relative_path: str
    data: bytes
    content_sha256: str

@dataclass(frozen=True, slots=True)
class ScopedFileReplaceV2:
    canonical_relative_path: str
    content_sha256: str
    byte_count: int
    replaced: bool

class ScopedFilesystemRootV2(AbstractContextManager["ScopedFilesystemRootV2"]):
    canonical_root: str
    platform: str
    volume_identity: str
    file_identity: str
    scope_hash: str
```

Reject absolute paths, drives, NUL, empty/`.`/`..` segments, Windows trailing dot or
space aliases, alternate data streams, and reserved device names before OS access.

- [ ] **Step 4: Implement POSIX descriptor-relative operations**

Open the root with `O_DIRECTORY | O_NOFOLLOW`, traverse intermediate directories with
`os.open(..., dir_fd=parent_fd)`, and retain only duplicated/pinned descriptors. Open
reads with `O_NOFOLLOW`; require `fstat` regular-file kind. Create replacement temps
with `O_CREAT | O_EXCL | O_NOFOLLOW`, fsync content, rename with `src_dir_fd` and
`dst_dir_fd`, and fsync the parent directory.

- [ ] **Step 5: Implement Windows handle-relative safety**

Bind `CreateFileW`, `GetFileInformationByHandleEx`, `GetFinalPathNameByHandleW`,
`ReadFile`, `WriteFile`, `FlushFileBuffers`, and `SetFileInformationByHandle` with
explicit `argtypes`/`restype`. Open reparse points rather than following final links,
validate directory/file kind and stable identities after opening, require descendant
containment under the pinned root, and rename the temporary handle relative to the
pinned parent. On missing API, failed identity query, or failed containment, raise a
stable `TEVS_SCOPED_FS_*` diagnostic; never call a path fallback.

- [ ] **Step 6: Add deterministic interposition race tests**

Patch the module's lowest-level open wrapper so a test swaps an intermediate parent
to an outside symlink/junction immediately before the real open. Assert each outcome
is either access to the originally pinned in-root object or `TEVS_SCOPED_FS_ESCAPE`,
never outside bytes or an outside replacement. Repeat for a root-path replacement.

- [ ] **Step 7: Run focused tests GREEN**

Run: `python -m unittest -v tests.test_scoped_filesystem_v2`

Expected: all tests pass with zero skips.

- [ ] **Step 8: Commit**

```powershell
git add tev_script/scoped_filesystem_v2.py tests/test_scoped_filesystem_v2.py
git commit -m "feat: anchor V2 filesystem authority to handles"
```

### Task 3: Refactor file.read and file.replace onto the secure primitive

**Files:**
- Modify: `tev_script/file_effect_provider_v2.py`
- Modify: `tev_script/file_observation_acquisition_v2.py`
- Modify: `tests/test_file_effect_provider_v2.py`
- Modify: `tests/test_file_observation_acquisition_v2.py`
- Modify: `tests/test_cli_file_observation_v2.py`
- Modify: `tests/test_cli_v2.py`

**Interfaces:**
- Consumes: the Task 2 scoped filesystem API.
- Produces: unchanged public provider/receipt wire shapes with stronger scope identity and secure physical operations.

- [ ] **Step 1: Write failing 1 MiB pre-admission test**

Patch the secure read backend with a stream that records requested byte counts. Assert
the acquisition performs bounded reads totaling at most
`MAX_FILE_READ_BYTES_V2 + 1`, raises `TEVS_FILE_READ_BUDGET`, never calls unbounded
`read()`/`Path.read_bytes()`, and never decodes or hashes rejected content.

- [ ] **Step 2: Write failing provider race tests**

Use the deterministic Task 2 interposition point during both observation acquisition
and effect commit. Assert outside sentinel files remain byte-identical and no receipt
reports success for outside content.

- [ ] **Step 3: Run focused tests and observe RED**

Run:

```powershell
python -m unittest -v tests.test_file_observation_acquisition_v2 tests.test_file_effect_provider_v2 tests.test_cli_file_observation_v2 tests.test_cli_v2
```

Expected: new pre-admission/race assertions fail against path-based operations.

- [ ] **Step 4: Replace path resolution with scoped handles**

Make `build_file_effect_scope_v2` derive its wire object from
`open_scoped_root_v2`. Make provider instances own and close their scoped root.
Acquire observations using `read_scoped_file_v2(...,
maximum_bytes=MAX_FILE_READ_BYTES_V2)`. Commit replacements using
`replace_scoped_file_v2`; use its exact opened-handle content identity in the receipt.

- [ ] **Step 5: Preserve deterministic provider contracts**

Update implementation hashes and descriptor validation without changing capability
IDs, command IDs, canonical JSON rules, or one-intent atomic-batch policy. Add explicit
context-manager/`close()` behavior and reject use after close.

- [ ] **Step 6: Run focused tests GREEN**

Run the Step 3 command.

Expected: all focused tests pass with zero skips.

- [ ] **Step 7: Commit**

```powershell
git add tev_script/file_effect_provider_v2.py tev_script/file_observation_acquisition_v2.py tests/test_file_effect_provider_v2.py tests/test_file_observation_acquisition_v2.py tests/test_cli_file_observation_v2.py tests/test_cli_v2.py
git commit -m "fix: close V2 filesystem races and read admission"
```

### Task 4: Make browser teardown fail closed

**Files:**
- Modify: `tools/validate_ir_v3_browser_wasm.py`
- Create: `tests/test_browser_profile_cleanup.py`

**Interfaces:**
- Consumes: `_stop_process` and the three existing browser gate call sites.
- Produces: `_stop_browser_process(process, profile) -> None` that either proves cleanup or raises `RuntimeError`.

- [ ] **Step 1: Write failure and timeout tests**

Mock `subprocess.run` to return code 1 and assert `_stop_browser_process` raises with
captured stdout/stderr. Mock `subprocess.run` to raise `TimeoutExpired` and assert the
helper raises a timeout diagnostic. Assert the call sets a Python timeout of 35
seconds and carries the exact resolved profile only through the environment.

- [ ] **Step 2: Run the new test and observe RED**

Run: `python -m unittest -v tests.test_browser_profile_cleanup`

Expected: the current helper silently returns on nonzero status and lacks a timeout.

- [ ] **Step 3: Implement fail-closed cleanup**

Capture the completed process, pass `timeout=35`, require `returncode == 0`, and raise
`RuntimeError` containing bounded stdout/stderr when cleanup fails. Convert
`TimeoutExpired` into a stable cleanup error. Keep exact-profile process matching.

- [ ] **Step 4: Run unit and real browser gates**

Run:

```powershell
python -m unittest -v tests.test_browser_profile_cleanup
python tools/validate_ir_v3_browser_wasm.py
python tools/validate_ir_v3_browser_signed_update.py
python tools/validate_v0_2_portable_hosts.py
```

Expected: unit tests pass; each available real gate exits 0 with its PASS witness.

- [ ] **Step 5: Commit**

```powershell
git add tools/validate_ir_v3_browser_wasm.py tests/test_browser_profile_cleanup.py
git commit -m "fix: fail closed on browser teardown"
```

### Task 5: Establish normative V2 specifications, schemas, and descriptor

**Files:**
- Create: `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- Create: `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`
- Create: `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`
- Create: `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- Create: `schemas/tev-script-v2-descriptor.schema.json`
- Create: `schemas/tev-script-program-ir-v4.schema.json`
- Create: `schemas/tev-script-v2-filesystem-artifacts.schema.json`
- Create: `schemas/tev-script-v2-certify-full-receipt.schema.json`
- Create: `tev_script/descriptor_v2.py`
- Create: `tests/test_v2_authority.py`
- Create: `tests/test_v2_schemas.py`
- Create: `tests/test_v2_descriptor.py`
- Modify: `CANONICAL_INDEX.json`
- Modify: `README.md`
- Modify: `PROJECT_STATE.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: implemented V2 language/IR constants and the approved safety design.
- Produces: normative documents, Draft 2020-12 schemas, `describe_v2()`, `tev-script-v2-describe`, and `tev-script-v2` installed commands.

- [ ] **Step 1: Write authority inventory tests**

Assert every normative path exists exactly once in `CANONICAL_INDEX.json`, every
feature-matrix path exists, V2 paths do not replace V0.2/V1 entries, and package
entry points map exactly to `tev_script.cli_v2:main` and
`tev_script.descriptor_v2:main`.

- [ ] **Step 2: Write descriptor and schema negative tests**

Validate schemas with `Draft202012Validator.check_schema`. Validate governed valid
fixtures, then mutate one field at a time: unknown property, missing hash, uppercase
hash, wrong schema discriminator, unbounded collection, mismatched V2 version, and
unsupported IR profile must all fail.

- [ ] **Step 3: Run authority tests and observe RED**

Run:

```powershell
python -m unittest -v tests.test_v2_authority tests.test_v2_schemas tests.test_v2_descriptor
```

Expected: missing authority, schemas, descriptor, and entry points fail.

- [ ] **Step 4: Write the normative language specification**

Specify lexical rules, grammar productions, declarations, type formation, generic
instantiation, protocol/associated-type coherence, bounded recursion, finite
collections, task DAG ordering, observation/effect separation, module acquisition,
diagnostics, and explicit exclusions. Cross-reference constants and conformance
fixtures by exact path; do not define behavior by Python implementation prose.

- [ ] **Step 5: Write Program IR V4 and filesystem specifications**

Specify profile discriminators, exact field sets, type-table closure, value encoding,
static step bounds, recursive contracts, task ordering/cancellation, observation
transcripts, effect planning/authorization/commit, canonical JSON/hash rules, receipt
fields, root-handle authority, race semantics, bounded reads, and rename
linearization.

- [ ] **Step 6: Implement strict schemas and descriptor**

Use `additionalProperties: false`, anchored lowercase SHA-256 patterns, bounded array
sizes, and `oneOf` profile closure. `describe_v2()` returns canonical data containing
language `2.0.0`, Program IR V4 schema IDs, normative paths, schema paths, gate path,
public commands, safety policies, and its descriptor hash.

- [ ] **Step 7: Update public authority indexes and entry points**

Add `tev-script-v2 = "tev_script.cli_v2:main"` and
`tev-script-v2-describe = "tev_script.descriptor_v2:main"`. Update README and project
state to mark V2 as a candidate awaiting its own certificate, never as stable or
published.

- [ ] **Step 8: Run authority tests GREEN**

Run the Step 3 command.

Expected: all tests pass with zero skips.

- [ ] **Step 9: Commit**

```powershell
git add spec/TEV_SCRIPT_V2_LANGUAGE.md spec/TEV_SCRIPT_PROGRAM_IR_V4.md spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json schemas/tev-script-v2-descriptor.schema.json schemas/tev-script-program-ir-v4.schema.json schemas/tev-script-v2-filesystem-artifacts.schema.json schemas/tev-script-v2-certify-full-receipt.schema.json tev_script/descriptor_v2.py tests/test_v2_authority.py tests/test_v2_schemas.py tests/test_v2_descriptor.py CANONICAL_INDEX.json README.md PROJECT_STATE.md pyproject.toml
git commit -m "docs: establish normative TEV Script V2 authority"
```

### Task 6: Add independent V2 conformance fixtures and certification

**Files:**
- Create: `conformance/v2-source-static-cases.json`
- Create: `conformance/program-ir-v4-cases.json`
- Create: `conformance/v2-filesystem-safety-cases.json`
- Create: `tools/validate_v2_authority.py`
- Create: `tools/validate_v2_filesystem_safety.py`
- Create: `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py`
- Create: `tests/test_v2_certify_full.py`
- Modify: `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- Modify: `CANONICAL_INDEX.json`

**Interfaces:**
- Consumes: Task 2-5 APIs, schemas, specs, CLI, and exact Git identity.
- Produces: canonical `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1` and `CERTIFY_V2=PASS|NO` output.

- [ ] **Step 1: Write certification fail-closed tests**

Run the gate in temporary Git repositories or mock only the subprocess boundary.
Assert failure for dirty worktree, detached/unresolved identity, missing authority
path, schema mutation, skipped mandatory test, V2 test failure, filesystem-safety
failure, stale expected HEAD/tree, V1 non-regression failure, and malformed receipt.

- [ ] **Step 2: Run the gate tests and observe RED**

Run: `python -m unittest -v tests.test_v2_certify_full`

Expected: import/file failure because the V2 gate does not exist.

- [ ] **Step 3: Add governed conformance cases**

Encode valid and invalid source/static-semantic cases for each V2 feature group;
valid/invalid Program IR V4 profiles; and filesystem traversal, final-link, parent
swap, root replacement, oversized file, malformed UTF-8, and atomic replacement
cases. Each case carries an exact expected status and diagnostic/result hash.

- [ ] **Step 4: Implement focused validators**

`validate_v2_authority.py` checks the index, matrix, schema, descriptor, and CLI
closure. `validate_v2_filesystem_safety.py` runs deterministic handle/race cases with
zero skips and emits separate witnesses for `FILESYSTEM_SAFETY`, `TOCTOU_CLOSURE`,
and `ONE_MIB_PRE_ADMISSION`.

- [ ] **Step 5: Implement the Git-bound V2 gate**

Require a clean branch checkout; resolve HEAD and `HEAD^{tree}`; run the two focused
validators and the exact V2 `unittest` module allowlist from the feature matrix;
require zero failures/errors/skips; invoke fresh V1 global certification; construct
canonical receipt JSON; validate it against the V2 receipt schema; write only when
`--receipt-out` is supplied; and print the canonical receipt SHA-256.

- [ ] **Step 6: Run certification tests GREEN**

Run: `python -m unittest -v tests.test_v2_certify_full`

Expected: all negative and positive harness tests pass with zero skips.

- [ ] **Step 7: Run the V2 gate once before commit**

Run:

```powershell
python RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --receipt-out evidence/TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT.json
```

Expected: the gate may report dirty-worktree rejection before commit; that proves the
identity guard. No PASS claim is recorded until Task 7 runs on a clean commit.

- [ ] **Step 8: Commit**

```powershell
git add conformance/v2-source-static-cases.json conformance/program-ir-v4-cases.json conformance/v2-filesystem-safety-cases.json tools/validate_v2_authority.py tools/validate_v2_filesystem_safety.py RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py tests/test_v2_certify_full.py spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json CANONICAL_INDEX.json
git commit -m "feat: add independent V2 certification authority"
```

### Task 7: Full regression, certificates, and exact freeze

**Files:**
- Modify only if a verification exposes a real defect; return to the owning task's RED/GREEN cycle before changing it.
- Produce externally: V1/V2 receipt JSON and Python wheel under the existing external certification directory.

**Interfaces:**
- Consumes: all committed V2 closure work.
- Produces: clean exact HEAD/tree identity and evidence hashes; no publication side effect.

- [ ] **Step 1: Run focused zero-skip closure tests**

Run:

```powershell
python -m unittest -v tests.test_scoped_filesystem_v2 tests.test_file_observation_acquisition_v2 tests.test_file_effect_provider_v2 tests.test_browser_profile_cleanup tests.test_v2_authority tests.test_v2_schemas tests.test_v2_descriptor tests.test_v2_certify_full
```

Expected: zero failures, errors, or skips.

- [ ] **Step 2: Run the entire regression suite**

Run: `python -m unittest discover -s tests -p "test*.py" -v`

Expected: zero failures/errors; any platform skip outside mandatory V2 closure is
reported separately and cannot substitute for a V2 gate.

- [ ] **Step 3: Run fresh V1 global certification**

Run:

```powershell
python RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py --profile stable --receipt-out C:/Users/benav/AppData/Local/Temp/tev-script-v2-cert-01a00195-20260814/tev-script-v1-final.json
```

Expected: exit 0, `CERTIFY_FULL=PASS`, `LANGUAGE_STABLE=NO`.

- [ ] **Step 4: Run fresh V1 Python product certification**

Run:

```powershell
python RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py --profile stable --artifact-out-dir C:/Users/benav/AppData/Local/Temp/tev-script-v2-cert-01a00195-20260814/python-final
```

Expected: exit 0 and `PYTHON_CERTIFY_FULL=PASS`.

- [ ] **Step 5: Run fresh V2 certification**

Run:

```powershell
python RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --receipt-out C:/Users/benav/AppData/Local/Temp/tev-script-v2-cert-01a00195-20260814/tev-script-v2-final.json
```

Expected: exit 0 with `FILESYSTEM_SAFETY=PASS`, `TOCTOU_CLOSURE=PASS`,
`ONE_MIB_PRE_ADMISSION=PASS`, `V2_NORMATIVE_SPEC=PASS`,
`V2_SCHEMAS_CONTRACTS=PASS`, `CLI_V2=PASS`, and `CERTIFY_V2=PASS`.

- [ ] **Step 6: Check repository integrity**

Run:

```powershell
git diff 284ec3ec8c41681825ec1a8421f7ee2a1b012d68 HEAD --check
git fsck --connectivity-only --no-dangling
git status --short
```

Expected: first two commands exit 0; status output is empty.

- [ ] **Step 7: Freeze and report exact identities**

Run:

```powershell
git rev-parse HEAD
git rev-parse HEAD^{tree}
git merge-base --is-ancestor 284ec3ec8c41681825ec1a8421f7ee2a1b012d68 HEAD
git diff --name-only 284ec3ec8c41681825ec1a8421f7ee2a1b012d68 HEAD | Measure-Object
git ls-remote origin refs/heads/main
```

Expected: a stable HEAD/tree pair, base ancestry exit 0, an exact changed-path count,
and remote `main` still at the expected base unless separately reported. Hash the
fresh V1/V2 receipts and wheel and include those hashes in the handoff. Do not push.
